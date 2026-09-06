"""Private local proposal store with immutable artifacts and SQLite state."""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

from .errors import StateError, StorageError
from .model import sha256_json, sha256_text, stable_json, utc_now

ID_RE = re.compile(r"^[0-9a-f]{32}$")
TERMINAL_STATES = {"APPLIED", "NO_CHANGE", "REJECTED", "SUPERSEDED"}
PENDING_STATES = {
    "DRAFT",
    "PREPARED",
    "PENDING_PERMISSION",
    "NEEDS_REVIEW",
    "NEEDS_REMERGE",
    "READY",
    "APPLYING",
    "VERIFYING",
    "UNKNOWN_REMOTE_RESULT",
    "PARTIAL_APPLIED",
    "FAILED",
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PREPARED", "REJECTED", "SUPERSEDED"},
    "PREPARED": {"PENDING_PERMISSION", "NEEDS_REVIEW", "NEEDS_REMERGE", "READY", "NO_CHANGE", "REJECTED", "SUPERSEDED"},
    "PENDING_PERMISSION": {"PENDING_PERMISSION", "READY", "NEEDS_REMERGE", "NEEDS_REVIEW", "REJECTED", "SUPERSEDED"},
    "NEEDS_REVIEW": {"NEEDS_REVIEW", "READY", "NEEDS_REMERGE", "REJECTED", "SUPERSEDED"},
    "NEEDS_REMERGE": {"NEEDS_REMERGE", "READY", "REJECTED", "SUPERSEDED"},
    "READY": {"READY", "PENDING_PERMISSION", "NEEDS_REMERGE", "NEEDS_REVIEW", "APPLYING", "REJECTED", "SUPERSEDED"},
    "APPLYING": {"VERIFYING", "UNKNOWN_REMOTE_RESULT", "PARTIAL_APPLIED", "FAILED"},
    "VERIFYING": {"APPLIED", "UNKNOWN_REMOTE_RESULT", "PARTIAL_APPLIED", "FAILED"},
    "UNKNOWN_REMOTE_RESULT": {"UNKNOWN_REMOTE_RESULT", "VERIFYING", "APPLIED", "PARTIAL_APPLIED", "REJECTED", "SUPERSEDED"},
    "PARTIAL_APPLIED": {"PARTIAL_APPLIED", "VERIFYING", "APPLIED", "REJECTED", "SUPERSEDED"},
    "FAILED": {"FAILED", "READY", "NEEDS_REMERGE", "PENDING_PERMISSION", "REJECTED", "SUPERSEDED"},
    "NO_CHANGE": set(),
    "APPLIED": set(),
    "REJECTED": set(),
    "SUPERSEDED": set(),
}


def _validate_id(value: str, label: str) -> None:
    if not ID_RE.fullmatch(value):
        raise StorageError(f"invalid {label}")


def _decode_json(value: object, label: str, expected_type: type[Any]) -> Any:
    if not isinstance(value, (str, bytes, bytearray)):
        raise StorageError(f"{label} is not encoded JSON")
    try:
        decoded = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageError(f"{label} is corrupt") from exc
    if not isinstance(decoded, expected_type):
        raise StorageError(f"{label} has an invalid JSON type")
    return decoded


def _chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError as exc:
        raise StorageError(f"cannot protect local state path: {path}") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        directory_fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise StorageError(f"cannot durably persist state directory: {path}") from exc


def _assert_private_root(path: Path) -> None:
    if path.is_symlink():
        raise StorageError("work directory must not be a symlink")
    existed = path.exists()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _chmod(path, 0o700)
    if not existed:
        _fsync_directory(path.parent)


def _assert_contained(path: Path, root: Path) -> None:
    resolved_root = root.resolve(strict=True)
    current = path
    while current != root:
        if current.exists() and current.is_symlink():
            raise StorageError(f"managed state path must not be a symlink: {current}")
        if current == current.parent:
            raise StorageError("managed state path is outside the workspace")
        current = current.parent
    try:
        path.resolve(strict=False).relative_to(resolved_root)
    except ValueError as exc:
        raise StorageError("managed state path escapes the workspace") from exc


def _secure_directory(path: Path, root: Path) -> None:
    if path.is_symlink():
        raise StorageError(f"managed state directory must not be a symlink: {path}")
    _assert_contained(path, root)
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        _chmod(directory, 0o700)
        _fsync_directory(directory.parent)
    if not path.is_dir():
        raise StorageError(f"managed state path is not a directory: {path}")
    _chmod(path, 0o700)


