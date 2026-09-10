"""Native W1 Job proof, with file barriers and kernel-handle exit oracles."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from tools.windows_probe.jobs import Job, Process, SpawnError


ROOT = Path(__file__).resolve().parents[2]
WAIT = """
import pathlib, sys, time
ready, release = map(pathlib.Path, sys.argv[1:3])
ready.write_text('ready')
deadline = time.monotonic() + 60
while not release.exists():
    if time.monotonic() > deadline:
        raise SystemExit(124)
    time.sleep(.01)
"""


@unittest.skipUnless(os.name == "nt", "native Windows W1 proof only")
class JobProof(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="w1 job 日本語 ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def barrier(self, path):
        deadline = time.monotonic() + 20
        while True:
            try:
                value = path.read_text()
            except FileNotFoundError:
                value = ""
            if value:
                return value
            if time.monotonic() > deadline:
                self.fail(f"ready barrier timeout: {path.name}")
            time.sleep(.01)

    def job(self):
        job = Job()
        self.addCleanup(job.close)
        return job

    def observe(self, pid):
        process = Process.observe(pid)
        self.addCleanup(process.close)
        return process

    def worker(self, job):
        ready, release = self.root / "ready", self.root / "release"
        process = job.spawn([sys.executable, "-c", WAIT, str(ready), str(release)])
        self.addCleanup(process.close)
        self.barrier(ready)
        self.assertTrue(process.in_job(job))
        return process

    def test_noninherited_job_and_last_handle_lifetime(self):
        job = self.job()
        self.assertFalse(job.inheritable())
        duplicate = job.duplicate_for_lifetime_probe()
        self.addCleanup(duplicate.close)
        self.assertFalse(duplicate.inheritable())
        process = self.worker(job)
        job.close()
        # The ready worker remains blocked on release while an extra Job
        # handle exists; only the final close must cause kernel-signaled exit.
        self.assertFalse(process.wait(0))
        duplicate.close()
        self.assertTrue(process.wait())

    def test_release_barrier_normal_exit(self):
        job = self.job()
        process = self.worker(job)
        (self.root / "release").touch()
        self.assertTrue(process.wait())
        self.assertEqual(process.exit_code(), 0)

    def test_failed_native_assignment_never_executes_child(self):
        job = self.job()
        job.close()  # Invalid native Job handle forces Assign failure.
        with self.assertRaises(SpawnError) as caught:
            job.spawn([sys.executable, "-c", WAIT,
                       str(self.root / "ready"), str(self.root / "release")])
        self.assertTrue(caught.exception.cleanup_confirmed)
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertFalse((self.root / "ready").exists())

    def test_job_close_kills_owned_descendant(self):
        job = self.job()
        grand_ready, release = self.root / "grand-ready", self.root / "release"
        pid_file = self.root / "pid"
        script = """
import pathlib, subprocess, sys, time
p = subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], sys.argv[3]])
pathlib.Path(sys.argv[4]).write_text(str(p.pid))
p.wait(timeout=60)
"""
        parent = job.spawn([sys.executable, "-c", script, WAIT,
                            str(grand_ready), str(release), str(pid_file)])
        self.addCleanup(parent.close)
        child = self.observe(int(self.barrier(pid_file)))
        self.barrier(grand_ready)
        self.assertTrue(child.in_job(job))
        job.close()
        self.assertTrue(parent.wait())
        self.assertTrue(child.wait())

    def test_owner_death_closes_job_and_kills_child(self):
        script = """
import pathlib, sys, time
from tools.windows_probe.jobs import Job
j = Job()
p = j.spawn([sys.executable, '-c', sys.argv[1], sys.argv[2], sys.argv[3]])
pathlib.Path(sys.argv[4]).write_text(str(p.pid))
time.sleep(60)
"""
        ready, release, pid_file = (self.root / n for n in ("ready", "release", "pid"))
        parent = subprocess.Popen([sys.executable, "-c", script, WAIT,
                                   str(ready), str(release), str(pid_file)], cwd=ROOT)
        def cleanup_parent():
            if parent.poll() is None:
                parent.kill()
            parent.wait(timeout=10)
        self.addCleanup(cleanup_parent)
        child = self.observe(int(self.barrier(pid_file)))
        self.barrier(ready)
        parent.kill()
        parent.wait(timeout=10)
        self.assertTrue(child.wait())

    def test_breakaway_request_rejected_inside_job(self):
        job = self.job()
        result = self.root / "result"
        script = """
import pathlib, subprocess, sys
try:
    p = subprocess.Popen([sys.executable, '-c', 'pass'], creationflags=0x01000000)
except OSError as exc:
    pathlib.Path(sys.argv[1]).write_text(str(exc.winerror))
else:
    p.wait(timeout=10)
    pathlib.Path(sys.argv[1]).write_text('escaped')
"""
        process = job.spawn([sys.executable, "-c", script, str(result)])
        self.addCleanup(process.close)
        self.assertTrue(process.wait())
        self.assertEqual(process.exit_code(), 0)
        self.assertEqual(self.barrier(result), "5")

    def test_nested_job_assignment_and_cleanup(self):
        outer = self.job()
        script = """
import pathlib, sys, time
from tools.windows_probe.jobs import Job
with Job() as inner:
    p = inner.spawn([sys.executable, '-c', sys.argv[1], sys.argv[2], sys.argv[3]])
    try:
        assert p.in_job(inner)
        deadline = time.monotonic() + 20
        while not pathlib.Path(sys.argv[2]).exists():
            if time.monotonic() > deadline:
                raise RuntimeError('nested ready timeout')
            time.sleep(.01)
        inner.close()
        assert p.wait()
    finally:
        p.close()
"""
        process = outer.spawn([sys.executable, "-c", script, WAIT,
                               str(self.root / "ready"), str(self.root / "release")],
                              cwd=ROOT)
        self.addCleanup(process.close)
        self.assertTrue(process.wait(30000))
        self.assertEqual(process.exit_code(), 0)

    def test_x64_abi_scope(self):
        self.assertEqual(ctypes.sizeof(ctypes.c_void_p), 8)
        # Job construction also checks every bound structure's native size.
        self.job()
