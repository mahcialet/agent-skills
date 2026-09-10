"""決定的タスクの発見。列挙ではtest moduleをimportしない。"""
from __future__ import annotations

import os
import importlib.util
import sys
import shutil
from pathlib import Path


def validate_tasks(tasks: list[dict], required: set[str]) -> None:
    ids = [task["id"] for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("ASKILLS-TASK-DUPLICATE: duplicate task registration")
    if required - set(ids):
        raise ValueError(f"ASKILLS-TASK-MISSING: missing mandatory tasks {sorted(required - set(ids))}")


def build_tasks(repo: Path, command: str) -> list[dict]:
    repo = repo.resolve()
    def task(name: str, *argv: str) -> dict:
        return {"id": name, "argv": [sys.executable, *argv], "cwd": str(repo)}

    def require(path: Path) -> None:
        if not path.exists():
            raise ValueError(f"ASKILLS-TASK-MISSING: {path.relative_to(repo)}")

    skills = sorted((repo / "skills").glob("*/SKILL.md"))
    if not skills:
        raise ValueError("ASKILLS-TASK-MISSING: no Skill definitions")
    check: list[dict] = []
    tests: list[dict] = []
    if command in {"check", "verify"}:
        require(repo / "scripts/validate_skills.py")
        check = [task("lint", "-m", "ruff", "check", "."),
                 task("skills-structure", "-m", "tools.repoctl._checks", "skills")]
        if importlib.util.find_spec("ruff") is None:
            check[0]["blocked_reason"] = "ASKILLS-DEPENDENCY: Ruff unavailable; install requirements-dev.txt"
        for skill in skills:
            validator = skill.parent / "scripts/validate_content.py"
            require(validator)
            check.append(task(f"content:{skill.parent.name}", str(validator)))
        check += [task("docs", "-m", "tools.repoctl._checks", "docs"),
                  task("plans-structure", "-m", "tools.repoctl._checks", "plans")]
    if command in {"generated-check", "check", "verify", "generate"}:
        require(repo / "scripts/generate-catalog.py")
        args = [] if command == "generate" else ["--check"]
        check.append(task("generated", "scripts/generate-catalog.py", *args, "--repo", str(repo)))
    if command == "docs-check":
        check = [task("docs", "-m", "tools.repoctl._checks", "docs"),
                 task("plans-structure", "-m", "tools.repoctl._checks", "plans")]
    if command in {"plans-check", "plans check"}:
        check = [task("plans", "-m", "tools.repoctl._checks", "plans", "--git")]
    required = set()
    if command in {"test", "verify"}:
        suites = [("root", repo / "tests"),
                  *[(f"skill:{s.parent.name}", s.parent / "tests") for s in skills],
                  ("repoctl", repo / "tests/repoctl")]
        for name, path in suites:
            require(path)
            if not list(path.glob("test_*.py")):
                raise ValueError(f"ASKILLS-TEST-EMPTY: {path.relative_to(repo)}")
            item = task(f"test:{name}", "-m", "tools.repoctl._checks", "suite", str(path))
            if name == "root" and os.name == "nt":
                item["blocked_reason"] = "ASKILLS-INSTALL-PLATFORM: existing installer requires POSIX locking and dir_fd"
            if name == "repoctl" and shutil.which("git") is None:
                item["blocked_reason"] = "ASKILLS-DEPENDENCY: Git required for mandatory local-history fixtures"
            tests.append(item)
            required.add(item["id"])
    result = check + tests
    validate_tasks(result, required)
    if not result:
        raise ValueError(f"ASKILLS-TASK-COMMAND: unsupported command {command}")
    return result
