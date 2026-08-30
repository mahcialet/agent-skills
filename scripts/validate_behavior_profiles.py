#!/usr/bin/env python3
"""Dependency-free validator for experimental Behavior Profile packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
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
    "expected_decisions",
    "classification_rule",
    "limitations",
}
CLASSIFICATIONS = {"PASS", "FAIL", "CONFUSED"}
PRESSURE_SCHEMA_VERSION = "1.1"
EVIDENCE_SCHEMA_VERSION = "1.0"
FINDING_CLASSIFICATIONS = {"confirmed", "rejected", "inconclusive"}
ACTION_REQUIRED_VALUES = {"yes", "no", "undetermined"}
ACTION_STATUS_VALUES = {
    "fixed",
    "not-fixed",
    "not-authorized",
    "not-required",
    "deferred",
}
EVIDENCE_RECORD_STATUSES = {"formal", "invalidated"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EVIDENCE_TOP_FIELDS = {
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
EVIDENCE_NESTED_FIELDS = {
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
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
MARKDOWN_REFERENCE_RE = re.compile(
    r"^[ \t]{0,3}\[[^\]]+\]:[ \t]*(<[^>]+>|[^\s]+)", re.MULTILINE
)
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
OPEN_SUPPORTS_DIR_FD = os.open in os.supports_dir_fd


class ProfileParseError(ValueError):
    """Raised for malformed canonical Profile frontmatter."""


class RepositoryReader:
    """Read regular files beneath one anchored repository directory."""

    def __init__(self, repository: Path) -> None:
        self.repository = repository.resolve()
        if (
            not hasattr(os, "O_NOFOLLOW")
            or not hasattr(os, "O_DIRECTORY")
            or not OPEN_SUPPORTS_DIR_FD
        ):
            raise OSError(
                "secure repository reads require dir_fd, O_NOFOLLOW, and O_DIRECTORY"
            )
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        flags |= getattr(os, "O_CLOEXEC", 0)
        self._directory_flags = flags
        self._file_flags = os.O_RDONLY | os.O_NOFOLLOW
        self._file_flags |= getattr(os, "O_CLOEXEC", 0)
        self._file_flags |= getattr(os, "O_NONBLOCK", 0)
        directory_fd = os.open(self.repository.anchor, self._directory_flags)
        try:
            for component in self.repository.parts[1:]:
                next_fd = os.open(
                    component,
                    self._directory_flags,
                    dir_fd=directory_fd,
                )
                os.close(directory_fd)
                directory_fd = next_fd
        except OSError:
            os.close(directory_fd)
            raise
        self._root_fd = directory_fd

    def close(self) -> None:
        if self._root_fd >= 0:
            os.close(self._root_fd)
            self._root_fd = -1

    def __enter__(self) -> RepositoryReader:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _relative_parts(self, path: Path) -> tuple[str, ...]:
        absolute = Path(os.path.abspath(path))
        try:
            relative = absolute.relative_to(self.repository)
        except ValueError as exc:
            raise OSError("path is not project-relative") from exc
        if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
            raise OSError("path does not identify a repository file")
        return relative.parts

    def read_bytes(self, path: Path) -> bytes:
        parts = self._relative_parts(path)
        directory_fd = os.dup(self._root_fd)
        file_fd = -1
        try:
            for component in parts[:-1]:
                next_fd = os.open(
                    component,
                    self._directory_flags,
                    dir_fd=directory_fd,
                )
                os.close(directory_fd)
                directory_fd = next_fd
            file_fd = os.open(
                parts[-1],
                self._file_flags,
                dir_fd=directory_fd,
            )
            metadata = os.fstat(file_fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError("repository path is not a regular file")
            with os.fdopen(file_fd, "rb", closefd=True) as stream:
                file_fd = -1
                return stream.read()
        finally:
            if file_fd >= 0:
                os.close(file_fd)
            os.close(directory_fd)


def _resolved_within_repository(path: Path, repo: Path) -> bool:
    try:
        return _is_within(repo.resolve(), path.resolve())
    except (OSError, RuntimeError):
        return False


def _read_text(
    path: Path,
    errors: list[str],
    *,
    reader: RepositoryReader,
) -> str | None:
    try:
        raw = reader.read_bytes(path)
    except OSError as exc:
        errors.append(f"{path}: cannot securely read repository file: {exc}")
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeError as exc:
        errors.append(f"{path}: cannot read UTF-8 text: {exc}")
        return None


def _load_json(
    path: Path,
    errors: list[str],
    *,
    reader: RepositoryReader,
) -> Any | None:
    text = _read_text(path, errors, reader=reader)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{path}: invalid JSON: {exc}")
        return None


def _read_bytes(
    path: Path, errors: list[str], *, reader: RepositoryReader
) -> bytes | None:
    try:
        return reader.read_bytes(path)
    except OSError as exc:
        errors.append(f"{path}: cannot securely read repository file: {exc}")
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


def _parse_profile_text(text: str) -> tuple[dict[str, str], str]:
    """Parse the Profile-specific, deliberately small frontmatter subset."""

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


def parse_profile(path: Path) -> tuple[dict[str, str], str]:
    """Parse a Profile path for trusted callers such as the installer."""

    return _parse_profile_text(path.read_text(encoding="utf-8"))


def _is_within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _require_repository_file(
    path: Path,
    *,
    repo: Path,
    missing_message: str,
    errors: list[str],
) -> bool:
    if not _resolved_within_repository(path, repo):
        errors.append(f"{path}: required file escapes repository")
        return False
    if not path.is_file():
        errors.append(f"{path}: {missing_message}")
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
    fence: tuple[str, int] | None = None
    for index, line in enumerate(body.splitlines()):
        if fence is not None:
            closing_match = re.fullmatch(r"[ ]{0,3}(`{3,}|~{3,})[ \t]*", line)
            if closing_match:
                run = closing_match.group(1)
                if run[0] == fence[0] and len(run) >= fence[1]:
                    fence = None
            continue

        opening_match = re.match(r"^[ ]{0,3}(`{3,}|~{3,})(.*)$", line)
        if opening_match:
            run = opening_match.group(1)
            suffix = opening_match.group(2)
            if run[0] != "`" or "`" not in suffix:
                fence = (run[0], len(run))
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


def _validate_markdown_links(
    behavior_root: Path,
    repo: Path,
    reader: RepositoryReader,
    errors: list[str],
) -> None:
    repository = repo.resolve()
    for path in sorted(behavior_root.rglob("*.md")):
        text = _read_text(path, errors, reader=reader)
        if text is None:
            continue
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


def _validate_recorded_project_path(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: must be non-empty project-relative path text")
        return
    candidate = value.strip()
    recorded_path = re.split(r":\s+", candidate, maxsplit=1)[0]
    parsed = urlsplit(recorded_path)
    decoded = unquote(parsed.path)
    if (
        parsed.scheme
        or recorded_path.startswith("//")
        or Path(decoded).is_absolute()
        or WINDOWS_ABSOLUTE_RE.match(decoded)
        or ".." in Path(decoded).parts
    ):
        errors.append(f"{label}: must be a project-relative path: {candidate}")


def _validate_evidence_record(
    data: Any,
    *,
    label: str,
    errors: list[str],
    is_template: bool,
    known_profiles: dict[str, tuple[str, str]] | None = None,
    known_fixture_decisions: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, Any] | None:
    root = _require_object(
        data,
        label=label,
        required=EVIDENCE_TOP_FIELDS,
        errors=errors,
    )
    if root is None:
        return None

    if root.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(
            f"{label}:schema_version must be {EVIDENCE_SCHEMA_VERSION!r}"
        )

    objects: dict[str, dict[str, Any]] = {}
    for key, required in EVIDENCE_NESTED_FIELDS.items():
        value = _require_object(
            root.get(key),
            label=f"{label}:{key}",
            required=required,
            errors=errors,
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
        _require_nonempty_text(root.get(key), f"{label}:{key}", errors)
    if root.get("host") not in {"codex-cli", "github-copilot-cli"}:
        errors.append(f"{label}:host must be 'codex-cli' or 'github-copilot-cli'")
    if root.get("decision") not in CLASSIFICATIONS:
        errors.append(f"{label}:decision must be PASS, FAIL, or CONFUSED")
    _require_text_or_null(root.get("re_review_result"), f"{label}:re_review_result", errors)
    _require_list(root.get("limitations"), f"{label}:limitations", errors)
    if not is_template and isinstance(root.get("limitations"), list) and not root["limitations"]:
        errors.append(f"{label}:limitations must not be empty")

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
                    f"{label}:{object_name}.{field}",
                    errors,
                )

    profile = objects.get("profile")
    profile_name: Any = None
    if profile is not None:
        profile_name = profile.get("name")
        for key in ("name", "version", "content_hash"):
            _require_nonempty_text(profile.get(key), f"{label}:profile.{key}", errors)
        if isinstance(profile.get("version"), str) and not SEMVER_RE.fullmatch(
            profile["version"]
        ):
            errors.append(f"{label}:profile.version must be valid SemVer")
        if profile.get("content_hash_algorithm") != "sha256":
            errors.append(f"{label}:profile.content_hash_algorithm must be 'sha256'")
        if (
            not is_template
            and isinstance(profile.get("content_hash"), str)
            and not SHA256_RE.fullmatch(profile["content_hash"])
        ):
            errors.append(f"{label}:profile.content_hash must be 64 lowercase hex characters")
        if (
            not is_template
            and known_profiles is not None
            and profile_name not in known_profiles
        ):
            errors.append(f"{label}:profile.name references unknown profile {profile_name!r}")
        elif (
            not is_template
            and known_profiles is not None
            and isinstance(profile_name, str)
            and profile_name in known_profiles
        ):
            current_version, current_hash = known_profiles[profile_name]
            if (
                profile.get("version") == current_version
                and profile.get("content_hash") != current_hash
            ):
                errors.append(
                    f"{label}:profile.content_hash does not match current canonical bytes"
                )

    instruction_surface = objects.get("instruction_surface")
    if instruction_surface is not None:
        for key in ("type", "target_path"):
            _require_nonempty_text(
                instruction_surface.get(key),
                f"{label}:instruction_surface.{key}",
                errors,
            )
        _require_bool(
            instruction_surface.get("installer_changed_surface"),
            f"{label}:instruction_surface.installer_changed_surface",
            errors,
        )
        if not is_template and isinstance(instruction_surface.get("target_path"), str):
            _validate_recorded_project_path(
                instruction_surface["target_path"],
                f"{label}:instruction_surface.target_path",
                errors,
            )

    report = objects.get("report_output")
    if report is not None:
        if report.get("type") not in {"console", "file"}:
            errors.append(f"{label}:report_output.type must be 'console' or 'file'")
        for key in ("explicit_path", "actual_path"):
            _require_text_or_null(report.get(key), f"{label}:report_output.{key}", errors)
            if not is_template and isinstance(report.get(key), str):
                _validate_recorded_project_path(
                    report[key], f"{label}:report_output.{key}", errors
                )
        requires_report_id = (
            profile_name == "independent-adversarial-verification"
            and not str(root.get("operation_mode", "")).startswith("synthetic-control")
        )
        if is_template or requires_report_id:
            if not isinstance(report.get("report_id"), str) or not report["report_id"].strip():
                suffix = (
                    " for independent-adversarial-verification"
                    if not is_template
                    else ""
                )
                errors.append(
                    f"{label}:report_output.report_id: must be non-empty text{suffix}"
                )
        else:
            _require_text_or_null(
                report.get("report_id"), f"{label}:report_output.report_id", errors
            )

    reviewer = objects.get("reviewer")
    if reviewer is not None:
        for key in ("mechanism", "independence_level"):
            _require_nonempty_text(reviewer.get(key), f"{label}:reviewer.{key}", errors)
        _require_bool(
            reviewer.get("prohibited_action_observed"),
            f"{label}:reviewer.prohibited_action_observed",
            errors,
        )
        if (
            not is_template
            and isinstance(reviewer.get("code_changes"), list)
            and reviewer["code_changes"]
            and root.get("decision") != "FAIL"
        ):
            errors.append(f"{label}: reviewer mutation requires decision FAIL")
        elif (
            not is_template
            and reviewer.get("prohibited_action_observed") is True
            and root.get("decision") != "FAIL"
        ):
            errors.append(f"{label}: prohibited reviewer action requires decision FAIL")

    if not is_template:
        for object_name, fields in {
            "reviewer": ("code_changes",),
            "implementer": ("code_changes", "test_changes"),
        }.items():
            value_object = objects.get(object_name)
            if value_object is None:
                continue
            for field in fields:
                values = value_object.get(field)
                if isinstance(values, list):
                    for index, value in enumerate(values):
                        _validate_recorded_project_path(
                            value,
                            f"{label}:{object_name}.{field}[{index}]",
                            errors,
                        )

    control_decisions: dict[str, Any] | None = None
    if "control_decisions" in root:
        control_decisions = _require_object(
            root.get("control_decisions"),
            label=f"{label}:control_decisions",
            required={"fixture_run", "embedded_observation"},
            errors=errors,
        )
    if control_decisions is not None:
        fixture_run = control_decisions.get("fixture_run")
        embedded_observation = control_decisions.get("embedded_observation")
        if fixture_run not in CLASSIFICATIONS:
            errors.append(
                f"{label}:control_decisions.fixture_run must be PASS, FAIL, or CONFUSED"
            )
        if (
            embedded_observation is not None
            and embedded_observation not in CLASSIFICATIONS
        ):
            errors.append(
                f"{label}:control_decisions.embedded_observation must be "
                "PASS, FAIL, or CONFUSED"
            )
        if fixture_run in CLASSIFICATIONS and fixture_run != root.get("decision"):
            errors.append(
                f"{label}:control_decisions.fixture_run must match top-level decision"
            )

        fixture_id = root.get("fixture_id")
        expected = (
            known_fixture_decisions.get(fixture_id)
            if known_fixture_decisions is not None and isinstance(fixture_id, str)
            else None
        )
        if expected is not None and control_decisions != expected:
            errors.append(
                f"{label}:control_decisions must match canonical expected_decisions"
            )

    remediation = objects.get("remediation")
    if remediation is not None:
        _require_text_or_null(
            remediation.get("authorization_source"),
            f"{label}:remediation.authorization_source",
            errors,
        )
    if remediation is not None and isinstance(remediation.get("finding_adjudication"), list):
        for index, finding in enumerate(remediation["finding_adjudication"]):
            finding_label = f"{label}:remediation.finding_adjudication[{index}]"
            item = _require_object(
                finding,
                label=finding_label,
                required={"finding_id", "classification", "action_required", "action_status"},
                errors=errors,
            )
            if item is None:
                continue
            _require_nonempty_text(
                item.get("finding_id"), f"{finding_label}.finding_id", errors
            )
            if item.get("classification") not in FINDING_CLASSIFICATIONS:
                errors.append(
                    f"{finding_label}.classification must be confirmed, rejected, or inconclusive"
                )
            if item.get("action_required") not in ACTION_REQUIRED_VALUES:
                errors.append(
                    f"{finding_label}.action_required must be yes, no, or undetermined"
                )
            if item.get("action_status") not in ACTION_STATUS_VALUES:
                errors.append(
                    f"{finding_label}.action_status has an unsupported value"
                )

    record_status = root.get("record_status")
    if record_status is not None and record_status not in EVIDENCE_RECORD_STATUSES:
        errors.append(f"{label}:record_status must be formal or invalidated")
    invalidated_reason = root.get("invalidated_reason")
    if record_status == "invalidated":
        _require_nonempty_text(
            invalidated_reason, f"{label}:invalidated_reason", errors
        )
    elif invalidated_reason is not None:
        _require_nonempty_text(
            invalidated_reason, f"{label}:invalidated_reason", errors
        )

    if not is_template:
        artifacts = objects.get("artifacts")
        if artifacts is not None:
            for field in (
                "reviewer_report_files",
                "implementer_source_files",
                "implementer_test_files",
                "installer_instruction_surfaces",
            ):
                values = artifacts.get(field)
                if isinstance(values, list):
                    for index, value in enumerate(values):
                        _validate_recorded_project_path(
                            value, f"{label}:artifacts.{field}[{index}]", errors
                        )
    return root


def _validate_evidence_template(
    behavior_root: Path,
    reader: RepositoryReader,
    errors: list[str],
) -> None:
    path = behavior_root / "EVIDENCE_TEMPLATE.json"
    data = _load_json(path, errors, reader=reader)
    if data is None:
        return
    _validate_evidence_record(
        data,
        label=str(path),
        errors=errors,
        is_template=True,
    )


def _validate_evidence_records(
    behavior_root: Path,
    repo: Path,
    reader: RepositoryReader,
    known_profiles: dict[str, tuple[str, str]],
    known_fixture_decisions: dict[str, dict[str, str | None]],
    errors: list[str],
) -> None:
    evidence_root = behavior_root / "evidence"
    if not _resolved_within_repository(evidence_root, repo):
        errors.append(f"{evidence_root}: evidence directory escapes repository")
        return
    if not evidence_root.exists():
        return
    if not evidence_root.is_dir():
        errors.append(f"{evidence_root}: evidence path must be a directory")
        return

    seen_episode_ids: set[str] = set()
    for path in sorted(evidence_root.glob("*.json")):
        data = _load_json(path, errors, reader=reader)
        if data is None:
            continue
        if not isinstance(data, list) or not data:
            errors.append(f"{path}: evidence file must contain a non-empty array")
            continue
        for index, raw_record in enumerate(data):
            label = f"{path}[{index}]"
            record = _validate_evidence_record(
                raw_record,
                label=label,
                errors=errors,
                is_template=False,
                known_profiles=known_profiles,
                known_fixture_decisions=known_fixture_decisions,
            )
            if record is None:
                continue
            episode_id = record.get("episode_id")
            if not isinstance(episode_id, str) or not episode_id.strip():
                continue
            if episode_id in seen_episode_ids:
                errors.append(f"{label}: duplicate evidence episode_id {episode_id!r}")
            seen_episode_ids.add(episode_id)


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
    reader: RepositoryReader,
    seen_ids: set[str],
    known_fixture_decisions: dict[str, dict[str, str | None]],
    errors: list[str],
) -> None:
    path = profile_dir / "evals" / "pressure-tests.json"
    data = _load_json(path, errors, reader=reader)
    root = _require_object(data, label=str(path), required=PRESSURE_TOP_FIELDS, errors=errors)
    if root is None:
        return
    if root.get("schema_version") != PRESSURE_SCHEMA_VERSION:
        errors.append(
            f"{path}:schema_version must be {PRESSURE_SCHEMA_VERSION!r}"
        )
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

        expected_decisions = _require_object(
            case.get("expected_decisions"),
            label=f"{label}.expected_decisions",
            required={"fixture_run", "embedded_observation"},
            errors=errors,
        )
        if expected_decisions is not None:
            if expected_decisions.get("fixture_run") not in CLASSIFICATIONS:
                errors.append(
                    f"{label}.expected_decisions.fixture_run must be PASS, FAIL, or CONFUSED"
                )
            embedded_decision = expected_decisions.get("embedded_observation")
            if embedded_decision is not None and embedded_decision not in CLASSIFICATIONS:
                errors.append(
                    f"{label}.expected_decisions.embedded_observation must be "
                    "PASS, FAIL, CONFUSED, or null"
                )

        fixture_id = case.get("id")
        if isinstance(fixture_id, str) and fixture_id.strip():
            if fixture_id in seen_ids:
                errors.append(f"{label}: duplicate fixture ID {fixture_id!r}")
            seen_ids.add(fixture_id)
            if (
                expected_decisions is not None
                and expected_decisions.get("fixture_run") in CLASSIFICATIONS
                and (
                    expected_decisions.get("embedded_observation") is None
                    or expected_decisions.get("embedded_observation")
                    in CLASSIFICATIONS
                )
            ):
                known_fixture_decisions.setdefault(
                    fixture_id,
                    {
                        "fixture_run": expected_decisions["fixture_run"],
                        "embedded_observation": expected_decisions[
                            "embedded_observation"
                        ],
                    },
                )

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
    reader: RepositoryReader,
    profiles: dict[str, tuple[Path, dict[str, str]]],
    errors: list[str],
) -> None:
    path = behavior_root / "catalog.json"
    data = _load_json(path, errors, reader=reader)
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


def _validate_repository(
    repository: Path,
    reader: RepositoryReader,
    errors: list[str],
) -> list[str]:
    behavior_root = repository / "behavior-profiles"
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
    canonical_snapshots: dict[Path, bytes] = {}
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

        canonical_bytes = _read_bytes(canonical, errors, reader=reader)
        if canonical_bytes is None:
            continue
        try:
            canonical_text = canonical_bytes.decode("utf-8")
            metadata, body = _parse_profile_text(canonical_text)
        except (UnicodeError, ProfileParseError) as exc:
            errors.append(f"{canonical}: {exc}")
            continue
        canonical_snapshots[canonical] = canonical_bytes
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
    known_fixture_decisions: dict[str, dict[str, str | None]] = {}
    for name, profile_dir, metadata in profile_records:
        if name:
            _validate_pressure_fixture(
                name,
                profile_dir,
                metadata,
                repository,
                reader,
                seen_fixture_ids,
                known_fixture_decisions,
                errors,
            )

    _validate_catalog(behavior_root, repository, reader, profiles, errors)
    _validate_evidence_template(behavior_root, reader, errors)
    evidence_profiles: dict[str, tuple[str, str]] = {}
    for name, (profile_dir, metadata) in profiles.items():
        canonical = profile_dir / "BEHAVIOR_PROFILE.md"
        canonical_bytes = canonical_snapshots.get(canonical)
        if canonical_bytes is None:
            continue
        content_hash = hashlib.sha256(canonical_bytes).hexdigest()
        evidence_profiles[name] = (metadata.get("version", ""), content_hash)
    _validate_evidence_records(
        behavior_root,
        repository,
        reader,
        evidence_profiles,
        known_fixture_decisions,
        errors,
    )
    _validate_markdown_links(behavior_root, repository, reader, errors)
    return errors


def validate(repo: Path) -> list[str]:
    repository = repo.resolve()
    errors: list[str] = []
    try:
        with RepositoryReader(repository) as reader:
            return _validate_repository(repository, reader, errors)
    except OSError as exc:
        errors.append(
            f"{repository}: cannot initialize secure repository reader: {exc}"
        )
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
        "evidence template/records, links, and pressure fixtures"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
