from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import FakeTrackerTransport, update_request, write_config
from ticket_state.adapters import BacklogAdapter, RedmineAdapter
from ticket_state.config import load_config
from ticket_state.storage import ProposalStore
from ticket_state.workflow import TicketStateService


class MutationBoundaryRegressionTests(unittest.TestCase):
    def test_prewrite_race_is_durable_without_mutation(self) -> None:
        for profile, adapter_type in (("backlog", BacklogAdapter), ("redmine", RedmineAdapter)):
            for change in ("description", "secret"):
                with self.subTest(profile=profile, change=change), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    config = root / "config.toml"
                    write_config(config)
                    with patch.dict(os.environ, {"BACKLOG_TEST_KEY": "backlog-secret", "REDMINE_TEST_KEY": "redmine-secret"}):
                        transport = FakeTrackerTransport()
                        store = ProposalStore(root / "state", workspace_id="demo")
                        service = TicketStateService(load_config(config), store, transport)
                        prepared = service.prepare(update_request(profile=profile))
                        proposal_id = prepared["proposal_id"]
                        reads = 0
                        original = adapter_type.read_ticket

                        def read_ticket(adapter, ticket):
                            nonlocal reads
                            reads += 1
                            if reads == 2:
                                value = f"{profile}-secret" if change == "secret" else "# Current State\nconcurrent change\n\n# Notes\nkeep\n"
                                setattr(transport, f"{profile}_description", value)
                            return original(adapter, ticket)

                        with patch.object(adapter_type, "read_ticket", read_ticket):
                            result = service.apply(proposal_id, dry_run=False)
                        expected = "FAILED" if change == "secret" else "NEEDS_REMERGE"
                        self.assertEqual(expected, result["state"])
                        self.assertEqual(expected, store.get_proposal(proposal_id)["state"])
                        self.assertEqual(0, result["remote_mutation_requests"])
                        self.assertEqual(0, transport.mutation_requests)
                        if change == "description":
                            self.assertEqual(2, store.get_proposal(proposal_id)["current_revision"])
                            self.assertTrue(store.get_revision(proposal_id)["metadata"]["remerge_required"])
                        for path in store.workspace.rglob("*"):
                            if path.is_file():
                                self.assertNotIn(f"{profile}-secret".encode(), path.read_bytes())
                        self.assertTrue(store.audit()["valid"])


if __name__ == "__main__":
    unittest.main()