def _refuse_unignored_repository_state(path: Path) -> None:
    candidate = path.absolute()
    for parent in (candidate, *candidate.parents):
        if (parent / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(parent), "check-ignore", "--quiet", "--", str(candidate)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode != 0:
                raise StorageError(
                    "work directory is inside a Git repository but is not ignored; "
                    "configure an ignore rule or use user-scoped state before storing ticket content"
                )
            return


def atomic_write(path: Path, data: bytes, *, mode: int = 0o600, root: Path | None = None) -> None:
    if root is not None:
        _assert_contained(path.parent, root)
    if path.exists() or path.is_symlink():
        raise StorageError(f"immutable artifact already exists: {path.name}")
    parent = path.parent
    if parent.is_symlink():
        raise StorageError("artifact parent must not be a symlink")
    if root is not None:
        _secure_directory(parent, root)
    else:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        _chmod(parent, 0o700)
    fd = -1
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".tmp-", dir=parent)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() or path.is_symlink():
            raise StorageError(f"immutable artifact already exists: {path.name}")
        os.link(temp_name, path)
        os.unlink(temp_name)
        temp_name = ""
        _fsync_directory(parent)
    except (OSError, StorageError) as exc:
        raise StorageError(f"cannot persist artifact {path}: {exc}") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if temp_name:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)


def atomic_replace(path: Path, data: bytes, *, root: Path, mode: int = 0o600) -> None:
    _assert_contained(path.parent, root)
    _secure_directory(path.parent, root)
    if path.is_symlink():
        raise StorageError("mutable state manifest must not be a symlink")
    fd = -1
    temp_name = ""
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb", closefd=True) as handle:
            fd = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = ""
        _fsync_directory(path.parent)
    except (OSError, StorageError) as exc:
        raise StorageError("cannot update workspace manifest") from exc
    finally:
        if fd >= 0:
            os.close(fd)
        if temp_name:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)


