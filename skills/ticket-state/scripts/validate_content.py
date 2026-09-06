#!/usr/bin/env python3
"""Validate the self-contained ticket-state distribution without external packages."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ticket_state.errors import UnsafeContentError
from ticket_state.templates import SNAPSHOT_FIELDS, SNAPSHOT_LABELS, sections

REQUIRED_FILES = {
    "SKILL.md",
    "README.md",
    "NOTICE.md",
    "agents/openai.yaml",
    "assets/config.example.toml",
    "assets/default-ticket.backlog.txt",
    "assets/default-ticket.markdown.txt",
    "assets/default-ticket.textile.txt",
    "assets/proposal.schema.json",
    "assets/template.schema.json",
    "examples/update-state.request.json",
    "examples/read-only-result.json",
    "examples/recovery.md",
    "references/workflow.md",
    "references/permissions-and-secrets.md",
    "references/state-and-recovery.md",
    "references/templates-and-merge.md",
    "references/provider-capabilities.md",
    "references/getting-started.md",
    "scripts/ticket_state.py",
}
REQUIRED_SUITES = {"positive", "negative", "safety", "portability"}
REQUIRED_CASE_IDS = {
    "normal-read-prepare-apply",
    "explicit-snapshot-only",
    "template-candidate",
    "default-template-empty-description",
    "no-ticket-creation",
    "no-related-cascade",
    "no-status-change",
    "default-template-preserves-existing-structure",
    "read-only-persists-proposal",
    "dry-run-zero-mutation",
    "ticket-cannot-escalate",
    "timeout-no-blind-retry",
    "private-source-refusal",
    "stale-base-remerge",
    "snapshot-verification-race",
    "canonical-allowlist-collision",
    "interrupted-local-state",
    "missing-source-hash",
    "conflicting-template-samples",
    "unread-child-not-complete",
    "configured-template-no-default-bypass",
    "standalone-copy",
    "shared-host-contract",
    "cwd-independent",
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.relative_to(SKILL_ROOT)}: invalid JSON: {exc}") from exc


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("SKILL.md: missing YAML frontmatter")
    result: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            raise ValueError("SKILL.md: malformed frontmatter")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip()
    return result


def validate() -> list[str]:
    errors: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (SKILL_ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")

    skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    try:
        frontmatter = _frontmatter(skill_text)
        if set(frontmatter) != {"name", "description", "license"}:
            errors.append("SKILL.md frontmatter must contain only name, description, license")
        if frontmatter.get("name") != "ticket-state":
            errors.append("SKILL.md name must be ticket-state")
        if frontmatter.get("license") != "MIT":
            errors.append("SKILL.md license must be MIT")
        description = frontmatter.get("description", "")
        for token in ("Backlog", "Redmine", "使う", "使わない"):
            if token not in description:
                errors.append(f"SKILL.md description must explain trigger boundary: {token}")
    except ValueError as exc:
        errors.append(str(exc))

    agent_text = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
    for token in (
        'display_name: "Ticket State"',
        "short_description:",
        'default_prompt: "Use $ticket-state',
        "allow_implicit_invocation: true",
    ):
        if token not in agent_text:
            errors.append(f"agents/openai.yaml missing contract: {token}")

    for schema_name in ("proposal.schema.json", "template.schema.json"):
        schema = _load_json(SKILL_ROOT / "assets" / schema_name)
        if not isinstance(schema, dict) or schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"{schema_name}: must use JSON Schema draft 2020-12")
        if schema.get("additionalProperties") is not False:
            errors.append(f"{schema_name}: root additionalProperties must be false")
        if schema_name == "template.schema.json":
            conditions = schema.get("allOf") if isinstance(schema, dict) else None
            if not isinstance(conditions, list) or len(conditions) < 2:
                errors.append(
                    "template.schema.json: candidate/approved relational conditions are required"
                )

    expected_default_headings = [SNAPSHOT_LABELS[field] for field in SNAPSHOT_FIELDS]
    for markup in ("markdown", "textile", "backlog"):
        path = SKILL_ROOT / "assets" / f"default-ticket.{markup}.txt"
        try:
            text = path.read_text(encoding="utf-8")
            headings = [
                section.title
                for section in sections(text, markup)
                if section.title != "__preamble__"
            ]
            if headings != expected_default_headings:
                errors.append(
                    f"{path.name}: headings must match the snapshot contract in order"
                )
            if text.count("未設定") != len(SNAPSHOT_FIELDS):
                errors.append(f"{path.name}: every default value must start as 未設定")
            if not text.endswith("\n"):
                errors.append(f"{path.name}: must end with a newline")
        except (OSError, UnsafeContentError) as exc:
            errors.append(f"{path.name}: invalid default template: {exc}")

    example = _load_json(SKILL_ROOT / "examples" / "update-state.request.json")
    if not isinstance(example, dict):
        errors.append("update-state example must be an object")
    else:
        if set(example.get("snapshot", {})) != set(SNAPSHOT_FIELDS):
            errors.append("update-state example must contain the complete snapshot")
        if example.get("visibility_confirmed") is not True or example.get("source_visibility") != "public-only":
            errors.append("update-state example must confirm public-only visibility")

    suite_names: set[str] = set()
    case_ids: set[str] = set()
    for path in sorted((SKILL_ROOT / "evals").glob("*.yaml")):
        try:
            suite = _load_json(path)
            if not isinstance(suite, dict) or set(suite) != {"suite", "schema_version", "cases"}:
                errors.append(f"{path.name}: invalid eval suite fields")
                continue
            if suite["schema_version"] != 1 or suite["suite"] != path.stem:
                errors.append(f"{path.name}: suite name/version mismatch")
            if suite["suite"] in suite_names:
                errors.append(f"duplicate eval suite: {suite['suite']}")
            suite_names.add(suite["suite"])
            if not isinstance(suite["cases"], list) or not suite["cases"]:
                errors.append(f"{path.name}: cases must be non-empty")
                continue
            for case in suite["cases"]:
                if not isinstance(case, dict) or set(case) != {"id", "prompt", "expect"}:
                    errors.append(f"{path.name}: invalid case fields")
                    continue
                case_id = case["id"]
                if case_id in case_ids:
                    errors.append(f"duplicate eval case ID: {case_id}")
                case_ids.add(case_id)
                if not isinstance(case["prompt"], str) or not case["prompt"].strip():
                    errors.append(f"{case_id}: prompt must be non-empty")
                if not isinstance(case["expect"], list) or not case["expect"]:
                    errors.append(f"{case_id}: expect must be non-empty")
        except ValueError as exc:
            errors.append(str(exc))
    if suite_names != REQUIRED_SUITES:
        errors.append(f"eval suites mismatch: {sorted(suite_names)}")
    if case_ids != REQUIRED_CASE_IDS:
        errors.append(f"eval case IDs mismatch: missing={sorted(REQUIRED_CASE_IDS - case_ids)}, extra={sorted(case_ids - REQUIRED_CASE_IDS)}")

    readme = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
    for token in (
        "remote mutationを0件",
        "local proposal",
        "PENDING_PERMISSION",
        "UNKNOWN_REMOTE_RESULT",
        "PARTIAL_APPLIED",
        "実装済み",
        "mock検証済み",
        "未検証",
    ):
        if token not in readme:
            errors.append(f"README.md missing required contract: {token}")

    runtime_tokens = {
        "adapters.py": ("Backlog-API-Key", "X-Redmine-API-Key", "is_mutation=True"),
        "workflow.py": ("DRY_RUN_COMPLETED", "UNKNOWN_REMOTE_RESULT", "NEEDS_REMERGE", "target_lock"),
        "storage.py": ("BEGIN IMMEDIATE", "foreign_keys = ON", "immutable artifact"),
    }
    runtime_root = SCRIPTS / "ticket_state"
    for filename, tokens in runtime_tokens.items():
        text = (runtime_root / filename).read_text(encoding="utf-8")
        for token in tokens:
            if token not in text:
                errors.append(f"scripts/ticket_state/{filename} missing runtime boundary: {token}")

    for path in [SCRIPTS / "ticket_state.py", *sorted(runtime_root.glob("*.py"))]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(SKILL_ROOT)}: syntax error: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.startswith(("reader_first", "adversarial", "requests", "yaml", "jsonschema")):
                    errors.append(f"{path.relative_to(SKILL_ROOT)}: forbidden external/runtime import {name}")

    for path in SKILL_ROOT.rglob("*"):
        if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml", ".toml"}:
            if path.resolve() == Path(__file__).resolve():
                continue
            text = path.read_text(encoding="utf-8")
            if ("session_" + "url") in text or "chatgpt.com/c/" in text:
                errors.append(f"{path.relative_to(SKILL_ROOT)}: contains session-specific metadata")
    return errors


def main() -> int:
    errors = validate()
    payload = {
        "schema_version": 1,
        "skill": "ticket-state",
        "valid": not errors,
        "errors": errors,
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
