from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_corpus_state import sample_record

SKILL_DIR = Path(__file__).resolve().parents[1]
CLI = SKILL_DIR / "scripts" / "corpus_tool.py"


def tree_snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def core_snapshot() -> dict[str, str]:
    paths = [SKILL_DIR / "SKILL.md"]
    paths.extend(sorted((SKILL_DIR / "references").rglob("*.md")))
    paths.extend(sorted((SKILL_DIR / "evals").glob("*.yaml")))
    return {
        str(path.relative_to(SKILL_DIR)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


class CorpusCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        self.record_path = self.root / "record.json"
        self.record_path.write_text(
            json.dumps(sample_record(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.annotation_path = self.root / "annotation.json"
        self.annotation_path.write_text(
            json.dumps(sample_record()["annotations"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run_cli(self, *args: str, data_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(CLI)]
        if data_dir is not None:
            command.extend(["--data-dir", str(data_dir)])
        command.extend(args)
        return subprocess.run(command, text=True, capture_output=True, check=False)

    def collect(self) -> str:
        result = self.run_cli(
            "corpus",
            "collect",
            "--record",
            str(self.record_path),
            "--actor",
            "tester",
            "--reason",
            "manual fixture",
            data_dir=self.data_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["created"]

    def test_read_only_commands_do_not_create_missing_data_directory(self) -> None:
        listed = self.run_cli("corpus", "list", data_dir=self.data_dir)
        validated = self.run_cli("corpus", "validate", data_dir=self.data_dir)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertEqual(validated.returncode, 0, validated.stderr)
        self.assertEqual(json.loads(listed.stdout)["records"], [])
        self.assertFalse(self.data_dir.exists())

    def test_collect_dry_run_does_not_write(self) -> None:
        result = self.run_cli(
            "corpus",
            "collect",
            "--record",
            str(self.record_path),
            "--actor",
            "tester",
            "--reason",
            "preview",
            "--dry-run",
            data_dir=self.data_dir,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["dry_run"])
        self.assertFalse(self.data_dir.exists())

    def test_full_manual_lifecycle_and_promotion_preview(self) -> None:
        core_before = core_snapshot()
        record_id = self.collect()
        inspected = self.run_cli("corpus", "inspect", record_id, data_dir=self.data_dir)
        self.assertEqual(json.loads(inspected.stdout)["decision"]["state"], "candidate")

        annotated = self.run_cli(
            "corpus",
            "annotate",
            record_id,
            "--annotation",
            str(self.annotation_path),
            "--actor",
            "reviewer",
            "--reason",
            "annotation confirmed",
            data_dir=self.data_dir,
        )
        self.assertEqual(annotated.returncode, 0, annotated.stderr)
        accepted = self.run_cli(
            "corpus",
            "accept",
            record_id,
            "--actor",
            "reviewer",
            "--reason",
            "clean sample accepted",
            data_dir=self.data_dir,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

        local_before = tree_snapshot(self.data_dir)
        preview = self.run_cli("corpus", "promote", record_id, data_dir=self.data_dir)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        preview_data = json.loads(preview.stdout)
        self.assertTrue(preview_data["dry_run"])
        self.assertFalse(preview_data["changes_rule_behavior"])
        self.assertEqual(tree_snapshot(self.data_dir), local_before)

        promoted = self.run_cli(
            "corpus",
            "promote",
            record_id,
            "--apply",
            "--actor",
            "reviewer",
            "--reason",
            "local regression sample",
            data_dir=self.data_dir,
        )
        self.assertEqual(promoted.returncode, 0, promoted.stderr)
        self.assertEqual(json.loads(promoted.stdout)["modified_core"], [])
        validated = self.run_cli("corpus", "validate", data_dir=self.data_dir)
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        listed = self.run_cli("corpus", "list", "--state", "promoted", data_dir=self.data_dir)
        self.assertEqual(json.loads(listed.stdout)["records"][0]["state"], "promoted")
        self.assertEqual(core_snapshot(), core_before)

    def test_reject_preserves_record_and_decision(self) -> None:
        record_id = self.collect()
        rejected = self.run_cli(
            "corpus",
            "reject",
            record_id,
            "--actor",
            "reviewer",
            "--reason",
            "not representative",
            data_dir=self.data_dir,
        )
        self.assertEqual(rejected.returncode, 0, rejected.stderr)
        record = json.loads(
            self.run_cli("corpus", "inspect", record_id, data_dir=self.data_dir).stdout
        )
        self.assertEqual(record["decision"]["state"], "rejected")
        self.assertEqual(record["decision"]["reason"], "not representative")

    def test_accept_without_annotation_is_rejected(self) -> None:
        record_id = self.collect()
        result = self.run_cli(
            "corpus",
            "accept",
            record_id,
            "--actor",
            "reviewer",
            "--reason",
            "skip annotation",
            data_dir=self.data_dir,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("state transition", result.stderr)

    def test_promotion_rejects_record_that_does_not_match_review_audit(self) -> None:
        record_id = self.collect()
        annotated = self.run_cli(
            "corpus",
            "annotate",
            record_id,
            "--annotation",
            str(self.annotation_path),
            "--actor",
            "reviewer",
            "--reason",
            "annotation confirmed",
            data_dir=self.data_dir,
        )
        self.assertEqual(annotated.returncode, 0, annotated.stderr)
        accepted = self.run_cli(
            "corpus",
            "accept",
            record_id,
            "--actor",
            "reviewer",
            "--reason",
            "accepted",
            data_dir=self.data_dir,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        path = self.data_dir / "accepted" / f"{record_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["decision"]["reviewer"] = "different-reviewer"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        preview = self.run_cli("corpus", "promote", record_id, data_dir=self.data_dir)
        self.assertEqual(preview.returncode, 2)
        self.assertIn("audit", preview.stderr)

    def test_promotion_rejects_forged_audit_chain(self) -> None:
        record_id = self.collect()
        self.assertEqual(
            self.run_cli(
                "corpus",
                "annotate",
                record_id,
                "--annotation",
                str(self.annotation_path),
                "--actor",
                "reviewer",
                "--reason",
                "annotation confirmed",
                data_dir=self.data_dir,
            ).returncode,
            0,
        )
        self.assertEqual(
            self.run_cli(
                "corpus",
                "accept",
                record_id,
                "--actor",
                "reviewer",
                "--reason",
                "accepted",
                data_dir=self.data_dir,
            ).returncode,
            0,
        )
        record = json.loads(
            (self.data_dir / "accepted" / f"{record_id}.json").read_text(encoding="utf-8")
        )
        forged = {
            "event_id": "forged-event",
            "timestamp": record["decision"]["decided_at"],
            "action": "collect",
            "record_id": record_id,
            "actor": record["decision"]["reviewer"],
            "reason": record["decision"]["reason"],
            "old_state": None,
            "new_state": "accepted",
            "schema_version": 1,
            "tool_version": "0.1.0",
        }
        (self.data_dir / "audit" / "events.jsonl").write_text(
            json.dumps(forged, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        validation = self.run_cli("corpus", "validate", data_dir=self.data_dir)
        preview = self.run_cli("corpus", "promote", record_id, data_dir=self.data_dir)
        self.assertEqual(validation.returncode, 1)
        self.assertEqual(preview.returncode, 2)
        self.assertIn("candidate", validation.stdout)

    def test_promotion_rejects_audit_actions_that_do_not_match_transitions(self) -> None:
        record_id = self.collect()
        self.assertEqual(
            self.run_cli(
                "corpus",
                "annotate",
                record_id,
                "--annotation",
                str(self.annotation_path),
                "--actor",
                "reviewer",
                "--reason",
                "annotation confirmed",
                data_dir=self.data_dir,
            ).returncode,
            0,
        )
        self.assertEqual(
            self.run_cli(
                "corpus",
                "accept",
                record_id,
                "--actor",
                "reviewer",
                "--reason",
                "accepted",
                data_dir=self.data_dir,
            ).returncode,
            0,
        )
        audit_path = self.data_dir / "audit" / "events.jsonl"
        events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        events[1]["action"] = "transition"
        events[2]["action"] = "annotate"
        audit_path.write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
            encoding="utf-8",
        )

        validation = self.run_cli("corpus", "validate", data_dir=self.data_dir)
        preview = self.run_cli("corpus", "promote", record_id, data_dir=self.data_dir)
        self.assertEqual(validation.returncode, 1)
        self.assertEqual(preview.returncode, 2)
        self.assertIn("action", validation.stdout)

    def test_project_write_requires_gitignore_or_explicit_override(self) -> None:
        project = self.root / "project"
        project.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=project, check=True)
        base_args = [
            "--scope",
            "project",
            "--project-root",
            str(project),
            "corpus",
            "collect",
            "--record",
            str(self.record_path),
            "--actor",
            "tester",
            "--reason",
            "project fixture",
        ]
        refused = subprocess.run(
            [sys.executable, str(CLI), *base_args], text=True, capture_output=True, check=False
        )
        self.assertEqual(refused.returncode, 2)
        self.assertFalse((project / ".reader-first-editor").exists())

        (project / ".gitignore").write_text(".reader-first-editor/\n", encoding="utf-8")
        allowed = subprocess.run(
            [sys.executable, str(CLI), *base_args], text=True, capture_output=True, check=False
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertTrue((project / ".reader-first-editor" / "candidates").is_dir())

    def test_explicit_data_dir_inside_git_still_requires_ignore(self) -> None:
        project = self.root / "explicit-project"
        project.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=project, check=True)
        data_dir = project / "local-corpus"
        refused = self.run_cli(
            "corpus",
            "collect",
            "--record",
            str(self.record_path),
            "--actor",
            "tester",
            "--reason",
            "explicit fixture",
            data_dir=data_dir,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertFalse(data_dir.exists())

        (project / ".gitignore").write_text("local-corpus/\n", encoding="utf-8")
        allowed = self.run_cli(
            "corpus",
            "collect",
            "--record",
            str(self.record_path),
            "--actor",
            "tester",
            "--reason",
            "explicit fixture",
            data_dir=data_dir,
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)


if __name__ == "__main__":
    unittest.main()
