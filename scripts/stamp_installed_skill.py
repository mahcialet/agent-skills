#!/usr/bin/env python3
"""Add install provenance to a copied Skill without changing its source."""

from __future__ import annotations

import os
import re
import stat
import tempfile
from pathlib import Path

from validate_skills import parse_frontmatter


MAX_DESCRIPTION_LENGTH = 1024
INSTALL_MARKERS = ("Install source:", "Install context:")
OID_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
BLOCK_SCALAR_PATTERN = re.compile(r"[>|](?:[1-9][+-]?|[+-][1-9]?)?\Z")


class StampError(ValueError):
    """Raised when a Skill description cannot be stamped safely."""


def annotation_for(
    state: str,
    oid: str | None,
    *,
    short_oid: str | None = None,
) -> str:
    if state in {"clean", "dirty"}:
        if oid is None or OID_PATTERN.fullmatch(oid) is None:
            raise StampError("clean and dirty states require a full lowercase Git object ID")
        if short_oid is not None and (
            re.fullmatch(r"[0-9a-f]{12,64}", short_oid) is None
            or not oid.startswith(short_oid)
        ):
            raise StampError("short Git object ID must be a prefix of the full object ID")
    elif oid is not None or short_oid is not None:
        raise StampError(f"state {state!r} must not include a Git object ID")

    displayed_oid = short_oid or (oid[:12] if oid is not None else None)

    if state == "clean":
        return f"Install source: Git commit {displayed_oid}."
    if state == "dirty":
        return (
            f"Install context: Git HEAD {displayed_oid}; "
            "copied Skill differs from the committed tree."
        )
    if state == "unborn":
        return "Install source: unborn Git worktree; copied content has no commit ID."
    if state == "non-git":
        return "Install source: non-Git directory; no commit ID is available."
    if state == "git-unavailable":
        return "Install source: Git unavailable; no commit ID is available."
    raise StampError(f"unsupported install state: {state}")


def _line_text(line: str) -> str:
    return line.rstrip("\r\n")


def _line_ending(lines: list[str]) -> str:
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"


def stamp_text(text: str, annotation: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or _line_text(lines[0]) != "---":
        raise StampError("SKILL.md must start with YAML frontmatter")

    closing_index = next(
        (index for index in range(1, len(lines)) if _line_text(lines[index]) == "---"),
        None,
    )
    if closing_index is None:
        raise StampError("SKILL.md frontmatter is not closed")

    description_indexes = [
        index
        for index in range(1, closing_index)
        if re.match(r"^description:[ \t]*", _line_text(lines[index]))
    ]
    if len(description_indexes) != 1:
        raise StampError("SKILL.md frontmatter must contain exactly one description")

    description_index = description_indexes[0]
    description_line = _line_text(lines[description_index])
    value = description_line.split(":", 1)[1].strip()
    newline = _line_ending(lines)

    if BLOCK_SCALAR_PATTERN.fullmatch(value):
        block_end = description_index + 1
        while block_end < closing_index:
            content = _line_text(lines[block_end])
            if content and not content[0].isspace():
                break
            block_end += 1

        if not any(
            _line_text(content_line).strip()
            for content_line in lines[description_index + 1 : block_end]
        ):
            raise StampError("block description must not be empty")

        raw_description = "".join(lines[description_index:block_end])
        if any(marker in raw_description for marker in INSTALL_MARKERS):
            raise StampError("description already contains an install source marker")

        indentation = "  "
        for content_line in lines[description_index + 1 : block_end]:
            content = _line_text(content_line)
            if content.strip():
                indentation = content[: len(content) - len(content.lstrip())]
                break
        lines.insert(block_end, f"{indentation}{annotation}{newline}")
    else:
        if not value:
            raise StampError("inline description must not be empty")
        if any(marker in value for marker in INSTALL_MARKERS):
            raise StampError("description already contains an install source marker")
        if re.search(r"[ \t]#", value):
            raise StampError("inline descriptions with comments cannot be stamped safely")

        if value[0] in {'"', "'"}:
            if len(value) < 2 or value[-1] != value[0]:
                raise StampError("quoted description is not closed on the same line")
            updated_value = f"{value[:-1]} {annotation}{value[-1]}"
        elif value[0] in "[{|>&*!%@`":
            raise StampError("unsupported inline description form")
        else:
            updated_value = f"{value} {annotation}"
        lines[description_index] = f"description: {updated_value}{newline}"

    return "".join(lines)


def stamp_file(source: Path, destination: Path, annotation: str) -> None:
    try:
        source_stat = source.lstat()
    except OSError as error:
        raise StampError(f"source SKILL.md not found: {source}: {error}") from error
    if not stat.S_ISREG(source_stat.st_mode):
        raise StampError(f"source SKILL.md not found: {source}")
    if os.path.lexists(destination) and destination.is_symlink():
        raise StampError("destination SKILL.md must be a regular, non-link file")
    if destination.exists() and os.path.samefile(source, destination):
        raise StampError("source and destination SKILL.md must be different files")

    try:
        source_frontmatter, _ = parse_frontmatter(source)
        source_description = source_frontmatter.get("description")
        if not isinstance(source_description, str) or not source_description.strip():
            raise StampError("source description is missing or empty")
        source_text = source.read_bytes().decode("utf-8")
        stamped_text = stamp_text(source_text, annotation)
    except (OSError, UnicodeError, ValueError) as error:
        raise StampError(str(error)) from error

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=destination.parent,
            prefix=".install-local-skill.",
            delete=False,
        ) as handle:
            handle.write(stamped_text)
            temporary_path = Path(handle.name)

        source_mode = stat.S_IMODE(source.stat().st_mode)
        temporary_path.chmod(source_mode)
        frontmatter, _ = parse_frontmatter(temporary_path)
        description = frontmatter.get("description")
        if not isinstance(description, str) or not description.strip():
            raise StampError("stamped description is missing or empty")
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise StampError(
                "stamped description exceeds the 1024-character Skill limit"
            )
        if description.count(annotation) != 1:
            raise StampError("install source marker was not added exactly once")

        os.replace(temporary_path, destination)
        temporary_path = None
    except (OSError, UnicodeError, ValueError) as error:
        raise StampError(str(error)) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
