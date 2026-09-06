"""Conservative section validation, snapshot rendering, and template candidates."""

from __future__ import annotations

import json
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import UnsafeContentError
from .model import sha256_json, sha256_text, stable_json, utc_now
from .storage import ID_RE, ProposalStore, atomic_write

SNAPSHOT_FIELDS = (
    "goal",
    "current_state",
    "decisions",
    "constraints",
    "progress",
    "blockers",
    "unresolved_issues",
    "next_actions",
    "verification_status",
)
SNAPSHOT_LABELS = {
    "goal": "目的",
    "current_state": "現在地",
    "decisions": "決定事項",
    "constraints": "制約",
    "progress": "進捗",
    "blockers": "Blockers",
    "unresolved_issues": "未解決事項",
    "next_actions": "次の行動",
    "verification_status": "検証状態",
}
PROTECTED_TITLES = {"goal", "目的", "constraints", "制約"}


@dataclass(frozen=True, slots=True)
class Section:
    title: str
    content: str


def _heading_match(line: str, markup: str) -> re.Match[str] | None:
    if markup == "markdown":
        return re.match(r"^#{1,6}[ \t]+(.+?)(?:[ \t]+#+[ \t]*)?$", line)
    if markup == "textile":
        return re.match(r"^h[1-6]\.\s+(.+?)\s*$", line, re.IGNORECASE)
    if markup == "backlog":
        return re.match(r"^\*{1,6}\s+(.+?)\s*$", line)
    raise UnsafeContentError(f"unsupported markup: {markup}")


def sections(text: str, markup: str) -> list[Section]:
    lines = text.splitlines(keepends=True)
    result: list[Section] = []
    title = "__preamble__"
    buffer: list[str] = []
    fenced = False
    fence_token = ""
    fence_length = 0
    for line in lines:
        stripped = line.lstrip()
        if markup == "markdown":
            fence_line = line.rstrip("\r\n")
            if not fenced:
                opener = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", fence_line)
                if opener:
                    token = opener.group(1)
                    info = opener.group(2)
                    if token[0] == "`" and "`" in info:
                        raise UnsafeContentError("ambiguous Markdown fenced code block")
                    fenced = True
                    fence_token = token[0]
                    fence_length = len(token)
            elif re.match(
                rf"^ {{0,3}}{re.escape(fence_token)}{{{fence_length},}}[ \t]*$",
                fence_line,
            ):
                fenced = False
                fence_token = ""
                fence_length = 0
            if not fenced:
                lowered = fence_line.casefold()
                if any(token in lowered for token in ("<pre", "</pre", "<code", "</code")):
                    raise UnsafeContentError(
                        "Markdown raw HTML code blocks are unsupported; use a fenced code block"
                    )
                setext = re.match(r"^ {0,3}(=+|-+)[ \t]*$", fence_line)
                if setext and buffer and buffer[-1].strip():
                    candidate = buffer[-1].rstrip("\r\n")
                    if candidate.startswith((" ", "\t")) or _heading_match(candidate, markup):
                        raise UnsafeContentError("ambiguous Markdown Setext heading")
                    result.append(Section(title, "".join(buffer[:-1])))
                    title = candidate.strip()
                    buffer = [buffer[-1], line]
                    continue
        elif markup == "textile":
            lowered = stripped.casefold()
            if not fenced and ("<pre" in lowered or "<code" in lowered):
                fenced = True
                fence_token = "</pre>" if "<pre" in lowered else "</code>"
            if fenced and fence_token in lowered:
                fenced = False
        elif markup == "backlog" and re.match(r"^\{code(?::[^}]*)?\}\s*$", stripped):
            fenced = not fenced
            fence_token = "{code}"
        match = None if fenced else _heading_match(line.rstrip("\r\n"), markup)
        if match:
            result.append(Section(title, "".join(buffer)))
            title = match.group(1).strip()
            buffer = [line]
        else:
            buffer.append(line)
    if fenced:
        raise UnsafeContentError("unterminated fenced code block")
    result.append(Section(title, "".join(buffer)))
    return result


