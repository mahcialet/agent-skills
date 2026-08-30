from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPOSITORY_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from stamp_installed_skill import (  # noqa: E402
    StampError,
    annotation_for,
    stamp_file,
    stamp_text,
)


SKILL_TEXT = """---
name: demo-skill
description: >-
  Explain when this demo Skill should be used.
license: MIT
---

# Demo Skill

Follow the fixture instructions.
"""


class LocalInstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = Path(self.temporary_directory.name) / "repository"
        self.scripts = self.repository / "scripts"
        self.skill = self.repository / "skills" / "demo-skill"
        self.scripts.mkdir(parents=True)
        self.skill.mkdir(parents=True)

        for script_name in (
            "install-local.sh",
            "install_local.py",
            "stamp_installed_skill.py",
            "validate_skills.py",
        ):
            shutil.copy2(SCRIPTS_DIR / script_name, self.scripts / script_name)
        (self.skill / "SKILL.md").write_text(SKILL_TEXT, encoding="utf-8")
        (self.skill / "asset.txt").write_text("fixture asset\n", encoding="utf-8")
        (self.repository / "README.md").write_text("fixture repository\n", encoding="utf-8")

    @property
    def installer(self) -> Path:
        return self.scripts / "install-local.sh"

    @property
    def active_skill(self) -> Path:
        return self.repository / ".agents" / "skills" / "demo-skill"

    @property
    def backup_root(self) -> Path:
        return self.repository / ".agents" / "backups"

    def run_command(
        self,
        *arguments: str,
        check: bool = True,
        cwd: Path | None = None,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(arguments),
            cwd=cwd or self.repository,
            check=check,
            env={**os.environ, **(environment or {})},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def run_installer(
        self,
        *arguments: str,
        check: bool = True,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return self.run_command(
            "bash",
            str(self.installer),
            "demo-skill",
            "--scope",
            "project",
            *arguments,
            check=check,
            environment=environment,
        )

    def initialize_git(self, *, commit: bool = True) -> str | None:
        self.run_command("git", "init", "-q")
        self.run_command("git", "config", "user.name", "Installer Test")
        self.run_command("git", "config", "user.email", "installer@example.invalid")
        if not commit:
            return None
        self.run_command("git", "add", ".")
        self.run_command(
            "git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"
        )
        return self.run_command("git", "rev-parse", "HEAD").stdout.strip()

    def commit_skill_change(self, message: str) -> str:
        self.run_command("git", "add", "skills/demo-skill")
        self.run_command(
            "git", "-c", "commit.gpgsign=false", "commit", "-qm", message
        )
        return self.run_command("git", "rev-parse", "HEAD").stdout.strip()

    def instrument_orchestrator_checkpoint(
        self,
        checkpoint: str,
        statements: list[str],
    ) -> None:
        orchestrator = self.scripts / "install_local.py"
        text = orchestrator.read_text(encoding="utf-8")
        lines = text.splitlines(keepends=True)
        matching_indexes = [
            index for index, line in enumerate(lines) if checkpoint in line
        ]
        self.assertEqual(
            1,
            len(matching_indexes),
            f"orchestrator checkpoint not unique: {checkpoint}",
        )
        checkpoint_index = matching_indexes[0]
        checkpoint_line = lines[checkpoint_index]
        indentation = checkpoint_line[: len(checkpoint_line) - len(checkpoint_line.lstrip())]
        newline = "\r\n" if checkpoint_line.endswith("\r\n") else "\n"
        injected = "".join(
            f"{indentation}{statement}{newline}" for statement in statements
        )
        lines[checkpoint_index] = f"{checkpoint_line}{injected}"
        orchestrator.write_text("".join(lines), encoding="utf-8", newline="")

    def test_clean_copy_stamps_short_commit_without_changing_source(self) -> None:
        oid = self.initialize_git()
        assert oid is not None
        source_before = (self.skill / "SKILL.md").read_bytes()

        codex_result = self.run_installer("--agent", "codex")
        installed_by_codex = (self.active_skill / "SKILL.md").read_bytes()

        self.assertIn(
            f"Install source: Git commit {oid[:12]}.".encode(),
            installed_by_codex,
        )
        self.assertNotIn(oid.encode(), installed_by_codex)
        self.assertEqual(source_before, (self.skill / "SKILL.md").read_bytes())
        self.assertIn(f"Git commit {oid[:12]}", codex_result.stdout)
        self.assertNotIn(oid, codex_result.stdout)

        self.run_installer("--agent", "github-copilot", "--force")
        installed_by_copilot = (self.active_skill / "SKILL.md").read_bytes()
        self.assertEqual(installed_by_codex, installed_by_copilot)
        self.assertEqual(1, len(list(self.backup_root.glob("demo-skill.backup.*"))))
        self.assertEqual([], list((self.repository / ".agents" / "skills").glob("*.backup.*")))

    def test_dirty_marker_includes_tracked_local_changes(self) -> None:
        oid = self.initialize_git()
        assert oid is not None
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nLocal fixture change.\n")

        self.run_installer()

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install context: Git HEAD {oid[:12]};", installed)
        self.assertIn("copied Skill differs from the committed tree.", installed)

    def test_ignored_copied_file_marks_install_as_dirty(self) -> None:
        (self.repository / ".gitignore").write_text("*.cache\n", encoding="utf-8")
        oid = self.initialize_git()
        assert oid is not None
        (self.skill / "generated.cache").write_text("ignored but copied\n", encoding="utf-8")

        self.run_installer()

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install context: Git HEAD {oid[:12]};", installed)
        self.assertTrue((self.active_skill / "generated.cache").is_file())

    def test_export_ignored_tracked_deletion_is_stamped_dirty(self) -> None:
        (self.skill / ".gitattributes").write_text(
            "asset.txt export-ignore\n",
            encoding="utf-8",
        )
        oid = self.initialize_git()
        assert oid is not None
        (self.skill / "asset.txt").unlink()

        result = self.run_installer(check=False)

        self.assertEqual(0, result.returncode, result.stderr)
        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install context: Git HEAD {oid[:12]};", installed)
        self.assertFalse((self.active_skill / "asset.txt").exists())

    def test_export_substitution_cannot_make_changed_asset_look_clean(self) -> None:
        (self.skill / ".gitattributes").write_text(
            "asset.txt export-subst\n",
            encoding="utf-8",
        )
        (self.skill / "asset.txt").write_text(
            "$Format:%H$\n",
            encoding="utf-8",
        )
        oid = self.initialize_git()
        assert oid is not None
        (self.skill / "asset.txt").write_text(f"{oid}\n", encoding="utf-8")

        result = self.run_installer(check=False)

        self.assertEqual(0, result.returncode, result.stderr)
        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install context: Git HEAD {oid[:12]};", installed)
        self.assertEqual(
            f"{oid}\n",
            (self.active_skill / "asset.txt").read_text(encoding="utf-8"),
        )

    def test_index_flags_cannot_hide_changes_from_dirty_marker(self) -> None:
        oid = self.initialize_git()
        assert oid is not None

        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                self.run_command(
                    "git",
                    "update-index",
                    flag,
                    "skills/demo-skill/asset.txt",
                )
                (self.skill / "asset.txt").write_text(
                    f"change hidden by {flag}\n",
                    encoding="utf-8",
                )

                arguments = (
                    ("--force", "--agent", "codex")
                    if self.active_skill.exists()
                    else ("--agent", "codex")
                )
                self.run_installer(*arguments)

                installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(f"Install context: Git HEAD {oid[:12]};", installed)
                self.run_command(
                    "git",
                    "update-index",
                    "--no-assume-unchanged" if flag == "--assume-unchanged" else "--no-skip-worktree",
                    "skills/demo-skill/asset.txt",
                )
                self.run_command("git", "restore", "skills/demo-skill/asset.txt")

    def test_changes_outside_skill_do_not_mark_copy_dirty(self) -> None:
        oid = self.initialize_git()
        assert oid is not None
        (self.repository / "README.md").write_text("changed elsewhere\n", encoding="utf-8")

        self.run_installer()

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install source: Git commit {oid[:12]}.", installed)
        self.assertNotIn("Install context:", installed)

    def test_force_migrates_legacy_backups_outside_skill_search_root(self) -> None:
        first_oid = self.initialize_git()
        assert first_oid is not None
        self.run_installer()

        legacy_name = "demo-skill.backup.20260831010101"
        legacy_backup = self.repository / ".agents" / "skills" / legacy_name
        shutil.copytree(self.active_skill, legacy_backup)
        self.backup_root.mkdir(parents=True)
        colliding_backup = self.backup_root / legacy_name
        shutil.copytree(self.active_skill, colliding_backup)

        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nCommitted update.\n")
        second_oid = self.commit_skill_change("update fixture")
        self.run_installer("--force")

        active_text = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install source: Git commit {second_oid[:12]}.", active_text)
        self.assertFalse(legacy_backup.exists())
        self.assertTrue(colliding_backup.is_dir())
        self.assertTrue((self.backup_root / f"{legacy_name}.1").is_dir())
        discovered = list((self.repository / ".agents" / "skills").glob("*/SKILL.md"))
        self.assertEqual([self.active_skill / "SKILL.md"], discovered)

    def test_without_force_leaves_active_and_legacy_backup_unchanged(self) -> None:
        self.initialize_git()
        self.run_installer()
        active_before = (self.active_skill / "SKILL.md").read_bytes()
        legacy_backup = (
            self.repository
            / ".agents"
            / "skills"
            / "demo-skill.backup.20260831020202"
        )
        shutil.copytree(self.active_skill, legacy_backup)

        result = self.run_installer(check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("Re-run with --force", result.stderr)
        self.assertEqual(active_before, (self.active_skill / "SKILL.md").read_bytes())
        self.assertTrue(legacy_backup.is_dir())
        self.assertFalse(self.backup_root.exists())

    def test_link_remains_live_and_is_not_revision_stamped(self) -> None:
        oid = self.initialize_git()
        assert oid is not None
        source_before = (self.skill / "SKILL.md").read_bytes()

        result = self.run_installer("--link")

        self.assertTrue(self.active_skill.is_symlink())
        self.assertEqual(source_before, (self.active_skill / "SKILL.md").read_bytes())
        self.assertNotIn(b"Install source:", (self.active_skill / "SKILL.md").read_bytes())
        self.assertIn("not revision-stamped", result.stdout)
        self.assertIn(oid[:12], result.stdout)
        self.assertNotIn(oid, result.stdout)
        with (self.skill / "asset.txt").open("a", encoding="utf-8") as handle:
            handle.write("live change\n")
        self.assertIn(
            "live change",
            (self.active_skill / "asset.txt").read_text(encoding="utf-8"),
        )

    def test_force_replaces_a_live_link_without_changing_source(self) -> None:
        oid = self.initialize_git()
        assert oid is not None
        source_before = (self.skill / "SKILL.md").read_bytes()
        self.run_installer("--link")

        self.run_installer("--force")

        self.assertFalse(self.active_skill.is_symlink())
        installed = (self.active_skill / "SKILL.md").read_bytes()
        self.assertIn(f"Install source: Git commit {oid[:12]}.".encode(), installed)
        self.assertEqual(source_before, (self.skill / "SKILL.md").read_bytes())
        backups = list(self.backup_root.glob("demo-skill.backup.*"))
        self.assertEqual(1, len(backups))
        self.assertTrue(backups[0].is_symlink())
        self.assertEqual(self.skill, backups[0].resolve())

    def test_force_replaces_and_backs_up_a_broken_link(self) -> None:
        self.initialize_git()
        self.active_skill.parent.mkdir(parents=True)
        self.active_skill.symlink_to(self.repository / "missing-skill")

        self.run_installer("--link", "--force")

        self.assertTrue(self.active_skill.is_symlink())
        self.assertEqual(self.skill, self.active_skill.resolve())
        backups = list(self.backup_root.glob("demo-skill.backup.*"))
        self.assertEqual(1, len(backups))
        self.assertTrue(backups[0].is_symlink())
        self.assertFalse(backups[0].exists())

    def test_source_alias_layout_is_rejected_before_force_moves_source(self) -> None:
        self.initialize_git()
        agents_root = self.repository / ".agents"
        agents_root.mkdir()
        (agents_root / "skills").symlink_to("../skills")
        source_before = (self.skill / "SKILL.md").read_bytes()

        result = self.run_installer("--force", check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(source_before, (self.skill / "SKILL.md").read_bytes())
        self.assertFalse(self.backup_root.exists())

    def test_target_root_swap_after_locked_validation_cannot_touch_source(self) -> None:
        source_skill_before = (self.skill / "SKILL.md").read_bytes()
        source_asset_before = (self.skill / "asset.txt").read_bytes()
        agents_root = self.repository / ".agents"
        target_root = agents_root / "skills"
        checkpoint_reached = Path(self.temporary_directory.name) / "layout-race-reached"
        self.instrument_orchestrator_checkpoint(
            "# Test checkpoint: layout validated under lock.",
            [
                '_test_os = __import__("os")',
                '_test_pathlib = __import__("pathlib")',
                "_test_target = _test_pathlib.Path("
                '_test_os.environ["INSTALL_TEST_RACE_TARGET_ROOT"])',
                "if _test_os.path.lexists(_test_target): _test_target.rmdir()",
                "_test_target.symlink_to('../skills', target_is_directory=True)",
                "_test_pathlib.Path("
                '_test_os.environ["INSTALL_TEST_RACE_REACHED"]).touch()',
            ],
        )
        environment = {
            "INSTALL_TEST_RACE_REACHED": str(checkpoint_reached),
            "INSTALL_TEST_RACE_TARGET_ROOT": str(target_root),
        }

        result = self.run_installer("--force", check=False, environment=environment)

        self.assertTrue(checkpoint_reached.is_file(), result.stderr)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(self.skill.is_dir())
        self.assertFalse(self.skill.is_symlink())
        self.assertEqual(source_skill_before, (self.skill / "SKILL.md").read_bytes())
        self.assertEqual(source_asset_before, (self.skill / "asset.txt").read_bytes())
        self.assertEqual([], list(self.backup_root.glob("demo-skill.backup.*")))
        self.assertEqual([], list(agents_root.glob(".install-local.*")))
        lock_root = agents_root / ".install-locks"
        if lock_root.exists():
            self.assertEqual([], list(lock_root.iterdir()))

    def test_inherited_git_repository_environment_is_ignored(self) -> None:
        local_oid = self.initialize_git()
        assert local_oid is not None
        other_repository = Path(self.temporary_directory.name) / "other-repository"
        other_repository.mkdir()
        self.run_command("git", "init", "-q", cwd=other_repository)
        self.run_command(
            "git", "config", "user.name", "Other Repository", cwd=other_repository
        )
        self.run_command(
            "git",
            "config",
            "user.email",
            "other@example.invalid",
            cwd=other_repository,
        )
        (other_repository / "other.txt").write_text("other\n", encoding="utf-8")
        self.run_command("git", "add", ".", cwd=other_repository)
        self.run_command(
            "git",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "other fixture",
            cwd=other_repository,
        )
        other_oid = self.run_command(
            "git", "rev-parse", "HEAD", cwd=other_repository
        ).stdout.strip()

        self.run_installer(
            environment={
                "GIT_DIR": str(other_repository / ".git"),
                "GIT_WORK_TREE": str(other_repository),
                "GIT_INDEX_FILE": str(other_repository / ".git" / "index"),
            }
        )

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install source: Git commit {local_oid[:12]}.", installed)
        self.assertNotIn(other_oid[:12], installed)

    def test_replace_ref_cannot_make_different_snapshot_look_clean(self) -> None:
        original_oid = self.initialize_git()
        assert original_oid is not None
        (self.skill / "asset.txt").write_text(
            "replacement tree asset\n",
            encoding="utf-8",
        )
        replacement_oid = self.commit_skill_change("replacement tree")
        self.run_command("git", "checkout", "--detach", "-q", original_oid)
        (self.skill / "asset.txt").write_text(
            "replacement tree asset\n",
            encoding="utf-8",
        )
        self.run_command("git", "replace", original_oid, replacement_oid)

        result = self.run_installer(check=False)

        self.assertEqual(0, result.returncode, result.stderr)
        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            f"Install context: Git HEAD {original_oid[:12]};",
            installed,
        )
        self.assertEqual(
            "replacement tree asset\n",
            (self.active_skill / "asset.txt").read_text(encoding="utf-8"),
        )

    def test_invalid_description_does_not_replace_active_copy(self) -> None:
        self.initialize_git()
        self.run_installer()
        active_before = (self.active_skill / "SKILL.md").read_bytes()
        (self.skill / "SKILL.md").write_text(
            "---\nname: demo-skill\nlicense: MIT\n---\n\n# Invalid\n",
            encoding="utf-8",
        )

        result = self.run_installer("--force", check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("source description is missing or empty", result.stderr)
        self.assertEqual(active_before, (self.active_skill / "SKILL.md").read_bytes())
        self.assertFalse(self.backup_root.exists())
        self.assertEqual([], list((self.repository / ".agents").glob(".install-local.*")))

    def test_absolute_external_skill_symlink_does_not_replace_active_copy(self) -> None:
        self.initialize_git()
        self.run_installer()
        active_before = (self.active_skill / "SKILL.md").read_bytes()
        external_skill = Path(self.temporary_directory.name) / "external-SKILL.md"
        external_skill.write_text(
            SKILL_TEXT.replace(
                "Explain when this demo Skill should be used.",
                "External instructions must not be installed.",
            ),
            encoding="utf-8",
        )
        external_before = external_skill.read_bytes()
        source_skill = self.skill / "SKILL.md"
        source_skill.unlink()
        source_skill.symlink_to(external_skill.resolve())
        self.commit_skill_change("track external SKILL symlink")

        result = self.run_installer("--force", check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(active_before, (self.active_skill / "SKILL.md").read_bytes())
        self.assertTrue(source_skill.is_symlink())
        self.assertEqual(external_skill.resolve(), source_skill.resolve())
        self.assertEqual(external_before, external_skill.read_bytes())
        self.assertEqual([], list(self.backup_root.glob("demo-skill.backup.*")))
        self.assertEqual([], list((self.repository / ".agents").glob(".install-local.*")))

    def test_empty_block_description_does_not_replace_active_copy(self) -> None:
        self.initialize_git()
        self.run_installer()
        active_before = (self.active_skill / "SKILL.md").read_bytes()
        (self.skill / "SKILL.md").write_text(
            "---\n"
            "name: demo-skill\n"
            "description: >-\n"
            "license: MIT\n"
            "---\n\n"
            "# Empty description\n",
            encoding="utf-8",
        )

        result = self.run_installer("--force", check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertRegex(result.stderr, r"(?i)description.*empty|empty.*description")
        self.assertEqual(active_before, (self.active_skill / "SKILL.md").read_bytes())
        self.assertFalse(self.backup_root.exists())
        self.assertEqual([], list((self.repository / ".agents").glob(".install-local.*")))

    def test_source_change_after_revision_capture_is_stamped_dirty(self) -> None:
        oid = self.initialize_git()
        assert oid is not None
        self.run_installer()
        active_before = (self.active_skill / "SKILL.md").read_bytes()
        self.instrument_orchestrator_checkpoint(
            "# Test checkpoint: layout validated under lock.",
            [
                '_test_os = __import__("os")',
                '_test_pathlib = __import__("pathlib")',
                "_test_pathlib.Path("
                '_test_os.environ["INSTALL_TEST_SOURCE_ASSET"]).write_text('
                '"changed after revision inspection\\n", encoding="utf-8")',
            ],
        )
        environment = {
            "INSTALL_TEST_SOURCE_ASSET": str(self.skill / "asset.txt"),
        }

        result = self.run_installer("--force", check=False, environment=environment)

        self.assertEqual(0, result.returncode, result.stderr)
        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install context: Git HEAD {oid[:12]};", installed)
        self.assertIn("copied Skill differs from the committed tree.", installed)
        self.assertEqual(
            "changed after revision inspection\n",
            (self.active_skill / "asset.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            "changed after revision inspection\n",
            (self.skill / "asset.txt").read_text(encoding="utf-8"),
        )
        backups = list(self.backup_root.glob("demo-skill.backup.*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(active_before, (backups[0] / "SKILL.md").read_bytes())
        self.assertEqual([], list((self.repository / ".agents").glob(".install-local.*")))
        self.assertEqual(
            [],
            list((self.repository / ".agents" / ".install-locks").iterdir()),
        )

    def test_signal_after_backup_restores_active_installation(self) -> None:
        self.initialize_git()
        self.run_installer()
        active_before = (self.active_skill / "SKILL.md").read_bytes()
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write("\nNew committed source.\n")
        self.commit_skill_change("new source for interrupted install")
        self.instrument_orchestrator_checkpoint(
            "# Test checkpoint: active Skill backed up.",
            [
                '_test_os = __import__("os")',
                '_test_signal = __import__("signal")',
                "_test_os.kill(_test_os.getpid(), _test_signal.SIGTERM)",
            ],
        )

        result = self.run_installer("--force", check=False)

        self.assertNotEqual(0, result.returncode)
        self.assertEqual(active_before, (self.active_skill / "SKILL.md").read_bytes())
        self.assertEqual([], list(self.backup_root.glob("demo-skill.backup.*")))
        self.assertEqual([], list((self.repository / ".agents").glob(".install-local.*")))

    def test_signal_rollback_after_target_root_swap_cannot_touch_source(self) -> None:
        self.initialize_git()
        self.run_installer()
        unique_source_line = "UNIQUE CURRENT SOURCE MUST SURVIVE ROLLBACK"
        with (self.skill / "SKILL.md").open("a", encoding="utf-8") as handle:
            handle.write(f"\n{unique_source_line}\n")
        source_before = (self.skill / "SKILL.md").read_bytes()
        agents_root = self.repository / ".agents"
        target_root = agents_root / "skills"
        hidden_root = agents_root / "skills-hidden"
        checkpoint_reached = Path(self.temporary_directory.name) / "signal-race-reached"
        self.instrument_orchestrator_checkpoint(
            "# Test checkpoint: staged Skill activated.",
            [
                '_test_os = __import__("os")',
                '_test_pathlib = __import__("pathlib")',
                '_test_signal = __import__("signal")',
                "_test_target = _test_pathlib.Path("
                '_test_os.environ["INSTALL_TEST_RACE_TARGET_ROOT"])',
                "_test_hidden = _test_pathlib.Path("
                '_test_os.environ["INSTALL_TEST_RACE_HIDDEN_ROOT"])',
                "_test_target.rename(_test_hidden)",
                "_test_target.symlink_to('../skills', target_is_directory=True)",
                "_test_pathlib.Path("
                '_test_os.environ["INSTALL_TEST_RACE_REACHED"]).touch()',
                "_test_os.kill(_test_os.getpid(), _test_signal.SIGTERM)",
            ],
        )
        environment = {
            "INSTALL_TEST_RACE_HIDDEN_ROOT": str(hidden_root),
            "INSTALL_TEST_RACE_REACHED": str(checkpoint_reached),
            "INSTALL_TEST_RACE_TARGET_ROOT": str(target_root),
        }

        result = self.run_installer("--force", check=False, environment=environment)

        self.assertTrue(checkpoint_reached.is_file(), result.stderr)
        self.assertNotEqual(0, result.returncode)
        self.assertTrue(hidden_root.is_dir())
        self.assertTrue(self.skill.is_dir())
        self.assertFalse(self.skill.is_symlink())
        self.assertEqual(source_before, (self.skill / "SKILL.md").read_bytes())
        self.assertIn(
            unique_source_line,
            (self.skill / "SKILL.md").read_text(encoding="utf-8"),
        )
        self.assertEqual([], list(agents_root.glob(".install-local.*")))
        lock_root = agents_root / ".install-locks"
        if lock_root.exists():
            self.assertEqual([], list(lock_root.iterdir()))

    def test_parallel_installs_serialize_writers_without_nested_backups(self) -> None:
        (self.skill / "large.bin").write_bytes(b"x" * (8 * 1024 * 1024))
        oid = self.initialize_git()
        assert oid is not None
        command = [
            "bash",
            str(self.installer),
            "demo-skill",
            "--scope",
            "project",
            "--force",
        ]
        processes: list[subprocess.Popen[str]] = []
        results: list[tuple[int, str, str]] = []
        try:
            for _ in range(30):
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=self.repository,
                        env=os.environ.copy(),
                        text=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                )
            for process in processes:
                stdout, stderr = process.communicate(timeout=30)
                results.append((process.returncode, stdout, stderr))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

        successes = [result for result in results if result[0] == 0]
        failures = [result for result in results if result[0] != 0]
        diagnostics = [(code, stderr.strip()) for code, _, stderr in results]
        self.assertGreaterEqual(len(successes), 1, diagnostics)
        self.assertEqual(30, len(successes) + len(failures), diagnostics)
        for _, _, stderr in failures:
            self.assertRegex(stderr, r"(?i)busy|in progress|another install")

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(f"Install source: Git commit {oid[:12]}.", installed)
        self.assertTrue((self.active_skill / "large.bin").is_file())
        self.assertFalse((self.active_skill / "demo-skill").exists())
        discovered = list((self.repository / ".agents" / "skills").glob("*/SKILL.md"))
        self.assertEqual([self.active_skill / "SKILL.md"], discovered)
        agents_root = self.repository / ".agents"
        backups = list((agents_root / "backups").glob("demo-skill.backup.*"))
        self.assertEqual(len(successes) - 1, len(backups), diagnostics)
        for backup in backups:
            self.assertTrue((backup / "SKILL.md").is_file())
        self.assertTrue(
            {path.name for path in agents_root.iterdir()}
            <= {".install-locks", "backups", "skills"}
        )
        self.assertEqual([], list((agents_root / ".install-locks").iterdir()))
        self.assertEqual([], list(agents_root.glob(".install-local.*")))

    def test_unborn_repository_uses_explicit_no_commit_marker(self) -> None:
        self.initialize_git(commit=False)

        self.run_installer()

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "Install source: unborn Git worktree; copied content has no commit ID.",
            installed,
        )

    def test_non_git_directory_uses_explicit_no_commit_marker(self) -> None:
        self.run_installer()

        installed = (self.active_skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "Install source: non-Git directory; no commit ID is available.",
            installed,
        )

    def test_invalid_skill_name_cannot_escape_install_roots(self) -> None:
        result = self.run_command(
            "bash",
            str(self.installer),
            "../demo-skill",
            "--scope",
            "project",
            check=False,
        )

        self.assertEqual(2, result.returncode)
        self.assertIn("Invalid Skill name", result.stderr)
        self.assertFalse((self.repository / ".agents").exists())


class StampInstalledSkillTestCase(unittest.TestCase):
    def test_inline_quoted_description_is_preserved_and_stamped(self) -> None:
        annotation = annotation_for("clean", "a" * 40)
        source = '---\nname: demo\ndescription: "Use this demo."\n---\n\n# Demo\n'

        stamped = stamp_text(source, annotation)

        self.assertIn(f'description: "Use this demo. {annotation}"', stamped)
        self.assertEqual(1, stamped.count(annotation))

    def test_invalid_oid_is_rejected(self) -> None:
        with self.assertRaises(StampError):
            annotation_for("clean", "not-a-commit")

    def test_extended_short_oid_is_preserved(self) -> None:
        oid = "f" * 64

        annotation = annotation_for("dirty", oid, short_oid=oid)

        self.assertEqual(137, len(annotation))
        self.assertIn(oid, annotation)

    def test_empty_quoted_description_is_rejected_without_replacement(self) -> None:
        annotation = annotation_for("clean", "d" * 40)
        source_text = (
            "---\n"
            "name: demo\n"
            'description: ""\n'
            "---\n\n"
            "# Demo\n"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.md"
            destination = root / "destination.md"
            source.write_text(source_text, encoding="utf-8")
            destination.write_text(source_text, encoding="utf-8")
            destination_before = destination.read_bytes()

            with self.assertRaises(StampError):
                stamp_file(source, destination, annotation)

            self.assertEqual(destination_before, destination.read_bytes())

    def test_tab_before_inline_comment_is_rejected_without_replacement(self) -> None:
        annotation = annotation_for("clean", "e" * 40)
        source_text = (
            "---\n"
            "name: demo\n"
            "description: Use this demo.\t# comment\n"
            "---\n\n"
            "# Demo\n"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.md"
            destination = root / "destination.md"
            source.write_text(source_text, encoding="utf-8")
            destination.write_text(source_text, encoding="utf-8")
            destination_before = destination.read_bytes()

            with self.assertRaises(StampError):
                stamp_file(source, destination, annotation)

            self.assertEqual(destination_before, destination.read_bytes())

    def test_description_limit_failure_does_not_replace_destination(self) -> None:
        annotation = annotation_for("dirty", "b" * 64)
        long_description = "x" * 980
        source_text = (
            "---\n"
            "name: demo\n"
            "description: >-\n"
            f"  {long_description}\n"
            "---\n\n"
            "# Demo\n"
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.md"
            destination = root / "destination.md"
            source.write_text(source_text, encoding="utf-8")
            destination.write_text(source_text, encoding="utf-8")
            destination_before = destination.read_bytes()

            with self.assertRaises(StampError):
                stamp_file(source, destination, annotation)

            self.assertEqual(destination_before, destination.read_bytes())

    def test_repository_descriptions_have_room_for_longest_marker(self) -> None:
        oid = "c" * 64
        annotation = annotation_for("dirty", oid, short_oid=oid)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for source in sorted((REPOSITORY_ROOT / "skills").glob("*/SKILL.md")):
                with self.subTest(skill=source.parent.name):
                    destination = root / f"{source.parent.name}.md"
                    shutil.copy2(source, destination)
                    stamp_file(source, destination, annotation)
                    self.assertEqual(
                        1,
                        destination.read_text(encoding="utf-8").count(annotation),
                    )


if __name__ == "__main__":
    unittest.main()
