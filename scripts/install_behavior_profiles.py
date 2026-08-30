#!/usr/bin/env python3
"""Render or atomically install canonical Behavior Profiles into AGENTS.md."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BEHAVIOR_ROOT = REPOSITORY_ROOT / "behavior-profiles"

BEGIN_MARKER_TEXT = "<!-- BEGIN agent-skills behavior-profiles -->"
END_MARKER_TEXT = "<!-- END agent-skills behavior-profiles -->"
BEGIN_MARKER = BEGIN_MARKER_TEXT.encode("ascii")
END_MARKER = END_MARKER_TEXT.encode("ascii")
TEMP_PREFIX = ".install-behavior-profiles."


class InstallerError(RuntimeError):
    """A fail-closed installer validation or write error."""


@dataclass(frozen=True)
class ProfileSource:
    """Canonical Profile content selected through the root catalog."""

    name: str
    version: str
    body: str


@dataclass(frozen=True)
class TargetSnapshot:
    """Target state captured before rendering or replacement."""

    path: Path
    existed: bool
    data: bytes
    mode: int
    identity: tuple[int, int] | None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read catalog {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise InstallerError(f"catalog must be a JSON object: {path}")
    return value


def _parse_canonical_profile(path: Path) -> tuple[dict[str, str], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InstallerError(f"cannot read canonical profile {path}: {exc}") from exc

    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise InstallerError(f"canonical profile frontmatter is missing: {path}")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise InstallerError(
            f"canonical profile frontmatter is not closed: {path}"
        ) from exc

    metadata: dict[str, str] = {}
    for line_number, line in enumerate(lines[1:closing], start=2):
        if not line.strip():
            continue
        if line[0].isspace() or ":" not in line:
            raise InstallerError(
                f"unsupported canonical frontmatter at {path}:{line_number}"
            )
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key or not value or key in metadata:
            raise InstallerError(
                f"invalid canonical frontmatter at {path}:{line_number}"
            )
        metadata[key] = value

    body = "\n".join(lines[closing + 1 :]).strip()
    if not body:
        raise InstallerError(f"canonical profile body is empty: {path}")
    return metadata, body


def _within(root: Path, candidate: Path) -> bool:
    return candidate == root or root in candidate.parents


def _catalog_profiles(behavior_root: Path = BEHAVIOR_ROOT) -> dict[str, ProfileSource]:
    catalog_path = behavior_root / "catalog.json"
    try:
        catalog_stat = catalog_path.lstat()
    except OSError as exc:
        raise InstallerError(f"cannot inspect catalog {catalog_path}: {exc}") from exc
    if stat.S_ISLNK(catalog_stat.st_mode) or not stat.S_ISREG(catalog_stat.st_mode):
        raise InstallerError(f"catalog must be a regular non-symlink file: {catalog_path}")

    catalog = _read_json_object(catalog_path)
    entries = catalog.get("profiles")
    if not isinstance(entries, list):
        raise InstallerError("catalog profiles must be a list")

    try:
        resolved_root = behavior_root.resolve(strict=True)
    except OSError as exc:
        raise InstallerError(f"cannot resolve Behavior Profile root: {exc}") from exc

    profiles: dict[str, ProfileSource] = {}
    for index, raw_entry in enumerate(entries):
        label = f"catalog profiles[{index}]"
        if not isinstance(raw_entry, dict):
            raise InstallerError(f"{label} must be an object")
        name = raw_entry.get("name")
        version = raw_entry.get("version")
        relative_path = raw_entry.get("path")
        if not isinstance(name, str) or not name:
            raise InstallerError(f"{label}.name must be non-empty text")
        if name in profiles:
            raise InstallerError(f"duplicate catalog profile: {name}")
        if not isinstance(version, str) or not version:
            raise InstallerError(f"{label}.version must be non-empty text")
        if not isinstance(relative_path, str) or not relative_path:
            raise InstallerError(f"{label}.path must be non-empty text")

        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise InstallerError(f"{label}.path escapes Behavior Profile root")
        source_path = behavior_root / relative
        try:
            source_stat = source_path.lstat()
            resolved_source = source_path.resolve(strict=True)
        except OSError as exc:
            raise InstallerError(f"cannot inspect canonical profile {source_path}: {exc}") from exc
        if stat.S_ISLNK(source_stat.st_mode) or not stat.S_ISREG(source_stat.st_mode):
            raise InstallerError(
                f"canonical profile must be a regular non-symlink file: {source_path}"
            )
        if not _within(resolved_root, resolved_source):
            raise InstallerError(f"canonical profile escapes Behavior Profile root: {source_path}")

        metadata, body = _parse_canonical_profile(source_path)
        if metadata.get("name") != name:
            raise InstallerError(
                f"catalog/profile name mismatch for {name}: {metadata.get('name')!r}"
            )
        if metadata.get("version") != version:
            raise InstallerError(
                f"catalog/profile version mismatch for {name}: {metadata.get('version')!r}"
            )
        if BEGIN_MARKER_TEXT in body or END_MARKER_TEXT in body:
            raise InstallerError(f"canonical profile contains managed marker: {source_path}")
        profiles[name] = ProfileSource(name=name, version=version, body=body)
    return profiles


def select_profiles(
    requested_names: Sequence[str], behavior_root: Path = BEHAVIOR_ROOT
) -> list[ProfileSource]:
    """Resolve requested names through the catalog while preserving CLI order."""

    if not requested_names:
        raise InstallerError("at least one --profile is required")
    seen: set[str] = set()
    for name in requested_names:
        if name in seen:
            raise InstallerError(f"duplicate profile: {name}")
        seen.add(name)

    catalog = _catalog_profiles(behavior_root)
    unknown = [name for name in requested_names if name not in catalog]
    if unknown:
        raise InstallerError(f"unknown profile: {unknown[0]}")
    return [catalog[name] for name in requested_names]


def render_managed_block(profiles: Sequence[ProfileSource]) -> bytes:
    """Render a deterministic block without canonical YAML frontmatter."""

    if not profiles:
        raise InstallerError("cannot render an empty profile selection")
    parts = [
        BEGIN_MARKER_TEXT,
        "<!-- Generated from canonical behavior-profiles/catalog.json; edit the source package instead. -->",
        "",
        "このmanaged blockは指定順でProfileを配置する。Profile間のsemantic conflictを解決せず、",
        "新しいtool、権限またはtaskを付与しない。",
    ]
    for profile in profiles:
        parts.extend(
            [
                "",
                f"## Installed Behavior Profile: `{profile.name}`",
                "",
                f"- Profile name: `{profile.name}`",
                f"- Profile version: `{profile.version}`",
                "",
                profile.body,
            ]
        )
    parts.extend(["", END_MARKER_TEXT, ""])
    return "\n".join(parts).encode("utf-8")


def render_profiles(
    requested_names: Sequence[str], behavior_root: Path = BEHAVIOR_ROOT
) -> bytes:
    """Select canonical Profiles and render their managed block."""

    return render_managed_block(select_profiles(requested_names, behavior_root))


def _marker_line_end(data: bytes, position: int, marker: bytes) -> int | None:
    if position != 0 and data[position - 1 : position] != b"\n":
        return None
    after = position + len(marker)
    if after == len(data):
        return after
    if data[after : after + 2] == b"\r\n":
        return after + 2
    if data[after : after + 1] == b"\n":
        return after + 1
    return None


def _managed_span(data: bytes) -> tuple[int, int] | None:
    begin_count = data.count(BEGIN_MARKER)
    end_count = data.count(END_MARKER)
    if begin_count == 0 and end_count == 0:
        return None
    if begin_count != 1 or end_count != 1:
        raise InstallerError(
            "managed marker corruption: expected exactly one BEGIN/END pair"
        )

    begin = data.find(BEGIN_MARKER)
    end = data.find(END_MARKER)
    if end < begin:
        raise InstallerError("managed marker corruption: END appears before BEGIN")
    begin_line_end = _marker_line_end(data, begin, BEGIN_MARKER)
    end_line_end = _marker_line_end(data, end, END_MARKER)
    if begin_line_end is None or end_line_end is None:
        raise InstallerError("managed marker corruption: markers must be exact lines")
    if end < begin_line_end:
        raise InstallerError("managed marker corruption: nested or overlapping markers")
    return begin, end_line_end


def merge_managed_block(existing: bytes, block: bytes) -> bytes:
    """Append or replace one valid managed block while preserving outside bytes."""

    span = _managed_span(existing)
    if span is not None:
        start, end = span
        return existing[:start] + block + existing[end:]
    if not existing:
        return block
    if existing.endswith(b"\n\n"):
        separator = b""
    elif existing.endswith(b"\n"):
        separator = b"\n"
    else:
        separator = b"\n\n"
    return existing + separator + block


def _normalize_target(raw_target: Path | str) -> Path:
    raw = Path(raw_target)
    if ".." in raw.parts:
        raise InstallerError("target path must not contain '..'")
    target = Path(os.path.abspath(os.fspath(raw)))
    if target.name != "AGENTS.md":
        raise InstallerError("target basename must be AGENTS.md")
    return target


def _validate_parent_chain(parent: Path) -> None:
    chain: list[Path] = []
    current = parent
    while True:
        chain.append(current)
        if current.parent == current:
            break
        current = current.parent
    for component in reversed(chain):
        try:
            component_stat = component.lstat()
        except FileNotFoundError as exc:
            raise InstallerError(f"target parent does not exist: {component}") from exc
        except OSError as exc:
            raise InstallerError(f"cannot inspect target parent {component}: {exc}") from exc
        if stat.S_ISLNK(component_stat.st_mode):
            raise InstallerError(f"target parent path contains symlink: {component}")
        if not stat.S_ISDIR(component_stat.st_mode):
            raise InstallerError(f"target parent path is not a directory: {component}")


def _read_regular_file(path: Path, expected: os.stat_result) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InstallerError(f"cannot open target safely {path}: {exc}") from exc
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise InstallerError(f"target is not a regular file: {path}")
        if (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino):
            raise InstallerError(f"target changed during inspection: {path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError as exc:
        raise InstallerError(f"cannot read target {path}: {exc}") from exc
    finally:
        os.close(descriptor)


def inspect_target(raw_target: Path | str) -> TargetSnapshot:
    """Validate an AGENTS.md target and capture bytes without following symlinks."""

    target = _normalize_target(raw_target)
    _validate_parent_chain(target.parent)
    try:
        target_stat = target.lstat()
    except FileNotFoundError:
        return TargetSnapshot(
            path=target,
            existed=False,
            data=b"",
            mode=0o644,
            identity=None,
        )
    except OSError as exc:
        raise InstallerError(f"cannot inspect target {target}: {exc}") from exc

    if stat.S_ISLNK(target_stat.st_mode):
        raise InstallerError(f"target must not be a symlink: {target}")
    if not stat.S_ISREG(target_stat.st_mode):
        raise InstallerError(f"target is not a regular file: {target}")
    return TargetSnapshot(
        path=target,
        existed=True,
        data=_read_regular_file(target, target_stat),
        mode=stat.S_IMODE(target_stat.st_mode),
        identity=(target_stat.st_dev, target_stat.st_ino),
    )


def _assert_snapshot_unchanged(snapshot: TargetSnapshot) -> None:
    _validate_parent_chain(snapshot.path.parent)
    try:
        observed = snapshot.path.lstat()
    except FileNotFoundError:
        if snapshot.existed:
            raise InstallerError(f"target disappeared before replacement: {snapshot.path}")
        return
    except OSError as exc:
        raise InstallerError(f"cannot re-inspect target {snapshot.path}: {exc}") from exc

    if not snapshot.existed:
        raise InstallerError(f"target appeared before replacement: {snapshot.path}")
    if stat.S_ISLNK(observed.st_mode) or not stat.S_ISREG(observed.st_mode):
        raise InstallerError(f"target became unsafe before replacement: {snapshot.path}")
    if (observed.st_dev, observed.st_ino) != snapshot.identity:
        raise InstallerError(f"target identity changed before replacement: {snapshot.path}")
    if _read_regular_file(snapshot.path, observed) != snapshot.data:
        raise InstallerError(f"target content changed before replacement: {snapshot.path}")


def _atomic_write(snapshot: TargetSnapshot, content: bytes) -> None:
    temporary_path: Path | None = None
    descriptor: int | None = None
    replaced = False
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=TEMP_PREFIX,
            dir=snapshot.path.parent,
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), snapshot.mode)
            os.fsync(handle.fileno())

        _assert_snapshot_unchanged(snapshot)
        os.replace(temporary_path, snapshot.path)
        replaced = True
        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(snapshot.path.parent, directory_flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except InstallerError:
        raise
    except OSError as exc:
        action = "post-replace directory sync" if replaced else "atomic write"
        raise InstallerError(f"{action} failed for {snapshot.path}: {exc}") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


def _unified_diff(before: bytes, after: bytes) -> bytes:
    if before == after:
        return b""
    lines = difflib.diff_bytes(
        difflib.unified_diff,
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=b"a/AGENTS.md",
        tofile=b"b/AGENTS.md",
        lineterm=b"\n",
    )
    return b"".join(lines)


def install_target(raw_target: Path | str, block: bytes, *, apply: bool) -> bytes:
    """Return a dry-run diff, or atomically apply and return no output."""

    snapshot = inspect_target(raw_target)
    updated = merge_managed_block(snapshot.data, block)
    if not apply:
        return _unified_diff(snapshot.data, updated)
    if updated == snapshot.data:
        return b""
    _atomic_write(snapshot, updated)
    return b""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render or install canonical Behavior Profiles in AGENTS.md."
    )
    parser.add_argument(
        "--profile",
        action="append",
        required=True,
        help="Profile name from behavior-profiles/catalog.json; repeat to preserve order.",
    )
    parser.add_argument("--target", type=Path, help="AGENTS.md target; default is stdout.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Atomically update --target. Without this flag, --target is dry-run only.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.apply and args.target is None:
        parser.error("--apply requires --target")
    try:
        block = render_profiles(args.profile)
        if args.target is None:
            output = block
        else:
            output = install_target(args.target, block, apply=args.apply)
    except InstallerError as exc:
        parser.error(str(exc))
    if output:
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
