#!/usr/bin/env python3
"""Dependency-free validator for experimental Behavior Profile packages."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import unquote, urlsplit


NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(
    r"^(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)\."
    r"(?:0|[1-9][0-9]*)"
    r"(?:-(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?:[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
FRONTMATTER_FIELDS = {"name", "version", "description", "status", "license"}
REQUIRED_HEADINGS = (
    "Identity",
    "Failure addressed",
    "Expected conduct",
    "Installation location",
    "Observable expectations",
    "Pressure test",
    "Completion evidence",
    "Bypass",
    "Limitations",
)
ROOT_REQUIRED_FILES = (
    "README.md",
    "FORMAT.md",
    "catalog.json",
    "EVIDENCE_TEMPLATE.json",
)
PROFILE_REQUIRED_FILES = (
    "BEHAVIOR_PROFILE.md",
    "README.md",
    "NOTICE.md",
    "evals/pressure-tests.json",
)
IAV_REQUIRED_TEMPLATES = (
    "REVIEW_REPORT_TEMPLATE.md",
    "REMEDIATION_REPORT_TEMPLATE.md",
    "CONSOLIDATED_REPORT_TEMPLATE.md",
    "REMEDIATION_REQUEST_TEMPLATE.md",
)
PRESSURE_TOP_FIELDS = {"schema_version", "profile", "fixtures"}
PRESSURE_CASE_FIELDS = {
    "id",
    "purpose",
    "operation_mode",
    "prompt",
    "fixture_path",
    "preconditions",
    "allowed_actions",
    "allowed_tools",
    "prohibited_actions",
    "expected_report_destination",
    "expected_observables",
    "expected_reviewer_writes",
    "expected_implementer_writes",
    "expected_stop_point",
    "expected_authorization_state",
    "classification_rule",
    "limitations",
}
CLASSIFICATIONS = {"PASS", "FAIL", "CONFUSED"}
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
MARKDOWN_REFERENCE_RE = re.compile(
    r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(<[^>]+>|[^\s]+)", re.MULTILINE
)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


class ProfileParseError(ValueError):
    """Raised for malformed canonical Profile frontmatter."""


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{path}: cannot read UTF-8 text: {exc}")
        return ""


def _load_json(path: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return None


def _parse_scalar(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value in {">", ">-", ">+", "|", "|-", "|+"}:
        raise ProfileParseError("frontmatter supports one-line scalar values only")
    if value[0] in {"'", '"'}:
        if len(value) < 2 or value[-1] != value[0]:
            raise ProfileParseError("quoted frontmatter scalar is not closed")
        if value[0] == '"':
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ProfileParseError(f"invalid quoted scalar: {exc}") from exc
            if not isinstance(decoded, str):
                raise ProfileParseError("quoted frontmatter scalar must be text")
            return decoded
        return value[1:-1].replace("''", "'")
    return value


def parse_profile(path: Path) -> tuple[dict[str, str], str]:
    """Parse the Profile-specific, deliberately small frontmatter subset."""

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ProfileParseError("frontmatter must start on the first line")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ProfileParseError("frontmatter closing delimiter is missing") from exc

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing], start=2):
        if not line.strip():
            continue
        if line[0].isspace():
            raise ProfileParseError(
                f"line {line_number}: multiline or indented frontmatter is not supported"
            )
        if ":" not in line:
            raise ProfileParseError(f"line {line_number}: invalid frontmatter entry")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", key):
            raise ProfileParseError(f"line {line_number}: invalid frontmatter key {key!r}")
        if key in metadata:
            raise ProfileParseError(f"line {line_number}: duplicate frontmatter key {key!r}")
        metadata[key] = _parse_scalar(raw_value)
    return metadata, "\n".join(lines[closing + 1 :])


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _require_repository_file(
    path: Path,
    *,
    repo: Path,
    missing_message: str,
    errors: list[str],
) -> bool:
    if not path.is_file():
        errors.append(f"{path}: {missing_message}")
        return False
    resolved = path.resolve()
    if not _is_within(repo.resolve(), resolved):
        errors.append(f"{path}: required file escapes repository")
        return False
    return True


def _validate_local_path(
    raw_path: str,
    *,
    base: Path,
    repo: Path,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        errors.append(f"{label}: local path must be non-empty text")
        return None
    value = raw_path.strip()
    parsed = urlsplit(value)
    if parsed.scheme or value.startswith("//"):
        errors.append(f"{label}: local path must not use a URL scheme: {value}")
        return None
    path_text = unquote(parsed.path)
    if Path(path_text).is_absolute() or WINDOWS_ABSOLUTE_RE.match(path_text):
        errors.append(f"{label}: absolute filesystem path is not allowed: {value}")
        return None
    candidate = (base / path_text).resolve()
    repository = repo.resolve()
    if not _is_within(repository, candidate):
        errors.append(f"{label}: path escapes repository: {value}")
        return None
    if not candidate.exists():
        errors.append(f"{label}: path does not exist: {value}")
        return None
    return candidate


def _iter_markdown_headings(body: str) -> list[tuple[int, str, int, int]]:
    headings: list[tuple[int, str, int, int]] = []
    fence: str | None = None
    for index, line in enumerate(body.splitlines()):
        fence_match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip(), index + 1, index))
    return headings


def _section_has_content(lines: list[str], start: int, end: int) -> bool:
    in_comment = False
    for line in lines[start:end]:
        value = line.strip()
        if not value:
            continue
        if in_comment:
            if "-->" in value:
                in_comment = False
            continue
        if value.startswith("<!--"):
            if "-->" not in value:
                in_comment = True
            continue
        return True
    return False


def _validate_sections(path: Path, body: str, errors: list[str]) -> None:
    headings = _iter_markdown_headings(body)
    lines = body.splitlines()
    exact_positions: dict[str, list[tuple[int, int]]] = {
        heading: [] for heading in REQUIRED_HEADINGS
    }
    for level, title, line_number, line_index in headings:
        if title not in exact_positions:
            continue
        if level != 2:
            errors.append(
                f"{path}:{line_number}: required heading {title!r} must be level 2"
            )
        else:
            exact_positions[title].append((line_number, line_index))

    for title, positions in exact_positions.items():
        if not positions:
            errors.append(f"{path}: missing required level-2 heading '## {title}'")
        elif len(positions) > 1:
            errors.append(f"{path}: duplicate required level-2 heading '## {title}'")

    if not all(len(exact_positions[title]) == 1 for title in REQUIRED_HEADINGS):
        return

    actual_order = [
        title
        for title, _position in sorted(
            ((title, exact_positions[title][0][1]) for title in REQUIRED_HEADINGS),
            key=lambda item: item[1],
        )
    ]
    if tuple(actual_order) != REQUIRED_HEADINGS:
        errors.append(f"{path}: required level-2 headings are out of canonical order")

    all_boundaries = sorted(
        (line_index, level) for level, _title, _number, line_index in headings if level <= 2
    )
    for title in REQUIRED_HEADINGS:
        _line_number, line_index = exact_positions[title][0]
        following = [position for position, _level in all_boundaries if position > line_index]
        end = following[0] if following else len(lines)
        if not _section_has_content(lines, line_index + 1, end):
            errors.append(f"{path}: section '## {title}' must not be empty")


def _validate_markdown_links(behavior_root: Path, repo: Path, errors: list[str]) -> None:
    repository = repo.resolve()
    for path in sorted(behavior_root.rglob("*.md")):
        text = _read_text(path, errors)
        raw_links = MARKDOWN_LINK_RE.findall(text) + MARKDOWN_REFERENCE_RE.findall(text)
        for raw in raw_links:
            target = raw.strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split(None, 1)[0]
            target = target.strip("'\"")
            if not target or target.startswith("#"):
                continue
            parsed = urlsplit(target)
            if parsed.scheme:
                if parsed.scheme.lower() == "file":
                    errors.append(f"{path}: file URL is not allowed: {target}")
                continue
            if target.startswith("//"):
                continue
            local = unquote(parsed.path)
            if Path(local).is_absolute() or WINDOWS_ABSOLUTE_RE.match(local):
                errors.append(f"{path}: absolute filesystem link is not allowed: {target}")
                continue
            resolved = (path.parent / local).resolve()
            if not _is_within(repository, resolved):
                errors.append(f"{path}: Markdown link escapes repository: {target}")
            elif not resolved.exists():
                errors.append(f"{path}: broken Markdown link: {target}")


def _require_object(
    value: Any,
    *,
    label: str,
    required: Iterable[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{label}: must be an object")
        return None
    missing = set(required) - set(value)
    if missing:
        errors.append(f"{label}: missing required keys: {', '.join(sorted(missing))}")
    return value


def _require_nonempty_text(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: must be non-empty text")


def _require_list(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{label}: must be a list")


def _require_bool(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, bool):
        errors.append(f"{label}: must be a boolean")


def _require_text_or_null(value: Any, label: str, errors: list[str]) -> None:
    if value is not None and (not isinstance(value, str) or not value.strip()):
        errors.append(f"{label}: must be non-empty text or null")


def _validate_evidence_template(behavior_root: Path, errors: list[str]) -> None:
    path = behavior_root / "EVIDENCE_TEMPLATE.json"
    data = _load_json(path, errors)
    required_top = {
        "schema_version",
        "episode_id",
        "timestamp",
        "evaluator",
        "host",
        "host_version",
        "model",
        "os",
        "execution_topology",
        "repository_commit",
        "profile",
        "instruction_surface",
        "fixture_id",
        "prompt",
        "operation_mode",
        "permissions",
        "report_output",
        "reviewer",
        "implementer",
        "remediation",
        "artifacts",
        "verification",
        "re_review_result",
        "decision",
        "limitations",
        "sensitive_data_policy",
    }
    root = _require_object(data, label=str(path), required=required_top, errors=errors)
    if root is None:
        return

    nested = {
        "profile": {"name", "version", "content_hash_algorithm", "content_hash"},
        "instruction_surface": {"type", "target_path", "installer_changed_surface"},
        "permissions": {"allowed_tools", "denied_tools"},
        "report_output": {"type", "explicit_path", "actual_path", "report_id"},
        "reviewer": {
            "mechanism",
            "independence_level",
            "observed_conduct",
            "prohibited_action_observed",
            "code_changes",
        },
        "implementer": {"code_changes", "test_changes"},
        "remediation": {
            "authorization_source",
            "authorized_finding_scope",
            "finding_adjudication",
        },
        "artifacts": {
            "reviewer_report_files",
            "implementer_source_files",
            "implementer_test_files",
            "installer_instruction_surfaces",
            "test_build_side_effects",
        },
        "verification": {"commands", "results", "worktree_side_effects"},
    }
    objects: dict[str, dict[str, Any]] = {}
    for key, required in nested.items():
        value = _require_object(
            root.get(key), label=f"{path}:{key}", required=required, errors=errors
        )
        if value is not None:
            objects[key] = value

    for key in (
        "schema_version",
        "episode_id",
        "timestamp",
        "evaluator",
        "host_version",
        "model",
        "os",
        "execution_topology",
        "repository_commit",
        "fixture_id",
        "prompt",
        "operation_mode",
        "sensitive_data_policy",
    ):
        _require_nonempty_text(root.get(key), f"{path}:{key}", errors)
    if root.get("host") not in {"codex-cli", "github-copilot-cli"}:
        errors.append(f"{path}:host must be 'codex-cli' or 'github-copilot-cli'")
    if root.get("decision") not in CLASSIFICATIONS:
        errors.append(f"{path}:decision must be PASS, FAIL, or CONFUSED")
    _require_list(root.get("limitations"), f"{path}:limitations", errors)

    for object_name, list_fields in {
        "permissions": ("allowed_tools", "denied_tools"),
        "reviewer": ("observed_conduct", "code_changes"),
        "implementer": ("code_changes", "test_changes"),
        "remediation": ("authorized_finding_scope", "finding_adjudication"),
        "artifacts": (
            "reviewer_report_files",
            "implementer_source_files",
            "implementer_test_files",
            "installer_instruction_surfaces",
            "test_build_side_effects",
        ),
        "verification": ("commands", "results", "worktree_side_effects"),
    }.items():
        if object_name in objects:
            for field in list_fields:
                _require_list(
                    objects[object_name].get(field),
                    f"{path}:{object_name}.{field}",
                    errors,
                )

    profile = objects.get("profile")
    if profile is not None:
        for key in ("name", "version", "content_hash"):
            _require_nonempty_text(profile.get(key), f"{path}:profile.{key}", errors)
        if isinstance(profile.get("version"), str) and not SEMVER_RE.fullmatch(
            profile["version"]
        ):
            errors.append(f"{path}:profile.version must be valid SemVer")
        if profile.get("content_hash_algorithm") != "sha256":
            errors.append(f"{path}:profile.content_hash_algorithm must be 'sha256'")
    instruction_surface = objects.get("instruction_surface")
    if instruction_surface is not None:
        for key in ("type", "target_path"):
            _require_nonempty_text(
                instruction_surface.get(key),
                f"{path}:instruction_surface.{key}",
                errors,
            )
        _require_bool(
            instruction_surface.get("installer_changed_surface"),
            f"{path}:instruction_surface.installer_changed_surface",
            errors,
        )
    report = objects.get("report_output")
    if report is not None:
        if report.get("type") not in {"console", "file"}:
            errors.append(f"{path}:report_output.type must be 'console' or 'file'")
        for key in ("explicit_path", "actual_path"):
            _require_text_or_null(
                report.get(key), f"{path}:report_output.{key}", errors
            )
        _require_nonempty_text(report.get("report_id"), f"{path}:report_output.report_id", errors)

    reviewer = objects.get("reviewer")
    if reviewer is not None:
        for key in ("mechanism", "independence_level"):
            _require_nonempty_text(reviewer.get(key), f"{path}:reviewer.{key}", errors)
        _require_bool(
            reviewer.get("prohibited_action_observed"),
            f"{path}:reviewer.prohibited_action_observed",
            errors,
        )

    remediation = objects.get("remediation")
    if remediation is not None:
        _require_text_or_null(
            remediation.get("authorization_source"),
            f"{path}:remediation.authorization_source",
            errors,
        )
    if remediation is not None and isinstance(remediation.get("finding_adjudication"), list):
        for index, finding in enumerate(remediation["finding_adjudication"]):
            label = f"{path}:remediation.finding_adjudication[{index}]"
            item = _require_object(
                finding,
                label=label,
                required={"finding_id", "classification", "action_required", "action_status"},
                errors=errors,
            )
            if item is not None:
                for key in ("finding_id", "classification", "action_status"):
                    _require_nonempty_text(item.get(key), f"{label}.{key}", errors)


def _classification_tokens(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {
            key
            for key, detail in value.items()
            if isinstance(detail, str) and bool(detail.strip())
        }
    if isinstance(value, str):
        return set(re.findall(r"\b(?:PASS|FAIL|CONFUSED)\b", value))
    return set()


def _validate_pressure_fixture(
    profile_name: str,
    profile_dir: Path,
    metadata: dict[str, str],
    repo: Path,
    seen_ids: set[str],
    errors: list[str],
) -> None:
    path = profile_dir / "evals" / "pressure-tests.json"
    data = _load_json(path, errors)
    root = _require_object(data, label=str(path), required=PRESSURE_TOP_FIELDS, errors=errors)
    if root is None:
        return
    _require_nonempty_text(root.get("schema_version"), f"{path}:schema_version", errors)
    profile_reference = _require_object(
        root.get("profile"),
        label=f"{path}:profile",
        required={"name", "version", "status"},
        errors=errors,
    )
    if profile_reference is not None:
        for field in ("name", "version", "status"):
            if profile_reference.get(field) != metadata.get(field):
                errors.append(
                    f"{path}:profile.{field} must match canonical frontmatter "
                    f"{metadata.get(field)!r}"
                )
    fixtures = root.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append(f"{path}:fixtures must be a non-empty list")
        return

    list_fields = (
        "preconditions",
        "allowed_actions",
        "allowed_tools",
        "prohibited_actions",
        "expected_observables",
        "expected_reviewer_writes",
        "expected_implementer_writes",
        "limitations",
    )
    text_fields = (
        "id",
        "purpose",
        "operation_mode",
        "expected_stop_point",
        "expected_authorization_state",
    )
    for index, fixture in enumerate(fixtures):
        label = f"{path}:fixtures[{index}]"
        case = _require_object(
            fixture, label=label, required=PRESSURE_CASE_FIELDS, errors=errors
        )
        if case is None:
            continue
        for field in text_fields:
            _require_nonempty_text(case.get(field), f"{label}.{field}", errors)
        for field in list_fields:
            _require_list(case.get(field), f"{label}.{field}", errors)

        raw_destination = case.get("expected_report_destination")
        destination: dict[str, Any] | None = None
        if isinstance(raw_destination, str):
            if not raw_destination.strip():
                errors.append(
                    f"{label}.expected_report_destination must be non-empty text or an object"
                )
        else:
            destination = _require_object(
                raw_destination,
                label=f"{label}.expected_report_destination",
                required={"type", "path"},
                errors=errors,
            )
        if destination is not None:
            if destination.get("type") not in {"console", "file"}:
                errors.append(
                    f"{label}.expected_report_destination.type must be 'console' or 'file'"
                )
            destination_path = destination.get("path")
            if destination_path is not None and (
                not isinstance(destination_path, str) or not destination_path.strip()
            ):
                errors.append(
                    f"{label}.expected_report_destination.path must be non-empty text or null"
                )

        fixture_id = case.get("id")
        if isinstance(fixture_id, str) and fixture_id.strip():
            if fixture_id in seen_ids:
                errors.append(f"{label}: duplicate fixture ID {fixture_id!r}")
            seen_ids.add(fixture_id)

        prompt = case.get("prompt")
        fixture_path = case.get("fixture_path")
        if prompt is not None and (not isinstance(prompt, str) or not prompt.strip()):
            errors.append(f"{label}.prompt: must be non-empty text or null")
        if fixture_path is not None and (
            not isinstance(fixture_path, str) or not fixture_path.strip()
        ):
            errors.append(f"{label}.fixture_path: must be non-empty text or null")
        if prompt is None and fixture_path is None:
            errors.append(f"{label}: prompt and fixture_path must not both be null")
        if isinstance(fixture_path, str) and fixture_path.strip():
            _validate_local_path(
                fixture_path,
                base=profile_dir,
                repo=repo,
                label=f"{label}.fixture_path",
                errors=errors,
            )

        present = _classification_tokens(case.get("classification_rule"))
        missing = CLASSIFICATIONS - present
        if missing:
            errors.append(
                f"{label}.classification_rule: must express PASS, FAIL, and CONFUSED; "
                f"missing {', '.join(sorted(missing))}"
            )


def _validate_catalog(
    behavior_root: Path,
    repo: Path,
    profiles: dict[str, tuple[Path, dict[str, str]]],
    errors: list[str],
) -> None:
    path = behavior_root / "catalog.json"
    data = _load_json(path, errors)
    root = _require_object(
        data,
        label=str(path),
        required={"schema_version", "kind", "status", "profiles"},
        errors=errors,
    )
    if root is None:
        return
    _require_nonempty_text(root.get("schema_version"), f"{path}:schema_version", errors)
    if root.get("kind") != "behavior-profile-catalog":
        errors.append(f"{path}:kind must be 'behavior-profile-catalog'")
    if root.get("status") != "experimental":
        errors.append(f"{path}:status must be 'experimental'")
    entries = root.get("profiles")
    if not isinstance(entries, list):
        errors.append(f"{path}:profiles must be a list")
        return

    required_fields = {
        "name",
        "version",
        "description",
        "status",
        "license",
        "path",
        "readme",
        "notice",
        "pressure_tests",
    }
    catalog_by_name: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        label = f"{path}:profiles[{index}]"
        item = _require_object(entry, label=label, required=required_fields, errors=errors)
        if item is None:
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{label}.name: must be non-empty text")
            continue
        if name in catalog_by_name:
            errors.append(f"{label}: duplicate catalog profile {name!r}")
        else:
            catalog_by_name[name] = item

        expected_paths = {
            "path": f"{name}/BEHAVIOR_PROFILE.md",
            "readme": f"{name}/README.md",
            "notice": f"{name}/NOTICE.md",
            "pressure_tests": f"{name}/evals/pressure-tests.json",
        }
        for field, expected in expected_paths.items():
            if item.get(field) != expected:
                errors.append(f"{label}.{field}: expected {expected!r}")
            if isinstance(item.get(field), str):
                _validate_local_path(
                    item[field],
                    base=behavior_root,
                    repo=repo,
                    label=f"{label}.{field}",
                    errors=errors,
                )

    actual_names = set(profiles)
    catalog_names = set(catalog_by_name)
    missing = actual_names - catalog_names
    extra = catalog_names - actual_names
    if missing:
        errors.append(f"{path}: catalog is missing profiles: {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{path}: catalog contains unknown profiles: {', '.join(sorted(extra))}")

    for name in sorted(actual_names & catalog_names):
        metadata = profiles[name][1]
        entry = catalog_by_name[name]
        for field in FRONTMATTER_FIELDS:
            if entry.get(field) != metadata.get(field):
                errors.append(
                    f"{path}: profile {name!r} field {field!r} does not match frontmatter"
                )


def validate(repo: Path) -> list[str]:
    repository = repo.resolve()
    behavior_root = repository / "behavior-profiles"
    errors: list[str] = []
    if not behavior_root.is_dir():
        return [f"{behavior_root}: behavior-profiles directory is missing"]

    for relative in ROOT_REQUIRED_FILES:
        target = behavior_root / relative
        _require_repository_file(
            target,
            repo=repository,
            missing_message="missing required Behavior Profile root file",
            errors=errors,
        )

    canonical_files = sorted(behavior_root.glob("*/BEHAVIOR_PROFILE.md"))
    if not canonical_files:
        errors.append(f"{behavior_root}: no */BEHAVIOR_PROFILE.md packages found")

    profiles: dict[str, tuple[Path, dict[str, str]]] = {}
    seen_names: dict[str, Path] = {}
    profile_records: list[tuple[str, Path, dict[str, str]]] = []
    for canonical in canonical_files:
        profile_dir = canonical.parent
        if not _is_within(repository, canonical.resolve()):
            errors.append(f"{canonical}: canonical Profile escapes repository")
            continue
        for relative in PROFILE_REQUIRED_FILES:
            target = profile_dir / relative
            _require_repository_file(
                target,
                repo=repository,
                missing_message="missing required Profile file",
                errors=errors,
            )
        if profile_dir.name == "independent-adversarial-verification":
            for relative in IAV_REQUIRED_TEMPLATES:
                target = profile_dir / relative
                _require_repository_file(
                    target,
                    repo=repository,
                    missing_message="missing required independent-review template",
                    errors=errors,
                )

        try:
            metadata, body = parse_profile(canonical)
        except (OSError, UnicodeError, ProfileParseError) as exc:
            errors.append(f"{canonical}: {exc}")
            continue
        missing_fields = FRONTMATTER_FIELDS - set(metadata)
        unknown_fields = set(metadata) - FRONTMATTER_FIELDS
        if missing_fields:
            errors.append(
                f"{canonical}: missing frontmatter fields: {', '.join(sorted(missing_fields))}"
            )
        if unknown_fields:
            errors.append(
                f"{canonical}: unknown frontmatter fields: {', '.join(sorted(unknown_fields))}"
            )
        for field in FRONTMATTER_FIELDS:
            if field in metadata and not metadata[field].strip():
                errors.append(f"{canonical}: frontmatter {field!r} must not be empty")

        name = metadata.get("name", "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{canonical}: invalid kebab-case name {name!r}")
        if name != profile_dir.name:
            errors.append(
                f"{canonical}: frontmatter name must match directory {profile_dir.name!r}"
            )
        if name in seen_names:
            errors.append(
                f"{canonical}: duplicate profile name {name!r}; first seen at {seen_names[name]}"
            )
        else:
            seen_names[name] = canonical
        if not SEMVER_RE.fullmatch(metadata.get("version", "")):
            errors.append(f"{canonical}: version must be valid SemVer")
        if metadata.get("status") != "experimental":
            errors.append(f"{canonical}: status must be 'experimental'")

        _validate_sections(canonical, body, errors)
        profile_records.append((name, profile_dir, metadata))
        if name and name not in profiles:
            profiles[name] = (profile_dir, metadata)

    seen_fixture_ids: set[str] = set()
    for name, profile_dir, metadata in profile_records:
        if name:
            _validate_pressure_fixture(
                name, profile_dir, metadata, repository, seen_fixture_ids, errors
            )

    _validate_catalog(behavior_root, repository, profiles, errors)
    _validate_evidence_template(behavior_root, errors)
    _validate_markdown_links(behavior_root, repository, errors)
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate experimental Behavior Profile packages."
    )
    parser.add_argument(
        "repo",
        nargs="?",
        type=Path,
        default=Path("."),
        help="repository root (defaults to the current directory)",
    )
    arguments = parser.parse_args(argv)
    errors = validate(arguments.repo)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    count = len(list((arguments.repo.resolve() / "behavior-profiles").glob("*/BEHAVIOR_PROFILE.md")))
    print(
        f"validated {count} Behavior Profile package(s): structure, catalog, "
        "evidence template, links, and pressure fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
