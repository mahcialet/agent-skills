from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from reader_first.state import (
    DuplicateRecordError,
    InvalidTransitionError,
    LocalCorpusStore,
    RecordValidationError,
    StoreError,
    deterministic_candidate_id,
    resolve_data_dir,
    validate_corpus_record,
)


def sample_record() -> dict:
    return {
        "id": "placeholder",
        "id_material": {
            "algorithm": "sha256",
            "canonicalization_version": 1,
            "fields": [
                "schema_version",
                "sample_type",
                "source.type",
                "source.repository",
                "source.pr_number",
                "source.immutable_revision",
                "source.file",
                "source.span",
            ],
        },
        "schema_version": 1,
        "language": "ja",
        "translation_status": "native",
        "genre": "technical-readme",
        "reader": {
            "description": "GitHubの基本操作を理解している読者",
            "evidence_source": "pr-body",
        },
        "sample_type": "positive-reviewed",
        "quality_class": "clean",
        "source": {
            "type": "github-pr",
            "repository": "example/repository",
            "pr_number": 138,
            "commit": "a" * 40,
            "file": "README.md",
            "span": "section:introduction",
            "url": "https://example.invalid/example/repository/pull/138",
            "immutable_revision": "a" * 40,
            "retrieved_at": "2026-08-30T00:00:00Z",
            "correlation_group": "example-repository-pr-138",
        },
        "authorship": {
            "initial": "human",
            "final": "human-approved",
            "ai_assisted": "unknown",
        },
        "review_signal": {
            "type": "approval",
            "summary": "読みやすさに関する承認がある",
            "raw_text_included": False,
        },
        "rights": {
            "status": "unknown",
            "repository_license": None,
            "raw_text_redistribution": "unknown",
            "review_comment_redistribution": "unknown",
            "local_only": True,
            "redacted": False,
            "notes": "権利確認前はreference-only",
        },
        "handling": {
            "anonymized": False,
            "modified": False,
            "redactions": [],
        },
        "text": {
            "storage": "reference-only",
            "content_hash": "b" * 64,
            "content": None,
        },
        "annotations": {
            "expected_behavior": "no-change",
            "rationale": "長いが手順関係が明確である",
            "semantic_invariants": [],
            "do_not_change": ["手順の順序"],
            "expected_reread_risks": [],
        },
        "decision": {
            "state": "candidate",
            "reviewer": None,
            "decided_at": None,
            "reason": "manual collection",
        },
        "confidence": "medium",
        "created_at": "2026-08-30T00:00:00Z",
    }


class DataDirectoryTests(unittest.TestCase):
    def test_explicit_directory_has_highest_priority_without_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "custom" / "data"
            resolved = resolve_data_dir(
                explicit=target,
                scope="project",
                project_root=Path(temp) / "project",
                environ={"XDG_DATA_HOME": str(Path(temp) / "xdg")},
            )
            self.assertEqual(resolved, target.resolve())
            self.assertFalse(target.exists())

    def test_user_scope_uses_xdg_data_home(self) -> None:
        resolved = resolve_data_dir(
            environ={"XDG_DATA_HOME": "/tmp/rfe-xdg"},
            home="/tmp/rfe-home",
            platform="linux",
        )
        self.assertEqual(resolved, Path("/tmp/rfe-xdg/reader-first-editor"))

    def test_platform_fallbacks(self) -> None:
        windows = resolve_data_dir(
            environ={"LOCALAPPDATA": "C:/Users/example/AppData/Local"},
            home="C:/Users/example",
            platform="win32",
        )
        macos = resolve_data_dir(environ={}, home="/Users/example", platform="darwin")
        linux = resolve_data_dir(environ={}, home="/home/example", platform="linux")
        self.assertTrue(str(windows).endswith("reader-first-editor"))
        self.assertEqual(macos, Path("/Users/example/Library/Application Support/reader-first-editor"))
        self.assertEqual(linux, Path("/home/example/.local/share/reader-first-editor"))

    def test_project_scope_is_opt_in(self) -> None:
        self.assertEqual(
            resolve_data_dir(scope="project", project_root="/tmp/project"),
            Path("/tmp/project/.reader-first-editor"),
        )
        with self.assertRaises(ValueError):
            resolve_data_dir(scope="project")

    def test_store_rejects_skill_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_dir = Path(temp) / "installed-skill"
            with self.assertRaises(StoreError):
                LocalCorpusStore(skill_dir / "local-data", skill_dir=skill_dir)

    def test_store_uses_its_own_skill_directory_as_default_guard(self) -> None:
        skill_dir = Path(__file__).resolve().parents[1]
        with self.assertRaises(StoreError):
            LocalCorpusStore(skill_dir / "local-data")


