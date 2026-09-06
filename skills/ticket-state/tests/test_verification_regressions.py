from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from helpers import FakeTrackerTransport, update_request, write_config
from ticket_state.config import load_config
from ticket_state.model import sha256_text
from ticket_state.storage import ProposalStore
from ticket_state.transport import HttpRequest, HttpResponse
from ticket_state.workflow import TicketStateService


class VerificationTransport(FakeTrackerTransport):
    def __init__(self) -> None:
        super().__init__()
        self.unsafe_kind: str | None = None
        self.unsafe_read = 1
        self.post_mutation_reads = 0
        self.drop_comments = False

    def send(self, request: HttpRequest) -> HttpResponse:
        response = super().send(request)
        if request.is_mutation and self.drop_comments:
            self.backlog_comments.clear()
            self.redmine_journals.clear()
        path = urlsplit(request.url).path
        issue_read = request.method == "GET" and (
            path == "/redmine/issues/7.json"
            or ("/api/v2/issues/" in path and not path.endswith("/comments"))
        )
        if self.mutation_requests and issue_read:
            self.post_mutation_reads += 1
            if self.unsafe_kind and self.post_mutation_reads >= self.unsafe_read:
                data = json.loads(response.body)
                issue = data.get("issue", data)
                if self.unsafe_kind == "identity":
                    if "project" in issue:
                        issue["project"]["id"] = 999
                    else:
                        issue["projectId"] = 999
                    issue["description"] = "untrusted remote record"
                else:
                    issue["description"] = (
                        "redmine-secret" if "issue" in data else "backlog-secret"
                    )
                return self._json(200, data)
        return response


class VerificationRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.toml"
        write_config(self.config_path)
        self.env = patch.dict(
            os.environ,
            {"BACKLOG_TEST_KEY": "backlog-secret", "REDMINE_TEST_KEY": "redmine-secret"},
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def service(self, name: str) -> tuple[TicketStateService, ProposalStore, VerificationTransport]:
        transport = VerificationTransport()
        store = ProposalStore(self.root / name, workspace_id="demo")
        return TicketStateService(load_config(self.config_path), store, transport), store, transport

    def snapshot_request(self) -> dict[str, object]:
        request = update_request()
        return {
            "schema_version": 1,
            "operation": "snapshot",
            "profile": "backlog",
            "ticket": "PROJ-1",
            "change_summary": ["状態を記録"],
            "snapshot": request["snapshot"],
            "snapshot_description_sha256": request["base_description_sha256"],
            "visibility_confirmed": True,
            "source_visibility": "public-only",
        }

    def test_unsafe_verification_is_persisted_and_reconciles_without_resend(self) -> None:
        for profile, positions in (("backlog", (1,)), ("redmine", (1, 2))):
            for kind in ("identity", "secret"):
                for position in positions:
                    with self.subTest(profile=profile, kind=kind, position=position):
                        service, store, transport = self.service(f"{profile}-{kind}-{position}")
                        prepared = service.prepare(update_request(profile=profile))
                        proposal_id = prepared["proposal_id"]
                        transport.unsafe_kind = kind
                        transport.unsafe_read = position
                        result = service.apply(proposal_id, dry_run=False)
                        self.assertEqual("UNKNOWN_REMOTE_RESULT", result["state"])
                        self.assertEqual("UNKNOWN_REMOTE_RESULT", store.get_proposal(proposal_id)["state"])
                        self.assertEqual("UNKNOWN_REMOTE_RESULT", service.reconcile(proposal_id)["state"])
                        self.assertEqual(1, transport.mutation_requests)
                        for path in store.workspace.rglob("*"):
                            if path.is_file():
                                for unsafe in (b"backlog-secret", b"redmine-secret", b"untrusted remote record"):
                                    self.assertNotIn(unsafe, path.read_bytes(), str(path))
                        transport.unsafe_kind = None
                        self.assertEqual("APPLIED", service.reconcile(proposal_id)["state"])
                        self.assertEqual(1, transport.mutation_requests)
                        self.assertTrue(store.audit()["valid"])

    def test_success_uses_only_comment_lookup_then_final_ticket_read(self) -> None:
        for profile, expected_issue_reads in (("backlog", 1), ("redmine", 2)):
            with self.subTest(profile=profile):
                service, _, transport = self.service(f"read-count-{profile}")
                result = service.update(update_request(profile=profile), "update-state", dry_run=False)
                self.assertEqual("APPLIED", result["state"])
                self.assertEqual(expected_issue_reads, transport.post_mutation_reads)
                self.assertEqual(1, transport.mutation_requests)

    def test_missing_comment_with_unchanged_description_is_unknown(self) -> None:
        for operation in ("snapshot", "update-state"):
            with self.subTest(operation=operation):
                service, store, transport = self.service(operation)
                transport.drop_comments = True
                request = self.snapshot_request() if operation == "snapshot" else update_request()
                if operation == "update-state":
                    request["proposed_description"] = transport.backlog_description
                    request["snapshot_description_sha256"] = sha256_text(transport.backlog_description)
                    request["state_changed"] = True
                result = service.update(request, operation, dry_run=False)
                self.assertEqual("UNKNOWN_REMOTE_RESULT", result["state"])
                self.assertEqual("UNKNOWN_REMOTE_RESULT", service.reconcile(result["proposal_id"])["state"])
                self.assertEqual(1, transport.mutation_requests)
                self.assertEqual([], transport.backlog_comments)
                self.assertEqual("UNKNOWN_REMOTE_RESULT", store.get_proposal(result["proposal_id"])["state"])

    def test_changed_description_without_comment_is_partial(self) -> None:
        service, _, transport = self.service("changed-description")
        transport.drop_comments = True
        result = service.update(update_request(), "update-state", dry_run=False)
        self.assertEqual("PARTIAL_APPLIED", result["state"])
        self.assertEqual(update_request()["proposed_description"], transport.backlog_description)
        self.assertEqual(1, transport.mutation_requests)

    def test_snapshot_success_and_description_race_keep_comment_evidence(self) -> None:
        for race, expected in ((False, "APPLIED"), (True, "PARTIAL_APPLIED")):
            with self.subTest(race=race):
                service, _, transport = self.service(f"snapshot-race-{race}")
                prepared = service.prepare(self.snapshot_request())
                transport.change_description_after_comment_lookup = race
                result = service.apply(prepared["proposal_id"], dry_run=False)
                self.assertEqual(expected, result["state"])
                self.assertEqual(1, transport.mutation_requests)
                self.assertEqual(1, len(transport.backlog_comments))


if __name__ == "__main__":
    unittest.main()
