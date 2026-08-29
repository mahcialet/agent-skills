#!/usr/bin/env python3
"""Validate reader-first-editor eval fixtures and report optional tripwires."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

MODES = {"review", "revise-safe", "revise-structural", "diff", "authoring", "jtf-only"}
REQUIRED_SUITES = {
    "semantic-preservation",
    "reread-risk-ja",
    "interaction-clarity-ja",
    "prose-pacing",
}


def load_suites(eval_dir: Path) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    suites: list[dict] = []
    for path in sorted(eval_dir.glob("*.yaml")):
        try:
            # JSON is a strict subset of YAML. Keeping fixtures in this subset lets
            # validation remain dependency-free on copied skill installations.
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid YAML/JSON subset: {exc}")
            continue
        if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
            errors.append(f"{path}: top level must contain a cases list")
            continue
        suites.append(data)
    return suites, errors


def validate(eval_dir: Path) -> list[str]:
    suites, errors = load_suites(eval_dir)
    seen_ids: set[str] = set()
    found_suites: set[str] = set()
    for suite in suites:
        suite_name = suite.get("suite")
        if not isinstance(suite_name, str) or not suite_name:
            errors.append("fixture suite must have a non-empty name")
        else:
            found_suites.add(suite_name)
        for index, case in enumerate(suite["cases"], start=1):
            label = f"{suite_name or '<unknown>'} case {index}"
            if not isinstance(case, dict):
                errors.append(f"{label}: case must be an object")
                continue
            case_id = case.get("id")
            if not isinstance(case_id, str) or not case_id:
                errors.append(f"{label}: missing id")
            elif case_id in seen_ids:
                errors.append(f"{label}: duplicate id {case_id}")
            else:
                seen_ids.add(case_id)
            if case.get("mode") not in MODES:
                errors.append(f"{label}: invalid mode {case.get('mode')!r}")
            if case.get("language") not in {"ja", "en"}:
                errors.append(f"{label}: language must be ja or en")
            if not isinstance(case.get("input"), str) or not case["input"].strip():
                errors.append(f"{label}: input must be non-empty text")
            if not isinstance(case.get("expected"), str) or not case["expected"].strip():
                errors.append(f"{label}: expected must be non-empty text")
            for key in ("must_preserve", "must_not_add", "expected_risks"):
                if key in case and not all(isinstance(item, str) for item in case[key]):
                    errors.append(f"{label}: {key} must be a string list")
    missing = REQUIRED_SUITES - found_suites
    if missing:
        errors.append(f"missing required suites: {', '.join(sorted(missing))}")
    return errors


def sentence_metrics(text: str) -> dict[str, object]:
    sentences = [s.strip() for s in re.split(r"(?<=[。！？.!?])\s*", text) if s.strip()]
    lengths = [len(s) for s in sentences]
    return {
        "sentence_count": len(sentences),
        "lengths": lengths,
        "mean_length": round(statistics.mean(lengths), 2) if lengths else 0,
        "length_stdev": round(statistics.pstdev(lengths), 2) if len(lengths) > 1 else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-dir", type=Path, default=Path(__file__).parent.parent / "evals")
    parser.add_argument("--metrics", help="Print descriptive tripwires for text; never pass/fail quality")
    args = parser.parse_args()
    errors = validate(args.eval_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.metrics is not None:
        print(json.dumps(sentence_metrics(args.metrics), ensure_ascii=False))
    print(f"validated {len(list(args.eval_dir.glob('*.yaml')))} eval suites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
