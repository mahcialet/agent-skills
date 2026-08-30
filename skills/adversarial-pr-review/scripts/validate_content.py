#!/usr/bin/env python3
"""Validate adversarial-pr-review fixtures, examples, policy, and portability."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

LEVELS = {"auto", "A0", "A1", "A2", "A3", "A4"}
EXPLICIT_LEVELS = LEVELS - {"auto"}
DEPTHS = {"focused", "standard", "deep"}
MODES = {"review", "gate"}
GATES = {"BLOCK", "CONDITIONAL", "PASS", "N/A"}
CONFIDENCES = {"Confirmed", "Strongly supported", "Hypothesis", "Not applicable"}
SPECIFICATION_STATUSES = {"sufficient", "partial", "missing"}
TEST_EVIDENCE = {"claimed", "observed", "executed", "not applicable"}
TRACEABILITY_STATUSES = {
    "Satisfied",
    "Violated",
    "Unverified",
    "Not applicable",
    "Conflicting requirements",
    "N/A",
}
APPROVAL_STATUSES = {"NOT GRANTED", "N/A"}
REQUIRED_SUITES = {
    "adversarial-levels",
    "evidence-and-findings",
    "safety-and-prompt-injection",
    "portability-and-invocation",
    "review-contract-and-approval",
}
REQUIRED_CASE_IDS = {
    "levels-docs-a0-candidate",
    "levels-docs-executable-promotes",
    "levels-a0-normal-contract",
    "levels-a1-failure-boundaries",
    "levels-a2-authorized-abuse",
    "levels-a3-boundary-attacker",
    "levels-a4-compromise-containment",
    "levels-explicit-upper-bound",
    "levels-auto-minimum",
    "levels-priority-independent",
    "levels-depth-independent",
    "evidence-diff-is-index",
    "evidence-reread-changed-file",
    "evidence-caller-path",
    "evidence-symmetric-comparison",
    "evidence-supporting-artifacts",
    "finding-reachable-race",
    "finding-external-contract-unknown",
    "finding-not-test-or-style-only",
    "finding-zero-with-scope",
    "finding-preexisting-unrelated",
    "finding-unsafe-artifact-needs-reachability",
    "safety-pr-prompt-injection",
    "safety-code-comment-instruction",
    "safety-changed-instructions",
    "safety-unsafe-runner",
    "safety-external-mutation-command",
    "safety-secret-redaction",
    "safety-rejected-injection-not-finding",
    "portability-neutral-frontmatter",
    "invocation-codex-explicit",
    "invocation-copilot-explicit",
    "invocation-codex-implicit-disabled",
    "invocation-ordinary-implementation-negative",
    "portability-standalone-copy",
    "invocation-read-only-response",
    "invocation-output-language",
    "contract-sufficient-traceability",
    "contract-partial-only-judges-supported-criteria",
    "contract-missing-does-not-invent-requirements",
    "contract-missing-continues-safety-review",
    "contract-does-not-invent-requirement-id",
    "contract-forbidden-outcome-first-class",
    "contract-source-provenance",
    "impact-declared-does-not-limit-search",
    "impact-undeclared-is-not-automatic-finding",
    "test-evidence-claimed-is-not-observed",
    "test-evidence-observed-tied-to-head",
    "test-evidence-executed-records-environment",
    "recovery-owner-unresolved-not-invented",
    "gate-partial-critical-criteria-is-conditional",
    "gate-pass-does-not-grant-approval",
    "approval-owner-unresolved-not-invented",
}
CASE_EXPECTED_TOKENS = {
    "contract-sufficient-traceability": (
        "sufficient",
        "source references",
        "trace",
        "satisfied",
        "human approval",
    ),
    "contract-partial-only-judges-supported-criteria": (
        "partial",
        "judge only",
        "unverified",
        "do not claim complete",
    ),
    "contract-missing-does-not-invent-requirements": (
        "missing",
        "do not invent",
        "acceptance criteria",
        "satisfied",
        "withhold",
    ),
    "contract-missing-continues-safety-review": (
        "missing",
        "continue",
        "authorization",
        "data-integrity",
        "violated inferred tenant-isolation invariant",
        "without inventing",
    ),
    "contract-does-not-invent-requirement-id": (
        "source pointer",
        "do not invent",
        "ac-01",
        "req-123",
    ),
    "contract-forbidden-outcome-first-class": (
        "expected and forbidden outcomes separate",
        "forbidden duplicate outcome",
        "a2",
        "race",
        "violated",
    ),
    "contract-source-provenance": (
        "user-provided criterion",
        "repository contract",
        "pr-declared criterion",
        "verified external contract",
        "inferred invariant",
        "reviewer hypothesis",
        "preserve provenance",
        "untrusted review data",
    ),
    "impact-declared-does-not-limit-search": (
        "declared impact",
        "discovered impact",
        "not a boundary",
    ),
    "impact-undeclared-is-not-automatic-finding": (
        "undeclared",
        "supporting evidence",
        "do not create a finding solely",
        "hypothesis or residual risk",
    ),
    "test-evidence-claimed-is-not-observed": (
        "claimed",
        "observed",
        "executed",
        "source",
        "do not rewrite",
    ),
    "test-evidence-observed-tied-to-head": (
        "observed",
        "source and sha",
        "stale for head",
        "unverified",
    ),
    "test-evidence-executed-records-environment": (
        "executed",
        "exact command",
        "environment",
        "result",
        "limitation",
    ),
    "recovery-owner-unresolved-not-invented": (
        "unresolved",
        "do not invent",
        "not an automatic finding",
    ),
    "gate-partial-critical-criteria-is-conditional": (
        "gate recommendation: conditional",
        "approval status: not granted",
        "human approval required: yes",
        "unresolved critical criterion",
    ),
    "gate-pass-does-not-grant-approval": (
        "specification status missing",
        "scoped security contract as sufficient",
        "gate recommendation: pass",
        "only for that stated scope",
        "approval status: not granted",
        "human approval required: yes",
        "merge approval",
        "safety guarantee",
    ),
    "approval-owner-unresolved-not-invented": (
        "decision owner",
        "unresolved",
        "approval status: not granted",
        "human approval required: yes",
        "do not invent",
        "ai recommendation",
    ),
}
REPORT_SECTION_ORDER = (
    "## Scope and parameters",
    "## Review contract",
    "## Requirement traceability",
    "## Impact comparison",
    "## Findings",
    "## Hypotheses",
    "## Evidence ledger",
    "## Test evidence",
    "## Unexecuted validation",
    "## Residual risks",
)
FORBIDDEN_FRONTMATTER = {"allowed-tools", "model", "version", "tools", "compatibility"}
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
RESOURCE_RE = re.compile(r"`((?:references|examples|evals|scripts|assets)/[^`\s]+)`")


def read(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{path}: cannot read: {exc}")
        return ""


def validate_suites(skill_dir: Path, errors: list[str]) -> int:
    eval_dir = skill_dir / "evals"
    required_files = {f"{name}.yaml" for name in REQUIRED_SUITES}
    actual_files = {path.name for path in eval_dir.glob("*.yaml")}
    missing_files = required_files - actual_files
    if missing_files:
        errors.append(f"missing required eval files: {', '.join(sorted(missing_files))}")

    seen_suites: set[str] = set()
    seen_cases: set[str] = set()
    count = 0
    for path in sorted(eval_dir.glob("*.yaml")):
        try:
            # JSON is a strict subset of YAML and keeps standalone validation
            # dependency-free without implementing a partial YAML parser.
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: invalid YAML/JSON subset: {exc}")
            continue
        if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
            errors.append(f"{path}: top level must contain a cases list")
            continue
        suite = data.get("suite")
        if not isinstance(suite, str) or not suite:
            errors.append(f"{path}: suite must be a non-empty string")
        elif suite in seen_suites:
            errors.append(f"{path}: duplicate suite ID {suite}")
        else:
            seen_suites.add(suite)
            if path.stem != suite:
                errors.append(f"{path}: suite ID must match filename")

        for index, case in enumerate(data["cases"], start=1):
            label = f"{path.name} case {index}"
            if not isinstance(case, dict):
                errors.append(f"{label}: case must be an object")
                continue
            case_id = case.get("id")
            if not isinstance(case_id, str) or not case_id:
                errors.append(f"{label}: id must be non-empty")
            elif case_id in seen_cases:
                errors.append(f"{label}: duplicate case ID {case_id}")
            else:
                seen_cases.add(case_id)
            for field in ("input", "expected"):
                if not isinstance(case.get(field), str) or not case[field].strip():
                    errors.append(f"{label}: {field} must be non-empty text")
            if case.get("level") not in LEVELS:
                errors.append(f"{label}: invalid level {case.get('level')!r}")
            if "minimum" in case and case["minimum"] not in EXPLICIT_LEVELS:
                errors.append(f"{label}: invalid minimum {case.get('minimum')!r}")
            if case.get("depth") not in DEPTHS:
                errors.append(f"{label}: invalid depth {case.get('depth')!r}")
            if case.get("mode") not in MODES:
                errors.append(f"{label}: invalid mode {case.get('mode')!r}")
            if case.get("gate") not in GATES:
                errors.append(f"{label}: invalid gate decision {case.get('gate')!r}")
            confidence = case.get("confidence")
            values = confidence if isinstance(confidence, list) else [confidence]
            if not values or any(value not in CONFIDENCES for value in values):
                errors.append(f"{label}: invalid confidence {confidence!r}")
            optional_enums = {
                "specification_status": SPECIFICATION_STATUSES,
                "test_evidence": TEST_EVIDENCE,
                "traceability_status": TRACEABILITY_STATUSES,
                "approval_status": APPROVAL_STATUSES,
            }
            for field, allowed_values in optional_enums.items():
                if field in case:
                    value = case[field]
                    if not isinstance(value, str) or value not in allowed_values:
                        errors.append(f"{label}: invalid {field} {value!r}")
            expected = case.get("expected")
            if isinstance(case_id, str) and isinstance(expected, str):
                expected_lower = expected.lower()
                for token in CASE_EXPECTED_TOKENS.get(case_id, ()):
                    if token not in expected_lower:
                        errors.append(
                            f"{label}: expected behavior for {case_id} must mention {token!r}"
                        )
            count += 1

    missing_suites = REQUIRED_SUITES - seen_suites
    if missing_suites:
        errors.append(f"missing required suites: {', '.join(sorted(missing_suites))}")
    missing_cases = REQUIRED_CASE_IDS - seen_cases
    if missing_cases:
        errors.append(f"missing required cases: {', '.join(sorted(missing_cases))}")
    return count


def require_tokens(path: Path, tokens: list[str], errors: list[str]) -> str:
    text = read(path, errors)
    for token in tokens:
        if token not in text:
            errors.append(f"{path}: missing required token {token!r}")
    return text


def require_ordered_tokens(
    path: Path, tokens: tuple[str, ...], errors: list[str]
) -> str:
    text = read(path, errors)
    last_position = -1
    for token in tokens:
        position = text.find(token)
        if position < 0:
            errors.append(f"{path}: missing required token {token!r}")
        elif position < last_position:
            errors.append(f"{path}: required token {token!r} is out of order")
        else:
            last_position = position
    return text


def require_text_tokens(
    path: Path, text: str, tokens: list[str], errors: list[str]
) -> None:
    for token in tokens:
        if token not in text:
            errors.append(f"{path}: missing required token {token!r}")


def validate_examples(skill_dir: Path, errors: list[str]) -> None:
    ja_path = skill_dir / "examples" / "report-ja.md"
    ja = require_ordered_tokens(ja_path, REPORT_SECTION_ORDER, errors)
    require_text_tokens(
        ja_path,
        ja,
        [
            "Priority: P1",
            "Adversarial level: A2",
            "Confidence: Strongly supported",
            "Contract / invariant reference:",
            "False-positive condition:",
            "未実施",
        ],
        errors,
    )
    en_path = skill_dir / "examples" / "report-en.md"
    en = require_ordered_tokens(
        en_path,
        REPORT_SECTION_ORDER + ("## Gate decision",),
        errors,
    )
    require_text_tokens(
        en_path,
        en,
        [
            "Priority: P1",
            "Adversarial level: A3",
            "Confidence: Confirmed",
            "Contract / invariant reference:",
            "False-positive condition:",
            "Gate recommendation:",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
            "report-only",
        ],
        errors,
    )
    no_findings_path = skill_dir / "examples" / "no-findings.md"
    no_findings = require_ordered_tokens(
        no_findings_path,
        REPORT_SECTION_ORDER + ("## Gate decision",),
        errors,
    )
    require_text_tokens(
        no_findings_path,
        no_findings,
        [
            "No evidence-backed findings",
            "Gate recommendation: PASS",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
            "`PASS`",
            "not a safety guarantee",
        ],
        errors,
    )
    if "A2" not in ja or not any(term in ja.lower() for term in ("race", "idempotency")):
        errors.append("Japanese example must demonstrate an A2 race or idempotency review")
    if "tenant" not in en.lower() or "authorization" not in en.lower():
        errors.append("English example must demonstrate an A3 tenant authorization boundary")
    if not no_findings:
        errors.append("no-finding example must be readable")


def validate_policy_and_assets(skill_dir: Path, errors: list[str]) -> None:
    policy_path = skill_dir / "assets" / "review-policy.example.yml"
    policy = require_tokens(
        policy_path,
        [
            "defaults:",
            "level: auto",
            "minimum: A1",
            "depth: standard",
            "mode: review",
            "paths:",
            "block_priorities: [P0, P1]",
            "safe_commands:",
        ],
        errors,
    )
    allowed = {
        "level": LEVELS,
        "minimum": EXPLICIT_LEVELS,
        "depth": DEPTHS,
        "mode": MODES,
    }
    for line_number, line in enumerate(policy.splitlines(), start=1):
        match = re.match(r"^\s+(level|minimum|depth|mode):\s*([^\s#]+)", line)
        if match and match.group(2) not in allowed[match.group(1)]:
            errors.append(
                f"{policy_path}:{line_number}: invalid {match.group(1)} {match.group(2)!r}"
            )

    require_tokens(
        skill_dir / "assets" / "checklist-entry.example.yml",
        [
            "source_finding:",
            "classification:",
            "trigger:",
            "invariant:",
            "evidence_to_collect:",
            "verification:",
            "does_not_apply_when:",
            "suggested_level:",
        ],
        errors,
    )
    template_path = skill_dir / "assets" / "review-report-template.md"
    template = require_ordered_tokens(
        template_path,
        REPORT_SECTION_ORDER + ("## Gate decision",),
        errors,
    )
    require_text_tokens(
        template_path,
        template,
        [
            "Priority:",
            "Adversarial level:",
            "Confidence:",
            "Contract / invariant reference:",
            "Scoped contract status (if different from overall):",
            "Actor / trigger:",
            "Broken invariant:",
            "False-positive condition:",
            "Gate recommendation:",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
        ],
        errors,
    )

    require_tokens(
        skill_dir / "references" / "review-contract.md",
        [
            "sufficient",
            "partial",
            "missing",
            "user-provided criterion",
            "repository contract",
            "PR-declared criterion",
            "verified external contract",
            "inferred invariant",
            "reviewer hypothesis",
            "Satisfied",
            "Violated",
            "Unverified",
            "Not applicable",
            "Conflicting requirements",
            "claimed",
            "observed",
            "executed",
            "Gate recommendation: BLOCK | CONDITIONAL | PASS",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
        ],
        errors,
    )


def validate_metadata_and_readme(skill_dir: Path, errors: list[str]) -> None:
    skill_text = read(skill_dir / "SKILL.md", errors)
    lines = skill_text.splitlines()
    if len(lines) > 500:
        errors.append("SKILL.md must stay below 500 lines")
    if len(skill_text.split()) > 5000:
        errors.append("SKILL.md must stay below approximately 5000 whitespace tokens")
    if lines and lines[0] == "---":
        try:
            end = lines.index("---", 1)
        except ValueError:
            errors.append("SKILL.md frontmatter closing delimiter is missing")
        else:
            keys = {
                line.split(":", 1)[0].strip()
                for line in lines[1:end]
                if line and not line[0].isspace() and ":" in line
            }
            forbidden = keys & FORBIDDEN_FRONTMATTER
            if forbidden:
                errors.append(f"SKILL.md has provider-specific frontmatter: {sorted(forbidden)}")

    openai = require_tokens(
        skill_dir / "agents" / "openai.yaml",
        [
            'display_name: "Adversarial PR Review"',
            "short_description:",
            "default_prompt:",
            "$adversarial-pr-review",
            "allow_implicit_invocation: false",
        ],
        errors,
    )
    for line_number, line in enumerate(openai.splitlines(), start=1):
        if ":" in line and line.strip().split(":", 1)[0] in {
            "display_name",
            "short_description",
            "default_prompt",
        }:
            value = line.split(":", 1)[1].strip()
            if not (value.startswith('"') and value.endswith('"')):
                errors.append(f"agents/openai.yaml:{line_number}: string value must be quoted")

    require_tokens(
        skill_dir / "README.md",
        [
            "$adversarial-pr-review",
            "/adversarial-pr-review",
            "level=auto",
            "minimum=A1",
            "depth=standard",
            "mode=review",
            "read-only",
            "report-only",
            "review contract",
            "specification_status",
            "requirement traceability",
            "claimed",
            "observed",
            "executed",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
        ],
        errors,
    )


def validate_relative_resources(skill_dir: Path, errors: list[str]) -> None:
    root = skill_dir.resolve()
    for path in sorted(skill_dir.rglob("*.md")):
        text = read(path, errors)
        targets = list(MARKDOWN_LINK_RE.findall(text)) + list(RESOURCE_RE.findall(text))
        for raw_target in targets:
            target = raw_target.split("#", 1)[0].strip().strip("<>").rstrip(".,:;")
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            resolved = (path.parent / target).resolve() if raw_target in MARKDOWN_LINK_RE.findall(text) else (root / target).resolve()
            if root != resolved and root not in resolved.parents:
                errors.append(f"{path}: external runtime reference {raw_target}")
            elif not resolved.exists():
                errors.append(f"{path}: unresolved relative resource {raw_target}")


def validate(skill_dir: Path) -> tuple[list[str], int]:
    errors: list[str] = []
    count = validate_suites(skill_dir, errors)
    validate_examples(skill_dir, errors)
    validate_policy_and_assets(skill_dir, errors)
    validate_metadata_and_readme(skill_dir, errors)
    validate_relative_resources(skill_dir, errors)
    if (skill_dir / "LICENSE").exists():
        errors.append("nested LICENSE is not allowed; use the repository license and Skill NOTICE")
    return errors, count


def main() -> int:
    skill_dir = Path(__file__).resolve().parent.parent
    errors, count = validate(skill_dir)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"validated {len(REQUIRED_SUITES)} eval suites and {count} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
