"""Unix-only shell compatibility, separate from mandatory Python core tests."""

from __future__ import annotations

import os
import shutil
import sys
import unittest

import test_install_local as core


@unittest.skipUnless(os.name == "posix", "Unix compatibility wrapper only")
class InstallerWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        # Bash absence on Unix is a failed precondition, never a silent skip.
        self.assertIsNotNone(shutil.which("bash"), "Unix wrapper suite requires Bash")
        self.fixture = core.LocalInstallerTestCase()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def wrapper(self, *arguments: str):
        return self.fixture.run_command(
            "bash", str(self.fixture.scripts / "install-local.sh"),
            *arguments, check=False,
        )

    def test_argument_exit_codes_match_python_entry(self) -> None:
        for arguments in (
            (), ("../demo-skill",), ("demo-skill", "--scope"),
            ("demo-skill", "--scope", "bad"),
            ("demo-skill", "--agent", "bad"),
            ("demo-skill", "--unknown"), ("demo-skill", "--s", "user"),
            ("missing-skill",), ("--help",),
        ):
            with self.subTest(arguments=arguments):
                python = self.fixture.run_command(
                    sys.executable, str(self.fixture.installer), *arguments, check=False
                )
                shell = self.wrapper(*arguments)
                self.assertEqual(python.returncode, shell.returncode)
                self.assertEqual(python.stderr, shell.stderr)
                self.assertEqual(python.stdout, shell.stdout)
                self.assertFalse((self.fixture.repository / ".agents").exists())

    def test_copy_collision_force_and_backup_use_shared_contract(self) -> None:
        oid = self.fixture.initialize_git()
        self.assertEqual(0, self.wrapper("demo-skill").returncode)
        before = (self.fixture.active_skill / "SKILL.md").read_bytes()
        self.assertIn(f"Git commit {oid[:12]}".encode(), before)
        self.assertEqual(1, self.wrapper("demo-skill").returncode)
        self.assertEqual(before, (self.fixture.active_skill / "SKILL.md").read_bytes())
        result = self.wrapper("demo-skill", "--force", "--agent", "github-copilot")
        self.assertEqual(0, result.returncode, result.stderr)
        backups = list(self.fixture.backup_root.glob("demo-skill.backup.*"))
        self.assertEqual(1, len(backups))
        self.assertEqual(before, (backups[0] / "SKILL.md").read_bytes())

    def test_corrupt_git_source_rejection_matches_python(self) -> None:
        (self.fixture.repository / ".git").write_text("invalid\n", encoding="utf-8")
        python = self.fixture.run_installer(check=False)
        shell = self.wrapper("demo-skill", "--scope", "project")
        self.assertEqual(1, shell.returncode)
        self.assertEqual(python.stderr, shell.stderr)
        self.assertFalse((self.fixture.repository / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
