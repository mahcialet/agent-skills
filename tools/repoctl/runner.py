"""Run explicit tasks in isolated subprocesses; aggregate without false green."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from . import evidence


def _execute(argv: list[str], cwd: str | Path, timeout: float) -> subprocess.CompletedProcess:
    if os.name == "nt" and not shutil.which("taskkill"):
        raise FileNotFoundError("taskkill is required for owned process cleanup")
    options = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace", **options)
    resources = [{"kind": "process-group" if os.name != "nt" else "process-tree", "pid": process.pid}]
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10, check=False)
            process.kill()
        stdout, stderr = process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            error = subprocess.TimeoutExpired(argv, timeout, output=stdout, stderr=stderr)
            error.owned_resources = resources
            error.cleanup_result = "PASS" if os.name != "nt" else "UNVERIFIED"
            raise error from None
        exc.owned_resources = resources
        exc.cleanup_result = "PASS" if os.name != "nt" else "UNVERIFIED"
        raise
    if os.name != "nt":
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            pass
        else:
            # The direct child is reaped, but owned descendants are still active.
            # Do not report success or leave the group running after the command.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            result = subprocess.CompletedProcess(argv, 4, stdout, stderr + "\nASKILLS-RUNNER-CHILD: task left an active process group; terminated, not PASS\n")
            result.owned_resources, result.cleanup_result = resources, "PASS"
            return result
    result = subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    result.owned_resources = resources
    result.cleanup_result = "PASS" if os.name != "nt" else "UNVERIFIED"
    return result


def run_tasks(repo: Path, tasks: list[dict], command: str, *, timeout: float = 300,
              output: Path | None = None) -> dict:
    run = evidence.start(repo, command, output)
    if command == "verify":
        run["not_requested"] = ["installer-smoke (M6)", "model-eval", "host-eval"]
    if not tasks or len({task["id"] for task in tasks}) != len(tasks):
        run["diagnostics"] = [{"rule_id": "ASKILLS-TASK-001", "message": "missing or duplicate tasks"}]
        return evidence.finish(run, "ERROR", 2)
    if sys.version_info < (3, 12):
        run["diagnostics"] = [{"rule_id": "ASKILLS-ENV-001", "message": "Python 3.12+ required"}]
        return evidence.finish(run, "BLOCKED", 3)
    for index, task in enumerate(tasks):
        started = time.monotonic()
        item = {"id": task["id"], "argv": evidence.safe_argv(task["argv"]), "cwd": str(task["cwd"])}
        stdout, stderr = "", ""
        if task.get("blocked_reason"):
            item.update(status="BLOCKED", returncode=3, message=task["blocked_reason"])
        else:
            try:
                process = _execute(task["argv"], task["cwd"], timeout)
                stdout, stderr = process.stdout, process.stderr
                item["owned_resources"] = process.owned_resources
                item["cleanup_result"] = process.cleanup_result
                code = process.returncode
                status = {0: "PASS", 1: "FAIL", 2: "ERROR", 3: "BLOCKED"}.get(code, "ERROR")
                item.update(status=status, returncode=code)
                try:
                    payload = json.loads(stdout)
                    if isinstance(payload, dict) and isinstance(payload.get("diagnostics"), list):
                        item["diagnostics"] = json.loads(evidence.scrub(json.dumps(payload["diagnostics"])))
                except (ValueError, TypeError):
                    pass
            except subprocess.TimeoutExpired as exc:
                stdout, stderr = exc.output or "", exc.stderr or ""
                item["owned_resources"] = getattr(exc, "owned_resources", [])
                item["cleanup_result"] = getattr(exc, "cleanup_result", "UNVERIFIED")
                item.update(status="ERROR", returncode=None, message=f"task timeout after {timeout}s")
            except FileNotFoundError:
                item.update(status="BLOCKED", returncode=None, message="required executable or cwd missing")
            except OSError as exc:
                item.update(status="ERROR", returncode=None, message=f"process launch failed: {type(exc).__name__}")
            except KeyboardInterrupt as exc:
                item["owned_resources"] = getattr(exc, "owned_resources", [])
                item["cleanup_result"] = getattr(exc, "cleanup_result", "UNVERIFIED")
                item.update(status="BLOCKED", returncode=None, message="interrupted; remaining tasks not executed")
                item["duration_seconds"] = time.monotonic() - started
                run["tasks"].append(item)
                for pending in tasks[index + 1:]:
                    run["tasks"].append({"id": pending["id"], "argv": evidence.safe_argv(pending["argv"]),
                                         "cwd": str(pending["cwd"]), "status": "BLOCKED", "returncode": None,
                                         "duration_seconds": 0, "message": "not executed: previous task interrupted"})
                return evidence.finish(run, "BLOCKED", 130)
        item["duration_seconds"] = time.monotonic() - started
        suffix = "_log" if run["run_dir"] else ""
        item["stdout" + suffix] = evidence.write_log(run, index, "stdout", stdout)
        item["stderr" + suffix] = evidence.write_log(run, index, "stderr", stderr)
        run["tasks"].append(item)
    statuses = {task["status"] for task in run["tasks"]}
    for status, code in (("ERROR", 2), ("FAIL", 1), ("BLOCKED", 3)):
        if status in statuses:
            return evidence.finish(run, status, code)
    return evidence.finish(run, "PASS", 0)
