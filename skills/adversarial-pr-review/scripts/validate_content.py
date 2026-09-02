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
REQUIRED_CASES_BY_SUITE = {
    "coverage-gap-audit": {
        "coverage-pr2-propagation-all-producers",
        "coverage-pr2-repository-rule-companion-example",
        "coverage-pr2-relational-oracle-invariants",
        "coverage-finding-count-is-not-completion",
        "coverage-verification-does-not-replace-blind-pass",
        "coverage-doc-only-change-no-companion-finding",
        "coverage-intentional-single-producer-not-applicable",
        "coverage-dynamic-route-remains-unverified",
        "coverage-no-new-finding-still-reports-evidence",
    },
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
CANONICAL_FIXTURE_DIGESTS = {
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
    "coverage-finding-count-is-not-completion": {
        "input": "cfa918a2435f6b2395b88da547f0ab04d5ef421805633724de5d94ae482c13b8",
        "expected": "b421203662721327487ec556b5ec7d22e36803b35714c1c3835b5b8e9e9ac6e3",
    },
    "coverage-verification-does-not-replace-blind-pass": {
        "input": "b138bd1c152667f1cc0590fbe4d3a103eb4ee46aeaa5157bf54a3f66efa13854",
        "expected": "c5d3cb8ae4d781804823aaedc3d90dd3b7d834fdef94201f076596a34b11aeba",
    },
    "coverage-doc-only-change-no-companion-finding": {
        "input": "a35409442d058d1c6364ee3f8a13049d36017f54a7c791d1361b86ff650f3c3a",
        "expected": "a4fda624f014d1a632efd87ecbfca0718a3794b2036e53978fc0cfa8126c06c2",
    },
    "coverage-intentional-single-producer-not-applicable": {
        "input": "53757e5b959760e6e80c91cf87911901986c429ab20286821512642a8f4d8a4d",
        "expected": "81477b66d29b56e17d9b6d9bfe1e789b538b36b080cc4f6c9da5d68d83dd94bb",
    },
    "coverage-dynamic-route-remains-unverified": {
        "input": "abfa09d66bfe61a9a15404015cd24c0a983c5a1aa2c06853efa1bb251124321d",
        "expected": "2a545b500b91607ca207be4608b6655002c34fc7b10a585c536b859062d32369",
    },
    "coverage-no-new-finding-still-reports-evidence": {
        "input": "7dfc6ad867c9cd11ae7425359db8ab7ca6915a697279626c8c24ab8e0f25baa1",
        "expected": "7abb95a37ed9d74f5c5105bc64e9cc1b13acfec053b742d0270cd06397379935",
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
HTML_BLOCK_TAG_RE = re.compile(
    r"^</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|"
    r"col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
    r"footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|"
    r"link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|"
    r"section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)"
    r"(?=[ \t/>]|$)",
    re.IGNORECASE,
)
HTML_COMPLETE_TAG_RE = re.compile(
    r"^</?[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:[^ \"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*"
    r"[ \t]*/?>[ \t]*$"
)


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
    seen_cases_by_suite: dict[str, set[str]] = {}
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
        suite_cases: set[str] | None = None
        if not isinstance(suite, str) or not suite:
            errors.append(f"{path}: suite must be a non-empty string")
        elif suite in seen_suites:
            errors.append(f"{path}: duplicate suite ID {suite}")
        else:
            seen_suites.add(suite)
            if path.stem != suite:
                errors.append(f"{path}: suite ID must match filename")
            suite_cases = seen_cases_by_suite.setdefault(suite, set())

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
            if suite_cases is not None and isinstance(case_id, str) and case_id:
                suite_cases.add(case_id)
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
            if isinstance(case_id, str) and case_id in CANONICAL_FIXTURE_DIGESTS:
                canonical_digests = CANONICAL_FIXTURE_DIGESTS[case_id]
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
    for suite, required_cases in REQUIRED_CASES_BY_SUITE.items():
        missing_suite_cases = required_cases - seen_cases_by_suite.get(suite, set())
        if missing_suite_cases:
            errors.append(
                f"missing required cases for suite {suite}: "
                f"{', '.join(sorted(missing_suite_cases))}"
            )
    return count


def require_tokens(path: Path, tokens: list[str], errors: list[str]) -> str:
    text = read(path, errors)
    for token in tokens:
        if token not in text:
            errors.append(f"{path}: missing required token {token!r}")
    return text


def _strip_html_comments(line: str, in_comment: bool) -> tuple[str, bool]:
    visible_parts: list[str] = []
    remainder = line
    while True:
        if in_comment:
            comment_end = remainder.find("-->")
            if comment_end < 0:
                return "".join(visible_parts), True
            remainder = remainder[comment_end + 3 :]
            in_comment = False

        comment_start = remainder.find("<!--")
        if comment_start < 0:
            visible_parts.append(remainder)
            return "".join(visible_parts), False
        visible_parts.append(remainder[:comment_start])
        remainder = remainder[comment_start + 4 :]
        in_comment = True


def _raw_html_block_end(line: str) -> str | None:
    """Return an end pattern for a CommonMark raw HTML block start."""
    leading_spaces = len(line) - len(line.lstrip(" "))
    if leading_spaces > 3:
        return None
    stripped = line[leading_spaces:]

    tag_match = re.match(
        r"^<(script|pre|style|textarea)(?=[ \t>])", stripped, re.IGNORECASE
    )
    if tag_match:
        return rf"</{re.escape(tag_match.group(1))}[ \t]*>"
    if stripped.startswith("<?"):
        return r"\?>"
    if re.match(r"^<![A-Z]", stripped):
        return r">"
    if stripped.startswith("<![CDATA["):
        return r"\]\]>"
    if HTML_BLOCK_TAG_RE.match(stripped) or HTML_COMPLETE_TAG_RE.fullmatch(stripped):
        # CommonMark block-tag and complete-tag blocks end at the next blank line.
        return ""
    return None


def _visible_markdown_lines(text: str) -> list[str]:
    """Return visible Markdown lines, excluding code and raw HTML blocks."""
    visible_lines: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    html_block_end: str | None = None
    in_html_comment = False

    for raw_line in text.splitlines():
        if fence_char is not None:
            closing_match = re.fullmatch(
                r"[ ]{0,3}([`~]{3,})[ \t]*", raw_line
            )
            if closing_match:
                marker = closing_match.group(1)
                if (
                    len(set(marker)) == 1
                    and marker[0] == fence_char
                    and len(marker) >= fence_length
                ):
                    fence_char = None
                    fence_length = 0
            continue

        if html_block_end is not None:
            if html_block_end == "":
                if not raw_line.strip():
                    html_block_end = None
            elif re.search(html_block_end, raw_line, re.IGNORECASE):
                html_block_end = None
            continue

        # A CommonMark HTML comment block consumes its complete closing line.
        # Text after ``-->`` on that line is not a Markdown heading.
        html_comment_block_line = in_html_comment or bool(
            re.match(r"^[ ]{0,3}<!--", raw_line)
        )
        line, in_html_comment = _strip_html_comments(raw_line, in_html_comment)
        if html_comment_block_line:
            continue
        if not line and in_html_comment:
            continue

        # Four-space and tab-indented lines are indented code blocks. Check
        # this before fence parsing so an indented fence is not treated as a
        # real delimiter.
        if line.startswith("    ") or line.startswith("\t"):
            continue

        opening_match = re.match(r"^[ ]{0,3}([`~]{3,})", line)
        if opening_match:
            marker = opening_match.group(1)
            if len(set(marker)) == 1:
                fence_char = marker[0]
                fence_length = len(marker)
                continue

        raw_html_end = _raw_html_block_end(line)
        if raw_html_end is not None:
            if raw_html_end == "" or not re.search(
                raw_html_end, line, re.IGNORECASE
            ):
                html_block_end = raw_html_end
            continue

        visible_lines.append(line)

    return visible_lines


def require_ordered_tokens(
    path: Path, tokens: tuple[str, ...], errors: list[str]
) -> str:
    text = read(path, errors)
    heading_positions: dict[str, list[int]] = {}
    for line_number, line in enumerate(_visible_markdown_lines(text)):
        stripped = line.strip()
        if stripped.startswith("#"):
            heading_positions.setdefault(stripped, []).append(line_number)

    last_position = -1
    for token in tokens:
        positions = heading_positions.get(token, [])
        if not positions:
            errors.append(f"{path}: missing required token {token!r}")
            continue
        if len(positions) > 1:
            errors.append(f"{path}: heading {token!r} must occur exactly once")
        position = positions[0]
        if position < last_position:
            errors.append(f"{path}: required token {token!r} is out of order")
        last_position = position
    return text


def require_text_tokens(
    path: Path, text: str, tokens: list[str], errors: list[str]
) -> None:
    for token in tokens:
        if token not in text:
            errors.append(f"{path}: missing required token {token!r}")


def _repository_label(
    path: Path, lines: list[str], errors: list[str]
) -> tuple[bool, str | None]:
    label_lines = [line for line in lines if line.startswith("- Repository label:")]
    if len(label_lines) != 1:
        errors.append(f"{path}: must contain exactly one repository label")
        return False, None

    label_line = label_lines[0]
    if label_line == "- Repository label: unverified":
        return True, None

    label_match = re.fullmatch(r"- Repository label:\s+`([^`]+)`", label_line)
    if not label_match:
        errors.append(f"{path}: repository label must be verified or unverified")
        return False, None
    repository_label = label_match.group(1)
    if (
        repository_label in {".", ".."}
        or repository_label.startswith("~")
        or any(separator in repository_label for separator in ("/", "\\", ":"))
        or any(ord(character) < 32 for character in repository_label)
    ):
        errors.append(f"{path}: repository label must be a portable path component")
        return False, None
    return True, repository_label


def _validate_location_entries(
    path: Path, text: str, errors: list[str], *, require_single: bool
) -> None:
    lines = _visible_markdown_lines(text)
    valid_label, repository_label = _repository_label(path, lines, errors)
    if not valid_label:
        return

    location_indexes = [
        index for index, line in enumerate(lines) if line.startswith("- Location:")
    ]
    if require_single and len(location_indexes) != 1:
        errors.append(f"{path}: must contain exactly one Location line")
        return
    if not require_single and not location_indexes:
        errors.append(f"{path}: must contain at least one Location line")
        return

    for position, location_index in enumerate(location_indexes):
        next_location = (
            location_indexes[position + 1]
            if position + 1 < len(location_indexes)
            else len(lines)
        )
        location_block = lines[location_index:next_location]
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
            continue
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
            symbol_lines = [
                line for line in location_block if line.startswith("- Confirmed symbol:")
            ]
            status_lines = [
                line
                for line in location_block
                if line.startswith("- Location line status:")
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
            for line in location_block
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
            continue

        if repository_label is not None:
            if not path_text.startswith(f"{repository_label}/"):
                errors.append(f"{path}: Location must start with verified repository label")
        elif path_text.startswith("unverified/"):
            errors.append(f"{path}: Location must not invent an unverified label prefix")


def validate_example_location(path: Path, text: str, errors: list[str]) -> None:
    _validate_location_entries(path, text, errors, require_single=True)


def validate_coverage_example_locations(path: Path, text: str, errors: list[str]) -> None:
    lines = _visible_markdown_lines(text)
    finding_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        finding_match = re.match(r"^### (F-\d{3})(?::|$)", line)
        if finding_match:
            finding_starts.append((index, finding_match.group(1)))

    if not finding_starts:
        errors.append(f"{path}: coverage example must contain at least one finding")
    for position, (start, finding_id) in enumerate(finding_starts):
        end = (
            finding_starts[position + 1][0]
            if position + 1 < len(finding_starts)
            else len(lines)
        )
        next_section = next(
            (
                index
                for index in range(start + 1, end)
                if lines[index].startswith(("## ", "### "))
            ),
            end,
        )
        location_count = sum(
            line.startswith("- Location:") for line in lines[start + 1 : next_section]
        )
        if location_count != 1:
            errors.append(
                f"{path}: finding {finding_id} must contain exactly one Location line"
            )

    _validate_location_entries(path, text, errors, require_single=False)


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
            "Identifier scope: new report",
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
            "Identifier scope: new report",
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
            "Identifier scope: new report",
            "Gate recommendation: PASS",
            "Approval status: NOT GRANTED",
            "Human approval required: yes",
            "`PASS`",
            "not a safety guarantee",
            "Initial findings were not used as the completion criterion",
            "No additional candidate was found",
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
            "Identifier scope: new report",
            "alternate producer",
            "paired presence",
            "base `AGENTS.md`",
            "Not applicable",
            "Unverified",
            "docs-only",
            "discussion_r3917733760",
            "discussion_r3917733769",
            "discussion_r3917733777",
            "| synthetic fixture contract | claimed |",
            "static oracle only",
            "保存済みlogやCI resultもない",
        ],
        errors,
    )
    validate_coverage_example_locations(coverage_path, coverage, errors)


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
            "Identifier scope:",
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
            "report-local F-* IDs",
            "report-local hypotheses",
            "follow-up preserves existing E-* IDs",
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
            "制約、follow-upへ接続した `Unverified`",
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
            "identifier and numbering",
        ],
        errors,
    )

    require_tokens(
        skill_dir / "references" / "identifier-and-numbering.md",
        [
            "F-001",
            "H-001",
            "E-01",
            "review series",
            "APR-01",
            "source-preserved",
            "CO-001",
            "RI-001",
            "RO-001",
            "AC-01",
            "REQ-123",
            "RR-01",
            "rfe-*",
            "rfi-*",
            "CHUNK-0001",
            "採番しない項目",
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
            "制約、follow-upへ接続した `Unverified`",
            "identifier and numbering",
            "checklist-only operation",
            "full-review sectionsは省略できる",
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
            "identifier and numbering",
            "checklist-only operation",
            "full-review output contract",
            "Coverage gap audit",
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
