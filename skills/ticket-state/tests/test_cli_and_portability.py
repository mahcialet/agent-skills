from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import snapshot
from ticket_state.model import sha256_text


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


class CliAndPortabilityTests(unittest.TestCase):
    def test_standalone_copy_public_cli_dry_run(self) -> None:
        source = Path(__file__).resolve().parents[1]
        source_hash = tree_hash(source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copied = root / "standalone" / "ticket-state"
            copied.parent.mkdir()
            shutil.copytree(source, copied, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            cwd = root / "unrelated-cwd"
            cwd.mkdir()
            config = copied / "assets" / "config.example.toml"
            work_dir = root / "private-state"
            request_path = root / "request.json"
            base = "## Current State\n未着手。\n\n## Notes\n保持する。\n"
            request = {
                "schema_version": 1,
                "operation": "update-state",
                "profile": "product_a",
                "ticket": "PRODA-123",
                "base_description_sha256": sha256_text(base),
                "proposed_description": base.replace("未着手", "mock検証済み"),
                "edited_sections": ["Current State"],
                "change_summary": ["mock検証を完了"],
                "snapshot": snapshot(),
                "snapshot_description_sha256": sha256_text(base.replace("未着手", "mock検証済み")),
                "state_changed": True,
                "visibility_confirmed": True,
                "source_visibility": "public-only",
            }
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            env = os.environ.copy()
            env["BACKLOG_API_KEY"] = "fixture-only-key"
            help_result = subprocess.run(
                [sys.executable, str(copied / "scripts" / "ticket_state.py"), "--help"],
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, help_result.returncode, help_result.stderr)
            self.assertFalse(work_dir.exists())
            validate_result = subprocess.run(
                [sys.executable, str(copied / "scripts" / "validate_content.py")],
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, validate_result.returncode, validate_result.stdout + validate_result.stderr)
            result = subprocess.run(
                [
                    sys.executable,
                    str(copied / "scripts" / "ticket_state.py"),
                    "--config",
                    str(config),
                    "--work-dir",
                    str(work_dir),
                    "--workspace-id",
                    "portable",
                    "--json",
                    "--fixture",
                    str(copied / "examples" / "fixtures" / "backlog.json"),
                    "update-state",
                    "--request",
                    str(request_path),
                    "--dry-run",
                ],
                cwd=cwd,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual("DRY_RUN", payload["outcome"])
            self.assertEqual(0, payload["remote_mutation_requests"])
            self.assertTrue((work_dir / "portable" / "state.sqlite3").exists())
            self.assertFalse((copied / ".agent-work").exists())
        self.assertEqual(source_hash, tree_hash(source))

    def test_secret_is_redacted_from_cli_errors(self) -> None:
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            text = (source / "assets" / "config.example.toml").read_text(encoding="utf-8")
            config.write_text(text, encoding="utf-8")
            fixture = root / "empty-fixture.json"
            fixture.write_text('{"schema_version":1,"responses":[]}', encoding="utf-8")
            env = os.environ.copy()
            env["BACKLOG_API_KEY"] = "do-not-print-this-secret"
            result = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "ticket_state.py"),
                    "--config",
                    str(config),
                    "--fixture",
                    str(fixture),
                    "--json",
                    "read",
                    "--profile",
                    "product_a",
                    "--ticket",
                    "PRODA-123",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertNotIn("do-not-print-this-secret", result.stdout + result.stderr)
            self.assertEqual("REMOTE_ERROR", json.loads(result.stderr)["error"])

    def test_read_refuses_secret_from_another_configured_instance(self) -> None:
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_value = json.loads(
                (source / "examples" / "fixtures" / "backlog.json").read_text(encoding="utf-8")
            )
            for response in fixture_value["responses"]:
                body = response.get("body", {})
                if isinstance(body, dict) and "description" in body:
                    body["description"] = "other-instance-secret"
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps(fixture_value, ensure_ascii=False), encoding="utf-8")
            env = os.environ.copy()
            env["BACKLOG_API_KEY"] = "backlog-fixture-key"
            env["REDMINE_API_KEY"] = "other-instance-secret"
            result = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "ticket_state.py"),
                    "--config",
                    str(source / "assets" / "config.example.toml"),
                    "--fixture",
                    str(fixture),
                    "--json",
                    "read",
                    "--profile",
                    "product_a",
                    "--ticket",
                    "PRODA-123",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertNotIn("other-instance-secret", result.stdout + result.stderr)
            self.assertEqual("NEEDS_REVIEW", json.loads(result.stderr)["error"])

    def test_read_only_text_output_explains_persisted_proposal(self) -> None:
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.toml"
            config.write_text(
                (source / "assets" / "config.example.toml")
                .read_text(encoding="utf-8")
                .replace(
                    '"PRODA-123" = ["description:write", "comment:append"]',
                    '"PRODA-123" = ["comment:append"]',
                ),
                encoding="utf-8",
            )
            base = "## Current State\n未着手。\n\n## Notes\n保持する。\n"
            proposed = base.replace("未着手", "mock検証済み")
            request = {
                "schema_version": 1,
                "operation": "update-state",
                "profile": "product_a",
                "ticket": "PRODA-123",
                "base_description_sha256": sha256_text(base),
                "proposed_description": proposed,
                "edited_sections": ["Current State"],
                "change_summary": ["mock検証を完了"],
                "snapshot": snapshot(),
                "snapshot_description_sha256": sha256_text(proposed),
                "state_changed": True,
                "visibility_confirmed": True,
                "source_visibility": "public-only",
            }
            request_path = root / "request.json"
            request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
            env = os.environ.copy()
            env["BACKLOG_API_KEY"] = "fixture-only-key"
            result = subprocess.run(
                [
                    sys.executable,
                    str(source / "scripts" / "ticket_state.py"),
                    "--config",
                    str(config),
                    "--work-dir",
                    str(root / "state"),
                    "--fixture",
                    str(source / "examples" / "fixtures" / "backlog.json"),
                    "update-state",
                    "--request",
                    str(request_path),
                    "--dry-run",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(2, result.returncode, result.stdout + result.stderr)
            self.assertIn("PENDING_PERMISSION", result.stdout)
            self.assertIn("remoteは更新していません", result.stdout)
            self.assertIn("必要な権限", result.stdout)
            self.assertIn("保存先", result.stdout)
            self.assertIn("差分", result.stdout)


if __name__ == "__main__":
    unittest.main()
