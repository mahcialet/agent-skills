from __future__ import annotations

import json
import os
import tempfile
import unittest
import sqlite3
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from helpers import FakeTrackerTransport, update_request, write_config
from ticket_state.config import load_config
from ticket_state.errors import StorageError
from ticket_state.model import sha256_text
from ticket_state.storage import ProposalStore
from ticket_state.workflow import TicketStateService


class ReceiptAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        config = self.root / "config.toml"
        write_config(config)
        self.env = patch.dict(os.environ, {"BACKLOG_TEST_KEY": "backlog-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.store = ProposalStore(self.root / "state", workspace_id="demo")
        self.service = TicketStateService(load_config(config), self.store, FakeTrackerTransport())

    def test_receipt_evidence_tampering_is_detected_on_open(self) -> None:
        result = self.service.update(update_request(), "update-state", dry_run=False)
        self.assertEqual("APPLIED", result["state"])
        operation_id = self.store.get_proposal(result["proposal_id"])["operation_id"]
        path = self.store.workspace / "receipts" / f"{operation_id}.json"
        original = json.loads(path.read_text())
        self.assertTrue(self.store.audit()["valid"])
        for field, replacement in (
            ("identity", {"provider": "redmine"}),
            ("description_sha256", "0" * 64),
            ("comment_marker", "ticket-state/" + "0" * 32),
            ("comment_id", "different-valid-id"),
            ("comment_sha256", "0" * 64),
        ):
            with self.subTest(field=field):
                path.write_text(json.dumps(original | {field: replacement}))
                with self.assertRaises(StorageError):
                    ProposalStore(self.root / "state", workspace_id="demo")
                path.write_text(json.dumps(original))
        self.assertTrue(self.store.audit()["valid"])

    def test_receipt_requires_independent_recorded_evidence(self) -> None:
        self.service.update(update_request(), "update-state", dry_run=False)
        with sqlite3.connect(self.store.db_path) as connection:
            connection.execute("DELETE FROM events WHERE event='REMOTE_RECEIPT_EVIDENCE'")
        with self.assertRaises(StorageError):
            self.store.audit()

    def test_comment_only_receipts_are_auditable(self) -> None:
        for operation in ("snapshot", "append-comment"):
            with self.subTest(operation=operation):
                request = {
                    "schema_version": 1, "operation": operation,
                    "profile": "backlog", "ticket": "PROJ-1",
                    "visibility_confirmed": True, "source_visibility": "public-only",
                }
                if operation == "snapshot":
                    request.update(
                        snapshot=update_request()["snapshot"],
                        change_summary=["状態を記録"],
                        snapshot_description_sha256=sha256_text(self.service.transport.backlog_description),
                    )
                else:
                    request["comment"] = "確認済みの補足"
                result = self.service.update(request, operation, dry_run=False)
                self.assertEqual("APPLIED", result["state"])
                self.assertTrue(self.store.audit()["valid"])

    def test_receipt_write_crash_recovers_without_resending(self) -> None:
        prepared = self.service.prepare(update_request())
        from ticket_state import storage

        real_write = storage.atomic_write

        def interrupted_write(path: Path, *args: object, **kwargs: object) -> None:
            if path.parent.name == "receipts":
                raise StorageError("simulated crash after durable evidence before receipt")
            real_write(path, *args, **kwargs)

        with patch.object(storage, "atomic_write", side_effect=interrupted_write):
            with self.assertRaises(StorageError):
                self.service.apply(prepared["proposal_id"], dry_run=False)
        self.assertEqual("VERIFYING", self.store.get_proposal(prepared["proposal_id"])["state"])
        reopened = ProposalStore(self.root / "state", workspace_id="demo")
        self.assertTrue(reopened.audit()["valid"])
        before = self.service.transport.mutation_requests
        recovered = self.reconcile_with_later_remote_timestamp(prepared["proposal_id"])
        self.assertEqual("APPLIED", recovered["state"])
        self.assertEqual(before, self.service.transport.mutation_requests)
        self.assertTrue(self.store.audit()["valid"])

    def reconcile_with_later_remote_timestamp(self, proposal_id: str) -> dict[str, object]:
        adapter = self.service._adapter("backlog")
        real_read = adapter.read_ticket
        self.service.transport.backlog_comments.append(
            {"id": 2, "content": "unrelated later comment", "created": "2026-09-07T00:00:00Z"}
        )
        with patch.object(self.service, "_adapter", return_value=adapter), patch.object(
            adapter, "read_ticket", side_effect=lambda ticket: replace(
                real_read(ticket), updated_at="2026-09-07T00:00:00Z"
            )
        ):
            return self.service.reconcile(proposal_id)

    def test_saved_receipt_recovers_after_unrelated_remote_timestamp_change(self) -> None:
        prepared = self.service.prepare(update_request())
        real_transition = self.store.transition

        def crash_before_applied(proposal_id: str, state: str, **kwargs: object) -> dict[str, object]:
            if state == "APPLIED":
                raise StorageError("simulated crash after receipt before applied")
            return real_transition(proposal_id, state, **kwargs)

        with patch.object(self.store, "transition", side_effect=crash_before_applied):
            with self.assertRaises(StorageError):
                self.service.apply(prepared["proposal_id"], dry_run=False)
        operation_id = self.store.get_proposal(prepared["proposal_id"])["operation_id"]
        path = self.store.workspace / "receipts" / f"{operation_id}.json"
        original = path.read_bytes()
        self.assertTrue(ProposalStore(self.root / "state", workspace_id="demo").audit()["valid"])
        before = self.service.transport.mutation_requests
        recovered = self.reconcile_with_later_remote_timestamp(prepared["proposal_id"])
        self.assertEqual("APPLIED", recovered["state"])
        self.assertEqual(before, self.service.transport.mutation_requests)
        self.assertEqual(original, path.read_bytes())
        self.assertTrue(self.store.audit()["valid"])

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_existing_work_directory_permissions_are_preserved(self) -> None:
        for mode in (0o755, 0o775):
            with self.subTest(mode=mode):
                parent = self.root / f"shared-{mode:o}"
                parent.mkdir(mode=mode)
                parent.chmod(mode)
                store = ProposalStore(parent, workspace_id="demo")
                self.assertEqual(mode, parent.stat().st_mode & 0o777)
                self.assertEqual(0o700, store.workspace.stat().st_mode & 0o777)
                self.assertEqual(0o600, store.db_path.stat().st_mode & 0o777)
                ProposalStore(parent, workspace_id="demo")
                self.assertEqual(mode, parent.stat().st_mode & 0o777)
