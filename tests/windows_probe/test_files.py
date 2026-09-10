"""Native temporary-tree proof, separate from mandatory installer acceptance."""

import ctypes
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

from tools.windows_probe.files import (
    FILE_RENAME_INFO, OBJECT_ATTRIBUTES, OVERLAPPED, PinnedDirectory,
    Unsupported, component,
)


@unittest.skipUnless(os.name == "nt", "experimental W1 requires native Windows")
class NativeFileProof(unittest.TestCase):
    def setUp(self):
        self.tree = tempfile.TemporaryDirectory(prefix="askills-w1-空 白-")
        self.addCleanup(self.tree.cleanup)
        self.root = Path(self.tree.name)

    def read_line(self, stream):
        output = queue.Queue()
        reader = threading.Thread(target=lambda: output.put(stream.readline()), daemon=True)
        reader.start()
        try:
            line = output.get(timeout=15)
        except queue.Empty:
            self.fail("child barrier timed out")
        reader.join(timeout=1)
        return line.strip()

    def test_abi(self):
        self.assertEqual(ctypes.sizeof(ctypes.c_void_p), 8)
        self.assertEqual(ctypes.sizeof(OBJECT_ATTRIBUTES), 48)
        self.assertEqual(FILE_RENAME_INFO.FileName.offset, 20)
        self.assertEqual(ctypes.sizeof(OVERLAPPED), 32)

    def test_bootstrap_identity_and_pinned_ancestor(self):
        nested = self.root / "祖先" / "child"
        nested.mkdir(parents=True)
        with PinnedDirectory(nested) as root:
            before = root.identity()
            with self.assertRaises(OSError):
                (self.root / "祖先").rename(self.root / "replacement")
            self.assertEqual(root.identity(), before)
            self.assertEqual(len(before.file_id), 16)

    def test_handle_relative_create_rename_no_replace_and_delete(self):
        (self.root / "occupied").write_text("third-party", encoding="utf-8")
        with PinnedDirectory(self.root) as root:
            with root.child("試験", create=True, mutable=True) as entry:
                identity = entry.identity()
                with self.assertRaises(OSError):
                    entry.rename(root, "occupied")
                self.assertEqual((self.root / "occupied").read_text(), "third-party")
                entry.rename(root, "renamed")
                self.assertFalse((self.root / "試験").exists())
                with root.child("renamed") as reopened:
                    self.assertEqual(reopened.identity(), identity)
                entry.delete()
            self.assertFalse((self.root / "renamed").exists())

    def test_directory_rename_and_disposition(self):
        with PinnedDirectory(self.root) as root:
            with root.child("stage", create=True, directory=True, mutable=True) as entry:
                identity = entry.identity()
                entry.rename(root, "active")
                with root.child("active", directory=True) as reopened:
                    self.assertEqual(reopened.identity(), identity)
                entry.delete()
            self.assertFalse((self.root / "active").exists())

    def test_bad_names_are_rejected_before_nt(self):
        with PinnedDirectory(self.root) as root:
            for name in ["..", ".", "a/b", "a\\b", "stream:ads", "CON", "LPT1.txt", "tail.", "tail "]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    root.child(name, create=True)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_junction_rejected_at_bootstrap_and_relative_open(self):
        target = self.root / "target"
        target.mkdir()
        marker = target / "marker"
        marker.write_text("untouched")
        junction = self.root / "junction"
        # Explicit adversarial fixture, never a symlink fallback in the prototype.
        result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        try:
            with PinnedDirectory(self.root) as root:
                with self.assertRaises((Unsupported, OSError)):
                    root.child("junction", directory=True)
            with self.assertRaises((Unsupported, OSError)):
                PinnedDirectory(junction)
            self.assertEqual(marker.read_text(), "untouched")
        finally:
            os.rmdir(junction)

    def test_guard_rejects_hardlink_and_prevents_replacement(self):
        guard_path = self.root / "guard"
        guard_path.touch()
        os.link(guard_path, self.root / "alias")
        with PinnedDirectory(self.root) as root:
            with root.child("guard", mutable=True, pinned=True) as guard:
                self.assertEqual(guard.identity().links, 2)
                with self.assertRaises(Unsupported):
                    guard.lock()
            (self.root / "alias").unlink()
            with root.child("guard", mutable=True, pinned=True) as guard:
                guard.lock()
                try:
                    with self.assertRaises(OSError):
                        guard_path.rename(self.root / "stolen")
                    with self.assertRaises(OSError):
                        guard_path.unlink()
                finally:
                    guard.unlock()
        self.assertTrue(guard_path.exists())

    def test_two_process_fixed_range_contention_and_release(self):
        (self.root / "guard").touch()
        code = '''
import sys
from tools.windows_probe.files import PinnedDirectory
with PinnedDirectory(sys.argv[1]) as root:
    with root.child("guard", mutable=True, pinned=True) as guard:
        print("READY", flush=True)
        assert sys.stdin.readline().strip() == "TRY"
        try:
            guard.lock()
        except OSError as error:
            print("BLOCKED:" + str(error.winerror), flush=True)
        else:
            guard.unlock()
            raise AssertionError("lock unexpectedly acquired")
        assert sys.stdin.readline().strip() == "RELEASED"
        guard.lock()
        guard.unlock()
        print("ACQUIRED", flush=True)
'''
        with PinnedDirectory(self.root) as root:
            with root.child("guard", mutable=True, pinned=True) as guard:
                guard.lock()
                child = subprocess.Popen([sys.executable, "-u", "-c", code, str(self.root)],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True)
                try:
                    self.assertEqual(self.read_line(child.stdout), "READY")
                    child.stdin.write("TRY\n")
                    child.stdin.flush()
                    self.assertEqual(self.read_line(child.stdout), "BLOCKED:33")
                    guard.unlock()
                    output, errors = child.communicate("RELEASED\n", timeout=15)
                    self.assertEqual(child.returncode, 0, errors)
                    self.assertEqual(output.strip(), "ACQUIRED")
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=15)

    def test_readonly_disposition_fails_without_changing_entry(self):
        path = self.root / "readonly"
        path.write_text("preserved")
        path.chmod(0o444)
        try:
            with PinnedDirectory(self.root) as root:
                # Request DELETE but not FILE_WRITE_DATA so the expected
                # failure must come from disposition, not a writable open.
                with root.child("readonly", delete_only=True) as entry:
                    with self.assertRaises(OSError) as error:
                        entry.delete()
                    self.assertEqual(error.exception.winerror, 5)
            self.assertEqual(path.read_text(), "preserved")
        finally:
            path.chmod(0o666)

    def test_acl_denied_write_data_is_not_bypassed(self):
        # Only this newly created temporary file's ACL changes. Do not change
        # caller/ancestor ACLs or print the runner's SID in test evidence.
        path = self.root / "acl-denied"
        path.write_text("preserved")
        identity = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
             "[Security.Principal.WindowsIdentity]::GetCurrent().User.Value"],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(identity.returncode, 0, "cannot inspect current token SID")
        sid = identity.stdout.strip()
        self.assertRegex(sid, r"^S-1-(?:\d+-)+\d+$")
        # Deny FILE_WRITE_DATA, which the mutable open explicitly requests.
        # DELETE alone is not a reliable denied-open oracle because the parent
        # directory may grant FILE_DELETE_CHILD independently of the file ACL.
        denied = subprocess.run(["icacls.exe", str(path), "/deny", f"*{sid}:(WD)"],
                                capture_output=True, timeout=15)
        self.assertEqual(denied.returncode, 0, "temporary ACL deny setup failed")
        try:
            with PinnedDirectory(self.root) as root:
                with self.assertRaises(OSError) as error:
                    root.child("acl-denied", mutable=True)
                self.assertEqual(error.exception.winerror, 5)
                with root.child("acl-denied") as entry:
                    self.assertEqual(entry.identity().links, 1)
            self.assertEqual(path.read_text(), "preserved")
        finally:
            restored = subprocess.run(["icacls.exe", str(path), "/remove:d", f"*{sid}"],
                                      capture_output=True, timeout=15)
            self.assertEqual(restored.returncode, 0, "temporary ACL restoration failed")


class ComponentProof(unittest.TestCase):
    def test_valid_unicode_and_non_normalizing_rejection(self):
        self.assertEqual(component("日本語 name"), "日本語 name")
        for name in ["CON", "nul.txt", "COM¹", "x:y", "a/../b", "tail ", ""]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                component(name)


if __name__ == "__main__":
    unittest.main()
