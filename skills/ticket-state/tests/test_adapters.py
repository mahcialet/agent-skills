from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import FakeTrackerTransport, write_config
from ticket_state.adapters import make_adapter
from ticket_state.config import canonical_identity, load_config
from ticket_state.errors import IdentityError, PermissionDenied, RemoteError
from ticket_state.model import MutationPlan, sha256_json, ticket_context_sha256


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.toml"
        write_config(self.config_path)
        self.env = patch.dict(os.environ, {"BACKLOG_TEST_KEY": "backlog-secret", "REDMINE_TEST_KEY": "redmine-secret"})
        self.env.start()
        self.config = load_config(self.config_path)
        self.transport = FakeTrackerTransport()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def test_backlog_and_redmine_reads_validate_project(self) -> None:
        backlog = make_adapter(self.config.profile("backlog"), self.transport).read_ticket("101")
        redmine = make_adapter(self.config.profile("redmine"), self.transport).read_ticket("7")
        self.assertEqual("PROJ-1", backlog.identity.ticket_id)
        self.assertEqual("7", redmine.identity.ticket_id)
        self.assertEqual("101", backlog.provider_ticket_numeric_id)
        self.transport.project_id_override = 999
        with self.assertRaises(IdentityError):
            make_adapter(self.config.profile("backlog"), self.transport).read_ticket("PROJ-1")

    def test_backlog_markup_must_match_trusted_profile(self) -> None:
        self.transport.backlog_formatting_rule = "backlog"
        with self.assertRaises(IdentityError):
            make_adapter(self.config.profile("backlog"), self.transport).read_ticket("PROJ-1")

    def test_mutation_boundary_refuses_dry_run(self) -> None:
        profile = self.config.profile("backlog")
        plan = MutationPlan(
            "update-state",
            canonical_identity(profile, "PROJ-1"),
            "new",
            "comment",
            ("description:write", "comment:append"),
            "a" * 32,
            sha256_json({"x": 1}),
            "101",
        )
        with self.assertRaises(PermissionDenied):
            make_adapter(profile, self.transport).apply(plan, dry_run=True)
        self.assertEqual(0, self.transport.mutation_requests)

    def test_mutation_boundary_refuses_read_only_target(self) -> None:
        write_config(self.config_path, backlog_permissions='["comment:append"]')
        config = load_config(self.config_path)
        profile = config.profile("backlog")
        adapter = make_adapter(profile, self.transport)
        remote = adapter.read_ticket("PROJ-1")
        plan = MutationPlan(
            "update-state",
            canonical_identity(profile, "PROJ-1"),
            "new",
            "comment",
            ("description:write", "comment:append"),
            "a" * 32,
            "b" * 64,
            "101",
            ticket_context_sha256(remote),
        )
        with self.assertRaises(PermissionDenied):
            adapter.apply(plan, dry_run=False)
        self.assertEqual(0, self.transport.mutation_requests)

    def test_mutation_boundary_refuses_strict_update_without_cas(self) -> None:
        write_config(self.config_path, concurrency="strict")
        profile = load_config(self.config_path).profile("backlog")
        adapter = make_adapter(profile, self.transport)
        remote = adapter.read_ticket("PROJ-1")
        plan = MutationPlan(
            "update-state",
            remote.identity,
            "new description",
            "snapshot",
            ("description:write", "comment:append"),
            "a" * 32,
            "b" * 64,
            remote.provider_ticket_numeric_id,
            ticket_context_sha256(remote),
        )
        with self.assertRaises(PermissionDenied):
            adapter.apply(plan, dry_run=False)
        self.assertEqual(0, self.transport.mutation_requests)

    def test_provider_payloads_include_only_allowed_fields(self) -> None:
        for profile_name, ticket in (("backlog", "PROJ-1"), ("redmine", "7")):
            profile = self.config.profile(profile_name)
            adapter = make_adapter(profile, self.transport)
            remote = adapter.read_ticket(ticket)
            plan = MutationPlan(
                "update-state",
                canonical_identity(profile, ticket),
                "new description",
                "snapshot",
                ("description:write", "comment:append"),
                "a" * 32,
                "b" * 64,
                "101" if profile_name == "backlog" else "7",
                ticket_context_sha256(remote),
            )
            adapter.apply(plan, dry_run=False)
        backlog_request = next(request for request in self.transport.requests if request.method == "PATCH")
        redmine_request = next(request for request in self.transport.requests if request.method == "PUT")
        self.assertIn(b"description=", backlog_request.body or b"")
        self.assertNotIn(b"status", backlog_request.body or b"")
        self.assertEqual(
            b'{"issue": {"description": "new description", "notes": "snapshot", "private_notes": false}}',
            redmine_request.body,
        )
        self.assertNotIn("backlog-secret", backlog_request.url)
        self.assertEqual("backlog-secret", backlog_request.headers["Backlog-API-Key"])

    def test_redirect_response_is_never_treated_as_success(self) -> None:
        self.transport.redirect_next = True
        with self.assertRaises(RemoteError):
            make_adapter(self.config.profile("backlog"), self.transport).read_ticket("PROJ-1")

    def test_response_identity_must_match_requested_key_and_numeric_id(self) -> None:
        adapter = make_adapter(self.config.profile("backlog"), self.transport)
        self.transport.issue_key_override = "PROJ-2"
        with self.assertRaises(IdentityError):
            adapter.read_ticket("PROJ-1")
        self.transport.issue_key_override = None
        self.transport.issue_numeric_id_override = 999
        with self.assertRaises(IdentityError):
            adapter.read_ticket("101")

    def test_plan_cannot_reduce_operation_permissions_or_spoof_numeric_alias(self) -> None:
        profile = self.config.profile("backlog")
        adapter = make_adapter(profile, self.transport)
        remote = adapter.read_ticket("PROJ-1")
        empty_permissions = MutationPlan(
            "update-state",
            remote.identity,
            "new",
            "comment",
            (),
            "a" * 32,
            "b" * 64,
            "101",
            ticket_context_sha256(remote),
        )
        with self.assertRaises(PermissionDenied):
            adapter.apply(empty_permissions, dry_run=False)
        spoofed_alias = MutationPlan(
            "update-state",
            remote.identity,
            "new",
            "comment",
            ("description:write", "comment:append"),
            "a" * 32,
            "b" * 64,
            "999",
            ticket_context_sha256(remote),
        )
        with self.assertRaises(IdentityError):
            adapter.apply(spoofed_alias, dry_run=False)
        self.assertEqual(0, self.transport.mutation_requests)

    def test_comment_marker_pagination_returns_exact_evidence(self) -> None:
        self.transport.backlog_comments = [
            {"id": number, "content": f"comment-{number}", "created": "now"}
            for number in range(1, 102)
        ]
        self.transport.backlog_comments[0]["content"] = "Operation: ticket-state/deadbeef"
        evidence = make_adapter(self.config.profile("backlog"), self.transport).find_comment(
            "PROJ-1", "Operation: ticket-state/deadbeef"
        )
        self.assertIsNotNone(evidence)
        self.assertEqual("1", evidence.comment_id)


if __name__ == "__main__":
    unittest.main()
