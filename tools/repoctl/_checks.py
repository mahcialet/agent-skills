"""repoctl subprocess adapters (not a public entry point)."""
from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["docs", "plans", "skills", "suite"])
    parser.add_argument("path", nargs="?")
    parser.add_argument("--git", action="store_true")
    args = parser.parse_args()
    repo = Path.cwd()
    if args.kind in {"docs", "plans"}:
        try:
            import yaml  # noqa: F401
        except ImportError:
            print(json.dumps({"diagnostics": [{"code": "ASKILLS-DEPENDENCY", "task_id": args.kind,
                              "path": "requirements-dev.txt", "reason": "PyYAML unavailable",
                              "repair": "Install declared development dependencies", "blocked": True}]}))
            return 3
    if args.kind == "suite":
        suite = unittest.TestLoader().discover(args.path, pattern="test_*.py")
        if not suite.countTestCases():
            print("ASKILLS-TEST-EMPTY: mandatory suite discovered zero tests", file=sys.stderr)
            return 1
        return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1
    if args.kind == "skills":
        from scripts.validate_skills import validate
        messages = validate(repo, run_content=False, run_tests=False, run_catalog=False, run_links=False)
        errors = [{"code": "ASKILLS-SKILL-STRUCTURE", "task_id": "skills-structure",
                   "path": "skills", "reason": msg, "repair": "Correct the Skill source contract"}
                  for msg in messages]
    elif args.kind == "docs":
        from .docs import validate
        errors = validate(repo)
    else:
        from .plans import validate
        errors = validate(repo, check_git=args.git)
    print(json.dumps({"diagnostics": errors}, ensure_ascii=False))
    return 3 if any(error.get("blocked") for error in errors) else int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
