#!/usr/bin/env python3
"""Validate adversarial-pr-review fixtures, examples, policy, and portability."""

from __future__ import annotations

import hashlib
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
    "coverage-gap-audit",
    "evidence-and-findings",
    "safety-and-prompt-injection",
    "portability-and-invocation",
    "review-contract-and-approval",
}
REQUIRED_CASE_IDS = {
    "coverage-pr2-propagation-all-producers",
    "coverage-pr2-repository-rule-companion-example",
    "coverage-pr2-relational-oracle-invariants",
    "coverage-finding-count-is-not-completion",
    "coverage-verification-does-not-replace-blind-pass",
    "coverage-doc-only-change-no-companion-finding",
    "coverage-intentional-single-producer-not-applicable",
    "coverage-dynamic-route-remains-unverified",
    "coverage-no-new-finding-still-reports-evidence",
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
    "finding-location-portable",
    "finding-location-no-absolute-link",
    "finding-location-unknown-boundary",
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
    "coverage-pr2-propagation-all-producers": (
        "13 findings",
        "blind pass",
        "every producer",
        "alternate producer",
        "allowlist",
        "transforms",
        "validator",
        "consumer",
        "caller-unavoidable",
    ),
    "coverage-pr2-repository-rule-companion-example": (
        "base instruction",
        "triggering behavior change",
        "head-side instruction as review data",
        "missing example",
        "fixed priority",
    ),
    "coverage-pr2-relational-oracle-invariants": (
        "paired presence",
        "non-empty cardinality",
        "exactly one status",
        "compatibility",
        "empty versus missing",
        "mode-dependent omission",
    ),
    "coverage-finding-count-is-not-completion": (
        "13 findings",
        "completion criterion",
        "blind pass",
        "change obligation",
    ),
    "coverage-verification-does-not-replace-blind-pass": (
        "verification",
        "blind-spot exploration",
        "separate work",
        "changed concepts",
        "alternate producer",
    ),
    "coverage-doc-only-change-no-companion-finding": (
        "behavior-change trigger does not apply",
        "not applicable",
        "docs-only evidence",
        "do not create",
    ),
    "coverage-intentional-single-producer-not-applicable": (
        "do not report missing propagation",
        "not applicable",
        "versioned contract",
        "dispatcher",
        "consumer evidence",
    ),
    "coverage-dynamic-route-remains-unverified": (
        "do not invent",
        "unverified",
        "hypothesis",
        "unexecuted validation",
        "residual risk",
    ),
    "coverage-no-new-finding-still-reports-evidence": (
        "no additional candidate",
        "inspected routes",
        "not applicable evidence",
        "inspection-separation limitation",
        "residual constraints",
        "proof of completeness",
    ),
    "finding-location-portable": (
        "visible inline locator",
        "repository-root-relative",
        "1-based line",
        "absolute checkout path",
        "markdown link",
    ),
    "finding-location-no-absolute-link": (
        "line-only label",
        "absolute target",
        "sample-repo/docs/policy.md:16",
        "without a markdown link",
    ),
    "finding-location-unknown-boundary": (
        "do not invent",
        "repository label: unverified",
        "docs/policy.md",
        "policytable",
        "location line status: unverified",
    ),
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
HISTORICAL_PROVENANCE = {
    "coverage-pr2-propagation-all-producers": (
        "mahcialet/agent-skills#2 @ "
        "8bf6c1ff9749a8736e4e4b6444883324465432c9 / discussion_r3917733760"
    ),
    "coverage-pr2-repository-rule-companion-example": (
        "mahcialet/agent-skills#2 @ "
        "8bf6c1ff9749a8736e4e4b6444883324465432c9 / discussion_r3917733769"
    ),
    "coverage-pr2-relational-oracle-invariants": (
        "mahcialet/agent-skills#2 @ "
        "8bf6c1ff9749a8736e4e4b6444883324465432c9 / discussion_r3917733777"
    ),
}
HISTORICAL_FIXTURE_DIGESTS = {
    "coverage-pr2-propagation-all-producers": {
        "input": "ae894fbfe0ae5382865d21a2a36be8032bf9a17494d6a7327ba3fda192ffca64",
        "expected": "293db3f795e115867ed270a4d274a258fbd59209a2af2241aedc8d05fdd4afa2",
    },
    "coverage-pr2-repository-rule-companion-example": {
        "input": "a50b4b2d0e098fff557c1f7f8e6442c18de25440ac12ac0082b7956aed12f733",
        "expected": "a97997bdaad2e48cd179c39592ee03677788ca02a329627127e8f9413b86162d",
    },
    "coverage-pr2-relational-oracle-invariants": {
        "input": "0380234976a5199e11ccfb6fab510630502b11e3a366e75c06f2c7d937394e2e",
        "expected": "40d5cf88a01897e788e5c892bd542f724e0638dd127b461a2026cb6c414641c2",
    },
}
REPORT_SECTION_ORDER = (
    "## Scope and parameters",
    "## Review contract",
    "## Requirement traceability",
    "## Impact comparison",
    "## Coverage gap audit",
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
            if isinstance(case_id, str) and case_id in HISTORICAL_PROVENANCE:
                provenance = case.get("provenance")
                if provenance != HISTORICAL_PROVENANCE[case_id]:
                    errors.append(
                        f"{label}: historical case {case_id} must preserve frozen provenance"
                    )
            if isinstance(case_id, str) and case_id in HISTORICAL_FIXTURE_DIGESTS:
                canonical_digests = HISTORICAL_FIXTURE_DIGESTS[case_id]
                for field in ("input", "expected"):
                    value = case.get(field)
                    if isinstance(value, str):
                        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                        if digest != canonical_digests[field]:
                            errors.append(
                                f"{label}: historical case {case_id} canonical "
                                f"{field} digest mismatch"
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


def validate_example_location(path: Path, text: str, errors: list[str]) -> None:
    lines = text.splitlines()
    label_lines = [line for line in lines if line.startswith("- Repository label:")]
    if len(label_lines) != 1:
        errors.append(f"{path}: must contain exactly one repository label")
        return

    label_line = label_lines[0]
    if label_line == "- Repository label: unverified":
        repository_label: str | None = None
    else:
        label_match = re.fullmatch(r"- Repository label:\s+`([^`]+)`", label_line)
        if not label_match:
            errors.append(f"{path}: repository label must be verified or unverified")
            return
        repository_label = label_match.group(1)
        if (
            repository_label in {".", ".."}
            or repository_label.startswith("~")
            or any(separator in repository_label for separator in ("/", "\\", ":"))
            or any(ord(character) < 32 for character in repository_label)
        ):
            errors.append(f"{path}: repository label must be a portable path component")
            return

    location_indexes = [
        index for index, line in enumerate(lines) if line.startswith("- Location:")
    ]
    if len(location_indexes) != 1:
        errors.append(f"{path}: must contain exactly one Location line")
        return
    location_index = location_indexes[0]
    location_line = lines[location_index]
    if (
        location_index + 1 < len(lines)
        and lines[location_index + 1].startswith((" ", "\t"))
    ):
        errors.append(f"{path}: Location must be a single-line field")
    if MARKDOWN_LINK_RE.search(location_line):
        errors.append(f"{path}: Location must not contain a Markdown link")

    location_match = re.fullmatch(r"- Location:\s+`([^`]+)`", location_line)
    if not location_match:
        errors.append(f"{path}: Location must contain only one inline locator")
        return
    locator = location_match.group(1)

    path_text, separator, line_text = locator.rpartition(":")
    line_match = re.fullmatch(r"([1-9]\d*)(?:-([1-9]\d*))?", line_text)
    has_verified_line = bool(separator and line_match)
    if has_verified_line:
        if line_match and line_match.group(2) and int(line_match.group(2)) < int(
            line_match.group(1)
        ):
            errors.append(f"{path}: Location line range must not be reversed")
    else:
        path_text = locator
        symbol_lines = [line for line in lines if line.startswith("- Confirmed symbol:")]
        status_lines = [
            line for line in lines if line.startswith("- Location line status:")
        ]
        if len(symbol_lines) > 1 or (
            symbol_lines
            and not re.fullmatch(r"- Confirmed symbol:\s+`[^`]+`", symbol_lines[0])
        ):
            errors.append(
                f"{path}: line-unverified Location has an invalid confirmed symbol"
            )
        if status_lines != ["- Location line status: unverified"]:
            errors.append(
                f"{path}: line-unverified Location must include unverified line status"
            )

    if has_verified_line and any(
        line.startswith(("- Confirmed symbol:", "- Location line status:"))
        for line in lines
    ):
        errors.append(f"{path}: verified line must not include fallback location fields")

    if (
        not path_text
        or path_text.startswith(("/", "\\", "~"))
        or "\\" in path_text
        or ":" in path_text
        or any(part in {"", ".", ".."} for part in path_text.split("/"))
        or any(ord(character) < 32 for character in path_text)
    ):
        errors.append(f"{path}: Location path must be a portable relative locator")
        return

    if repository_label is not None:
        if not path_text.startswith(f"{repository_label}/"):
            errors.append(f"{path}: Location must start with verified repository label")
    elif path_text.startswith("unverified/"):
        errors.append(f"{path}: Location must not invent an unverified label prefix")


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
            "Initial findings were not used as the completion criterion",
            "Change-obligation coverage",
            "Relational-invariant coverage",
            "Repository-rule obligations",
            "Blind-spot result",
        ],
        errors,
    )
    validate_example_location(ja_path, ja, errors)
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
            "Initial findings were not used as the completion criterion",
            "Change-obligation coverage",
            "Relational-invariant coverage",
            "Repository-rule obligations",
            "Blind-spot result",
        ],
        errors,
    )
    validate_example_location(en_path, en, errors)
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
            "Initial findings were not used as the completion criterion",
            "追加candidateはなかった",
            "Not applicable",
            "Unverified",
        ],
        errors,
    )
    if "A2" not in ja or not any(term in ja.lower() for term in ("race", "idempotency")):
        errors.append("Japanese example must demonstrate an A2 race or idempotency review")
    if "tenant" not in en.lower() or "authorization" not in en.lower():
        errors.append("English example must demonstrate an A3 tenant authorization boundary")
    if not no_findings:
        errors.append("no-finding example must be readable")

    coverage_path = skill_dir / "examples" / "coverage-gap-audit.md"
    coverage = require_ordered_tokens(coverage_path, REPORT_SECTION_ORDER, errors)
    require_text_tokens(
        coverage_path,
        coverage,
        [
            "13 findings",
            "alternate producer",
            "paired presence",
            "base `AGENTS.md`",
            "Not applicable",
            "Unverified",
            "docs-only",
            "discussion_r3917733760",
            "discussion_r3917733769",
            "discussion_r3917733777",
        ],
        errors,
    )


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
            "Repository label:",
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
            "<repository>/<repository-root-relative-path>:<line-or-range>",
            "<repository-root-relative-path>",
            "confirmed symbol",
            "line unverified",
            "- Location line status: unverified",
            "literal `unverified`",
            "Initial findings were not used as the completion criterion",
            "Change-obligation coverage",
            "Relational-invariant coverage",
            "Repository-rule obligations",
            "Blind-spot result",
        ],
        errors,
    )

    require_tokens(
        skill_dir / "references" / "coverage-gap-audit.md",
        [
            "Change-obligation coverage",
            "Relational-invariant audit",
            "Repository-rule obligation audit",
            "Inspected",
            "Not applicable",
            "Unverified",
            "findingが0件でも多数でも",
            "独立したread-only reviewer",
            "provider固有toolをcore workflowの必須条件にしない",
            "discussion_r3917733760",
            "discussion_r3917733769",
            "discussion_r3917733777",
        ],
        errors,
    )

    require_tokens(
        skill_dir / "references" / "finding-schema.md",
        [
            "repository-root-relative path",
            "<repository>/<path>:<line>",
            "absolute filesystem path",
            "行番号だけのlabel",
            "lineを創作せず",
            "canonical locator",
            "Location line status: unverified",
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
            "change_obligations",
            "repository_rule_obligations",
            "coverage-gap audit",
            "Gate recommendation: BLOCK | CONDITIONAL | PASS",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
        ],
        errors,
    )


def validate_metadata_and_readme(skill_dir: Path, errors: list[str]) -> None:
    skill_path = skill_dir / "SKILL.md"
    skill_text = read(skill_path, errors)
    require_text_tokens(
        skill_path,
        skill_text,
        [
            "repository root",
            "repository label",
            "portable locator",
            "absolute path",
            "行番号だけのlabel",
            "coverage-gap audit",
            "初回finding数を終了理由にせず",
            "paired presence",
            "base側のtrusted repository instruction",
            "independent inspectionを確保できなかった制約",
        ],
        errors,
    )
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
            "repository-root-relative path",
            "absolute path",
            "coverage-gap audit",
            "findingが0件でも多数でも",
            "producer、transform、serialization、validator、consumer",
            "paired presence",
            "base側repository",
            "provider固有のagent機能を必須にしません",
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
