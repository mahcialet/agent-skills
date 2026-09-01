#!/usr/bin/env python3
"""Validate reader-first-editor eval fixtures and report optional tripwires."""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

MODES = {
    "review",
    "repository-review",
    "revise-safe",
    "revise-structural",
    "diff",
    "authoring",
    "jtf-only",
}
EVIDENCE_STATUSES = {
    "VERIFIED",
    "CONTRADICTED",
    "SUPPORTED-BY-CITATION",
    "UNSUPPORTED",
    "UNVERIFIED",
}
EVIDENCE_TYPES = {
    "DOC↔CODE",
    "DOC↔CONFIG",
    "DOC↔TEST",
    "DOC↔DOC",
    "DOC↔HISTORY",
    "CITATION",
    "EVIDENCE-GAP",
    "UNVERIFIED",
}
COVERAGE_STATUSES = {"checked", "partial", "not-checked"}
ANOMALY_STATUSES = {"EXPLAINED", "UNEXPLAINED", "CONTRADICTED", "NOT-AN-OUTLIER"}
REQUIRED_SUITES = {
    "semantic-preservation",
    "reread-risk-ja",
    "interaction-clarity-ja",
    "relationship-clarity-ja",
    "review-coverage-ja",
    "local-consistency-review",
    "prose-pacing",
    "repository-grounded-review",
}
REQUIRED_SCHEMAS = {
    "corpus-record.schema.json",
    "investigation-bundle.schema.json",
    "investigation.schema.json",
    "regression-plan.schema.json",
    "regression-report.schema.json",
    "regression-run.schema.json",
    "review-coverage.schema.json",
    "rule-approval.schema.json",
    "rule-proposal.schema.json",
    "syntax-ab-input.schema.json",
    "syntax-ab-report.schema.json",
    "syntax-signal.schema.json",
}
REQUIRED_TOOL_FILES = {
    "scripts/analyze_ja.py",
    "scripts/corpus_tool.py",
    "scripts/review_coverage.py",
    "scripts/scan_db_consistency.py",
    "scripts/scan_relationships.py",
    "scripts/reader_first/__init__.py",
    "scripts/reader_first/db_consistency.py",
    "scripts/reader_first/github.py",
    "scripts/reader_first/investigation.py",
    "scripts/reader_first/japanese_syntax.py",
    "scripts/reader_first/regression.py",
    "scripts/reader_first/relationship_candidates.py",
    "scripts/reader_first/review_coverage.py",
    "scripts/reader_first/schema_validation.py",
    "scripts/reader_first/state.py",
}
REQUIRED_GITHUB_FIXTURES = {
    "pr-138-reference-only.json",
    "pr-187-reference-only.json",
}
REQUIRED_SYNTAX_FIXTURES = {"ginza-5.2.0-ja-ginza-5.2.0.json"}
FORBIDDEN_GITHUB_FIXTURE_KEYS = {"body", "content", "diff_hunk", "login", "patch"}


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
            for key in (
                "must_preserve",
                "must_not_add",
                "must_not_claim",
                "expected_risks",
                "expected_statuses",
                "expected_evidence_types",
                "expected_coverage_statuses",
                "expected_anomaly_statuses",
            ):
                if key in case:
                    value = case[key]
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        errors.append(f"{label}: {key} must be a string list")
            coverage_statuses = case.get("expected_coverage_statuses")
            if isinstance(coverage_statuses, list):
                if unknown := set(coverage_statuses) - COVERAGE_STATUSES:
                    errors.append(f"{label}: invalid coverage statuses {sorted(unknown)}")
            anomaly_statuses = case.get("expected_anomaly_statuses")
            if isinstance(anomaly_statuses, list):
                if unknown := set(anomaly_statuses) - ANOMALY_STATUSES:
                    errors.append(f"{label}: invalid anomaly statuses {sorted(unknown)}")
            if case.get("mode") == "repository-review":
                statuses = case.get("expected_statuses")
                evidence_types = case.get("expected_evidence_types")
                if not isinstance(statuses, list) or not statuses:
                    errors.append(f"{label}: repository-review requires expected_statuses")
                elif unknown := set(statuses) - EVIDENCE_STATUSES:
                    errors.append(f"{label}: invalid evidence statuses {sorted(unknown)}")
                if not isinstance(evidence_types, list) or not evidence_types:
                    errors.append(f"{label}: repository-review requires expected_evidence_types")
                elif unknown := set(evidence_types) - EVIDENCE_TYPES:
                    errors.append(f"{label}: invalid evidence types {sorted(unknown)}")
                if isinstance(statuses, list) and isinstance(evidence_types, list):
                    if "UNSUPPORTED" in statuses and "EVIDENCE-GAP" not in evidence_types:
                        errors.append(
                            f"{label}: UNSUPPORTED requires EVIDENCE-GAP evidence type"
                        )
                    if "UNVERIFIED" in statuses and "UNVERIFIED" not in evidence_types:
                        errors.append(
                            f"{label}: UNVERIFIED requires UNVERIFIED evidence type"
                        )
    missing = REQUIRED_SUITES - found_suites
    if missing:
        errors.append(f"missing required suites: {', '.join(sorted(missing))}")
    return errors


