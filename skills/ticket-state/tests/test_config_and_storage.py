from __future__ import annotations

import multiprocessing
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import write_config
from ticket_state.config import canonical_identity, load_config, normalize_target, permissions_for
from ticket_state.errors import ConfigurationError, IdentityError, StateError, StorageError
from ticket_state.storage import ProposalStore, atomic_write


def _hold_target_lock(root: str, ready: object, release: object) -> None:
    store = ProposalStore(Path(root), workspace_id="demo")
    with store.target_lock("a" * 64):
        ready.set()
        release.wait(5)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config_path = self.root / "config.toml"
        write_config(self.config_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_target_identity_includes_instance_and_project(self) -> None:
        config = load_config(self.config_path)
        profile = config.profile("backlog")
        identity = canonical_identity(profile, "PROJ-1")
        self.assertEqual("https://example.backlog.com", identity.base_url)
        self.assertEqual(10, identity.project_id)
        other = identity.__class__("backlog", "https://other.invalid", 10, "PROJ-1")
        self.assertNotEqual(identity.key, other.key)

    def test_urls_are_limited_to_configured_origin_and_subpath(self) -> None:
        config = load_config(self.config_path)
        self.assertEqual("PROJ-1", normalize_target(config.profile("backlog"), "https://example.backlog.com/view/PROJ-1"))
        self.assertEqual("7", normalize_target(config.profile("redmine"), "https://redmine.example.invalid/redmine/issues/7"))
        with self.assertRaises(IdentityError):
            normalize_target(config.profile("redmine"), "https://redmine.example.invalid/issues/7")
        with self.assertRaises(IdentityError):
            normalize_target(config.profile("backlog"), "https://user@example.backlog.com/view/PROJ-1")

    def test_default_https_port_and_ipv6_are_normalized_consistently(self) -> None:
        text = self.config_path.read_text(encoding="utf-8").replace(
            'base_url = "https://redmine.example.invalid/redmine"',
            'base_url = "https://[2001:db8::1]:443/redmine"',
        )
        self.config_path.write_text(text, encoding="utf-8")
        config = load_config(self.config_path)
        profile = config.profile("redmine")
        self.assertEqual("https://[2001:db8::1]/redmine", profile.instance.base_url)
        self.assertEqual(
            "7",
            normalize_target(profile, "https://[2001:db8::1]:443/redmine/issues/7"),
        )

    def test_backlog_base_path_is_rejected(self) -> None:
        text = self.config_path.read_text(encoding="utf-8").replace(
            'base_url = "https://example.backlog.com"',
            'base_url = "https://example.backlog.com/path"',
        )
        self.config_path.write_text(text, encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            load_config(self.config_path)

    def test_numeric_backlog_allowlist_alias_is_supported_after_resolution(self) -> None:
        write_config(self.config_path, backlog_allowlist_id="101")
        config = load_config(self.config_path)
        identity = canonical_identity(config.profile("backlog"), "PROJ-1")
        granted = permissions_for(config.profile("backlog"), identity, ("101",))
        self.assertEqual({"description:write", "comment:append"}, set(granted))

    def test_canonical_duplicate_allowlist_entries_are_rejected(self) -> None:
        text = self.config_path.read_text(encoding="utf-8").replace(
            '"PROJ-1" = ["description:write", "comment:append"]',
            '"PROJ-1" = ["description:write"]\n'
            '"proj-1" = ["comment:append"]',
        )
        self.config_path.write_text(text, encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            load_config(self.config_path)

    def test_allowlist_permission_does_not_propagate_to_other_ticket(self) -> None:
        config = load_config(self.config_path)
        profile = config.profile("backlog")
        child_or_related = canonical_identity(profile, "PROJ-2")
        self.assertEqual(frozenset(), permissions_for(profile, child_or_related))


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ProposalStore(self.root / "state", workspace_id="demo")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create(self) -> dict[str, object]:
        return self.store.create_proposal(
            profile_name="backlog",
            operation="update-state",
            identity={"provider": "backlog", "base_url": "https://example.backlog.com", "project_id": 10, "ticket_id": "PROJ-1"},
            state="PENDING_PERMISSION",
            required_permissions=["description:write", "comment:append"],
            reason="read only",
            artifacts={"metadata.json": b'{"schema_version":1}\n', "description.diff": b"diff\n"},
            metadata={"schema_version": 1},
        )

    def test_pending_and_history_survive_new_store_instance(self) -> None:
        proposal = self._create()
        reopened = ProposalStore(self.root / "state", workspace_id="demo")
        self.assertEqual(proposal["proposal_id"], reopened.list_pending()[0]["proposal_id"])
        self.assertEqual("PROPOSAL_CREATED", reopened.history(proposal["proposal_id"])[0]["event"])

    def test_revision_artifacts_are_immutable(self) -> None:
        proposal = self._create()
        path = Path(proposal["revision_path"]) / "metadata.json"
        with self.assertRaises(StorageError):
            atomic_write(path, b'{"changed":true}\n')
        self.assertEqual(b'{"schema_version":1}\n', path.read_bytes())

    def test_crlf_revision_artifact_hash_is_byte_stable(self) -> None:
        proposal = self.store.create_proposal(
            profile_name="redmine",
            operation="append-comment",
            identity={
                "provider": "redmine",
                "base_url": "https://redmine.example.invalid",
                "project_id": 20,
                "ticket_id": "7",
            },
            state="PENDING_PERMISSION",
            required_permissions=["comment:append"],
            reason="read only",
            artifacts={
                "metadata.json": b'{"schema_version":1}\n',
                "proposed-description.txt": b"first\r\nsecond\r\n",
            },
            metadata={"schema_version": 1},
        )

        reopened = ProposalStore(self.root / "state", workspace_id="demo")
        self.assertEqual(
            b"first\r\nsecond\r\n",
            reopened.read_artifact(str(proposal["proposal_id"]), "proposed-description.txt"),
        )

    def test_invalid_state_transition_is_rejected(self) -> None:
        proposal = self._create()
        self.store.transition(proposal["proposal_id"], "REJECTED", event="TEST")
        with self.assertRaises(StateError):
            self.store.transition(proposal["proposal_id"], "READY", event="TEST")

    def test_private_permissions_are_applied(self) -> None:
        proposal = self._create()
        proposal_dir = self.store.workspace / "proposals" / proposal["proposal_id"]
        self.assertEqual(0o700, proposal_dir.stat().st_mode & 0o777)
        self.assertEqual(0o600, (proposal_dir / "proposal.md").stat().st_mode & 0o777)
        self.assertEqual(0o600, self.store.db_path.stat().st_mode & 0o777)

    def test_modified_revision_artifact_is_detected_on_open(self) -> None:
        proposal = self._create()
        path = Path(proposal["revision_path"]) / "description.diff"
        path.write_text("tampered\n", encoding="utf-8")
        with self.assertRaises(StorageError):
            ProposalStore(self.root / "state", workspace_id="demo")

    def test_database_json_corruption_is_reported_as_storage_error(self) -> None:
        proposal = self._create()
        proposal_id = str(proposal["proposal_id"])
        connection = sqlite3.connect(self.store.db_path)
        try:
            connection.execute(
                "UPDATE proposals SET identity_json='{' WHERE proposal_id=?",
                (proposal_id,),
            )
            connection.execute(
                "UPDATE events SET data_json='[' WHERE proposal_id=?",
                (proposal_id,),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StorageError):
            self.store.get_proposal(proposal_id)
        with self.assertRaises(StorageError):
            self.store.history(proposal_id)
        with self.assertRaises(StorageError):
            self.store.audit()

    def test_approval_must_match_immutable_revision_hash(self) -> None:
        proposal = self._create()
        proposal_id = str(proposal["proposal_id"])
        revision = self.store.get_revision(proposal_id)
        self.store.record_approval(
            proposal_id,
            revision=1,
            content_sha256=revision["content_sha256"],
            approved_by="reviewer",
            reason="content reviewed",
        )
        connection = sqlite3.connect(self.store.db_path)
        try:
            connection.execute(
                "UPDATE approvals SET content_sha256=? WHERE proposal_id=?",
                ("0" * 64, proposal_id),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(StorageError):
            self.store.audit()

    def test_orphan_is_quarantined_then_audit_succeeds(self) -> None:
        orphan = self.store.workspace / "proposals" / ("f" * 32)
        orphan.mkdir()
        with self.assertRaises(StorageError):
            self.store.audit()
        report = self.store.recover_orphans(reason="interrupted local write")
        self.assertEqual([f"proposals/{'f' * 32}"], report["moved"])
        self.assertTrue(report["audit"]["valid"])
        self.assertFalse(orphan.exists())
        self.assertTrue(Path(report["path"]).is_file())

    def test_managed_directory_symlink_is_rejected(self) -> None:
        locks = self.store.workspace / "locks"
        locks.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        locks.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(StorageError):
            ProposalStore(self.root / "state", workspace_id="demo")

    @unittest.skipIf(os.name == "nt", "fork-based process lock test")
    def test_target_lock_is_process_safe(self) -> None:
        context = multiprocessing.get_context("fork")
        ready = context.Event()
        release = context.Event()
        process = context.Process(
            target=_hold_target_lock,
            args=(str(self.root / "state"), ready, release),
        )
        process.start()
        try:
            self.assertTrue(ready.wait(5))
            with self.assertRaises(StorageError):
                with self.store.target_lock("a" * 64, timeout=0.1):
                    pass
        finally:
            release.set()
            process.join(5)
            if process.is_alive():
                process.terminate()
                process.join(5)
        self.assertEqual(0, process.exitcode)

    def test_unignored_repository_work_directory_is_rejected(self) -> None:
        repository = self.root / "repository"
        repository.mkdir()
        subprocess.run(
            ["git", "init", "--quiet", str(repository)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with self.assertRaises(StorageError):
            ProposalStore(repository / "state", workspace_id="demo")


if __name__ == "__main__":
    unittest.main()
