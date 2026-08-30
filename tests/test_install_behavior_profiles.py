from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPOSITORY_ROOT / "scripts"
INSTALLER_PATH = SCRIPTS_DIR / "install_behavior_profiles.py"
sys.path.insert(0, str(SCRIPTS_DIR))

import install_behavior_profiles as installer  # noqa: E402


class BehaviorProfileInstallerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)

    def run_installer(
        self, *arguments: str, check: bool = False
    ) -> subprocess.CompletedProcess[bytes]:
        result = subprocess.run(
            [sys.executable, str(INSTALLER_PATH), *arguments],
            cwd=REPOSITORY_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if check and result.returncode != 0:
            self.fail(result.stderr.decode("utf-8", errors="replace"))
        return result

    def target(self, parent: Path | None = None) -> Path:
        return (parent or self.root) / "AGENTS.md"

    def apply(self, target: Path, *profiles: str) -> subprocess.CompletedProcess[bytes]:
        arguments: list[str] = []
        for profile in profiles or ("scope-control",):
            arguments.extend(["--profile", profile])
        arguments.extend(["--target", str(target), "--apply"])
        return self.run_installer(*arguments)

    def uninstall(
        self, target: Path, *, apply: bool = True
    ) -> subprocess.CompletedProcess[bytes]:
        arguments = ["--uninstall", "--target", str(target)]
        if apply:
            arguments.append("--apply")
        return self.run_installer(*arguments)

    def test_installer_uses_validator_semantics_for_quoted_frontmatter(self) -> None:
        behavior_root = self.root / "behavior-profiles"
        profile_root = behavior_root / "scope-control"
        profile_root.mkdir(parents=True)
        canonical = profile_root / "BEHAVIOR_PROFILE.md"
        canonical.write_text(
            "\n".join(
                [
                    "---",
                    'name: "scope-control"',
                    "version: '0.1.0'",
                    'description: "quoted scalar"',
                    "status: 'experimental'",
                    'license: "MIT"',
                    "---",
                    "",
                    "## Body",
                    "",
                    "Profile body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (behavior_root / "catalog.json").write_text(
            json.dumps(
                {
                    "profiles": [
                        {
                            "name": "scope-control",
                            "version": "0.1.0",
                            "path": "scope-control/BEHAVIOR_PROFILE.md",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        selected = installer.select_profiles(["scope-control"], behavior_root)

        self.assertEqual("scope-control", selected[0].name)
        self.assertEqual("0.1.0", selected[0].version)
        self.assertIn("## Body", selected[0].body)

        canonical.write_text(
            canonical.read_text(encoding="utf-8")
            + f"\n{installer.OWNERSHIP_MARKER_PREFIX_TEXT}none -->\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(installer.InstallerError, "managed marker"):
            installer.select_profiles(["scope-control"], behavior_root)

    def test_stdout_render_has_no_write_and_omits_frontmatter(self) -> None:
        result = self.run_installer("--profile", "scope-control", check=True)

        self.assertEqual(b"", result.stderr)
        self.assertTrue(result.stdout.startswith(installer.BEGIN_MARKER + b"\n"))
        self.assertTrue(result.stdout.endswith(installer.END_MARKER + b"\n"))
        self.assertIn(b"Profile name: `scope-control`", result.stdout)
        self.assertIn(b"Profile version: `0.1.0`", result.stdout)
        self.assertNotIn(b"\nname: scope-control\n", result.stdout)
        self.assertNotIn(b"\ndescription:", result.stdout)
        self.assertNotIn(b"\nstatus: experimental\n", result.stdout)
        self.assertNotIn(b"\nlicense: MIT\n", result.stdout)
        self.assertEqual([], list(self.root.iterdir()))

    def test_same_profile_order_renders_identical_bytes(self) -> None:
        first = installer.render_profiles(
            ["scope-control", "independent-adversarial-verification"]
        )
        second = installer.render_profiles(
            ["scope-control", "independent-adversarial-verification"]
        )

        self.assertEqual(first, second)

    def test_target_without_apply_prints_diff_and_does_not_write(self) -> None:
        target = self.target()
        original = b"# Existing instructions\n"
        target.write_bytes(original)

        result = self.run_installer(
            "--profile",
            "scope-control",
            "--target",
            str(target),
            check=True,
        )

        self.assertEqual(original, target.read_bytes())
        self.assertIn(b"--- a/AGENTS.md", result.stdout)
        self.assertIn(b"+++ b/AGENTS.md", result.stdout)
        self.assertIn(installer.BEGIN_MARKER, result.stdout)

    def test_dry_run_represents_missing_final_newline_without_joining_lines(
        self,
    ) -> None:
        target = self.target()
        original = b"# Existing"
        target.write_bytes(original)

        result = self.run_installer(
            "--profile",
            "scope-control",
            "--target",
            str(target),
            check=True,
        )

        self.assertEqual(original, target.read_bytes())
        self.assertNotIn(b"-# Existing+# Existing", result.stdout)
        self.assertIn(
            b"-# Existing\n\\ No newline at end of file\n+# Existing\n",
            result.stdout,
        )

    def test_target_without_apply_does_not_create_missing_target(self) -> None:
        target = self.target()

        result = self.run_installer(
            "--profile",
            "scope-control",
            "--target",
            str(target),
            check=True,
        )

        self.assertFalse(target.exists())
        self.assertIn(installer.BEGIN_MARKER, result.stdout)

    def test_apply_creates_new_target_atomically(self) -> None:
        target = self.target()

        result = self.apply(target, "scope-control")

        self.assertEqual(0, result.returncode, result.stderr)
        content = target.read_bytes()
        self.assertEqual(1, content.count(installer.BEGIN_MARKER))
        self.assertEqual(1, content.count(installer.END_MARKER))
        self.assertIn(b"Profile name: `scope-control`", content)
        self.assertEqual([], list(self.root.glob(f"{installer.TEMP_PREFIX}*")))

    def test_apply_replaces_existing_block_and_preserves_outside_bytes(self) -> None:
        target = self.target()
        old_block = installer.render_profiles(["scope-control"])
        prefix = b"\xffprefix bytes\r\n\r\n"
        suffix = b"\r\n\x80suffix bytes"
        target.write_bytes(prefix + old_block + suffix)

        result = self.apply(
            target,
            "independent-adversarial-verification",
            "scope-control",
        )

        self.assertEqual(0, result.returncode, result.stderr)
        updated = target.read_bytes()
        self.assertTrue(updated.startswith(prefix))
        self.assertTrue(updated.endswith(suffix))
        self.assertEqual(1, updated.count(installer.BEGIN_MARKER))
        self.assertLess(
            updated.index(
                b"Profile name: `independent-adversarial-verification`"
            ),
            updated.index(b"Profile name: `scope-control`"),
        )

    def test_append_keeps_existing_bytes_as_exact_prefix(self) -> None:
        target = self.target()
        original = b"existing without final newline\xff"
        target.write_bytes(original)

        result = self.apply(target, "scope-control")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(target.read_bytes().startswith(original))

    def test_install_then_uninstall_restores_exact_line_endings(self) -> None:
        cases = {
            "empty": (b"", b""),
            "no-final-lf": (b"# Existing", b"\n\n"),
            "one-lf": (b"# Existing\n", b"\n"),
            "two-lf": (b"# Existing\n\n", b""),
            "one-crlf": (b"# Existing\r\n", b"\r\n"),
            "two-crlf": (b"# Existing\r\n\r\n", b""),
        }
        for name, (original, owned_separator) in cases.items():
            with self.subTest(name=name):
                case_root = self.root / f"round-trip-{name}"
                case_root.mkdir()
                target = self.target(case_root)
                target.write_bytes(original)

                installed = self.apply(target, "scope-control")
                self.assertEqual(0, installed.returncode, installed.stderr)
                installed_bytes = target.read_bytes()
                self.assertIn(installer.OWNERSHIP_MARKER_PREFIX, installed_bytes)
                self.assertTrue(
                    installed_bytes.startswith(
                        original + owned_separator + installer.BEGIN_MARKER
                    )
                )

                preview = self.uninstall(target, apply=False)
                self.assertEqual(0, preview.returncode, preview.stderr)
                self.assertEqual(installed_bytes, target.read_bytes())
                self.assertIn(installer.BEGIN_MARKER, preview.stdout)
                if name == "no-final-lf":
                    self.assertIn(
                        b"+# Existing\n\\ No newline at end of file\n",
                        preview.stdout,
                    )

                removed = self.uninstall(target)
                self.assertEqual(0, removed.returncode, removed.stderr)
                self.assertEqual(original, target.read_bytes())
                before_noop = target.stat()

                second = self.uninstall(target)

                self.assertEqual(0, second.returncode, second.stderr)
                self.assertEqual(b"", second.stdout)
                self.assertEqual(original, target.read_bytes())
                self.assertEqual(before_noop.st_ino, target.stat().st_ino)
                self.assertEqual(before_noop.st_mtime_ns, target.stat().st_mtime_ns)

    def test_update_and_idempotency_preserve_uninstall_round_trip(self) -> None:
        cases = {
            "no-final-lf": b"# Existing",
            "crlf": b"# Existing\r\n",
        }
        for name, original in cases.items():
            with self.subTest(name=name):
                case_root = self.root / f"update-{name}"
                case_root.mkdir()
                target = self.target(case_root)
                target.write_bytes(original)

                first = self.apply(target, "scope-control")
                self.assertEqual(0, first.returncode, first.stderr)
                update = self.apply(
                    target,
                    "independent-adversarial-verification",
                    "scope-control",
                )
                self.assertEqual(0, update.returncode, update.stderr)
                before_noop = target.read_bytes()
                before_stat = target.stat()

                noop = self.apply(
                    target,
                    "independent-adversarial-verification",
                    "scope-control",
                )

                self.assertEqual(0, noop.returncode, noop.stderr)
                self.assertEqual(b"", noop.stdout)
                self.assertEqual(before_noop, target.read_bytes())
                self.assertEqual(before_stat.st_ino, target.stat().st_ino)
                self.assertEqual(before_stat.st_mtime_ns, target.stat().st_mtime_ns)
                removed = self.uninstall(target)
                self.assertEqual(0, removed.returncode, removed.stderr)
                self.assertEqual(original, target.read_bytes())

    def test_profile_order_is_cli_order(self) -> None:
        result = self.run_installer(
            "--profile",
            "independent-adversarial-verification",
            "--profile",
            "scope-control",
            check=True,
        )

        self.assertLess(
            result.stdout.index(
                b"Profile name: `independent-adversarial-verification`"
            ),
            result.stdout.index(b"Profile name: `scope-control`"),
        )

    def test_second_apply_is_noop(self) -> None:
        target = self.target()
        first = self.apply(target, "scope-control")
        self.assertEqual(0, first.returncode, first.stderr)
        before = target.read_bytes()
        before_stat = target.stat()

        second = self.apply(target, "scope-control")

        self.assertEqual(0, second.returncode, second.stderr)
        after_stat = target.stat()
        self.assertEqual(b"", second.stdout)
        self.assertEqual(before, target.read_bytes())
        self.assertEqual(before_stat.st_ino, after_stat.st_ino)
        self.assertEqual(before_stat.st_mtime_ns, after_stat.st_mtime_ns)

    def test_existing_mode_is_preserved(self) -> None:
        target = self.target()
        target.write_text("# Existing\n", encoding="utf-8")
        target.chmod(0o640)

        result = self.apply(target, "scope-control")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(0o640, target.stat().st_mode & 0o777)

    def test_concurrent_mode_hardening_fails_closed(self) -> None:
        target = self.target()
        original = b"# Existing\n"
        target.write_bytes(original)
        target.chmod(0o644)
        original_inode = target.stat().st_ino
        block = installer.render_profiles(["scope-control"])
        original_assert = installer._assert_snapshot_unchanged

        def harden_before_assert(snapshot: installer.TargetSnapshot) -> None:
            snapshot.path.chmod(0o600)
            original_assert(snapshot)

        with mock.patch.object(
            installer,
            "_assert_snapshot_unchanged",
            side_effect=harden_before_assert,
        ):
            with self.assertRaisesRegex(installer.InstallerError, "mode changed"):
                installer.install_target(target, block, apply=True)

        self.assertEqual(original, target.read_bytes())
        self.assertEqual(0o600, target.stat().st_mode & 0o777)
        self.assertEqual(original_inode, target.stat().st_ino)
        self.assertEqual([], list(self.root.glob(f"{installer.TEMP_PREFIX}*")))

    def test_duplicate_profile_is_rejected_without_write(self) -> None:
        target = self.target()
        result = self.run_installer(
            "--profile",
            "scope-control",
            "--profile",
            "scope-control",
            "--target",
            str(target),
            "--apply",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn(b"duplicate profile", result.stderr)
        self.assertFalse(target.exists())

    def test_unknown_profile_is_rejected_without_write(self) -> None:
        target = self.target()
        result = self.run_installer(
            "--profile",
            "not-a-profile",
            "--target",
            str(target),
            "--apply",
        )

        self.assertEqual(2, result.returncode)
        self.assertIn(b"unknown profile", result.stderr)
        self.assertFalse(target.exists())

    def test_profile_is_required(self) -> None:
        result = self.run_installer()

        self.assertEqual(2, result.returncode)
        self.assertIn(b"--profile", result.stderr)

    def test_apply_without_target_is_rejected(self) -> None:
        result = self.run_installer("--profile", "scope-control", "--apply")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"--apply requires --target", result.stderr)

    def test_uninstall_requires_target_and_disallows_profiles(self) -> None:
        missing_target = self.run_installer("--uninstall")
        combined = self.run_installer(
            "--uninstall",
            "--profile",
            "scope-control",
            "--target",
            str(self.target()),
            "--apply",
        )

        self.assertEqual(2, missing_target.returncode)
        self.assertIn(b"--uninstall requires --target", missing_target.stderr)
        self.assertEqual(2, combined.returncode)
        self.assertIn(b"cannot be combined", combined.stderr)
        self.assertFalse(self.target().exists())

    def test_marker_corruption_fails_closed(self) -> None:
        begin = installer.BEGIN_MARKER
        end = installer.END_MARKER
        corruptions = {
            "begin-only": b"prefix\n" + begin + b"\ncontent\n",
            "end-only": b"prefix\n" + end + b"\n",
            "reverse": end + b"\ncontent\n" + begin + b"\n",
            "multiple": (
                begin
                + b"\none\n"
                + end
                + b"\n"
                + begin
                + b"\ntwo\n"
                + end
                + b"\n"
            ),
            "nested": (
                begin
                + b"\n"
                + begin
                + b"\ncontent\n"
                + end
                + b"\n"
                + end
                + b"\n"
            ),
        }
        for name, original in corruptions.items():
            with self.subTest(name=name):
                case_root = self.root / name
                case_root.mkdir()
                target = self.target(case_root)
                target.write_bytes(original)

                result = self.apply(target, "scope-control")

                self.assertEqual(2, result.returncode)
                self.assertIn(b"marker corruption", result.stderr)
                self.assertEqual(original, target.read_bytes())

    def test_marker_must_be_an_exact_line(self) -> None:
        target = self.target()
        original = b"prefix " + installer.BEGIN_MARKER + b"\n" + installer.END_MARKER
        target.write_bytes(original)

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"markers must be exact lines", result.stderr)
        self.assertEqual(original, target.read_bytes())

    def test_malformed_separator_ownership_fails_closed(self) -> None:
        valid = installer.render_profiles(["scope-control"])
        marker_line = installer.OWNERSHIP_MARKER_PREFIX + b"none -->"
        corruptions = {
            "missing": valid.replace(marker_line + b"\n", b"", 1),
            "duplicate": valid.replace(
                marker_line + b"\n", (marker_line + b"\n") * 2, 1
            ),
            "unknown": valid.replace(marker_line, b"invalid ownership", 1),
            "separator-mismatch": valid.replace(
                marker_line,
                installer.OWNERSHIP_MARKER_PREFIX + b"lf -->",
                1,
            ),
        }
        for name, original in corruptions.items():
            with self.subTest(name=name):
                case_root = self.root / f"ownership-{name}"
                case_root.mkdir()
                target = self.target(case_root)
                target.write_bytes(original)

                update = self.apply(target, "scope-control")
                uninstall = self.uninstall(target)

                self.assertEqual(2, update.returncode)
                self.assertIn(b"ownership", update.stderr)
                self.assertEqual(2, uninstall.returncode)
                self.assertIn(b"ownership", uninstall.stderr)
                self.assertEqual(original, target.read_bytes())

    def test_missing_parent_is_rejected(self) -> None:
        target = self.root / "missing" / "AGENTS.md"

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"parent does not exist", result.stderr)
        self.assertFalse(target.exists())

    def test_non_directory_parent_is_rejected(self) -> None:
        parent = self.root / "not-a-directory"
        parent.write_text("regular file\n", encoding="utf-8")
        target = parent / "AGENTS.md"

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"parent path is not a directory", result.stderr)
        self.assertEqual("regular file\n", parent.read_text(encoding="utf-8"))

    def test_target_symlink_is_rejected(self) -> None:
        external = self.root / "external.md"
        external.write_text("external\n", encoding="utf-8")
        target = self.target()
        target.symlink_to(external)

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"must not be a symlink", result.stderr)
        self.assertEqual("external\n", external.read_text(encoding="utf-8"))

    def test_uninstall_target_symlink_is_rejected(self) -> None:
        external = self.root / "external.md"
        original = installer.render_profiles(["scope-control"])
        external.write_bytes(original)
        target = self.target()
        target.symlink_to(external)

        result = self.uninstall(target)

        self.assertEqual(2, result.returncode)
        self.assertIn(b"must not be a symlink", result.stderr)
        self.assertEqual(original, external.read_bytes())

    def test_parent_symlink_is_rejected(self) -> None:
        real_parent = self.root / "real"
        real_parent.mkdir()
        linked_parent = self.root / "linked"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        target = self.target(linked_parent)

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"parent path contains symlink", result.stderr)
        self.assertFalse((real_parent / "AGENTS.md").exists())

    def test_dangerous_basename_is_rejected(self) -> None:
        target = self.root / "README.md"

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"basename must be AGENTS.md", result.stderr)
        self.assertFalse(target.exists())

    def test_non_regular_target_is_rejected(self) -> None:
        target = self.target()
        target.mkdir()

        result = self.apply(target, "scope-control")

        self.assertEqual(2, result.returncode)
        self.assertIn(b"not a regular file", result.stderr)
        self.assertTrue(target.is_dir())

    def test_atomic_replace_failure_preserves_old_file(self) -> None:
        target = self.target()
        original = b"# Original\n"
        target.write_bytes(original)
        block = installer.render_profiles(["scope-control"])

        with mock.patch.object(
            installer.os, "replace", side_effect=OSError("injected replace failure")
        ):
            with self.assertRaisesRegex(installer.InstallerError, "atomic write failed"):
                installer.install_target(target, block, apply=True)

        self.assertEqual(original, target.read_bytes())
        self.assertEqual([], list(self.root.glob(f"{installer.TEMP_PREFIX}*")))


if __name__ == "__main__":
    unittest.main()
