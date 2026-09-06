from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import FakeTrackerTransport, snapshot, update_request, write_config
from ticket_state.config import load_config
from ticket_state.errors import UnsafeContentError
from ticket_state.model import sha256_text
from ticket_state.storage import ProposalStore
from ticket_state.templates import approve_template, extract_template_candidate
from ticket_state.workflow import TicketStateService


class SelectedTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.toml"
        write_config(self.config_path)
        environment = patch.dict(os.environ, {"BACKLOG_TEST_KEY": "backlog-secret"})
        environment.start()
        self.addCleanup(environment.stop)
        self.transport = FakeTrackerTransport()
        self.store = ProposalStore(self.root / "state", workspace_id="demo")
        candidate = extract_template_candidate(
            [
                (
                    {"provider": "backlog", "base_url": "https://example.backlog.com",
                     "project_id": 10, "ticket_id": f"PROJ-{number}"},
                    "now",
                    description,
                )
                for number, description in enumerate(
                    (
                        "# Current State\nold\n\n# Notes\nkeep\n\n# Optional\nextra\n",
                        "# Current State\nold\n\n# Notes\nkeep\n",
                    ),
                    start=1,
                )
            ],
            markup="markdown",
            store=self.store,
        )
        approved = approve_template(
            Path(candidate["path"]), store=self.store,
            approved_by="test-reviewer", reason="必須見出しと任意見出しの順序を確認",
        )
        self.selection = {
            "template_id": approved["template_id"],
            "template_sha256": approved["artifact_sha256"],
        }
        self.config_path.write_text(
            self.config_path.read_text().replace(
                "[profiles.backlog.write_allowlist]",
                f'template = "{approved["template_id"]}"\n\n[profiles.backlog.write_allowlist]',
            ), encoding="utf-8",
        )
        self.service = TicketStateService(load_config(self.config_path), self.store, self.transport)

    def request(self, operation: str, description: str | None = None) -> dict[str, object]:
        if operation == "update-state":
            request = update_request()
            proposed = description if description is not None else str(request["proposed_description"])
            request.update(
                base_description_sha256=sha256_text(self.transport.backlog_description),
                proposed_description=proposed,
                snapshot_description_sha256=sha256_text(proposed),
                edited_sections=["Current State", "Notes", "Optional", "Custom", "__preamble__", "__structure__"],
            )
        else:
            request = {
                "schema_version": 1, "operation": operation, "profile": "backlog",
                "ticket": "PROJ-1", "visibility_confirmed": True,
                "source_visibility": "public-only",
            }
            if operation == "snapshot":
                request.update(
                    snapshot=snapshot(), change_summary=["状態を記録"],
                    snapshot_description_sha256=sha256_text(self.transport.backlog_description),
                )
            else:
                request["comment"] = "検証結果を記録"
        request.update(self.selection)
        return request

    def test_update_rejects_missing_required_or_reordered_headings(self) -> None:
        for description in (
            "# Current State\nnew\n",
            "# Notes\nkeep\n\n# Current State\nnew\n",
            "# Optional\nextra\n\n# Current State\nnew\n\n# Notes\nkeep\n",
        ):
            with self.subTest(description=description):
                with self.assertRaises(UnsafeContentError):
                    self.service.prepare(self.request("update-state", description))
                self.assertEqual([], self.store.list_pending())
                self.assertEqual(0, self.transport.mutation_requests)

    def test_request_cannot_select_template_without_profile_selection(self) -> None:
        self.config_path.write_text(
            self.config_path.read_text().replace(f'template = "{self.selection["template_id"]}"', ""),
            encoding="utf-8",
        )
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        for selection in (self.selection, {"template_sha256": self.selection["template_sha256"]}):
            with self.subTest(selection=selection):
                request = update_request()
                request.update(selection)
                with self.assertRaises(UnsafeContentError):
                    service.prepare(request)
                self.assertEqual([], self.store.list_pending())
                self.assertEqual(0, self.transport.mutation_requests)

    def test_update_can_initialize_or_repair_nonconforming_base(self) -> None:
        for base in ("", "# Current State\nold\n", "# Notes\nkeep\n\n# Current State\nold\n"):
            with self.subTest(base=base):
                self.transport.backlog_description = base
                result = self.service.update(self.request("update-state"), "update-state", dry_run=False)
                self.assertEqual("APPLIED", result["state"])
                self.assertEqual(update_request()["proposed_description"], self.transport.backlog_description)

    def test_optional_absence_and_custom_sections_are_allowed(self) -> None:
        for description in (
            str(update_request()["proposed_description"]),
            "前置き\n# Current State\nnew\n\n# Custom\n独自内容\n\n# Notes\nkeep\n",
            "# Current State\nnew\n\n# Notes\nkeep\n\n# Optional\nextra\n",
        ):
            with self.subTest(description=description):
                result = self.service.prepare(self.request("update-state", description))
                self.assertEqual("READY", result["state"])
                self.assertEqual(0, self.transport.mutation_requests)

    def test_comment_operations_validate_unchanged_description(self) -> None:
        for operation in ("snapshot", "append-comment"):
            for description in (
                "# Current State\nold\n",
                "# Notes\nkeep\n\n# Current State\nold\n",
                "# Current State\nold\n\n# Notes\nkeep\n\n# Notes\nduplicate\n",
            ):
                with self.subTest(operation=operation, description=description):
                    self.transport.backlog_description = description
                    with self.assertRaises(UnsafeContentError):
                        self.service.prepare(self.request(operation))
                    self.assertEqual([], self.store.list_pending())
                    self.assertEqual(0, self.transport.mutation_requests)

    def test_apply_and_revalidate_check_current_description_again(self) -> None:
        valid = self.transport.backlog_description
        for operation in ("snapshot", "append-comment"):
            for action in ("apply", "revalidate"):
                with self.subTest(operation=operation, action=action):
                    self.transport.backlog_description = valid
                    prepared = self.service.prepare(self.request(operation))
                    self.transport.backlog_description = "# Current State\nold\n"
                    with self.assertRaises(UnsafeContentError):
                        if action == "apply":
                            self.service.apply(prepared["proposal_id"], dry_run=False)
                        else:
                            self.service.revalidate(prepared["proposal_id"])
                    self.assertEqual(0, self.transport.mutation_requests)

    def test_reconcile_uses_recorded_plan_after_template_selection_changes(self) -> None:
        for change in ("artifact-removed", "configured-template-changed"):
            with self.subTest(change=change):
                prepared = self.service.prepare(self.request("snapshot"))
                original_backlog = self.transport._backlog

                def hide_comments(request, path, query):
                    if (
                        request.method == "GET" and path.endswith("/comments")
                        and self.transport.mutation_requests > before
                    ):
                        return self.transport._json(200, [])
                    return original_backlog(request, path, query)

                before = self.transport.mutation_requests
                with patch.object(self.transport, "_backlog", side_effect=hide_comments):
                    unknown = self.service.apply(prepared["proposal_id"], dry_run=False)
                self.assertEqual("UNKNOWN_REMOTE_RESULT", unknown["state"])
                self.assertEqual(before + 1, self.transport.mutation_requests)

                artifact = self.store.template_path("approved", self.selection["template_id"])
                saved_artifact = artifact.with_suffix(".saved")
                config_text = self.config_path.read_text(encoding="utf-8")
                try:
                    if change == "artifact-removed":
                        artifact.rename(saved_artifact)
                    else:
                        self.config_path.write_text(
                            config_text.replace(self.selection["template_id"], "0" * 32),
                            encoding="utf-8",
                        )
                    service = TicketStateService(
                        load_config(self.config_path), self.store, self.transport,
                    )
                    reconciled = service.reconcile(prepared["proposal_id"])
                    self.assertEqual("APPLIED", reconciled["state"])
                    self.assertEqual(before + 1, self.transport.mutation_requests)
                finally:
                    if saved_artifact.exists():
                        saved_artifact.rename(artifact)
                    self.config_path.write_text(config_text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