class RecordTests(unittest.TestCase):
    def test_deterministic_id_is_stable_and_source_sensitive(self) -> None:
        record = sample_record()
        self.assertEqual(deterministic_candidate_id(record), deterministic_candidate_id(deepcopy(record)))
        changed = deepcopy(record)
        changed["source"]["span"] = "section:usage"
        self.assertNotEqual(deterministic_candidate_id(record), deterministic_candidate_id(changed))

    def test_record_validation_rejects_reference_only_raw_text(self) -> None:
        record = sample_record()
        record["id"] = deterministic_candidate_id(record)
        record["text"]["content"] = "保存してはいけないthird-party text"
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)

    def test_record_validation_requires_rights_status(self) -> None:
        record = sample_record()
        record["id"] = deterministic_candidate_id(record)
        record["rights"]["status"] = "assumed"
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)

    def test_record_validation_rejects_unknown_fields(self) -> None:
        record = sample_record()
        record["id"] = deterministic_candidate_id(record)
        record["source"]["assumed_license"] = "MIT"
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)

    def test_record_validation_recomputes_deterministic_id(self) -> None:
        record = sample_record()
        record["id"] = "rfe-" + "0" * 20
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)

    def test_record_validation_rejects_incomplete_github_provenance(self) -> None:
        record = sample_record()
        record["source"]["repository"] = None
        record["id"] = deterministic_candidate_id(record)
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)

    def test_record_validation_rejects_nonpositive_or_boolean_pr_number(self) -> None:
        for value in (0, -1, True):
            with self.subTest(value=value):
                record = sample_record()
                record["source"]["pr_number"] = value
                record["id"] = deterministic_candidate_id(record)
                with self.assertRaises(RecordValidationError):
                    validate_corpus_record(record)

    def test_record_validation_rejects_public_unknown_rights(self) -> None:
        record = sample_record()
        record["rights"]["local_only"] = False
        record["id"] = deterministic_candidate_id(record)
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)

    def test_all_quality_classes_are_valid_corpus_inputs(self) -> None:
        for quality in ("problematic", "clean", "borderline"):
            with self.subTest(quality=quality):
                record = sample_record()
                record["quality_class"] = quality
                record["id"] = deterministic_candidate_id(record)
                validate_corpus_record(record)
                self.assertEqual(record["quality_class"], quality)

    def test_rejected_suggestion_can_be_kept_as_negative_control(self) -> None:
        record = sample_record()
        record["sample_type"] = "rejected-suggestion"
        record["review_signal"] = {
            "type": "rejection",
            "summary": "人間が変更不要と判断した",
            "raw_text_included": False,
        }
        record["id"] = deterministic_candidate_id(record)
        validate_corpus_record(record)
        self.assertEqual(record["sample_type"], "rejected-suggestion")
        self.assertEqual(record["annotations"]["expected_behavior"], "no-change")

    def test_non_candidate_requires_reviewer_decision(self) -> None:
        record = sample_record()
        record["id"] = deterministic_candidate_id(record)
        record["decision"]["state"] = "accepted"
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(record)


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = LocalCorpusStore(
            Path(self.temp.name) / "data",
            skill_dir=Path(self.temp.name) / "installed-skill",
            clock=lambda: "2026-08-30T12:00:00Z",
        )

    def test_create_detects_duplicate_and_records_audit(self) -> None:
        created = self.store.create_candidate(sample_record(), actor="tester", reason="fixture")
        with self.assertRaises(DuplicateRecordError):
            self.store.create_candidate(sample_record(), actor="tester", reason="duplicate")
        self.assertEqual(self.store.load_record(created["id"]), created)
        events = [json.loads(line) for line in self.store.audit_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["new_state"], "candidate")

    def test_batch_duplicate_preflight_prevents_partial_creation(self) -> None:
        existing = self.store.create_candidate(sample_record(), actor="tester", reason="fixture")
        fresh = sample_record()
        fresh["source"]["span"] = "section:fresh"
        with self.assertRaises(DuplicateRecordError):
            self.store.create_candidates(
                [fresh, sample_record()],
                actor="tester",
                reason="batch fixture",
            )
        self.assertEqual(self.store.list_records()[0]["id"], existing["id"])
        self.assertEqual(len(self.store.list_records()), 1)

    def test_audit_actor_and_reason_are_required(self) -> None:
        with self.assertRaises(StoreError):
            self.store.create_candidate(sample_record(), actor="", reason="fixture")
        with self.assertRaises(StoreError):
            self.store.create_candidate(sample_record(), actor="tester", reason="")
        self.assertFalse(self.store.root.exists())

    def test_internal_state_directory_symlink_is_rejected(self) -> None:
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        self.store.root.mkdir(parents=True)
        try:
            (self.store.root / "candidates").symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinkを作成できません: {exc}")
        with self.assertRaises(StoreError):
            self.store.create_candidate(sample_record(), actor="collector", reason="symlink test")
        self.assertEqual(list(outside.iterdir()), [])

    def test_valid_state_transitions_preserve_record_and_append_audit(self) -> None:
        created = self.store.create_candidate(sample_record(), actor="collector", reason="fixture")
        annotated = self.store.transition(
            created["id"], "annotated", actor="reviewer", reason="annotation confirmed"
        )
        accepted = self.store.transition(
            created["id"], "accepted", actor="reviewer", reason="useful clean sample"
        )
        self.assertEqual(annotated["decision"]["state"], "annotated")
        self.assertEqual(accepted["decision"]["state"], "accepted")
        self.assertEqual(accepted["source"], created["source"])
        events = self.store.audit_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(events), 3)
        self.assertEqual(self.store.validate_store(), [])

    def test_invalid_transition_is_rejected_without_moving_record(self) -> None:
        created = self.store.create_candidate(sample_record(), actor="collector", reason="fixture")
        with self.assertRaises(InvalidTransitionError):
            self.store.transition(created["id"], "accepted", actor="reviewer", reason="skip annotation")
        with self.assertRaises(InvalidTransitionError):
            self.store.transition(created["id"], "promoted", actor="reviewer", reason="direct promotion")
        self.assertEqual(self.store.load_record(created["id"])["decision"]["state"], "candidate")

    def test_missing_annotation_is_rejected(self) -> None:
        record = sample_record()
        record["annotations"]["rationale"] = ""
        created = self.store.create_candidate(record, actor="collector", reason="fixture")
        with self.assertRaises(RecordValidationError):
            self.store.transition(created["id"], "annotated", actor="reviewer", reason="not annotated")

    def test_corrupted_record_is_reported(self) -> None:
        created = self.store.create_candidate(sample_record(), actor="collector", reason="fixture")
        path = self.store.root / "candidates" / f"{created['id']}.json"
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(StoreError):
            self.store.load_record(created["id"])

    def test_record_id_cannot_escape_state_directory(self) -> None:
        with self.assertRaises(StoreError):
            self.store.load_record("../../outside")

    def test_create_rolls_back_when_audit_commit_fails(self) -> None:
        record_id = deterministic_candidate_id(sample_record())
        with (
            mock.patch.object(self.store, "_atomic_append_audit", side_effect=OSError("audit failed")),
            self.assertRaises(OSError),
        ):
            self.store.create_candidate(sample_record(), actor="collector", reason="fixture")
        self.assertEqual(self.store._locations(record_id), [])
        self.assertEqual(list(self.store.pending_dir.glob("*.json")), [])

    def test_transition_rolls_back_when_audit_commit_fails(self) -> None:
        created = self.store.create_candidate(sample_record(), actor="collector", reason="fixture")
        before_events = self.store.audit_path.read_text(encoding="utf-8")
        with (
            mock.patch.object(self.store, "_atomic_append_audit", side_effect=OSError("audit failed")),
            self.assertRaises(OSError),
        ):
            self.store.transition(
                created["id"], "annotated", actor="reviewer", reason="annotation confirmed"
            )
        self.assertEqual(self.store.load_record(created["id"])["decision"]["state"], "candidate")
        self.assertEqual(self.store.audit_path.read_text(encoding="utf-8"), before_events)
        self.assertEqual(list(self.store.pending_dir.glob("*.json")), [])

    def test_initialize_recovers_uncommitted_transition_journal(self) -> None:
        created = self.store.create_candidate(sample_record(), actor="collector", reason="fixture")
        before = self.store.load_record(created["id"])
        after = deepcopy(before)
        after["decision"] = {
            "state": "annotated",
            "reviewer": "reviewer",
            "decided_at": "2026-08-30T12:00:00Z",
            "reason": "annotation confirmed",
        }
        event = self.store._make_event(
            action="transition",
            record_id=created["id"],
            actor="reviewer",
            reason="annotation confirmed",
            old_state="candidate",
            new_state="annotated",
        )
        pending = self.store.pending_dir / f"{event['event_id']}.json"
        self.store._atomic_write(pending, {"event": event, "before": before, "after": after})
        self.store._place_record(after)

        recovered = LocalCorpusStore(
            self.store.root,
            skill_dir=Path(self.temp.name) / "installed-skill",
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        recovered.initialize()
        self.assertEqual(recovered.load_record(created["id"])["decision"]["state"], "candidate")
        self.assertEqual(list(recovered.pending_dir.glob("*.json")), [])

    def test_concurrent_writers_preserve_all_audit_events(self) -> None:
        class SlowAuditStore(LocalCorpusStore):
            def _atomic_append_audit(self, event: dict) -> None:
                time.sleep(0.005)
                super()._atomic_append_audit(event)

        stores = [
            SlowAuditStore(
                self.store.root,
                skill_dir=Path(self.temp.name) / "installed-skill",
                clock=lambda: "2026-08-30T12:00:00Z",
            )
            for _ in range(4)
        ]

        def create(index: int) -> str:
            record = sample_record()
            record["source"]["span"] = f"section:{index}"
            return stores[index % len(stores)].create_candidate(
                record, actor=f"writer-{index}", reason="concurrency test"
            )["id"]

        with ThreadPoolExecutor(max_workers=4) as executor:
            record_ids = list(executor.map(create, range(12)))
        events = [json.loads(line) for line in self.store.audit_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(events), 12)
        self.assertEqual({event["record_id"] for event in events}, set(record_ids))

    def test_concurrent_duplicate_creation_has_one_winner(self) -> None:
        stores = [
            LocalCorpusStore(
                self.store.root,
                skill_dir=Path(self.temp.name) / "installed-skill",
                clock=lambda: "2026-08-30T12:00:00Z",
            )
            for _ in range(2)
        ]

        def create(store: LocalCorpusStore) -> str:
            try:
                store.create_candidate(sample_record(), actor="writer", reason="duplicate race")
                return "created"
            except DuplicateRecordError:
                return "duplicate"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, stores))
        self.assertCountEqual(results, ["created", "duplicate"])


if __name__ == "__main__":
    unittest.main()
