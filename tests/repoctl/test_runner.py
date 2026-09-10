from pathlib import Path
import json
import tempfile
import unittest
import sys
import os
import time
import subprocess
import signal
from unittest.mock import patch

from tools.repoctl import evidence
from tools.repoctl.runner import run_tasks


class RunnerTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "POSIX group assertion; native Windows lifecycle remains unverified")
    def test_normal_parent_exit_with_live_owned_child_is_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            ready, release = repo / "ready", repo / "release"
            child = f"from pathlib import Path; import time; Path({str(ready)!r}).touch();\nwhile not Path({str(release)!r}).exists(): time.sleep(0.01)"
            parent = (f"import subprocess,sys,time; from pathlib import Path; "
                      f"subprocess.Popen([sys.executable,'-c',{child!r}],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
                      f"deadline=time.monotonic()+5\nwhile not Path({str(ready)!r}).exists() and time.monotonic()<deadline: time.sleep(0.01)\n"
                      f"assert Path({str(ready)!r}).exists()")
            result = run_tasks(repo, [{"id": "tree", "argv": [sys.executable, "-c", parent], "cwd": repo}], "test")
            self.assertTrue(ready.exists())
            self.assertEqual("ERROR", result["status"])
            self.assertIn("ASKILLS-RUNNER-CHILD", result["tasks"][0]["stderr"])

    @unittest.skipIf(os.name == "nt", "POSIX process-group assertion; Windows requires native evidence")
    def test_timeout_terminates_owned_grandchild_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            ready, barrier = repo / "child-ready", repo / "parent-ready"
            child = f"from pathlib import Path; import time; Path({str(ready)!r}).touch();\nwhile True: time.sleep(1)"
            code = (f"import subprocess,sys,time; from pathlib import Path; "
                    f"subprocess.Popen([sys.executable, '-c', {child!r}]);\n"
                    f"while not Path({str(ready)!r}).exists(): time.sleep(0.01)\n"
                    f"print('before timeout',flush=True); Path({str(barrier)!r}).touch()\nwhile True: time.sleep(1)")
            real_popen = subprocess.Popen

            def launch(*args, **kwargs):
                process = real_popen(*args, **kwargs)
                communicate = process.communicate
                first = True

                def controlled_timeout(*args, **kwargs):
                    nonlocal first
                    if first:
                        first = False
                        deadline = time.monotonic() + 5
                        while not barrier.exists() and time.monotonic() < deadline:
                            time.sleep(0.01)
                        if not barrier.exists():
                            os.killpg(process.pid, signal.SIGKILL)
                            communicate()
                            self.fail("readiness barrier was not reached")
                        raise subprocess.TimeoutExpired(process.args, 300)
                    return communicate(*args, **kwargs)
                process.communicate = controlled_timeout
                return process

            with patch("tools.repoctl.evidence.git_state", return_value={}), \
                    patch("tools.repoctl.runner.subprocess.Popen", side_effect=launch), \
                    patch("tools.repoctl.runner.os.killpg", wraps=os.killpg) as kill_group:
                result = run_tasks(repo, [{"id": "tree", "argv": [sys.executable, "-c", code], "cwd": repo}], "test")
                pid = result["tasks"][0]["owned_resources"][0]["pid"]
                kill_group.assert_called_once_with(pid, signal.SIGKILL)
            self.assertEqual("ERROR", result["status"])
            self.assertIn("before timeout", result["tasks"][0]["stdout"])
            self.assertEqual("PASS", result["cleanup_result"])

    def test_exit_classification_and_log_evidence(self):
        for code, expected in ((0, "PASS"), (1, "FAIL"), (2, "ERROR"), (3, "BLOCKED"), (99, "ERROR")):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                result = run_tasks(repo, [{"id": "sample", "argv": [sys.executable, "-c", f"raise SystemExit({code})"], "cwd": repo}], "test", output=repo / "evidence")
                self.assertEqual(expected, result["status"])
                saved = json.loads((Path(result["run_dir"]) / "summary.json").read_text())
                self.assertEqual(result, saved)
                self.assertIn("operation_result", result)
                self.assertIn("subject_result", result)
                if code == 1:
                    self.assertEqual("PASS", result["operation_result"])
                    self.assertEqual("FAIL", result["subject_result"])
                self.assertTrue(Path(result["tasks"][0]["stdout_log"]).is_file())

    def test_empty_duplicate_missing_timeout_and_interruption_not_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            task = {"id": "sample", "argv": [sys.executable, "-c", "import time; time.sleep(1)"], "cwd": repo}
            self.assertEqual("ERROR", run_tasks(repo, [], "test")["status"])
            self.assertEqual("ERROR", run_tasks(repo, [task, task], "test")["status"])
            self.assertEqual("ERROR", run_tasks(repo, [task], "test", timeout=0.01)["status"])
            task["argv"] = [str(repo / "missing-program")]
            self.assertEqual("BLOCKED", run_tasks(repo, [task], "test")["status"])
            task["blocked_reason"] = "native platform unsupported"
            self.assertEqual("BLOCKED", run_tasks(repo, [task], "test")["status"])
            task.pop("blocked_reason")
            with patch("tools.repoctl.runner._execute", side_effect=KeyboardInterrupt):
                pending = {**task, "id": "pending"}
                result = run_tasks(repo, [task, pending], "test")
                self.assertEqual("BLOCKED", result["status"])
                self.assertEqual(130, result["exit_code"])
                self.assertEqual(2, len(result["tasks"]))
                self.assertIn("not executed", result["tasks"][1]["message"])

    def test_default_console_only_and_argv_redacted(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            result = run_tasks(repo, [{"id": "sample", "argv": [sys.executable, "-c", "pass", "--password", "SYNTHETIC_SECRET_SENTINEL"], "cwd": repo}], "test")
            self.assertEqual("PASS", result["status"])
            self.assertIsNone(result["run_dir"])
            self.assertEqual([], list(repo.iterdir()))
            self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", json.dumps(result))

    def test_scrub_does_not_expose_credentials(self):
        output = evidence.scrub("Authorization: Bearer very-private\napiKey=sensitive&x=y\nordinary failure")
        self.assertNotIn("very-private", output)
        self.assertNotIn("sensitive", output)
        self.assertIn("ordinary failure", output)
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", evidence.scrub('{"api_key":"SYNTHETIC_SECRET_SENTINEL"}'))
        self.assertNotIn("SYNTHETIC_SECRET_SENTINEL", str(evidence.safe_argv(["--token=SYNTHETIC_SECRET_SENTINEL"])))


if __name__ == "__main__":
    unittest.main()
