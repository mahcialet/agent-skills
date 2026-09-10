"""Public source checks work without importing the POSIX transaction backend."""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import install_local_cli as cli  # noqa: E402


class InstallerSourceChecks(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repository = Path(self.temporary.name)
        (self.repository / ".git").mkdir()

    def result(self, text: str = "", code: int = 0):
        return subprocess.CompletedProcess([], code, text, "")

    def test_git_environment_is_sanitized_without_mutating_parent(self) -> None:
        polluted = {
            "GIT_DIR": "/other", "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.worktree", "GIT_CONFIG_VALUE_0": "/other",
            "GIT_NO_REPLACE_OBJECTS": "0", "UNCHANGED_FIXTURE": "preserved",
        }
        with mock.patch.dict(os.environ, polluted):
            environment = cli.source_git_environment()
            self.assertEqual("/other", os.environ["GIT_DIR"])
        self.assertEqual("preserved", environment["UNCHANGED_FIXTURE"])
        self.assertEqual("1", environment["GIT_NO_REPLACE_OBJECTS"])
        self.assertEqual(
            {"GIT_NO_REPLACE_OBJECTS", "GIT_OPTIONAL_LOCKS"},
            {key for key in environment if key.upper().startswith("GIT_")},
        )

    def test_git_unavailable_is_distinct_from_non_git(self) -> None:
        with mock.patch.object(cli.shutil, "which", return_value=None):
            self.assertEqual(("git-unavailable", None), cli.inspect_source(self.repository))
        (self.repository / ".git").rmdir()
        with mock.patch.object(cli.shutil, "which", return_value="git"):
            self.assertEqual(("non-git", None), cli.inspect_source(self.repository))

    def test_root_mismatch_bad_oid_and_unreadable_head_are_refused(self) -> None:
        for responses, expected in (
            ([self.result(str(self.repository / "other"))], "Unexpected Git repository root"),
            ([self.result(str(self.repository)), self.result("not-an-oid")], "unsupported commit ID"),
            ([self.result(str(self.repository)), self.result(code=1), self.result(code=1)], "not a readable commit"),
            ([self.result(code=1)], "Unable to inspect Git metadata"),
        ):
            with self.subTest(expected=expected), mock.patch.object(
                cli.shutil, "which", return_value="git"
            ), mock.patch.object(cli.subprocess, "run", side_effect=responses):
                with self.assertRaisesRegex(cli.SourceError, expected):
                    cli.inspect_source(self.repository)

    def test_head_and_unborn_states_use_sanitized_argv(self) -> None:
        for state, responses in (
            (("head", "a" * 40), [self.result(str(self.repository)), self.result("a" * 40)]),
            (("unborn", None), [self.result(str(self.repository)), self.result(code=1), self.result()]),
        ):
            with self.subTest(state=state), mock.patch.object(
                cli.shutil, "which", return_value="/fixture/git"
            ), mock.patch.object(cli.subprocess, "run", side_effect=responses) as run:
                self.assertEqual(state, cli.inspect_source(self.repository))
                for call in run.call_args_list:
                    self.assertEqual(["/fixture/git", "-C", str(self.repository)], call.args[0][:3])
                    self.assertNotIn("shell", call.kwargs)
                    self.assertEqual("1", call.kwargs["env"]["GIT_NO_REPLACE_OBJECTS"])

    def test_unsupported_platform_blocks_before_git_or_transaction(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        skill = next((repository / "skills").glob("*/SKILL.md")).parent.name
        stderr = io.StringIO()
        # Replace only the os view in the entry module: pathlib must still use
        # the native filesystem class on this test machine.
        platform = SimpleNamespace(name="nt", execv=mock.Mock())
        with mock.patch.object(cli, "os", platform), mock.patch.object(
            cli, "inspect_source"
        ) as inspect, contextlib.redirect_stderr(stderr):
            self.assertEqual(3, cli.main([skill]))
        self.assertIn("ASKILLS-INSTALL-PLATFORM", stderr.getvalue())
        inspect.assert_not_called()
        platform.execv.assert_not_called()


if __name__ == "__main__":
    unittest.main()
