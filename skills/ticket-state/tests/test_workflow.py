from __future__ import annotations

import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from helpers import FakeTrackerTransport, update_request, write_config
from ticket_state.config import load_config
from ticket_state.errors import IdentityError, StorageError, UnsafeContentError
from ticket_state.model import sha256_text
from ticket_state.storage import ProposalStore
from ticket_state.templates import approve_template, extract_template_candidate
from ticket_state.workflow import TicketStateService


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.toml"
        write_config(self.config_path)
        self.env = patch.dict(os.environ, {"BACKLOG_TEST_KEY": "backlog-secret", "REDMINE_TEST_KEY": "redmine-secret"})
        self.env.start()
        self.transport = FakeTrackerTransport()
        self.store = ProposalStore(self.root / "state", workspace_id="demo")
        self.service = TicketStateService(load_config(self.config_path), self.store, self.transport)

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_writable_dry_run_persists_exact_diff_and_sends_no_mutation(self) -> None:
        result = self.service.update(update_request(), "update-state", dry_run=True)
        self.assertEqual("DRY_RUN", result["outcome"])
        self.assertEqual(0, result["remote_mutation_requests"])
        self.assertEqual(0, self.transport.mutation_requests)
        self.assertIn("-old", Path(result["description_diff_path"]).read_text(encoding="utf-8"))
        self.assertIn("Current State Snapshot", Path(result["comment_path"]).read_text(encoding="utf-8"))
        self.assertIn("DRY_RUN_COMPLETED", [item["event"] for item in self.store.history(result["proposal_id"])])

    def test_read_only_dry_run_is_persistent_and_never_calls_mutation(self) -> None:
        write_config(self.config_path, backlog_permissions='["comment:append"]')
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        result = service.update(update_request(), "update-state", dry_run=True)
        self.assertEqual("PENDING_PERMISSION", result["state"])
        self.assertFalse(result["would_write"])
        self.assertEqual(0, self.transport.mutation_requests)
        reopened = ProposalStore(self.root / "state", workspace_id="demo")
        self.assertEqual(result["proposal_id"], reopened.list_pending()[0]["proposal_id"])

    def test_combined_update_is_verified_for_both_providers(self) -> None:
        for profile in ("backlog", "redmine"):
            result = self.service.update(update_request(profile=profile), "update-state", dry_run=False)
            self.assertEqual("APPLIED", result["state"])
            self.assertEqual(1, result["remote_mutation_requests"])
        self.assertEqual(2, self.transport.mutation_requests)

    def test_stale_input_is_saved_for_remerge_without_mutation(self) -> None:
        request = update_request()
        request["base_description_sha256"] = "0" * 64
        result = self.service.update(request, "update-state", dry_run=False)
        self.assertEqual("NEEDS_REMERGE", result["state"])
        self.assertEqual(0, self.transport.mutation_requests)
        self.assertEqual("NEEDS_REMERGE", self.service.revalidate(result["proposal_id"])["state"])

    def test_update_state_requires_source_description_hash(self) -> None:
        for missing_value in ("missing", None):
            request = update_request()
            if missing_value == "missing":
                request.pop("base_description_sha256")
            else:
                request["base_description_sha256"] = missing_value
            with self.subTest(value=missing_value):
                with self.assertRaises(UnsafeContentError):
                    self.service.prepare(request)
        self.assertEqual([], self.store.list_pending())
        self.assertEqual(0, self.transport.mutation_requests)

    def test_permission_revocation_is_rechecked_before_apply(self) -> None:
        prepared = self.service.prepare(update_request())
        write_config(self.config_path, backlog_permissions='["comment:append"]')
        revoked = TicketStateService(load_config(self.config_path), self.store, self.transport)
        result = revoked.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("PENDING_PERMISSION", result["state"])
        self.assertEqual(0, self.transport.mutation_requests)

    def test_timeout_after_remote_apply_reconciles_without_resend(self) -> None:
        prepared = self.service.prepare(update_request())
        self.transport.timeout_after_mutation = True
        unknown = self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("UNKNOWN_REMOTE_RESULT", unknown["state"])
        self.assertEqual(1, self.transport.mutation_requests)
        reconciled = self.service.reconcile(prepared["proposal_id"])
        self.assertEqual("APPLIED", reconciled["state"])
        self.assertEqual(1, self.transport.mutation_requests)

    def test_partial_combined_update_is_not_rolled_back_or_marked_applied(self) -> None:
        self.transport.partial_description_only = True
        result = self.service.update(update_request(), "update-state", dry_run=False)
        self.assertEqual("PARTIAL_APPLIED", result["state"])
        self.assertIn("new", self.transport.backlog_description)
        self.assertEqual([], self.transport.backlog_comments)

    def test_private_remote_comment_is_not_accepted_as_public_snapshot(self) -> None:
        self.transport.redmine_private_notes = True
        result = self.service.update(
            update_request(profile="redmine"), "update-state", dry_run=False
        )
        self.assertEqual("PARTIAL_APPLIED", result["state"])
        self.assertFalse(result["would_write"])
        self.assertEqual(1, self.transport.mutation_requests)

    def test_no_change_does_not_append_snapshot(self) -> None:
        request = update_request()
        request["proposed_description"] = self.transport.backlog_description
        request["snapshot_description_sha256"] = sha256_text(self.transport.backlog_description)
        request["state_changed"] = False
        result = self.service.update(request, "update-state", dry_run=False)
        self.assertEqual("NO_CHANGE", result["state"])
        self.assertEqual(0, self.transport.mutation_requests)
        self.assertEqual("", Path(result["comment_path"]).read_text(encoding="utf-8"))

    def test_empty_description_no_change_is_preserved(self) -> None:
        self.transport.backlog_description = ""
        request = update_request()
        request["base_description_sha256"] = sha256_text("")
        request["proposed_description"] = ""
        request["edited_sections"] = []
        request["snapshot_description_sha256"] = sha256_text("")
        request["state_changed"] = False
        result = self.service.update(request, "update-state", dry_run=True)
        self.assertEqual("NO_CHANGE", result["state"])
        self.assertEqual(0, self.transport.mutation_requests)

    def test_japanese_long_description_and_trailing_newlines_are_preserved(self) -> None:
        self.transport.backlog_description = ""
        proposed = "日本語の現在地\n" + ("長文" * 20000) + "\n\n"
        request = update_request()
        request["base_description_sha256"] = sha256_text("")
        request["proposed_description"] = proposed
        request["edited_sections"] = ["__preamble__"]
        request["snapshot_description_sha256"] = sha256_text(proposed)
        result = self.service.update(request, "update-state", dry_run=True)
        saved = Path(result["planned_payload_path"]).parent / "proposed-description.txt"
        self.assertEqual(proposed, saved.read_text(encoding="utf-8"))
        self.assertIn("日本語の現在地", Path(result["description_diff_path"]).read_text(encoding="utf-8"))
        self.assertEqual(0, self.transport.mutation_requests)

    def test_same_proposal_concurrent_apply_mutates_once(self) -> None:
        prepared = self.service.prepare(update_request())
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.service.apply(prepared["proposal_id"], dry_run=False), range(2)))
        self.assertEqual(1, self.transport.mutation_requests)
        self.assertEqual({"APPLIED"}, {result["state"] for result in results})

    def test_strict_concurrency_refuses_unconfirmed_cas(self) -> None:
        write_config(self.config_path, concurrency="strict")
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        result = service.update(update_request(), "update-state", dry_run=False)
        self.assertEqual("NEEDS_REVIEW", result["state"])
        self.assertEqual(0, self.transport.mutation_requests)

    def test_snapshot_detects_description_change_during_verification(self) -> None:
        request = {
            "schema_version": 1,
            "operation": "snapshot",
            "profile": "backlog",
            "ticket": "PROJ-1",
            "change_summary": ["状態を記録"],
            "snapshot": update_request()["snapshot"],
            "snapshot_description_sha256": sha256_text(self.transport.backlog_description),
            "visibility_confirmed": True,
            "source_visibility": "public-only",
        }
        prepared = self.service.prepare(request)
        self.transport.change_description_after_comment_lookup = True
        result = self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("PARTIAL_APPLIED", result["state"])
        self.assertFalse(result["would_write"])
        self.assertEqual(1, self.transport.mutation_requests)

    def test_comment_only_operations_use_only_comment_permission(self) -> None:
        write_config(self.config_path, backlog_permissions='["comment:append"]')
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        snapshot_request = {
            "schema_version": 1,
            "operation": "snapshot",
            "profile": "backlog",
            "ticket": "PROJ-1",
            "change_summary": ["状態を記録"],
            "snapshot": update_request()["snapshot"],
            "snapshot_description_sha256": sha256_text(self.transport.backlog_description),
            "visibility_confirmed": True,
            "source_visibility": "public-only",
        }
        snapshot_result = service.update(snapshot_request, "snapshot", dry_run=False)
        self.assertEqual("APPLIED", snapshot_result["state"])
        append_request = {
            "schema_version": 1,
            "operation": "append-comment",
            "profile": "backlog",
            "ticket": "PROJ-1",
            "comment": "補足: @teamへのmentionは再発火させない",
            "visibility_confirmed": True,
            "source_visibility": "public-only",
        }
        dry_result = service.update(append_request, "append-comment", dry_run=True)
        self.assertEqual("DRY_RUN", dry_result["outcome"])
        self.assertIn("@\u200bteam", Path(dry_result["comment_path"]).read_text(encoding="utf-8"))
        self.assertEqual(1, self.transport.mutation_requests)

    def test_external_update_creates_new_immutable_stale_revision(self) -> None:
        prepared = self.service.prepare(update_request())
        self.transport.backlog_description = self.transport.backlog_description.replace("keep", "human edit")
        result = self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("NEEDS_REMERGE", result["state"])
        self.assertEqual(2, result["proposal_revision"])
        self.assertEqual(0, self.transport.mutation_requests)
        self.assertTrue((self.store.workspace / "proposals" / prepared["proposal_id"] / "revisions" / "0001").exists())
        self.assertTrue((self.store.workspace / "proposals" / prepared["proposal_id"] / "revisions" / "0002").exists())

    def test_changes_outside_declared_sections_are_refused_before_storage(self) -> None:
        request = update_request()
        request["proposed_description"] = str(request["proposed_description"]).replace("keep", "overwrite")
        with self.assertRaises(UnsafeContentError):
            self.service.prepare(request)
        self.assertEqual([], self.store.list_pending())
        self.assertEqual(0, self.transport.mutation_requests)

    def test_project_mismatch_is_not_persisted(self) -> None:
        self.transport.project_id_override = 999
        with self.assertRaises(IdentityError):
            self.service.prepare(update_request())
        self.assertEqual([], self.store.list_pending())
        self.assertEqual(0, self.transport.mutation_requests)

    def test_local_persistence_failure_prevents_remote_mutation(self) -> None:
        with patch.object(self.store, "create_proposal", side_effect=StorageError("disk full")):
            with self.assertRaises(StorageError):
                self.service.update(update_request(), "update-state", dry_run=False)
        self.assertEqual(0, self.transport.mutation_requests)

    def test_api_key_is_absent_from_all_local_artifacts(self) -> None:
        self.service.update(update_request(), "update-state", dry_run=True)
        for path in self.store.workspace.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"backlog-secret", path.read_bytes(), str(path))

    def test_numeric_backlog_allowlist_is_resolved_to_canonical_ticket(self) -> None:
        write_config(self.config_path, backlog_allowlist_id="101")
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        request = update_request(ticket="101")
        result = service.update(request, "update-state", dry_run=True)
        self.assertEqual("DRY_RUN", result["outcome"])
        proposal = self.store.get_proposal(result["proposal_id"])
        self.assertEqual("PROJ-1", proposal["identity"]["ticket_id"])

    def test_new_remote_comment_forces_semantic_remerge(self) -> None:
        prepared = self.service.prepare(update_request())
        self.transport.backlog_comments.append(
            {"id": 1, "content": "human decision", "created": "2026-09-06T01:00:00Z"}
        )
        result = self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("NEEDS_REMERGE", result["state"])
        self.assertEqual(0, self.transport.mutation_requests)

    def test_marker_substring_without_exact_snapshot_is_not_applied(self) -> None:
        prepared = self.service.prepare(update_request())
        self.transport.timeout_after_mutation = True
        unknown = self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("UNKNOWN_REMOTE_RESULT", unknown["state"])
        marker = "ticket-state/" + self.store.get_revision(prepared["proposal_id"])["metadata"]["operation_id"]
        self.transport.backlog_comments[0]["content"] = f"truncated {marker}"
        result = self.service.reconcile(prepared["proposal_id"])
        self.assertEqual("PARTIAL_APPLIED", result["state"])
        self.assertEqual(1, self.transport.mutation_requests)

    def test_receipt_records_exact_comment_evidence(self) -> None:
        result = self.service.update(update_request(), "update-state", dry_run=False)
        metadata = self.store.get_revision(result["proposal_id"])["metadata"]
        receipt = self.store.workspace / "receipts" / f"{metadata['operation_id']}.json"
        value = __import__("json").loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual("1", value["comment_id"])
        self.assertEqual(metadata["comment_sha256"], value["comment_sha256"])

    def test_redmine_legacy_200_update_is_verified_before_applied(self) -> None:
        self.transport.redmine_success_status = 200
        result = self.service.update(
            update_request(profile="redmine"), "update-state", dry_run=False
        )
        self.assertEqual("APPLIED", result["state"])
        self.assertEqual(1, result["remote_mutation_requests"])
        self.assertEqual("h1. Current State\nnew\n\nh1. Notes\nkeep\n", self.transport.redmine_description)

    def test_applied_proposal_requires_immutable_receipt_for_audit(self) -> None:
        result = self.service.update(update_request(), "update-state", dry_run=False)
        operation_id = self.store.get_revision(result["proposal_id"])["metadata"]["operation_id"]
        receipt = self.store.workspace / "receipts" / f"{operation_id}.json"
        receipt.unlink()
        with self.assertRaises(StorageError):
            self.store.audit()

    def test_remote_status_classification_never_blind_retries(self) -> None:
        for status in (401, 403, 404, 422, 429, 500):
            with self.subTest(status=status):
                transport = FakeTrackerTransport()
                transport.mutation_status = status
                store = ProposalStore(self.root / f"state-{status}", workspace_id="demo")
                service = TicketStateService(load_config(self.config_path), store, transport)
                result = service.update(update_request(), "update-state", dry_run=False)
                self.assertEqual("UNKNOWN_REMOTE_RESULT" if status == 500 else "FAILED", result["state"])
                self.assertEqual(1, transport.mutation_requests)

    def test_unexpected_mutation_success_or_redirect_is_ambiguous(self) -> None:
        for status in (201, 302):
            with self.subTest(status=status):
                transport = FakeTrackerTransport()
                transport.mutation_status = status
                store = ProposalStore(self.root / f"state-unexpected-{status}", workspace_id="demo")
                service = TicketStateService(load_config(self.config_path), store, transport)
                result = service.update(update_request(), "update-state", dry_run=False)
                self.assertEqual("UNKNOWN_REMOTE_RESULT", result["state"])
                self.assertFalse(result["would_write"])
                self.assertEqual(1, transport.mutation_requests)

    def test_permission_decision_change_creates_revision_and_updates_diff_metadata(self) -> None:
        write_config(self.config_path, backlog_permissions='["comment:append"]')
        read_only = TicketStateService(load_config(self.config_path), self.store, self.transport)
        prepared = read_only.prepare(update_request())
        self.assertEqual("PENDING_PERMISSION", prepared["state"])
        write_config(self.config_path)
        writable = TicketStateService(load_config(self.config_path), self.store, self.transport)
        result = writable.revalidate(prepared["proposal_id"])
        self.assertEqual("READY", result["state"])
        self.assertEqual(2, result["proposal_revision"])
        diff = writable.diff(prepared["proposal_id"])
        self.assertEqual([], diff["missing_permissions"])
        self.assertEqual(2, diff["revision"])

    def test_request_containing_configured_secret_is_never_persisted(self) -> None:
        request = update_request()
        request["change_summary"] = ["leaked backlog-secret"]
        with self.assertRaises(UnsafeContentError):
            self.service.prepare(request)
        self.assertEqual([], self.store.list_pending())

    def test_json_escaped_secret_is_never_persisted(self) -> None:
        request = update_request()
        request["change_summary"] = ['contains key"tail value']
        with patch.dict(os.environ, {"REDMINE_TEST_KEY": 'key"tail'}):
            with self.assertRaises(UnsafeContentError):
                self.service.prepare(request)
        self.assertEqual([], self.store.list_pending())

    def test_remote_content_matching_another_profile_secret_is_not_persisted(self) -> None:
        self.transport.backlog_description = "redmine-secret"
        with self.assertRaises(UnsafeContentError):
            self.service.prepare(update_request())
        self.assertEqual([], self.store.list_pending())

    def test_persisted_draft_can_be_revalidated_after_prepare_crash(self) -> None:
        with patch.object(
            self.store,
            "transition",
            side_effect=StorageError("simulated crash after draft commit"),
        ):
            with self.assertRaises(StorageError):
                self.service.prepare(update_request())
        draft = self.store.list_pending()[0]
        self.assertEqual("DRAFT", draft["state"])
        result = self.service.revalidate(draft["proposal_id"])
        self.assertEqual("READY", result["state"])
        self.assertTrue(result["would_write"])
        self.assertIn(
            "DRAFT_RECOVERED",
            [event["event"] for event in self.store.history(draft["proposal_id"])],
        )

    def test_receipt_survives_crash_before_applied_transition(self) -> None:
        prepared = self.service.prepare(update_request())
        original_transition = self.store.transition
        failed_once = False

        def fail_applied_once(*args: object, **kwargs: object) -> dict[str, object]:
            nonlocal failed_once
            state = args[1] if len(args) > 1 else kwargs.get("state")
            if state == "APPLIED" and not failed_once:
                failed_once = True
                raise StorageError("simulated crash after receipt")
            return original_transition(*args, **kwargs)

        with patch.object(self.store, "transition", side_effect=fail_applied_once):
            with self.assertRaises(StorageError):
                self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("VERIFYING", self.store.get_proposal(prepared["proposal_id"])["state"])
        receipt = self.store.workspace / "receipts" / f"{self.store.get_revision(prepared['proposal_id'])['metadata']['operation_id']}.json"
        self.assertTrue(receipt.is_file())
        self.assertTrue(self.store.audit()["valid"])
        result = self.service.reconcile(prepared["proposal_id"])
        self.assertEqual("APPLIED", result["state"])
        self.assertFalse(result["would_write"])
        self.assertEqual(1, self.transport.mutation_requests)

    def test_content_approval_is_bound_to_exact_revision_and_not_inherited(self) -> None:
        prepared = self.service.prepare(update_request())
        revision = self.store.get_revision(prepared["proposal_id"])
        approval = self.store.record_approval(
            prepared["proposal_id"],
            revision=1,
            content_sha256=revision["content_sha256"],
            approved_by="reviewer",
            reason="diffを確認",
        )
        self.assertEqual(1, approval["revision"])
        with self.assertRaises(StorageError):
            self.store.record_approval(
                prepared["proposal_id"],
                revision=1,
                content_sha256="0" * 64,
                approved_by="reviewer",
                reason="wrong hash",
            )
        self.transport.backlog_comments.append({"id": 1, "content": "new decision", "created": "now"})
        stale = self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual(2, stale["proposal_revision"])
        self.assertEqual([], self.store.approvals(prepared["proposal_id"]))
        self.assertEqual(1, len(self.store.approvals(prepared["proposal_id"], 1)))

    def test_approved_template_id_and_artifact_hash_are_gates(self) -> None:
        candidate = extract_template_candidate(
            [
                ({"provider": "backlog", "base_url": "https://example.backlog.com", "project_id": 10, "ticket_id": f"PROJ-{number}"}, "now", self.transport.backlog_description)
                for number in (1, 2)
            ],
            markup="markdown",
            store=self.store,
        )
        approved = approve_template(
            Path(candidate["path"]),
            store=self.store,
            approved_by="reviewer",
            reason="見出しを確認",
        )
        config_text = self.config_path.read_text(encoding="utf-8").replace(
            '[profiles.backlog.write_allowlist]',
            f'template = "{approved["template_id"]}"\n\n[profiles.backlog.write_allowlist]',
        )
        self.config_path.write_text(config_text, encoding="utf-8")
        request = update_request()
        request["template_id"] = approved["template_id"]
        request["template_sha256"] = approved["artifact_sha256"]
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        self.assertEqual("DRY_RUN", service.update(request, "update-state", dry_run=True)["outcome"])
        approved_path = Path(approved["path"])
        approved_path.write_text(approved_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(UnsafeContentError):
            service.prepare(request)

    def test_approved_template_markup_must_match_profile(self) -> None:
        candidate = extract_template_candidate(
            [
                (
                    {
                        "provider": "redmine",
                        "base_url": "https://redmine.example.invalid/redmine",
                        "project_id": 20,
                        "ticket_id": str(number),
                    },
                    "now",
                    "h1. Current State\nold\n",
                )
                for number in (7, 8)
            ],
            markup="textile",
            store=self.store,
        )
        approved = approve_template(
            Path(candidate["path"]),
            store=self.store,
            approved_by="reviewer",
            reason="Textile形式を確認",
        )
        config_text = self.config_path.read_text(encoding="utf-8").replace(
            "[profiles.backlog.write_allowlist]",
            f'template = "{approved["template_id"]}"\n\n[profiles.backlog.write_allowlist]',
        )
        self.config_path.write_text(config_text, encoding="utf-8")
        request = update_request()
        request["template_id"] = approved["template_id"]
        request["template_sha256"] = approved["artifact_sha256"]
        service = TicketStateService(load_config(self.config_path), self.store, self.transport)
        with self.assertRaises(UnsafeContentError):
            service.prepare(request)

    def test_draft_prepared_and_mode_are_recorded_separately(self) -> None:
        result = self.service.update(update_request(), "update-state", dry_run=True)
        events = self.store.history(result["proposal_id"])
        self.assertEqual(
            ["PROPOSAL_CREATED", "PROPOSAL_PREPARED", "PROPOSAL_DECISION_RECORDED"],
            [item["event"] for item in events[:3]],
        )
        self.assertEqual("DRAFT", events[0]["state"])
        self.assertEqual("DRY_RUN_COMPLETED", events[-1]["event"])
        self.assertEqual("dry-run", self.store.get_proposal(result["proposal_id"])["last_mode"])
        self.assertTrue(Path(result["planned_payload_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
