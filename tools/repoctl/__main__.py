"""python -m tools.repoctl: local repository checks, not host execution."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

from . import evidence
from .runner import run_tasks


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    repo = Path(__file__).resolve().parents[2]
    if argv and argv[0] == "install":
        return subprocess.call([sys.executable, str(repo / "scripts/install_local_cli.py"), *argv[1:]])
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("install", help="install into an explicitly selected host root; use install --help")
    for name in ("doctor", "check", "test", "verify", "docs", "plans", "docs-check", "generated-check", "generate"):
        command = sub.add_parser(name)
        if name in {"docs", "plans"}:
            command.add_argument("action", choices=["check"] if name == "docs" else ["list", "check"])
        command.add_argument("--format", choices=["json", "text"], default="text")
        command.add_argument("--timeout", type=float, default=300)
        command.add_argument("--out", type=Path, help="new evidence directory (must not exist); default console only")
        if name == "test":
            command.add_argument("--list", action="store_true", help="list suite tasks without executing them")
        if name == "plans":
            command.add_argument("--check-git", action="store_true")
    args = parser.parse_args(argv)
    if args.timeout <= 0 or not math.isfinite(args.timeout):
        parser.error("--timeout must be positive")
    from . import tasks
    if args.command == "plans" and args.action == "list":
        try:
            from . import plans
            rows = plans.list_plans(repo)
        except ImportError:
            print(json.dumps({"status": "BLOCKED", "exit_code": 3, "message": "Install requirements-dev.txt (PyYAML required)"}))
            return 3
        if args.format == "json":
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            for row in rows:
                print(json.dumps(row, ensure_ascii=False))
        return 0
    label = args.command
    try:
        if args.command == "test" and args.list:
            print(json.dumps(tasks.build_tasks(repo, "test"), default=str, ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            selected = [{"id": "doctor", "argv": [sys.executable, "-m", "tools.repoctl._doctor"], "cwd": repo}]
        elif args.command == "docs":
            label += " check"
            selected = tasks.build_tasks(repo, "docs-check")
        elif args.command == "plans":
            label += " check"
            task_argv = [sys.executable, "-m", "tools.repoctl._checks", args.command]
            task_argv.append("--git")
            selected = [{"id": args.command, "argv": task_argv, "cwd": repo}]
        else:
            selected = tasks.build_tasks(repo, args.command)
        result = run_tasks(repo, selected, label, timeout=args.timeout, output=args.out)
    except (ValueError, OSError) as exc:
        result = evidence.start(repo, label)
        result["diagnostics"] = [{"rule_id": "ASKILLS-HARNESS-001", "message": evidence.scrub(str(exc))}]
        result = evidence.finish(result, "ERROR", 2)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for task in result["tasks"]:
            print(f"{task['status']:7} {task['id']}")
            for diagnostic in task.get("diagnostics", []):
                print(f"  {diagnostic.get('code', 'ERROR')}: {diagnostic.get('path', '')}: {diagnostic.get('reason', '')}")
                print(f"  {diagnostic.get('repair', '')}")
            if task.get("message"):
                print(f"  {task['message']}")
            if task["status"] != "PASS" and not task.get("diagnostics"):
                print(f"  {task.get('stderr_log') or task.get('stderr', '')[-2000:]}")
        print(f"{result['status']} — evidence: {result['run_dir'] or 'console only'}")
        for diagnostic in result.get("diagnostics", []):
            print(f"{diagnostic['rule_id']}: {diagnostic['message']}")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