class ProposalStore:
    def __init__(self, root: Path, *, workspace_id: str, audit_on_open: bool = True) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", workspace_id):
            raise StorageError("workspace_id contains unsafe characters")
        if root.is_symlink():
            raise StorageError("work directory must not be a symlink")
        _refuse_unignored_repository_state(root)
        self.root = root.resolve(strict=False)
        self.workspace_id = workspace_id
        self.workspace = self.root / workspace_id
        _assert_private_root(self.root)
        _assert_private_root(self.workspace)
        for name in ("proposals", "receipts", "locks", "templates", "recovery"):
            directory = self.workspace / name
            _secure_directory(directory, self.workspace)
        self.db_path = self.workspace / "state.sqlite3"
        if self.db_path.is_symlink():
            raise StorageError("state database must not be a symlink")
        self._initialize()
        workspace_file = self.workspace / "workspace.json"
        if workspace_file.is_symlink():
            raise StorageError("workspace manifest must not be a symlink")
        if not workspace_file.exists():
            atomic_write(
                workspace_file,
                (
                    stable_json(
                        {"schema_version": 1, "workspace_id": workspace_id, "profile_bindings": {}}
                    )
                    + "\n"
                ).encode("utf-8"),
                root=self.workspace,
            )
        if audit_on_open:
            self.audit()

    def bind_profile(self, profile_name: str, binding: dict[str, Any]) -> None:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", profile_name):
            raise StorageError("profile name contains unsafe characters")
        with self.workspace_lock():
            self._bind_profile_unlocked(profile_name, binding)

    def _bind_profile_unlocked(self, profile_name: str, binding: dict[str, Any]) -> None:
        workspace_file = self.workspace / "workspace.json"
        try:
            manifest = _decode_json(
                workspace_file.read_text(encoding="utf-8"),
                "workspace manifest",
                dict,
            )
        except OSError as exc:
            raise StorageError("workspace manifest is corrupt") from exc
        if manifest.get("schema_version") != 1:
            raise StorageError("workspace manifest is invalid")
        bindings = manifest.get("profile_bindings")
        if not isinstance(bindings, dict):
            raise StorageError("workspace profile bindings are invalid")
        existing = bindings.get(profile_name)
        if existing is not None and existing != binding:
            raise StorageError("workspace profile binding conflicts with trusted config")
        if existing == binding:
            return
        bindings[profile_name] = binding
        atomic_replace(
            workspace_file,
            (stable_json(manifest) + "\n").encode("utf-8"),
            root=self.workspace,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    profile_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    identity_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    required_permissions_json TEXT NOT NULL,
                    current_revision INTEGER NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    operation_id TEXT,
                    payload_sha256 TEXT,
                    last_validated_at TEXT
                    ,last_mode TEXT
                );
                CREATE TABLE IF NOT EXISTS revisions (
                    proposal_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (proposal_id, revision),
                    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    state TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (proposal_id) REFERENCES proposals(proposal_id)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proposal_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (proposal_id, revision, content_sha256, approved_by),
                    FOREIGN KEY (proposal_id, revision) REFERENCES revisions(proposal_id, revision)
                );
                CREATE INDEX IF NOT EXISTS proposal_state_idx ON proposals(state, updated_at);
                CREATE INDEX IF NOT EXISTS event_proposal_idx ON events(proposal_id, sequence);
                CREATE INDEX IF NOT EXISTS approval_proposal_idx ON approvals(proposal_id, revision);
                """
            )
            current = connection.execute("SELECT value FROM metadata WHERE key='db_schema_version'").fetchone()
            if current is None:
                connection.execute("INSERT INTO metadata(key, value) VALUES('db_schema_version', '1')")
            elif current["value"] != "1":
                raise StorageError("unsupported state database schema")
            connection.commit()
        except sqlite3.Error as exc:
            raise StorageError(f"cannot initialize state database: {exc}") from exc
        finally:
            connection.close()
        _chmod(self.db_path, 0o600)

    def _revision_dir(self, proposal_id: str, revision: int) -> Path:
        _validate_id(proposal_id, "proposal ID")
        if revision <= 0:
            raise StorageError("invalid proposal revision")
        return self.workspace / "proposals" / proposal_id / "revisions" / f"{revision:04d}"

    def create_proposal(
        self,
        *,
        profile_name: str,
        operation: str,
        identity: dict[str, Any],
        state: str,
        required_permissions: list[str],
        reason: str | None,
        artifacts: dict[str, bytes],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        with self.workspace_lock():
            return self._create_proposal_unlocked(
                profile_name=profile_name,
                operation=operation,
                identity=identity,
                state=state,
                required_permissions=required_permissions,
                reason=reason,
                artifacts=artifacts,
                metadata=metadata,
            )

    def _create_proposal_unlocked(
        self,
        *,
        profile_name: str,
        operation: str,
        identity: dict[str, Any],
        state: str,
        required_permissions: list[str],
        reason: str | None,
        artifacts: dict[str, bytes],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if state not in ALLOWED_TRANSITIONS:
            raise StateError(f"unknown proposal state: {state}")
        proposal_id = uuid.uuid4().hex
        revision = 1
        revision_dir = self._revision_dir(proposal_id, revision)
        for name, data in artifacts.items():
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name):
                raise StorageError("unsafe artifact name")
            atomic_write(revision_dir / name, data, root=self.workspace)
        summary = {
            "schema_version": 1,
            "proposal_id": proposal_id,
            "operation": operation,
            "state": state,
            "reason": reason,
            "required_permissions": required_permissions,
            "revision": revision,
            "created_at": utc_now(),
        }
        atomic_write(
            self.workspace / "proposals" / proposal_id / "proposal.json",
            (stable_json(summary) + "\n").encode("utf-8"),
            root=self.workspace,
        )
        permissions_text = ", ".join(required_permissions) if required_permissions else "なし"
        proposal_markdown = (
            f"# Proposal {proposal_id}\n\n"
            f"- Operation: {operation}\n"
            f"- State: {state}\n"
            f"- Required permissions: {permissions_text}\n"
            f"- Reason: {reason or 'なし'}\n"
            f"- Revision: {revision}\n"
            f"- Created at: {summary['created_at']}\n"
        )
        atomic_write(
            self.workspace / "proposals" / proposal_id / "proposal.md",
            proposal_markdown.encode("utf-8"),
            root=self.workspace,
        )
        content_hash = sha256_json({name: sha256_text(value.decode("utf-8")) for name, value in sorted(artifacts.items())})
        now = summary["created_at"]
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO proposals(
                    proposal_id, profile_name, operation, identity_json, state,
                    required_permissions_json, current_revision, reason, created_at, updated_at
                    ,last_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    proposal_id,
                    profile_name,
                    operation,
                    stable_json(identity),
                    state,
                    stable_json(required_permissions),
                    revision,
                    reason,
                    now,
                    now,
                    None,
                ),
            )
            connection.execute(
                "INSERT INTO revisions VALUES (?, ?, ?, ?, ?)",
                (proposal_id, revision, stable_json(metadata), content_hash, now),
            )
            connection.execute(
                "INSERT INTO events(proposal_id, event, state, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, "PROPOSAL_CREATED", state, stable_json({"revision": revision, "reason": reason}), now),
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise StorageError(f"cannot record proposal: {exc}") from exc
        finally:
            connection.close()
        return self.get_proposal(proposal_id)

    def add_revision(
        self,
        proposal_id: str,
        *,
        state: str,
        reason: str | None,
        artifacts: dict[str, bytes],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        with self.workspace_lock():
            return self._add_revision_unlocked(
                proposal_id,
                state=state,
                reason=reason,
                artifacts=artifacts,
                metadata=metadata,
            )

    def _add_revision_unlocked(
        self,
        proposal_id: str,
        *,
        state: str,
        reason: str | None,
        artifacts: dict[str, bytes],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        proposal = self.get_proposal(proposal_id)
        revision = int(proposal["current_revision"]) + 1
        revision_dir = self._revision_dir(proposal_id, revision)
        for name, data in artifacts.items():
            if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name):
                raise StorageError("unsafe artifact name")
            atomic_write(revision_dir / name, data, root=self.workspace)
        content_hash = sha256_json({name: sha256_text(value.decode("utf-8")) for name, value in sorted(artifacts.items())})
        now = utc_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT state, current_revision FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row is None or int(row["current_revision"]) != revision - 1:
                raise StorageError("proposal changed during revision creation")
            self._assert_transition(row["state"], state)
            connection.execute(
                "INSERT INTO revisions VALUES (?, ?, ?, ?, ?)",
                (proposal_id, revision, stable_json(metadata), content_hash, now),
            )
            connection.execute(
                "UPDATE proposals SET state=?, reason=?, current_revision=?, updated_at=?, operation_id=NULL, payload_sha256=NULL WHERE proposal_id=?",
                (state, reason, revision, now, proposal_id),
            )
            connection.execute(
                "INSERT INTO events(proposal_id, event, state, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, "REVISION_CREATED", state, stable_json({"revision": revision, "reason": reason}), now),
            )
            connection.commit()
        except (sqlite3.Error, StorageError, StateError) as exc:
            connection.rollback()
            if isinstance(exc, (StorageError, StateError)):
                raise
            raise StorageError(f"cannot record proposal revision: {exc}") from exc
        finally:
            connection.close()
        return self.get_proposal(proposal_id)

    def _assert_transition(self, old: str, new: str) -> None:
        if old == new:
            return
        if new not in ALLOWED_TRANSITIONS.get(old, set()):
            raise StateError(f"invalid proposal transition: {old} -> {new}")

    def transition(
        self,
        proposal_id: str,
        state: str,
        *,
        event: str,
        reason: str | None = None,
        data: dict[str, Any] | None = None,
        operation_id: str | None = None,
        payload_sha256: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        _validate_id(proposal_id, "proposal ID")
        if state not in ALLOWED_TRANSITIONS:
            raise StateError(f"unknown proposal state: {state}")
        now = utc_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT state FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
            if row is None:
                raise StorageError("proposal not found")
            self._assert_transition(row["state"], state)
            connection.execute(
                """UPDATE proposals SET state=?, reason=?, updated_at=?, last_validated_at=?,
                   operation_id=COALESCE(?, operation_id), payload_sha256=COALESCE(?, payload_sha256),
                   last_mode=COALESCE(?, last_mode)
                   WHERE proposal_id=?""",
                (state, reason, now, now, operation_id, payload_sha256, mode, proposal_id),
            )
            connection.execute(
                "INSERT INTO events(proposal_id, event, state, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, event, state, stable_json(data or {}), now),
            )
            connection.commit()
        except (sqlite3.Error, StorageError, StateError) as exc:
            connection.rollback()
            if isinstance(exc, (StorageError, StateError)):
                raise
            raise StorageError(f"cannot transition proposal: {exc}") from exc
        finally:
            connection.close()
        return self.get_proposal(proposal_id)

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        _validate_id(proposal_id, "proposal ID")
        connection = self._connect()
        try:
            row = connection.execute("SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise StorageError("proposal not found")
        result = dict(row)
        result["identity"] = _decode_json(
            result.pop("identity_json"), "proposal identity", dict
        )
        result["required_permissions"] = _decode_json(
            result.pop("required_permissions_json"),
            "proposal required permissions",
            list,
        )
        if any(not isinstance(value, str) for value in result["required_permissions"]):
            raise StorageError("proposal required permissions contain an invalid value")
        if result["state"] not in ALLOWED_TRANSITIONS:
            raise StorageError("proposal state is invalid")
        result["schema_version"] = 1
        result["revision_path"] = str(self._revision_dir(proposal_id, int(result["current_revision"])))
        return result

    def get_revision(self, proposal_id: str, revision: int | None = None) -> dict[str, Any]:
        proposal = self.get_proposal(proposal_id)
        selected = int(proposal["current_revision"]) if revision is None else revision
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM revisions WHERE proposal_id=? AND revision=?",
                (proposal_id, selected),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise StorageError("proposal revision not found")
        result = dict(row)
        result["metadata"] = _decode_json(
            result.pop("metadata_json"), "proposal revision metadata", dict
        )
        revision_path = self._revision_dir(proposal_id, selected)
        actual_hash = self._revision_content_hash(revision_path)
        if actual_hash != result["content_sha256"]:
            raise StorageError("proposal revision artifact hash mismatch")
        metadata_path = revision_path / "metadata.json"
        if metadata_path.is_file() and not metadata_path.is_symlink():
            try:
                artifact_metadata = _decode_json(
                    metadata_path.read_text(encoding="utf-8"),
                    "proposal revision metadata artifact",
                    dict,
                )
            except OSError as exc:
                raise StorageError("proposal revision metadata artifact is corrupt") from exc
            if artifact_metadata != result["metadata"]:
                raise StorageError("database metadata does not match immutable metadata artifact")
        result["path"] = str(revision_path)
        return result

    def read_artifact(self, proposal_id: str, name: str, revision: int | None = None) -> bytes:
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name):
            raise StorageError("unsafe artifact name")
        selected = self.get_revision(proposal_id, revision)
        path = Path(selected["path"]) / name
        if path.is_symlink() or not path.is_file():
            raise StorageError(f"proposal artifact is missing: {name}")
        return path.read_bytes()

    def list_pending(self) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT proposal_id FROM proposals WHERE state NOT IN ('APPLIED','NO_CHANGE','REJECTED','SUPERSEDED') ORDER BY updated_at"
            ).fetchall()
        finally:
            connection.close()
        return [self.get_proposal(row["proposal_id"]) for row in rows]

    def history(self, proposal_id: str | None = None) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            if proposal_id is None:
                rows = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            else:
                _validate_id(proposal_id, "proposal ID")
                rows = connection.execute(
                    "SELECT * FROM events WHERE proposal_id=? ORDER BY sequence", (proposal_id,)
                ).fetchall()
        finally:
            connection.close()
        result = []
        for row in rows:
            item = dict(row)
            item["data"] = _decode_json(
                item.pop("data_json"), "proposal history event data", dict
            )
            if item["state"] not in ALLOWED_TRANSITIONS:
                raise StorageError("proposal history event state is invalid")
            item["schema_version"] = 1
            result.append(item)
        return result

    def record_approval(
        self,
        proposal_id: str,
        *,
        revision: int,
        content_sha256: str,
        approved_by: str,
        reason: str,
    ) -> dict[str, Any]:
        _validate_id(proposal_id, "proposal ID")
        if revision <= 0 or not re.fullmatch(r"[0-9a-f]{64}", content_sha256):
            raise StorageError("approval revision or content hash is invalid")
        if not approved_by.strip() or not reason.strip():
            raise StorageError("approval requires approved_by and reason")
        current = self.get_revision(proposal_id, revision)
        if current["content_sha256"] != content_sha256:
            raise StorageError("approval hash does not match the selected immutable revision")
        now = utc_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT OR IGNORE INTO approvals(
                    proposal_id, revision, content_sha256, approved_by, reason, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (proposal_id, revision, content_sha256, approved_by.strip(), reason.strip(), now),
            )
            row = connection.execute(
                """SELECT * FROM approvals
                   WHERE proposal_id=? AND revision=? AND content_sha256=? AND approved_by=?""",
                (proposal_id, revision, content_sha256, approved_by.strip()),
            ).fetchone()
            proposal = connection.execute(
                "SELECT state FROM proposals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if row is None or proposal is None:
                raise StorageError("cannot persist approval")
            connection.execute(
                "INSERT INTO events(proposal_id, event, state, data_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    proposal_id,
                    "CONTENT_REVISION_APPROVED",
                    proposal["state"],
                    stable_json(
                        {
                            "revision": revision,
                            "content_sha256": content_sha256,
                            "approved_by": approved_by.strip(),
                        }
                    ),
                    now,
                ),
            )
            connection.commit()
        except (sqlite3.Error, StorageError) as exc:
            connection.rollback()
            if isinstance(exc, StorageError):
                raise
            raise StorageError(f"cannot record content approval: {exc}") from exc
        finally:
            connection.close()
        result = dict(row)
        result["schema_version"] = 1
        return result

    def approvals(self, proposal_id: str, revision: int | None = None) -> list[dict[str, Any]]:
        proposal = self.get_proposal(proposal_id)
        selected = int(proposal["current_revision"]) if revision is None else revision
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM approvals WHERE proposal_id=? AND revision=? ORDER BY approval_id",
                (proposal_id, selected),
            ).fetchall()
        finally:
            connection.close()
        return [dict(row) | {"schema_version": 1} for row in rows]

    def save_receipt(self, operation_id: str, receipt: dict[str, Any]) -> Path:
        _validate_id(operation_id, "operation ID")
        path = self.workspace / "receipts" / f"{operation_id}.json"
        data = (stable_json(receipt) + "\n").encode("utf-8")
        if path.exists() and not path.is_symlink():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise StorageError("existing receipt is unreadable") from exc
            existing_comparable = dict(existing) if isinstance(existing, dict) else {}
            new_comparable = dict(receipt)
            for volatile_key in ("verified_at", "remote_retrieved_at"):
                existing_comparable.pop(volatile_key, None)
                new_comparable.pop(volatile_key, None)
            if existing_comparable != new_comparable:
                raise StorageError("existing receipt does not match recovered remote evidence")
            return path
        atomic_write(path, data, root=self.workspace)
        return path

    def template_path(self, kind: str, template_id: str) -> Path:
        if kind not in {"candidates", "approved"} or not ID_RE.fullmatch(template_id):
            raise StorageError("invalid template path")
        directory = self.workspace / "templates" / kind
        _secure_directory(directory, self.workspace)
        return directory / f"{template_id}.json"

    @contextlib.contextmanager
    def workspace_lock(self, *, timeout: float = 10.0) -> Iterator[None]:
        with self.target_lock(sha256_text("ticket-state-workspace-wide-lock"), timeout=timeout):
            yield

    @contextlib.contextmanager
    def target_lock(self, identity_key: str, *, timeout: float = 10.0) -> Iterator[None]:
        if not re.fullmatch(r"[0-9a-f]{64}", identity_key):
            raise StorageError("invalid target lock key")
        path = self.workspace / "locks" / f"{identity_key}.lock"
        _assert_contained(path.parent, self.workspace)
        if path.is_symlink():
            raise StorageError("lock path must not be a symlink")
        handle = path.open("a+b")
        _chmod(path, 0o600)
        if os.name == "nt" and path.stat().st_size == 0:
            handle.write(b"\0")
            handle.flush()
        deadline = time.monotonic() + timeout
        locked = False
        try:
            while not locked:
                try:
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except (BlockingIOError, OSError):
                    if time.monotonic() >= deadline:
                        raise StorageError("timed out waiting for target lock")
                    time.sleep(0.05)
            yield
        finally:
            if locked:
                with contextlib.suppress(OSError):
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    def _revision_content_hash(self, path: Path) -> str:
        if path.is_symlink() or not path.is_dir():
            raise StorageError("proposal revision directory is missing or unsafe")
        _assert_contained(path, self.workspace)
        hashes: dict[str, str] = {}
        for artifact in sorted(path.iterdir(), key=lambda item: item.name):
            if artifact.is_symlink() or not artifact.is_file():
                raise StorageError("proposal revision contains an unsafe artifact")
            try:
                text = artifact.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise StorageError("proposal revision artifact is unreadable") from exc
            hashes[artifact.name] = sha256_text(text)
        return sha256_json(hashes)

    def audit(self) -> dict[str, Any]:
        if self.db_path.is_symlink():
            raise StorageError("state database must not be a symlink")
        workspace_file = self.workspace / "workspace.json"
        if workspace_file.is_symlink() or not workspace_file.is_file():
            raise StorageError("workspace manifest is missing or unsafe")
        try:
            manifest = _decode_json(
                workspace_file.read_text(encoding="utf-8"),
                "workspace manifest",
                dict,
            )
        except OSError as exc:
            raise StorageError("workspace manifest is unreadable") from exc
        if manifest.get("schema_version") != 1 or not isinstance(
            manifest.get("profile_bindings"), dict
        ):
            raise StorageError("workspace manifest is invalid")
        connection = self._connect()
        try:
            proposal_rows = connection.execute(
                "SELECT proposal_id, identity_json, state, required_permissions_json, "
                "current_revision, operation_id, payload_sha256 FROM proposals"
            ).fetchall()
            revision_rows = connection.execute(
                "SELECT proposal_id, revision, metadata_json, content_sha256 FROM revisions"
            ).fetchall()
            event_rows = connection.execute(
                "SELECT state, data_json FROM events"
            ).fetchall()
            approval_rows = connection.execute(
                "SELECT proposal_id, revision, content_sha256 FROM approvals"
            ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"cannot audit state database: {exc}") from exc
        finally:
            connection.close()
        for row in proposal_rows:
            _validate_id(row["proposal_id"], "proposal ID")
            identity = _decode_json(row["identity_json"], "proposal identity", dict)
            required = _decode_json(
                row["required_permissions_json"],
                "proposal required permissions",
                list,
            )
            if not identity or any(not isinstance(value, str) for value in required):
                raise StorageError("proposal database JSON is invalid")
            if row["state"] not in ALLOWED_TRANSITIONS or int(row["current_revision"]) <= 0:
                raise StorageError("proposal database state is invalid")
            if row["operation_id"] is not None and not ID_RE.fullmatch(row["operation_id"]):
                raise StorageError("proposal operation ID is invalid")
            if row["payload_sha256"] is not None and not re.fullmatch(
                r"[0-9a-f]{64}", row["payload_sha256"]
            ):
                raise StorageError("proposal payload hash is invalid")
            if row["state"] == "APPLIED" and (
                row["operation_id"] is None or row["payload_sha256"] is None
            ):
                raise StorageError("applied proposal is missing receipt identity")
        for row in revision_rows:
            _validate_id(row["proposal_id"], "proposal ID")
            _decode_json(row["metadata_json"], "proposal revision metadata", dict)
            if not re.fullmatch(r"[0-9a-f]{64}", row["content_sha256"]):
                raise StorageError("proposal revision content hash is invalid")
        for row in event_rows:
            if row["state"] not in ALLOWED_TRANSITIONS:
                raise StorageError("proposal history event state is invalid")
            _decode_json(row["data_json"], "proposal history event data", dict)
        expected_proposals = {row["proposal_id"] for row in proposal_rows}
        proposals_root = self.workspace / "proposals"
        actual_proposals: set[str] = set()
        for proposal_dir in proposals_root.iterdir():
            if proposal_dir.is_symlink() or not proposal_dir.is_dir() or not ID_RE.fullmatch(proposal_dir.name):
                raise StorageError("proposal store contains an orphan or unsafe entry")
            actual_proposals.add(proposal_dir.name)
            for required in ("proposal.json", "proposal.md", "revisions"):
                child = proposal_dir / required
                if child.is_symlink() or not child.exists():
                    raise StorageError("proposal store is missing required metadata")
        if actual_proposals != expected_proposals:
            raise StorageError("proposal store has orphaned or missing proposal directories")
        expected_revisions = {
            (row["proposal_id"], int(row["revision"])): row["content_sha256"]
            for row in revision_rows
        }
        if any(
            (row["proposal_id"], int(row["current_revision"])) not in expected_revisions
            for row in proposal_rows
        ):
            raise StorageError("proposal current revision is missing from the database")
        for row in approval_rows:
            revision_hash = expected_revisions.get(
                (row["proposal_id"], int(row["revision"]))
            )
            if revision_hash is None or row["content_sha256"] != revision_hash:
                raise StorageError("proposal approval does not match an immutable revision")
        actual_revisions: set[tuple[str, int]] = set()
        for proposal_id in expected_proposals:
            revisions_dir = proposals_root / proposal_id / "revisions"
            if revisions_dir.is_symlink() or not revisions_dir.is_dir():
                raise StorageError("proposal revisions directory is unsafe")
            for revision_dir in revisions_dir.iterdir():
                if revision_dir.is_symlink() or not revision_dir.is_dir() or not re.fullmatch(r"[0-9]{4}", revision_dir.name):
                    raise StorageError("proposal store contains an unsafe revision entry")
                key = (proposal_id, int(revision_dir.name))
                actual_revisions.add(key)
                expected_hash = expected_revisions.get(key)
                if expected_hash is None or self._revision_content_hash(revision_dir) != expected_hash:
                    raise StorageError("proposal store contains an orphaned or modified revision")
        if actual_revisions != set(expected_revisions):
            raise StorageError("proposal store has missing revision directories")
        proposals_by_operation = {
            row["operation_id"]: row
            for row in proposal_rows
            if row["operation_id"] is not None
        }
        receipts_root = self.workspace / "receipts"
        receipt_ids: set[str] = set()
        for receipt_path in receipts_root.iterdir():
            match = re.fullmatch(r"([0-9a-f]{32})\.json", receipt_path.name)
            if receipt_path.is_symlink() or not receipt_path.is_file() or match is None:
                raise StorageError("receipt store contains an unsafe entry")
            operation_id = match.group(1)
            try:
                receipt = _decode_json(
                    receipt_path.read_text(encoding="utf-8"), "remote receipt", dict
                )
            except OSError as exc:
                raise StorageError("remote receipt is unreadable") from exc
            proposal_row = proposals_by_operation.get(operation_id)
            if proposal_row is None:
                raise StorageError("receipt store contains an orphan receipt")
            if (
                receipt.get("schema_version") != 1
                or receipt.get("proposal_id") != proposal_row["proposal_id"]
                or receipt.get("operation_id") != operation_id
                or receipt.get("payload_sha256") != proposal_row["payload_sha256"]
                or receipt.get("result") != "APPLIED"
            ):
                raise StorageError("remote receipt does not match proposal state")
            receipt_ids.add(operation_id)
        for row in proposal_rows:
            if row["state"] == "APPLIED" and row["operation_id"] not in receipt_ids:
                raise StorageError("applied proposal is missing its immutable receipt")
        return {
            "schema_version": 1,
            "workspace": str(self.workspace),
            "proposals": len(expected_proposals),
            "revisions": len(expected_revisions),
            "receipts": len(receipt_ids),
            "valid": True,
        }

    def recover_orphans(self, *, reason: str) -> dict[str, Any]:
        with self.workspace_lock():
            return self._recover_orphans_unlocked(reason=reason)

    def _recover_orphans_unlocked(self, *, reason: str) -> dict[str, Any]:
        if not reason.strip():
            raise StorageError("local recovery requires a reason")
        connection = self._connect()
        try:
            expected_proposals = {
                row["proposal_id"]
                for row in connection.execute("SELECT proposal_id FROM proposals").fetchall()
            }
            expected_revisions = {
                (row["proposal_id"], int(row["revision"]))
                for row in connection.execute("SELECT proposal_id, revision FROM revisions").fetchall()
            }
            expected_operation_ids = {
                row["operation_id"]
                for row in connection.execute(
                    "SELECT operation_id FROM proposals WHERE operation_id IS NOT NULL"
                ).fetchall()
            }
        finally:
            connection.close()
        recovery_id = uuid.uuid4().hex
        recovery_dir = self.workspace / "recovery" / recovery_id
        _secure_directory(recovery_dir, self.workspace)
        moved: list[str] = []
        proposals_root = self.workspace / "proposals"
        for proposal_path in list(proposals_root.iterdir()):
            proposal_id = proposal_path.name
            if proposal_id not in expected_proposals:
                destination = recovery_dir / f"orphan-proposal-{proposal_id}"
                os.replace(proposal_path, destination)
                moved.append(str(proposal_path.relative_to(self.workspace)))
                continue
            revisions_path = proposal_path / "revisions"
            if not revisions_path.is_dir() or revisions_path.is_symlink():
                continue
            for revision_path in list(revisions_path.iterdir()):
                try:
                    revision_number = int(revision_path.name)
                except ValueError:
                    revision_number = -1
                if (proposal_id, revision_number) not in expected_revisions:
                    destination = recovery_dir / f"orphan-revision-{proposal_id}-{revision_path.name}"
                    os.replace(revision_path, destination)
                    moved.append(str(revision_path.relative_to(self.workspace)))
        receipts_root = self.workspace / "receipts"
        for receipt_path in list(receipts_root.iterdir()):
            match = re.fullmatch(r"([0-9a-f]{32})\.json", receipt_path.name)
            if match is None or match.group(1) not in expected_operation_ids:
                destination = recovery_dir / f"orphan-receipt-{receipt_path.name}"
                os.replace(receipt_path, destination)
                moved.append(str(receipt_path.relative_to(self.workspace)))
        if moved:
            _fsync_directory(proposals_root)
            _fsync_directory(receipts_root)
            _fsync_directory(recovery_dir)
        report = {
            "schema_version": 1,
            "recovery_id": recovery_id,
            "reason": reason.strip(),
            "moved": moved,
            "created_at": utc_now(),
            "disposition": "quarantined; not deleted",
        }
        atomic_write(
            recovery_dir / "recovery.json",
            (stable_json(report) + "\n").encode("utf-8"),
            root=self.workspace,
        )
        report["audit"] = self.audit()
        report["path"] = str(recovery_dir / "recovery.json")
        return report
