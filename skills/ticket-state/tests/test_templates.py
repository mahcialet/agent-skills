from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ticket_state.errors import UnsafeContentError
from ticket_state.model import sha256_json
from ticket_state.storage import ProposalStore
from ticket_state.templates import (
    approve_template,
    extract_template_candidate,
    render_snapshot,
    sections,
    validate_edit_scope,
    validate_template,
)

from helpers import snapshot


class TemplateAndMarkupTests(unittest.TestCase):
    def test_formatted_protected_headings_are_detected_without_changing_scope(self) -> None:
        cases = (
            ("markdown", "# **Goal**", "**Goal**", "goal"),
            ("markdown", "# Goal {#goal}", "Goal {#goal}", "goal"),
            ("markdown", "# ***Constraints*** {#limits}", "***Constraints*** {#limits}", "constraints"),
            ("markdown", "__目的__\n====", "__目的__", "目的"),
            ("markdown", "# `制約`", "`制約`", "制約"),
            ("textile", "h1. *Constraints*", "*Constraints*", "constraints"),
            ("backlog", "* ''制約''", "''制約''", "制約"),
        )
        for markup, heading, title, protected in cases:
            with self.subTest(markup=markup, heading=heading):
                base = heading + "\nold\n"
                proposed = heading + "\nnew\n"
                self.assertEqual(title, sections(base, markup)[1].title)
                self.assertEqual(
                    {protected},
                    validate_edit_scope(base, proposed, markup=markup, edited_sections=[title]),
                )
                with self.assertRaises(UnsafeContentError):
                    validate_edit_scope(base, proposed, markup=markup, edited_sections=[protected])

    def test_protected_matching_does_not_match_partial_titles_or_code_contents(self) -> None:
        for title in ("**Goal status**", "Goals", "Constraints discussion", "Goal {invalid}"):
            with self.subTest(title=title):
                base = f"# {title}\nold\n"
                self.assertEqual(
                    set(),
                    validate_edit_scope(base, base.replace("old", "new"), markup="markdown", edited_sections=[title]),
                )
        base = "# Notes\n```md\n# **Goal**\nold\n```\n"
        self.assertEqual(
            set(),
            validate_edit_scope(base, base.replace("old", "new"), markup="markdown", edited_sections=["Notes"]),
        )

    def test_protected_heading_format_change_and_removal_are_detected(self) -> None:
        self.assertEqual(
            {"goal"},
            validate_edit_scope(
                "# **Goal**\nold\n", "# Goal {#goal}\nold\n",
                markup="markdown", edited_sections=["**Goal**", "Goal {#goal}", "__structure__"],
            ),
        )
        self.assertEqual(
            {"goal"},
            validate_edit_scope(
                "# **Goal**\nold\n", "",
                markup="markdown", edited_sections=["**Goal**", "__structure__"],
            ),
        )
        self.assertEqual(
            {"constraints"},
            validate_edit_scope(
                "", "# **Constraints**\nnew\n",
                markup="markdown", edited_sections=["**Constraints**", "__structure__"],
            ),
        )
        base = "# **Goal**\nkeep\n# Notes\nold\n"
        self.assertEqual(
            set(),
            validate_edit_scope(
                base, base.replace("old", "new"),
                markup="markdown", edited_sections=["Notes"],
            ),
        )

    def test_deferred_protected_review_returns_changes_but_retains_scope_checks(
        self,
    ) -> None:
        base = "# Goal\nold\n\n# Notes\nkeep\n"
        proposed = base.replace("old", "new")
        self.assertEqual(
            {"goal"},
            validate_edit_scope(
                base,
                proposed,
                markup="markdown",
                edited_sections=["Goal"],
            ),
        )
        with self.assertRaises(UnsafeContentError):
            validate_edit_scope(
                base,
                proposed.replace("keep", "unexpected change"),
                markup="markdown",
                edited_sections=["Goal"],
            )
        with self.assertRaises(UnsafeContentError):
            validate_edit_scope(
                base,
                proposed + "\n# Goal\nduplicate\n",
                markup="markdown",
                edited_sections=["Goal", "__structure__"],
            )

    def test_packaged_default_templates_share_snapshot_structure(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        expected = [
            "目的",
            "現在地",
            "決定事項",
            "制約",
            "進捗",
            "Blockers",
            "未解決事項",
            "次の行動",
            "検証状態",
        ]
        for markup in ("markdown", "textile", "backlog"):
            with self.subTest(markup=markup):
                path = skill_root / "assets" / f"default-ticket.{markup}.txt"
                text = path.read_text(encoding="utf-8")
                headings = [
                    item.title
                    for item in sections(text, markup)
                    if item.title != "__preamble__"
                ]
                self.assertEqual(expected, headings)
                self.assertEqual(len(expected), text.count("未設定"))
                self.assertTrue(text.endswith("\n"))

    def test_default_template_initialization_detects_protected_changes(self) -> None:
        skill_root = Path(__file__).resolve().parents[1]
        edited_sections = [
            "目的",
            "現在地",
            "決定事項",
            "制約",
            "進捗",
            "Blockers",
            "未解決事項",
            "次の行動",
            "検証状態",
            "__structure__",
        ]
        for markup in ("markdown", "textile", "backlog"):
            with self.subTest(markup=markup):
                proposed = (
                    skill_root / "assets" / f"default-ticket.{markup}.txt"
                ).read_text(encoding="utf-8")
                protected = validate_edit_scope(
                    "",
                    proposed,
                    markup=markup,
                    edited_sections=edited_sections,
                )
                self.assertTrue(protected)

    def test_edit_scope_preserves_unrelated_sections_and_code_blocks(self) -> None:
        base = "# Current State\nold\n\n# Notes\n```md\n# not a heading\n```\nkeep\n"
        proposed = base.replace("old", "new", 1)
        validate_edit_scope(
            base,
            proposed,
            markup="markdown",
            edited_sections=["Current State"],
        )
        with self.assertRaises(UnsafeContentError):
            validate_edit_scope(
                base,
                proposed.replace("keep", "changed"),
                markup="markdown",
                edited_sections=["Current State"],
            )

    def test_duplicate_headings_rejected_and_protected_change_detected(self) -> None:
        with self.assertRaises(UnsafeContentError):
            validate_edit_scope(
                "# Goal\na\n# Goal\nb\n",
                "# Goal\nc\n# Goal\nb\n",
                markup="markdown",
                edited_sections=["Goal"],
            )
        self.assertEqual(
            {"goal"},
            validate_edit_scope(
                "# Goal\na\n",
                "# Goal\nb\n",
                markup="markdown",
                edited_sections=["Goal"],
            ),
        )

    def test_provider_code_blocks_do_not_create_editable_sections(self) -> None:
        samples = (
            (
                "markdown",
                "# Current State\nold\n# Notes\n````md\n```\n# Current State\ninside\n````\nkeep\n",
            ),
            (
                "textile",
                "h1. Current State\nold\nh1. Notes\n<pre>\nh1. Current State\ninside\n</pre>\nkeep\n",
            ),
            (
                "backlog",
                "* Current State\nold\n* Notes\n{code}\n* Current State\ninside\n{code}\nkeep\n",
            ),
        )
        for markup, base in samples:
            with self.subTest(markup=markup):
                proposed = base.replace("old", "new", 1)
                validate_edit_scope(
                    base,
                    proposed,
                    markup=markup,
                    edited_sections=["Current State"],
                )
                with self.assertRaises(UnsafeContentError):
                    validate_edit_scope(
                        base,
                        proposed.replace("inside", "changed"),
                        markup=markup,
                        edited_sections=["Current State"],
                    )

    def test_markdown_closing_atx_goal_is_still_protected(self) -> None:
        self.assertEqual(
            {"goal"},
            validate_edit_scope(
                "# Goal #\na\n",
                "# Goal #\nb\n",
                markup="markdown",
                edited_sections=["Goal"],
            ),
        )

    def test_markdown_setext_goal_is_still_protected(self) -> None:
        with self.assertRaises(UnsafeContentError):
            validate_edit_scope(
                "Goal\n====\na\n\nProgress\n--------\nold\n",
                "Goal\n====\nb\n\nProgress\n--------\nnew\n",
                markup="markdown",
                edited_sections=["Progress"],
            )

    def test_markdown_raw_html_code_block_is_refused(self) -> None:
        with self.assertRaises(UnsafeContentError):
            validate_edit_scope(
                "# Current State\nold\n<pre>\n# Goal\ninside\n</pre>\n",
                "# Current State\nnew\n<pre>\n# Goal\ninside\n</pre>\n",
                markup="markdown",
                edited_sections=["Current State"],
            )

    def test_snapshot_is_complete_and_mentions_are_neutralized(self) -> None:
        value = snapshot()
        value["next_actions"] = "@teamに確認"
        rendered = render_snapshot(
            value,
            ["現在地を更新"],
            markup="textile",
            prepared_at="2026-09-06T00:00:00Z",
            operation_id="a" * 32,
        )
        self.assertIn("Current State Snapshot", rendered)
        self.assertIn("@\u200bteam", rendered)
        self.assertIn("ticket-state/" + "a" * 32, rendered)
        broken = dict(value)
        broken.pop("goal")
        with self.assertRaises(UnsafeContentError):
            render_snapshot(broken, ["x"], markup="textile", prepared_at="now", operation_id="a" * 32)
        injected = dict(value)
        injected["progress"] = "ok\nh1. forged"
        with self.assertRaises(UnsafeContentError):
            render_snapshot(injected, ["x"], markup="textile", prepared_at="now", operation_id="a" * 32)

    def test_template_extraction_stops_at_candidate_until_separate_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ProposalStore(Path(directory) / "state", workspace_id="demo")
            samples = [
                ({"provider": "backlog", "base_url": "https://example.invalid", "project_id": 1, "ticket_id": f"P-{number}"}, "now", "# Goal\nx\n# Notes\ny\n")
                for number in (1, 2)
            ]
            candidate = extract_template_candidate(samples, markup="markdown", store=store)
            self.assertFalse(candidate["approved"])
            self.assertEqual("candidate", candidate["kind"])
            path = Path(candidate["path"])
            validate_template(json.loads(path.read_text(encoding="utf-8")))
            approved = approve_template(path, store=store, approved_by="reviewer", reason="構造を確認")
            self.assertTrue(approved["approved"])
            self.assertNotEqual(path, Path(approved["path"]))

    def test_conflicting_template_samples_require_review(self) -> None:
        structures = (
            ("disjoint", ("# Alpha\na\n", "# Beta\nb\n")),
            ("reversed", ("# Alpha\na\n# Beta\nb\n", "# Beta\nb\n# Alpha\na\n")),
            ("partial", ("# Alpha\na\n# Beta\nb\n", "# Alpha\na\n")),
        )
        for label, descriptions in structures:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                store = ProposalStore(Path(directory) / "state", workspace_id="demo")
                candidate = extract_template_candidate(
                    [
                        (
                            {
                                "provider": "backlog",
                                "base_url": "https://example.invalid",
                                "project_id": 1,
                                "ticket_id": f"P-{number}",
                            },
                            "now",
                            description,
                        )
                        for number, description in enumerate(descriptions, start=1)
                    ],
                    markup="markdown",
                    store=store,
                )
                self.assertEqual("NEEDS_REVIEW", candidate["status"])

    def test_single_template_sample_needs_more_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ProposalStore(Path(directory) / "state", workspace_id="demo")
            candidate = extract_template_candidate(
                [
                    (
                        {
                            "provider": "backlog",
                            "base_url": "https://example.invalid",
                            "project_id": 1,
                            "ticket_id": "P-1",
                        },
                        "now",
                        "# Alpha\na\n",
                    )
                ],
                markup="markdown",
                store=store,
            )
            self.assertEqual("NEEDS_MORE_EVIDENCE", candidate["status"])

    def test_runtime_template_validation_matches_relational_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ProposalStore(Path(directory) / "state", workspace_id="demo")
            candidate = extract_template_candidate(
                [
                    (
                        {
                            "provider": "backlog",
                            "base_url": "https://example.invalid",
                            "project_id": 1,
                            "ticket_id": f"P-{number}",
                        },
                        "now",
                        "# Current State\nold\n",
                    )
                    for number in (1, 2)
                ],
                markup="markdown",
                store=store,
            )
            invalid = dict(candidate)
            invalid.pop("path")
            invalid["status"] = "BOGUS"
            invalid["sample_count"] = -1
            hash_input = dict(invalid)
            hash_input.pop("candidate_sha256")
            invalid["candidate_sha256"] = sha256_json(hash_input)
            with self.assertRaises(UnsafeContentError):
                validate_template(invalid)


if __name__ == "__main__":
    unittest.main()