def validate_schemas(schema_dir: Path) -> list[str]:
    errors: list[str] = []
    found = {path.name for path in schema_dir.glob("*.schema.json")}
    missing = REQUIRED_SCHEMAS - found
    if missing:
        errors.append(f"missing required schemas: {', '.join(sorted(missing))}")
    for name in sorted(REQUIRED_SCHEMAS & found):
        path = schema_dir / name
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid JSON schema: {exc}")
            continue
        if not isinstance(schema, dict):
            errors.append(f"{path}: schema must be an object")
            continue
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{path}: unsupported or missing $schema")
        if schema.get("type") != "object":
            errors.append(f"{path}: root type must be object")
        if schema.get("additionalProperties") is not False:
            errors.append(f"{path}: root additionalProperties must be false")
        required = schema.get("required")
        properties = schema.get("properties")
        if not isinstance(required, list) or not required:
            errors.append(f"{path}: required must be a non-empty list")
        if not isinstance(properties, dict):
            errors.append(f"{path}: properties must be an object")
        elif isinstance(required, list):
            unknown = set(required) - properties.keys()
            if unknown:
                errors.append(f"{path}: required keys missing from properties: {sorted(unknown)}")
    return errors


def validate_tooling(skill_dir: Path) -> list[str]:
    errors: list[str] = []
    for relative in sorted(REQUIRED_TOOL_FILES):
        if not (skill_dir / relative).is_file():
            errors.append(f"missing required corpus tool file: {relative}")
    for name in (
        "corpus_tool.py",
        "analyze_ja.py",
        "review_coverage.py",
        "scan_db_consistency.py",
        "scan_relationships.py",
    ):
        tool = skill_dir / "scripts" / name
        if tool.is_file():
            result = subprocess.run(
                [sys.executable, str(tool), "--version"],
                cwd=skill_dir,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode or not result.stdout.strip():
                errors.append(f"{name} --version failed: {result.stderr.strip()}")
    return errors


def validate_github_fixtures(skill_dir: Path) -> list[str]:
    fixture_dir = skill_dir / "tests" / "fixtures" / "github"
    errors: list[str] = []
    found = {path.name for path in fixture_dir.glob("*.json")}
    if missing := REQUIRED_GITHUB_FIXTURES - found:
        errors.append(f"missing GitHub fixtures: {', '.join(sorted(missing))}")

    def scan(value: object, path: str, file: Path) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in FORBIDDEN_GITHUB_FIXTURE_KEYS:
                    errors.append(f"{file}: raw/private field is forbidden at {path}.{key}")
                scan(child, f"{path}.{key}", file)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                scan(child, f"{path}[{index}]", file)

    for name in sorted(REQUIRED_GITHUB_FIXTURES & found):
        path = fixture_dir / name
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid JSON fixture: {exc}")
            continue
        if not isinstance(fixture, dict) or fixture.get("schema_version") != 1:
            errors.append(f"{path}: fixture schema_version must be 1")
            continue
        scan(fixture, "$", path)
    return errors


def validate_syntax_fixtures(skill_dir: Path) -> list[str]:
    fixture_dir = skill_dir / "tests" / "fixtures" / "syntax"
    errors: list[str] = []
    found = {path.name for path in fixture_dir.glob("*.json")}
    if missing := REQUIRED_SYNTAX_FIXTURES - found:
        errors.append(f"missing syntax fixtures: {', '.join(sorted(missing))}")
    for name in sorted(REQUIRED_SYNTAX_FIXTURES & found):
        path = fixture_dir / name
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid JSON fixture: {exc}")
            continue
        if not isinstance(fixture, dict):
            errors.append(f"{path}: fixture rootはobjectである必要があります")
            continue
        expected = fixture.get("expected")
        recorded = fixture.get("recorded_with")
        if fixture.get("fixture_schema_version") != 1 or not isinstance(expected, dict):
            errors.append(f"{path}: fixture schema_versionまたはexpectedが不正です")
            continue
        if not isinstance(recorded, dict) or not all(
            isinstance(recorded.get(key), str)
            for key in ("python", "ginza", "ja_ginza", "spacy", "click")
        ):
            errors.append(f"{path}: parser/model version metadataが必要です")
        if expected.get("interpretation") != "observation-only":
            errors.append(f"{path}: parser resultを判定として保存できません")
        if expected.get("backend") != "ginza" or expected.get("available") is not True:
            errors.append(f"{path}: recorded GiNZA resultが必要です")
        if any(key in expected for key in ("readability", "reread_risk", "verdict")):
            errors.append(f"{path}: fixtureへ可読性の最終判定を保存できません")
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
    parser.add_argument("--schema-dir", type=Path, default=Path(__file__).parent.parent / "schemas")
    parser.add_argument("--metrics", help="Print descriptive tripwires for text; never pass/fail quality")
    args = parser.parse_args()
    skill_dir = Path(__file__).parent.parent
    errors = (
        validate(args.eval_dir)
        + validate_schemas(args.schema_dir)
        + validate_tooling(skill_dir)
        + validate_github_fixtures(skill_dir)
        + validate_syntax_fixtures(skill_dir)
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.metrics is not None:
        print(json.dumps(sentence_metrics(args.metrics), ensure_ascii=False))
    print(
        f"validated {len(list(args.eval_dir.glob('*.yaml')))} eval suites "
        f"and {len(REQUIRED_SCHEMAS)} schemas and corpus/syntax tooling"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