def _normalized_title(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_edit_scope(
    base: str,
    proposed: str,
    *,
    markup: str,
    edited_sections: list[str],
) -> set[str]:
    base_sections = sections(base, markup)
    proposed_sections = sections(proposed, markup)
    for label, values in (("base", base_sections), ("proposed", proposed_sections)):
        normalized = [_normalized_title(section.title) for section in values]
        duplicates = sorted(title for title, count in Counter(normalized).items() if count > 1 and title != "__preamble__")
        if duplicates:
            raise UnsafeContentError(f"{label} contains duplicate headings: {', '.join(duplicates)}")
    allowed = {_normalized_title(value) for value in edited_sections}
    if not allowed and base != proposed:
        raise UnsafeContentError("edited_sections is required when description changes")
    base_map = {_normalized_title(item.title): item.content for item in base_sections}
    proposed_map = {_normalized_title(item.title): item.content for item in proposed_sections}
    changed = {title for title in set(base_map) | set(proposed_map) if base_map.get(title) != proposed_map.get(title)}
    base_order = [_normalized_title(item.title) for item in base_sections]
    proposed_order = [_normalized_title(item.title) for item in proposed_sections]
    if base_order != proposed_order:
        changed.add("__structure__")
    undeclared = sorted(changed - allowed)
    if undeclared:
        raise UnsafeContentError(f"description changed outside edited_sections: {', '.join(undeclared)}")
    protected = changed & PROTECTED_TITLES
    return protected


def _safe_text(value: Any) -> str:
    if isinstance(value, str):
        result = value.strip()
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        result = "; ".join(item.strip() for item in value if item.strip())
    else:
        raise UnsafeContentError("snapshot values must be text or arrays of text")
    if not result:
        result = "なし"
    if any(character in result for character in ("\r", "\n", "\x00")):
        raise UnsafeContentError("snapshot text must be a single plain-text line")
    lowered = result.casefold()
    if any(token in lowered for token in ("{code", "{{", "}}", "[[", "]]", "<pre", "<code", "</")):
        raise UnsafeContentError("snapshot text contains unsupported structural markup")
    return result.replace("@", "@\u200b")


def render_snapshot(
    snapshot: dict[str, Any],
    change_summary: list[str],
    *,
    markup: str,
    prepared_at: str,
    operation_id: str,
) -> str:
    if set(snapshot) != set(SNAPSHOT_FIELDS):
        missing = sorted(set(SNAPSHOT_FIELDS) - set(snapshot))
        extra = sorted(set(snapshot) - set(SNAPSHOT_FIELDS))
        raise UnsafeContentError(f"snapshot fields mismatch; missing={missing}, extra={extra}")
    if not change_summary or any(not isinstance(item, str) or not item.strip() for item in change_summary):
        raise UnsafeContentError("change_summary must contain non-empty text items")
    summary = [_safe_text(item) for item in change_summary]
    values = {key: _safe_text(snapshot[key]) for key in SNAPSHOT_FIELDS}
    marker = f"ticket-state/{operation_id}"
    if markup == "markdown":
        lines = ["## 状態更新記録", "", "### 今回の変更"]
        lines.extend(f"- {item}" for item in summary)
        lines.extend(["", "### Current State Snapshot"])
        lines.extend(f"- {SNAPSHOT_LABELS[key]}: {values[key]}" for key in SNAPSHOT_FIELDS)
    elif markup == "textile":
        lines = ["h2. 状態更新記録", "", "h3. 今回の変更"]
        lines.extend(f"* {item}" for item in summary)
        lines.extend(["", "h3. Current State Snapshot"])
        lines.extend(f"* {SNAPSHOT_LABELS[key]}: {values[key]}" for key in SNAPSHOT_FIELDS)
    elif markup == "backlog":
        lines = ["* 状態更新記録", "", "** 今回の変更"]
        lines.extend(f"- {item}" for item in summary)
        lines.extend(["", "** Current State Snapshot"])
        lines.extend(f"- {SNAPSHOT_LABELS[key]}: {values[key]}" for key in SNAPSHOT_FIELDS)
    else:
        raise UnsafeContentError(f"unsupported markup: {markup}")
    lines.extend(["", f"Snapshot prepared at: {prepared_at}", f"Operation: {marker}"])
    rendered = "\n".join(lines) + "\n"
    if len(rendered.encode("utf-8")) > 60_000:
        raise UnsafeContentError("snapshot exceeds the conservative 60000-byte limit")
    return rendered


def extract_template_candidate(
    samples: list[tuple[dict[str, Any], str, str]],
    *,
    markup: str,
    store: ProposalStore,
) -> dict[str, Any]:
    if len(samples) < 2:
        status = "NEEDS_MORE_EVIDENCE"
    else:
        status = "CANDIDATE"
    orders: list[list[str]] = []
    evidence: list[dict[str, Any]] = []
    for identity, retrieved_at, description in samples:
        observed = [item.title for item in sections(description, markup) if item.title != "__preamble__"]
        orders.append(observed)
        evidence.append(
            {
                "identity": identity,
                "retrieved_at": retrieved_at,
                "description_sha256": sha256_text(description),
            }
        )
    counts = Counter(title for order in orders for title in dict.fromkeys(order))
    first_order = orders[0] if orders else []
    compatible_order = all(order == first_order for order in orders)
    if not compatible_order:
        status = "NEEDS_REVIEW"
    template_id = uuid.uuid4().hex
    candidate = {
        "schema_version": 1,
        "template_id": template_id,
        "kind": "candidate",
        "status": status,
        "markup": markup,
        "sample_count": len(samples),
        "headings": [
            {
                "title": title,
                "observed_count": counts[title],
                "required_candidate": len(samples) >= 2 and counts[title] == len(samples),
                "confidence": counts[title] / len(samples) if samples else 0.0,
            }
            for title in first_order
        ],
        "exceptions": [order for order in orders if order != first_order],
        "evidence": evidence,
        "created_at": utc_now(),
        "approved": False,
    }
    candidate["candidate_sha256"] = sha256_json(candidate)
    path = store.template_path("candidates", template_id)
    atomic_write(path, (stable_json(candidate) + "\n").encode("utf-8"), root=store.workspace)
    candidate["path"] = str(path)
    return candidate


def validate_template(value: dict[str, Any], *, require_approved: bool = False) -> None:
    required = {"schema_version", "template_id", "kind", "status", "markup", "sample_count", "headings", "exceptions", "evidence", "created_at", "approved", "candidate_sha256"}
    allowed = required | {
        "approved_at",
        "approved_by",
        "approval_reason",
        "source_candidate_sha256",
        "source_candidate_status",
    }
    if not required <= set(value) or set(value) - allowed:
        raise UnsafeContentError("template candidate fields do not match schema")
    if value["schema_version"] != 1 or value["markup"] not in {"markdown", "textile", "backlog"}:
        raise UnsafeContentError("template candidate has invalid version or markup")
    if not ID_RE.fullmatch(str(value["template_id"])):
        raise UnsafeContentError("template candidate has invalid ID")
    if (
        not isinstance(value["sample_count"], int)
        or isinstance(value["sample_count"], bool)
        or value["sample_count"] < 1
        or not isinstance(value["created_at"], str)
        or not value["created_at"].strip()
    ):
        raise UnsafeContentError("template candidate metadata is invalid")
    if (
        not isinstance(value["headings"], list)
        or not isinstance(value["exceptions"], list)
        or not isinstance(value["evidence"], list)
    ):
        raise UnsafeContentError("template candidate arrays are invalid")
    for heading in value["headings"]:
        if not isinstance(heading, dict) or set(heading) != {
            "title",
            "observed_count",
            "required_candidate",
            "confidence",
        }:
            raise UnsafeContentError("template heading evidence is invalid")
        if (
            not isinstance(heading["title"], str)
            or not heading["title"].strip()
            or not isinstance(heading["observed_count"], int)
            or isinstance(heading["observed_count"], bool)
            or heading["observed_count"] < 1
            or not isinstance(heading["required_candidate"], bool)
            or not isinstance(heading["confidence"], (int, float))
            or isinstance(heading["confidence"], bool)
            or not 0 <= heading["confidence"] <= 1
        ):
            raise UnsafeContentError("template heading values are invalid")
    if any(
        not isinstance(exception, list)
        or any(not isinstance(title, str) for title in exception)
        for exception in value["exceptions"]
    ):
        raise UnsafeContentError("template exceptions are invalid")
    if any(
        not isinstance(item, dict)
        or set(item) != {"identity", "retrieved_at", "description_sha256"}
        or not isinstance(item.get("identity"), dict)
        or not isinstance(item.get("retrieved_at"), str)
        or not isinstance(item.get("description_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", item["description_sha256"])
        for item in value["evidence"]
    ):
        raise UnsafeContentError("template source evidence is invalid")
    if (
        not isinstance(value["candidate_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["candidate_sha256"])
    ):
        raise UnsafeContentError("template candidate hash is invalid")
    if value.get("kind") == "candidate":
        if value.get("approved") is not False or value.get("status") not in {
            "CANDIDATE",
            "NEEDS_MORE_EVIDENCE",
            "NEEDS_REVIEW",
        }:
            raise UnsafeContentError("candidate cannot be marked approved")
        if set(value) & {
            "approved_at",
            "approved_by",
            "approval_reason",
            "source_candidate_sha256",
            "source_candidate_status",
        }:
            raise UnsafeContentError("candidate contains approval-only fields")
        hash_input = dict(value)
        recorded_hash = hash_input.pop("candidate_sha256")
        if recorded_hash != sha256_json(hash_input):
            raise UnsafeContentError("template candidate hash does not match its content")
    elif value.get("kind") == "approved":
        approval_fields = (
            "approved_at",
            "approved_by",
            "approval_reason",
            "source_candidate_sha256",
            "source_candidate_status",
        )
        if value.get("approved") is not True or value.get("status") != "APPROVED":
            raise UnsafeContentError("approved template has inconsistent status")
        if any(not isinstance(value.get(field), str) or not value.get(field, "").strip() for field in approval_fields):
            raise UnsafeContentError("approved template is missing approval provenance")
        if value["source_candidate_status"] not in {
            "CANDIDATE",
            "NEEDS_MORE_EVIDENCE",
            "NEEDS_REVIEW",
        }:
            raise UnsafeContentError("approved template has invalid source candidate status")
        if value["source_candidate_sha256"] != value["candidate_sha256"]:
            raise UnsafeContentError("approved template source candidate hash is inconsistent")
        projection = dict(value)
        for field in approval_fields:
            projection.pop(field)
        projection["kind"] = "candidate"
        projection["status"] = value["source_candidate_status"]
        projection["approved"] = False
        recorded_hash = projection.pop("candidate_sha256")
        if recorded_hash != sha256_json(projection):
            raise UnsafeContentError("approved template no longer matches its reviewed candidate")
    else:
        raise UnsafeContentError("template kind must be candidate or approved")
    if require_approved and value.get("approved") is not True:
        raise UnsafeContentError("template is not approved")


def approve_template(
    candidate_path: Path,
    *,
    store: ProposalStore,
    approved_by: str,
    reason: str,
) -> dict[str, Any]:
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnsafeContentError(f"cannot read template candidate: {exc}") from exc
    if not isinstance(candidate, dict):
        raise UnsafeContentError("template candidate must be an object")
    validate_template(candidate)
    if candidate.get("kind") != "candidate" or candidate.get("approved") is not False:
        raise UnsafeContentError("only an unapproved candidate can be approved")
    if not approved_by.strip() or not reason.strip():
        raise UnsafeContentError("template approval requires approver and reason")
    approved = dict(candidate)
    approved.update(
        {
            "kind": "approved",
            "status": "APPROVED",
            "approved": True,
            "approved_at": utc_now(),
            "approved_by": approved_by.strip(),
            "approval_reason": reason.strip(),
            "source_candidate_sha256": candidate["candidate_sha256"],
            "source_candidate_status": candidate["status"],
        }
    )
    path = store.template_path("approved", str(candidate["template_id"]))
    atomic_write(path, (stable_json(approved) + "\n").encode("utf-8"), root=store.workspace)
    approved["path"] = str(path)
    approved["artifact_sha256"] = sha256_text(path.read_text(encoding="utf-8"))
    return approved
