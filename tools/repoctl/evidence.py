"""Private, local execution evidence. No environment values are recorded."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import uuid


def scrub(text: str) -> str:
    text = re.sub(r"(?i)(authorization\s*[:=]\s*)([^\r\n]+)", r"\1[REDACTED]", text)
    return re.sub(
        r'''(?i)((?:api[_-]?key|password|access_token|token|secret)["']?\s*[:=]\s*["']?)([^\s,;"'}]+)''',
        r"\1[REDACTED]", text,
    )


def safe_argv(argv: list[str]) -> list[str]:
    result, sensitive = [], False
    for part in argv:
        result.append("[REDACTED]" if sensitive else scrub(str(part)))
        sensitive = bool(re.fullmatch(r"(?i)--?(?:password|api[_-]?key|token|secret|authorization)", str(part)))
    return result


def git_state(repo: Path) -> dict:
    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=10,
                check=False, env={key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None
    status = run("status", "--porcelain")
    fingerprint = hashlib.sha256()
    paths = run("ls-files", "-co", "--exclude-standard", "-z")
    for name in sorted(set((paths or "").split("\0")) - {""}):
        path = repo / name
        if path.is_symlink():
            fingerprint.update(name.encode("utf-8") + b"\0LINK\0" + os.readlink(path).encode("utf-8"))
            continue
        if not path.resolve().is_relative_to(repo.resolve()):
            fingerprint.update(name.encode("utf-8") + b"\0EXTERNAL\0")
            continue
        try:
            fingerprint.update(name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
        except (OSError, ValueError):
            fingerprint.update(name.encode("utf-8") + b"\0UNREADABLE\0")
    return {"commit": run("rev-parse", "HEAD"), "dirty": bool(status) if status is not None else None,
            "source_sha256": fingerprint.hexdigest() if paths is not None else None}


def start(repo: Path, command: str, output: Path | None = None) -> dict:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{uuid.uuid4().hex[:12]}"
    run_dir = output
    if run_dir:
        run_dir.mkdir(parents=True, mode=0o700)
    return {
        "schema_version": 1, "run_id": run_id, "command": command, "started_at": stamp,
        "parent_run_id": None, "attempt_id": 1, "_started_monotonic": time.monotonic(),
        "evidence_class": "repository-local", "provenance_kind": "actual-local-subprocess",
        "scope": "M1-M4 local checks; native OS and M5+ acceptance are separate",
        "run_dir": str(run_dir) if run_dir else None, "repository": str(repo),
        "platform": {"system": platform.system(), "release": platform.release()},
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "git": git_state(repo), "tasks": [],
    }


def write_log(run: dict, index: int, stream: str, value: str) -> str:
    # Bound logs, redact credential-shaped output, never dump environment variables.
    data = scrub(value)
    if len(data) > 1_000_000:
        data = data[:1_000_000] + "\n[TRUNCATED]\n"
    if run["run_dir"] is None:
        return data
    path = Path(run["run_dir"]) / f"{index:03d}-{stream}.log"
    with path.open("x", encoding="utf-8") as handle:
        handle.write(data)
    if os.name != "nt":
        path.chmod(0o600)
    return str(path)


def finish(run: dict, status: str, exit_code: int) -> dict:
    run.update(status=status, exit_code=exit_code)
    evaluated = run["command"] not in {"doctor", "generate"}
    run["operation_result"] = "PASS" if exit_code == 0 or (exit_code == 1 and evaluated) else status
    run["subject_result"] = "NOT_RUN" if run["command"] in {"doctor", "generate"} else status
    run["ended_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    run["duration_seconds"] = time.monotonic() - run.pop("_started_monotonic")
    run["owned_resources"] = [resource for task in run["tasks"] for resource in task.get("owned_resources", [])]
    cleanup = {task.get("cleanup_result", "NOT_RUN") for task in run["tasks"]} - {"NOT_RUN"}
    run["cleanup_result"] = "NOT_RUN" if not cleanup else "PASS" if cleanup == {"PASS"} else "UNVERIFIED"
    if run["run_dir"] is None:
        return run
    path = Path(run["run_dir"]) / "summary.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(run, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if os.name != "nt":
        path.chmod(0o600)
    return run
