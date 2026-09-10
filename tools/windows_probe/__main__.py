"""W1専用の実機試験入口。本体のWindows対応判定とは独立する。"""
from __future__ import annotations

import argparse
import json
import os
import platform
import struct
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from tools.repoctl.evidence import scrub


def native_supported() -> bool:
    return (os.name == "nt" and struct.calcsize("P") == 8
            and platform.machine().lower() in {"amd64", "x86_64"})


def native_suite():
    directory = Path(__file__).resolve().parents[2] / "tests/windows_probe"
    suites = []
    for filename in ("test_files.py", "test_jobs.py"):
        if not (directory / filename).is_file():
            raise RuntimeError(f"ASKILLS-W1-SUITE-MISSING: {filename}")
        suite = unittest.TestLoader().discover(str(directory), pattern=filename)
        if not suite.countTestCases():
            raise RuntimeError(f"ASKILLS-W1-SUITE-EMPTY: {filename}")
        suites.append(suite)
    return unittest.TestSuite(suites)


class Result(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.cases.append({"id": test.id(), "status": "PASS"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.cases.append({"id": test.id(), "status": "FAIL"})

    def addError(self, test, err):
        super().addError(test, err)
        self.cases.append({"id": test.id(), "status": "ERROR"})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.cases.append({"id": test.id(), "status": "BLOCKED", "reason": reason})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        self.cases.append({"id": subtest.id(), "status": "PASS" if err is None else "FAIL"})

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.cases.append({"id": test.id(), "status": "BLOCKED", "reason": "expected failure"})

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.cases.append({"id": test.id(), "status": "FAIL", "reason": "unexpected success"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="new evidence directory; default console only")
    args = parser.parse_args()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
    summary = {
        "schema_version": 1,
        "scope": "W1 experimental primitives only; not installer/backend acceptance",
        "evidence_class": "preflight",
        "revision": os.environ.get("GITHUB_SHA", "unknown-local-revision"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "pointer_bits": struct.calcsize("P") * 8,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cases": [],
    }
    if not native_supported():
        summary.update(status="BLOCKED", reason="ASKILLS-W1-PLATFORM: native Windows x64 required")
        code = 3
    else:
        try:
            suite = native_suite()
            result = unittest.TextTestRunner(verbosity=2, resultclass=Result).run(suite)
            code = 0 if (result.wasSuccessful() and result.testsRun and not result.skipped
                         and not result.expectedFailures) else 1
            summary.update(status="PASS" if code == 0 else "FAIL", tests_run=result.testsRun,
                           cases=result.cases, evidence_class="direct-native / forced-invariant")
        except Exception as exc:
            code = 2
            summary.update(status="ERROR", reason=scrub(f"ASKILLS-W1-EXECUTION: {type(exc).__name__}: {exc}"))
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        temporary = args.out / "summary.json.tmp"
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(args.out / "summary.json")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
