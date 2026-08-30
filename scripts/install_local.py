#!/usr/bin/env python3
"""Install one repository Skill without exposing backups as Skills."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import errno
import fcntl
import hashlib
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
from typing import Iterator, Sequence

from stamp_installed_skill import StampError, annotation_for, stamp_file


SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
OID_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
HANDLED_SIGNALS = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
READ_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NONBLOCK", 0)
)


class InstallError(RuntimeError):
    """An expected installation failure."""


class InstallationSignal(BaseException):
    """A catchable signal received while the transaction is reversible."""

    def __init__(self, signum: int) -> None:
        super().__init__(signum)
        self.signum = signum


@dataclasses.dataclass(frozen=True)
class SnapshotEntry:
    kind: str
    mode: int = 0
    link_target: bytes | None = None
    digest: bytes | None = None


def _identity(value: os.stat_result) -> tuple[int, int]:
    return value.st_dev, value.st_ino


def _entry_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _lexists_at(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _open_real_directory(path: Path, label: str) -> tuple[int, os.stat_result]:
    try:
        descriptor = os.open(path, DIRECTORY_FLAGS)
    except OSError as error:
        raise InstallError(f"{label} must be a real directory: {path}: {error}") from error
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(descriptor)
        raise InstallError(f"{label} must be a real directory: {path}")
    try:
        named = os.stat(path, follow_symlinks=False)
    except OSError as error:
        os.close(descriptor)
        raise InstallError(f"Cannot verify {label}: {path}: {error}") from error
    if not stat.S_ISDIR(named.st_mode) or _identity(named) != _identity(opened):
        os.close(descriptor)
        raise InstallError(f"{label} changed while it was opened: {path}")
    return descriptor, opened


def _ensure_directory_at(parent_fd: int, name: str, mode: int = 0o755) -> int:
    try:
        os.mkdir(name, mode, dir_fd=parent_fd)
    except FileExistsError:
        pass
    except OSError as error:
        raise InstallError(f"Cannot create installation directory {name}: {error}") from error
    descriptor: int | None = None
    try:
        descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=parent_fd)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        opened = os.fstat(descriptor)
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise InstallError(f"Installation path is not a real directory: {name}: {error}") from error
    if (
        not stat.S_ISDIR(named.st_mode)
        or not stat.S_ISDIR(opened.st_mode)
        or _identity(named) != _identity(opened)
    ):
        os.close(descriptor)
        raise InstallError(f"Installation path changed while it was opened: {name}")
    return descriptor


def _fd_is_ancestor(ancestor_fd: int, descendant_fd: int) -> bool:
    ancestor = _identity(os.fstat(ancestor_fd))
    current = os.dup(descendant_fd)
    try:
        while True:
            current_identity = _identity(os.fstat(current))
            if current_identity == ancestor:
                return True
            parent = os.open("..", DIRECTORY_FLAGS, dir_fd=current)
            parent_identity = _identity(os.fstat(parent))
            if parent_identity == current_identity:
                os.close(parent)
                return False
            os.close(current)
            current = parent
    finally:
        os.close(current)


def _open_components(root_fd: int, components: Sequence[str], final_flags: int) -> int:
    if not components:
        return os.dup(root_fd)
    current = os.dup(root_fd)
    try:
        for component in components[:-1]:
            following = os.open(component, DIRECTORY_FLAGS, dir_fd=current)
            os.close(current)
            current = following
        result = os.open(components[-1], final_flags, dir_fd=current)
    finally:
        os.close(current)
    return result


def _read_regular_at(root_fd: int, components: Sequence[str]) -> bytes:
    if not components:
        raise InstallError("Cannot read a staged directory as a regular file")
    parent_fd: int | None = None
    try:
        parent_fd = _open_components(root_fd, components[:-1], DIRECTORY_FLAGS)
        descriptor = os.open(components[-1], READ_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        if parent_fd is not None:
            os.close(parent_fd)
        raise InstallError(f"Cannot read staged file {'/'.join(components)}: {error}") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise InstallError(f"Staged entry is not a regular file: {'/'.join(components)}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named_after = os.stat(
            components[-1], dir_fd=parent_fd, follow_symlinks=False
        )
        if (
            _entry_identity(before) != _entry_identity(after)
            or _entry_identity(before) != _entry_identity(named_after)
        ):
            raise InstallError(f"Staged file changed while being read: {'/'.join(components)}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)
        os.close(parent_fd)


def _remove_entry_at(parent_fd: int, name: str) -> None:
    try:
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(entry.st_mode):
        os.unlink(name, dir_fd=parent_fd)
        return
    # Copied source modes may remove owner access. The staged copy is ours.
    os.chmod(name, 0o700, dir_fd=parent_fd, follow_symlinks=False)
    directory_fd = os.open(name, DIRECTORY_FLAGS, dir_fd=parent_fd)
    try:
        with os.scandir(directory_fd) as entries:
            children = [child.name for child in entries]
        for child in children:
            _remove_entry_at(directory_fd, child)
    finally:
        os.close(directory_fd)
    os.rmdir(name, dir_fd=parent_fd)


class LocalInstaller:
    def __init__(self, arguments: argparse.Namespace) -> None:
        self.source_path = Path(os.path.abspath(arguments.source_dir))
        self.repo_path = Path(os.path.abspath(arguments.repo_dir))
        self.agents_path = Path(os.path.abspath(arguments.agents_root))
        self.skill_name: str = arguments.skill_name
        self.source_state: str = arguments.source_state
        self.oid: str | None = arguments.oid
        self.link_mode: bool = arguments.link
        self.force: bool = arguments.force
        self.agent: str = arguments.agent
        self.scope: str = arguments.scope

        self.source_fd: int | None = None
        self.repo_fd: int | None = None
        self.agents_fd: int | None = None
        self.skills_fd: int | None = None
        self.backups_fd: int | None = None
        self.locks_fd: int | None = None
        self.staging_fd: int | None = None
        self.lock_fd: int | None = None
        self.transaction_fd: int | None = None
        self.source_stat: os.stat_result | None = None
        self.repo_stat: os.stat_result | None = None
        self.agents_stat: os.stat_result | None = None
        self.child_identities: dict[str, tuple[int, int]] = {}
        self.transaction_name: str | None = None
        self.staged_present = False
        self.activated = False
        self.committed = False
        self.active_backup: str | None = None
        self.display_oid: str | None = None
        self.manifest: dict[tuple[str, ...], SnapshotEntry] = {}
        self.stamped_skill_digest: bytes | None = None
        self.final_fingerprint: dict[tuple[str, ...], SnapshotEntry] | None = None
        self.source_root_mode = 0o755
        self._old_handlers: dict[int, signal.Handlers] = {}

    @property
    def destination_path(self) -> Path:
        return self.agents_path / "skills" / self.skill_name

    def _require_fd(self, value: int | None, label: str) -> int:
        if value is None:
            raise InstallError(f"Internal installer state missing {label}")
        return value

    def prepare_roots(self) -> None:
        self.source_fd, self.source_stat = _open_real_directory(
            self.source_path, "Skill source"
        )
        self.repo_fd, self.repo_stat = _open_real_directory(
            self.repo_path, "repository root"
        )
        source_real = Path(os.path.realpath(self.source_path))
        agents_real = Path(os.path.realpath(self.agents_path))
        if (
            source_real == agents_real
            or source_real in agents_real.parents
            or agents_real in source_real.parents
        ):
            raise InstallError(
                f"Skill source and agents root overlap: {self.source_path} and {self.agents_path}"
            )
        try:
            os.mkdir(self.agents_path, 0o755)
        except FileExistsError:
            pass
        except OSError as error:
            raise InstallError(f"Cannot create agents root {self.agents_path}: {error}") from error

        self.agents_fd, self.agents_stat = _open_real_directory(
            self.agents_path, "agents root"
        )
        self._validate_overlap()
        agents_fd = self._require_fd(self.agents_fd, "agents root")
        skills_path = self.agents_path / "skills"
        if skills_path.is_symlink():
            try:
                if os.path.samefile(skills_path / self.skill_name, self.source_path):
                    raise InstallError(
                        "Active Skill path resolves to the source Skill directory"
                    )
            except FileNotFoundError:
                pass
        self.skills_fd = _ensure_directory_at(agents_fd, "skills")
        self.child_identities["skills"] = _identity(os.fstat(self.skills_fd))
        self.locks_fd = _ensure_directory_at(agents_fd, ".install-locks", 0o700)
        self.child_identities[".install-locks"] = _identity(os.fstat(self.locks_fd))

    def _verify_named_root(self, path: Path, descriptor: int, expected: os.stat_result) -> None:
        try:
            named = os.stat(path, follow_symlinks=False)
            opened = os.fstat(descriptor)
        except OSError as error:
            raise InstallError(f"Installation root cannot be revalidated: {path}: {error}") from error
        if (
            not stat.S_ISDIR(named.st_mode)
            or _identity(named) != _identity(expected)
            or _identity(opened) != _identity(expected)
        ):
            raise InstallError(f"Installation root changed during installation: {path}")

    def _verify_child(self, name: str, descriptor: int | None) -> None:
        root_fd = self._require_fd(self.agents_fd, "agents root")
        child_fd = self._require_fd(descriptor, name)
        try:
            named = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        except OSError as error:
            raise InstallError(f"Installation directory changed during installation: {name}: {error}") from error
        if (
            not stat.S_ISDIR(named.st_mode)
            or _identity(named) != self.child_identities[name]
            or _identity(os.fstat(child_fd)) != self.child_identities[name]
        ):
            raise InstallError(f"Installation directory changed during installation: {name}")

    def verify_roots(self) -> None:
        self._verify_named_root(
            self.source_path,
            self._require_fd(self.source_fd, "Skill source"),
            self.source_stat,  # type: ignore[arg-type]
        )
        self._verify_named_root(
            self.repo_path,
            self._require_fd(self.repo_fd, "repository root"),
            self.repo_stat,  # type: ignore[arg-type]
        )
        self._verify_named_root(
            self.agents_path,
            self._require_fd(self.agents_fd, "agents root"),
            self.agents_stat,  # type: ignore[arg-type]
        )
        self._verify_child("skills", self.skills_fd)
        self._verify_child(".install-locks", self.locks_fd)
        if self.backups_fd is not None:
            self._verify_child("backups", self.backups_fd)
        if self.staging_fd is not None:
            self._verify_child(".install-staging", self.staging_fd)

    def _validate_overlap(self) -> None:
        source_fd = self._require_fd(self.source_fd, "Skill source")
        agents_fd = self._require_fd(self.agents_fd, "agents root")
        if _fd_is_ancestor(source_fd, agents_fd) or _fd_is_ancestor(agents_fd, source_fd):
            raise InstallError(
                f"Skill source and agents root overlap: {self.source_path} and {self.agents_path}"
            )

    def _validate_skill_file(self) -> None:
        source_fd = self._require_fd(self.source_fd, "Skill source")
        try:
            skill_file = os.stat("SKILL.md", dir_fd=source_fd, follow_symlinks=False)
        except FileNotFoundError as error:
            raise InstallError(f"Skill not found: {self.source_path}") from error
        except OSError as error:
            raise InstallError(f"Cannot inspect {self.source_path / 'SKILL.md'}: {error}") from error
        if not stat.S_ISREG(skill_file.st_mode):
            raise InstallError(f"SKILL.md must be a regular non-symlink file: {self.source_path}")

    def _validate_active_not_source(self) -> None:
        skills_fd = self._require_fd(self.skills_fd, "skills")
        try:
            active = os.stat(self.skill_name, dir_fd=skills_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if stat.S_ISLNK(active.st_mode) or not stat.S_ISDIR(active.st_mode):
            return
        active_fd = os.open(self.skill_name, DIRECTORY_FLAGS, dir_fd=skills_fd)
        try:
            if _identity(os.fstat(active_fd)) == _identity(
                os.fstat(self._require_fd(self.source_fd, "Skill source"))
            ):
                raise InstallError("Active Skill path resolves to the source Skill directory")
        finally:
            os.close(active_fd)

    def validate_layout(self) -> None:
        self.verify_roots()
        self._validate_overlap()
        self._validate_skill_file()
        self._validate_active_not_source()

    def validate_layout_under_lock(self) -> None:
        self.validate_layout()

    def acquire_lock(self) -> None:
        locks_fd = self._require_fd(self.locks_fd, ".install-locks")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        # The directory lock protects the open/flock and unlink/close pairs.
        # Without it, a delayed opener could retain an unlinked lock inode
        # while a later process locks a newly created inode of the same name.
        with self._signals_blocked():
            with self._lock_registry():
                lock_fd: int | None = None
                try:
                    lock_fd = os.open(self.skill_name, flags, 0o600, dir_fd=locks_fd)
                    lock_stat = os.fstat(lock_fd)
                    if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_nlink != 1:
                        raise InstallError(
                            f"Installation lock is not a regular private file: {self.skill_name}"
                        )
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    if lock_fd is not None:
                        os.close(lock_fd)
                    raise InstallError(
                        f"Another installation is already updating {self.destination_path}. "
                        "Try again after it finishes."
                    ) from error
                except (InstallError, OSError) as error:
                    if lock_fd is not None:
                        os.close(lock_fd)
                    if isinstance(error, InstallError):
                        raise
                    raise InstallError(
                        f"Cannot open installation lock for {self.skill_name}: {error}"
                    ) from error
                self.lock_fd = lock_fd

    def _open_transaction_roots(self) -> None:
        agents_fd = self._require_fd(self.agents_fd, "agents root")
        with self._signals_blocked():
            with self._lock_registry():
                self.staging_fd = _ensure_directory_at(agents_fd, ".install-staging", 0o700)
                self.child_identities[".install-staging"] = _identity(os.fstat(self.staging_fd))
                staging_fd = self._require_fd(self.staging_fd, ".install-staging")
                for _ in range(128):
                    name = f"{self.skill_name}.{os.getpid()}.{secrets.token_hex(8)}"
                    try:
                        os.mkdir(name, 0o700, dir_fd=staging_fd)
                    except FileExistsError:
                        continue
                    self.transaction_name = name
                    self.transaction_fd = os.open(name, DIRECTORY_FLAGS, dir_fd=staging_fd)
                    return
        raise InstallError("Cannot allocate a unique installation staging directory")

    @contextlib.contextmanager
    def _lock_registry(self) -> Iterator[None]:
        locks_fd = self._require_fd(self.locks_fd, ".install-locks")
        fcntl.flock(locks_fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(locks_fd, fcntl.LOCK_UN)

    def _ensure_backups_root(self) -> int:
        if self.backups_fd is None:
            agents_fd = self._require_fd(self.agents_fd, "agents root")
            self.backups_fd = _ensure_directory_at(agents_fd, "backups")
            self.child_identities["backups"] = _identity(os.fstat(self.backups_fd))
        return self.backups_fd

    def _copy_regular(
        self,
        source_parent_fd: int,
        target_parent_fd: int,
        name: str,
        expected: os.stat_result,
    ) -> bytes:
        source_fd = os.open(name, READ_FLAGS, dir_fd=source_parent_fd)
        target_flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        target_fd: int | None = None
        digest = hashlib.sha256()
        try:
            opened = os.fstat(source_fd)
            if not stat.S_ISREG(opened.st_mode) or _entry_identity(opened) != _entry_identity(expected):
                raise InstallError(f"Source entry changed while being copied: {name}")
            target_fd = os.open(name, target_flags, 0o600, dir_fd=target_parent_fd)
            while True:
                chunk = os.read(source_fd, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                view = memoryview(chunk)
                while view:
                    written = os.write(target_fd, view)
                    if written == 0:
                        raise InstallError(f"Could not finish copying source file: {name}")
                    view = view[written:]
            after = os.fstat(source_fd)
            named_after = os.stat(name, dir_fd=source_parent_fd, follow_symlinks=False)
            if (
                _entry_identity(after) != _entry_identity(expected)
                or _entry_identity(named_after) != _entry_identity(expected)
            ):
                raise InstallError(f"Source file changed while being copied: {name}")
            return digest.digest()
        finally:
            os.close(source_fd)
            if target_fd is not None:
                os.close(target_fd)

    def _copy_directory(
        self,
        source_fd: int,
        target_fd: int,
        relative: tuple[str, ...],
    ) -> None:
        before = os.fstat(source_fd)
        try:
            with os.scandir(source_fd) as entries:
                names = sorted(entry.name for entry in entries)
        except OSError as error:
            raise InstallError(f"Cannot enumerate Skill source: {error}") from error
        for name in names:
            try:
                entry = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
            except OSError as error:
                raise InstallError(f"Cannot inspect Skill source entry {name}: {error}") from error
            path = relative + (name,)
            mode = entry.st_mode
            if stat.S_ISREG(mode):
                digest = self._copy_regular(source_fd, target_fd, name, entry)
                self.manifest[path] = SnapshotEntry(
                    "file", stat.S_IMODE(mode), digest=digest
                )
            elif stat.S_ISDIR(mode):
                os.mkdir(name, 0o700, dir_fd=target_fd)
                source_child = os.open(name, DIRECTORY_FLAGS, dir_fd=source_fd)
                try:
                    target_child = os.open(name, DIRECTORY_FLAGS, dir_fd=target_fd)
                    try:
                        if _entry_identity(os.fstat(source_child)) != _entry_identity(entry):
                            raise InstallError(
                                f"Source directory changed while being copied: {'/'.join(path)}"
                            )
                        self.manifest[path] = SnapshotEntry("directory", stat.S_IMODE(mode))
                        self._copy_directory(source_child, target_child, path)
                    finally:
                        os.close(target_child)
                finally:
                    os.close(source_child)
            elif stat.S_ISLNK(mode):
                target = os.readlink(name, dir_fd=source_fd)
                os.symlink(target, name, dir_fd=target_fd)
                after = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
                if _entry_identity(after) != _entry_identity(entry) or os.readlink(
                    name, dir_fd=source_fd
                ) != target:
                    raise InstallError(f"Source link changed while being copied: {'/'.join(path)}")
                self.manifest[path] = SnapshotEntry("symlink", link_target=os.fsencode(target))
            else:
                raise InstallError(
                    f"Special files cannot be installed from a Skill source: {'/'.join(path)}"
                )
        with os.scandir(source_fd) as entries:
            names_after = sorted(entry.name for entry in entries)
        after = os.fstat(source_fd)
        if names_after != names or _entry_identity(before) != _entry_identity(after):
            raise InstallError("Skill source directory changed while it was being copied")

    def stage_copy(self) -> None:
        transaction_fd = self._require_fd(self.transaction_fd, "transaction")
        os.mkdir(self.skill_name, 0o700, dir_fd=transaction_fd)
        staged_fd = os.open(self.skill_name, DIRECTORY_FLAGS, dir_fd=transaction_fd)
        self.staged_present = True
        try:
            source_fd = self._require_fd(self.source_fd, "Skill source")
            self.source_root_mode = stat.S_IMODE(os.fstat(source_fd).st_mode)
            self._copy_directory(source_fd, staged_fd, ())
            skill_entry = self.manifest.get(("SKILL.md",))
            if skill_entry is None or skill_entry.kind != "file":
                raise InstallError("SKILL.md must be a regular non-symlink file")
        finally:
            os.close(staged_fd)

    def stage_link(self) -> None:
        transaction_fd = self._require_fd(self.transaction_fd, "transaction")
        self.verify_roots()
        os.symlink(
            str(self.source_path),
            self.skill_name,
            dir_fd=transaction_fd,
            target_is_directory=True,
        )
        self.staged_present = True

    def _fingerprint_directory(
        self,
        directory_fd: int,
        relative: tuple[str, ...] = (),
        result: dict[tuple[str, ...], SnapshotEntry] | None = None,
    ) -> dict[tuple[str, ...], SnapshotEntry]:
        if result is None:
            result = {}
        before = os.fstat(directory_fd)
        if not stat.S_ISDIR(before.st_mode):
            raise InstallError("Staged Skill root is not a directory")
        result[relative] = SnapshotEntry("directory", stat.S_IMODE(before.st_mode))
        with os.scandir(directory_fd) as entries:
            names = sorted(entry.name for entry in entries)
        for name in names:
            entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            path = relative + (name,)
            if stat.S_ISREG(entry.st_mode):
                content = _read_regular_at(directory_fd, (name,))
                result[path] = SnapshotEntry(
                    "file",
                    stat.S_IMODE(entry.st_mode),
                    digest=hashlib.sha256(content).digest(),
                )
            elif stat.S_ISDIR(entry.st_mode):
                child_fd = os.open(name, DIRECTORY_FLAGS, dir_fd=directory_fd)
                try:
                    if _entry_identity(os.fstat(child_fd)) != _entry_identity(entry):
                        raise InstallError(
                            f"Staged directory changed while being inspected: {'/'.join(path)}"
                        )
                    self._fingerprint_directory(child_fd, path, result)
                finally:
                    os.close(child_fd)
            elif stat.S_ISLNK(entry.st_mode):
                target = os.readlink(name, dir_fd=directory_fd)
                after = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if _entry_identity(after) != _entry_identity(entry):
                    raise InstallError(
                        f"Staged link changed while being inspected: {'/'.join(path)}"
                    )
                result[path] = SnapshotEntry(
                    "symlink",
                    link_target=os.fsencode(target),
                )
            else:
                raise InstallError(
                    f"Special file appeared in staged Skill: {'/'.join(path)}"
                )
        with os.scandir(directory_fd) as entries:
            names_after = sorted(entry.name for entry in entries)
        after = os.fstat(directory_fd)
        if names_after != names or _entry_identity(before) != _entry_identity(after):
            raise InstallError("Staged Skill changed while it was being inspected")
        return result

    def _fingerprint_staged_copy(self) -> dict[tuple[str, ...], SnapshotEntry]:
        transaction_fd = self._require_fd(self.transaction_fd, "transaction")
        staged_fd = os.open(
            self.skill_name,
            DIRECTORY_FLAGS,
            dir_fd=transaction_fd,
        )
        try:
            opened = os.fstat(staged_fd)
            fingerprint = self._fingerprint_directory(staged_fd)
            after = os.fstat(staged_fd)
            named_after = os.stat(
                self.skill_name,
                dir_fd=transaction_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(named_after.st_mode)
                or _identity(opened) != _identity(after)
                or _identity(opened) != _identity(named_after)
            ):
                raise InstallError("Staged Skill root changed while being inspected")
            return fingerprint
        finally:
            os.close(staged_fd)

    def _verify_copy_fingerprint(
        self,
        fingerprint: dict[tuple[str, ...], SnapshotEntry],
        *,
        stamped: bool = False,
    ) -> None:
        expected_paths = set(self.manifest) | {()}
        if set(fingerprint) != expected_paths:
            raise InstallError("Staged Skill tree differs from the copied snapshot")
        for path, expected in self.manifest.items():
            actual = fingerprint[path]
            if actual.kind != expected.kind:
                raise InstallError(
                    f"Staged entry changed type after copy: {'/'.join(path)}"
                )
            if expected.kind == "symlink" and actual.link_target != expected.link_target:
                raise InstallError(
                    f"Staged link changed after copy: {'/'.join(path)}"
                )
            if expected.kind == "file" and (
                not stamped or path != ("SKILL.md",)
            ) and actual.digest != expected.digest:
                raise InstallError(
                    f"Staged file changed after copy: {'/'.join(path)}"
                )
            if (
                stamped
                and path == ("SKILL.md",)
                and actual.digest != self.stamped_skill_digest
            ):
                raise InstallError("Stamped SKILL.md changed before activation")

    def capture_final_fingerprint(self) -> None:
        fingerprint = self._fingerprint_staged_copy()
        self._verify_copy_fingerprint(fingerprint, stamped=True)
        self.final_fingerprint = fingerprint

    def verify_staged_ready(self) -> None:
        transaction_fd = self._require_fd(self.transaction_fd, "transaction")
        if self.link_mode:
            entry = os.stat(
                self.skill_name,
                dir_fd=transaction_fd,
                follow_symlinks=False,
            )
            if not stat.S_ISLNK(entry.st_mode):
                raise InstallError("Staged live installation is not a symlink")
            target = os.readlink(self.skill_name, dir_fd=transaction_fd)
            after = os.stat(
                self.skill_name,
                dir_fd=transaction_fd,
                follow_symlinks=False,
            )
            if (
                target != str(self.source_path)
                or _entry_identity(after) != _entry_identity(entry)
            ):
                raise InstallError("Staged live installation changed before activation")
            return
        if self.final_fingerprint is None:
            raise InstallError("Missing final staged Skill fingerprint")
        if self._fingerprint_staged_copy() != self.final_fingerprint:
            raise InstallError("Staged Skill changed before activation")

    def _git_environment(self) -> dict[str, str]:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        environment.update(
            {
                "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_LITERAL_PATHSPECS": "1",
                "GIT_OPTIONAL_LOCKS": "0",
                "LC_ALL": "C",
            }
        )
        return environment

    def _run_git(self, arguments: Sequence[str]) -> bytes:
        self._verify_named_root(
            self.repo_path,
            self._require_fd(self.repo_fd, "repository root"),
            self.repo_stat,  # type: ignore[arg-type]
        )
        try:
            result = subprocess.run(
                ["git", "--no-replace-objects", "-C", str(self.repo_path), *arguments],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._git_environment(),
            )
        except FileNotFoundError as error:
            raise InstallError("Git became unavailable while the copied Skill was classified") from error
        self._verify_named_root(
            self.repo_path,
            self._require_fd(self.repo_fd, "repository root"),
            self.repo_stat,  # type: ignore[arg-type]
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", "replace").strip()
            raise InstallError(f"Git inspection failed: {detail or 'unknown Git error'}")
        return result.stdout

    def _git_relative_source(self) -> bytes:
        source_real = Path(os.path.realpath(self.source_path))
        repo_real = Path(os.path.realpath(self.repo_path))
        try:
            relative = source_real.relative_to(repo_real)
        except ValueError as error:
            raise InstallError("A Git-tracked Skill source must be inside the repository root") from error
        if not relative.parts:
            raise InstallError("The repository root itself cannot be installed as a Skill")
        return os.fsencode(relative.as_posix())

    def _git_manifest(self) -> dict[bytes, tuple[str, str | None, bytes | None]]:
        oid = self.oid
        if oid is None:
            raise InstallError("A full Git commit ID is required for source state 'head'")
        relative = self._git_relative_source()
        output = self._run_git(
            ["ls-tree", "-r", "-t", "-z", "--full-tree", oid, "--", os.fsdecode(relative)]
        )
        records: dict[bytes, tuple[str, str | None, bytes | None]] = {}
        prefix = relative + b"/"
        root_seen = False
        for record in output.split(b"\0"):
            if not record:
                continue
            try:
                header, path = record.split(b"\t", 1)
                mode, object_type, object_id = header.split(b" ", 2)
            except ValueError as error:
                raise InstallError("Git returned malformed ls-tree output") from error
            if path == relative:
                root_seen = object_type == b"tree"
                if not root_seen:
                    return {b"": ("mismatch", None, None)}
                continue
            # With -t, Git also reports each ancestor tree selected by the
            # pathspec (for example, `skills` before `skills/demo-skill`).
            if object_type == b"tree" and relative.startswith(path + b"/"):
                continue
            if not path.startswith(prefix):
                raise InstallError("Git returned a tree entry outside the Skill source")
            local_path = path[len(prefix) :]
            if object_type == b"tree":
                value = ("directory", None, None)
            elif object_type == b"blob" and mode in (b"100644", b"100755"):
                value = ("file", mode.decode("ascii"), object_id)
            elif object_type == b"blob" and mode == b"120000":
                value = ("symlink", None, object_id)
            else:
                value = ("mismatch", mode.decode("ascii", "replace"), object_id)
            if local_path in records:
                raise InstallError("Git returned duplicate tree entries")
            records[local_path] = value
        if not root_seen and not records:
            return {b"": ("mismatch", None, None)}
        return records

    def resolve_short_oid(self) -> None:
        if self.source_state != "head" or self.oid is None:
            self.display_oid = None
            return
        commit_oid = self._run_git(
            ["rev-parse", "--verify", f"{self.oid}^{{commit}}"]
        ).decode("ascii", "strict").strip()
        head_oid = self._run_git(
            ["rev-parse", "--verify", "HEAD^{commit}"]
        ).decode("ascii", "strict").strip()
        if commit_oid != self.oid or head_oid != self.oid:
            raise InstallError("The supplied Git object ID is not the current HEAD commit ID")
        value = self._run_git(["rev-parse", "--short=12", self.oid]).decode(
            "ascii", "strict"
        ).strip()
        if not re.fullmatch(r"[0-9a-f]{12,64}", value) or not self.oid.startswith(value):
            raise InstallError(f"Git returned an invalid short commit ID: {value}")
        self.display_oid = value

    def classify_copy(self) -> str:
        before = self._fingerprint_staged_copy()
        self._verify_copy_fingerprint(before)
        try:
            return self._classify_copy_against_git()
        finally:
            after = self._fingerprint_staged_copy()
            self._verify_copy_fingerprint(after)
            if after != before:
                raise InstallError("Staged Skill changed during Git classification")

    def _classify_copy_against_git(self) -> str:
        git_entries = self._git_manifest()
        staged_entries = {
            os.fsencode("/".join(path)): entry for path, entry in self.manifest.items()
        }
        if set(git_entries) != set(staged_entries):
            return "dirty"
        staged_fd = os.open(
            self.skill_name,
            DIRECTORY_FLAGS,
            dir_fd=self._require_fd(self.transaction_fd, "transaction"),
        )
        try:
            blob_cache: dict[bytes, bytes] = {}
            for path_bytes, staged in staged_entries.items():
                git_kind, git_mode, object_id = git_entries[path_bytes]
                if staged.kind != git_kind:
                    return "dirty"
                if staged.kind == "directory":
                    continue
                if object_id is None or not OID_PATTERN.fullmatch(object_id.decode("ascii", "strict")):
                    raise InstallError("Git returned an unsupported object ID")
                if object_id not in blob_cache:
                    blob_cache[object_id] = self._run_git(
                        ["cat-file", "blob", object_id.decode("ascii")]
                    )
                git_bytes = blob_cache[object_id]
                if staged.kind == "symlink":
                    if staged.link_target != git_bytes:
                        return "dirty"
                else:
                    expected_mode = "100755" if staged.mode & 0o111 else "100644"
                    if git_mode != expected_mode:
                        return "dirty"
                    components = tuple(os.fsdecode(part) for part in path_bytes.split(b"/"))
                    if _read_regular_at(staged_fd, components) != git_bytes:
                        return "dirty"
        finally:
            os.close(staged_fd)
        return "clean"

    def _stable_fd_path(self, descriptor: int) -> Path:
        expected = _identity(os.fstat(descriptor))
        for base in (Path("/proc/self/fd"), Path("/dev/fd")):
            candidate = base / str(descriptor)
            try:
                if _identity(os.stat(candidate)) == expected:
                    return candidate
            except OSError:
                continue
        self.verify_roots()
        if self.transaction_name is None:
            raise InstallError("Missing installation transaction name")
        return self.agents_path / ".install-staging" / self.transaction_name

    def stamp_copy(self, install_state: str) -> None:
        transaction_fd = self._require_fd(self.transaction_fd, "transaction")
        before = self._fingerprint_staged_copy()
        self._verify_copy_fingerprint(before)
        base = self._stable_fd_path(transaction_fd)
        skill_bytes = _read_regular_at(
            transaction_fd, (self.skill_name, "SKILL.md")
        )
        expected_skill = self.manifest[("SKILL.md",)]
        if hashlib.sha256(skill_bytes).digest() != expected_skill.digest:
            raise InstallError("Staged SKILL.md changed before revision stamping")
        unstamped_name = f".unstamped-SKILL.{secrets.token_hex(8)}.md"
        stamped_name = f".stamped-SKILL.{secrets.token_hex(8)}.md"
        source = base / unstamped_name
        destination = base / stamped_name
        unstamped_fd = os.open(
            unstamped_name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=transaction_fd,
        )
        try:
            remaining = memoryview(skill_bytes)
            while remaining:
                written = os.write(unstamped_fd, remaining)
                if written == 0:
                    raise InstallError("Could not write the unstamped SKILL.md snapshot")
                remaining = remaining[written:]
        finally:
            os.close(unstamped_fd)
        try:
            annotation = annotation_for(
                install_state,
                self.oid,
                short_oid=self.display_oid,
            )
            stamp_file(source, destination, annotation)
        except (StampError, OSError, UnicodeError, ValueError) as error:
            raise InstallError(str(error)) from error
        try:
            stamped = os.stat(stamped_name, dir_fd=transaction_fd, follow_symlinks=False)
            if not stat.S_ISREG(stamped.st_mode):
                raise InstallError("Stamped SKILL.md is not a regular file")
            self.stamped_skill_digest = hashlib.sha256(
                _read_regular_at(transaction_fd, (stamped_name,))
            ).digest()
            staged_fd = os.open(self.skill_name, DIRECTORY_FLAGS, dir_fd=transaction_fd)
            try:
                os.rename(
                    stamped_name,
                    "SKILL.md",
                    src_dir_fd=transaction_fd,
                    dst_dir_fd=staged_fd,
                )
            finally:
                os.close(staged_fd)
        finally:
            if _lexists_at(transaction_fd, stamped_name):
                _remove_entry_at(transaction_fd, stamped_name)
            if _lexists_at(transaction_fd, unstamped_name):
                _remove_entry_at(transaction_fd, unstamped_name)

    def _apply_snapshot_modes(self) -> None:
        staged_fd = os.open(
            self.skill_name,
            DIRECTORY_FLAGS,
            dir_fd=self._require_fd(self.transaction_fd, "transaction"),
        )
        try:
            files = [(path, item) for path, item in self.manifest.items() if item.kind == "file"]
            directories = [
                (path, item) for path, item in self.manifest.items() if item.kind == "directory"
            ]
            for path, item in files:
                descriptor = _open_components(staged_fd, path, READ_FLAGS)
                try:
                    os.fchmod(descriptor, item.mode)
                finally:
                    os.close(descriptor)
            for path, item in sorted(directories, key=lambda value: len(value[0]), reverse=True):
                descriptor = _open_components(staged_fd, path, DIRECTORY_FLAGS)
                try:
                    os.fchmod(descriptor, item.mode)
                finally:
                    os.close(descriptor)
            os.fchmod(staged_fd, self.source_root_mode)
        finally:
            os.close(staged_fd)

    def _next_backup_name(self, base: str) -> str:
        backups_fd = self._require_fd(self.backups_fd, "backups")
        candidate = base
        counter = 1
        while _lexists_at(backups_fd, candidate):
            candidate = f"{base}.{counter}"
            counter += 1
        return candidate

    def migrate_legacy_backups(self) -> None:
        skills_fd = self._require_fd(self.skills_fd, "skills")
        prefix = f"{self.skill_name}.backup."
        with os.scandir(skills_fd) as entries:
            names = sorted(entry.name for entry in entries if entry.name.startswith(prefix))
        if not names:
            return
        backups_fd = self._ensure_backups_root()
        for name in names:
            if not _lexists_at(skills_fd, name):
                continue
            destination = self._next_backup_name(name)
            os.rename(name, destination, src_dir_fd=skills_fd, dst_dir_fd=backups_fd)
            print(
                f"Moved legacy backup out of the Skill search path: "
                f"{self.agents_path / 'backups' / destination}"
            )

    @contextlib.contextmanager
    def _signals_blocked(self) -> Iterator[None]:
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED_SIGNALS)
        try:
            yield
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)

    def backup_active_skill(self) -> None:
        skills_fd = self._require_fd(self.skills_fd, "skills")
        if not _lexists_at(skills_fd, self.skill_name):
            return
        backups_fd = self._ensure_backups_root()
        base = f"{self.skill_name}.backup.{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"
        backup = self._next_backup_name(base)
        with self._signals_blocked():
            os.rename(
                self.skill_name,
                backup,
                src_dir_fd=skills_fd,
                dst_dir_fd=backups_fd,
            )
            self.active_backup = backup
        print(f"Backed up existing installation to {self.agents_path / 'backups' / backup}")

    def activate_staged_skill(self) -> None:
        skills_fd = self._require_fd(self.skills_fd, "skills")
        transaction_fd = self._require_fd(self.transaction_fd, "transaction")
        if _lexists_at(skills_fd, self.skill_name):
            raise InstallError(f"Destination appeared during installation: {self.destination_path}")
        with self._signals_blocked():
            self.verify_staged_ready()
            if not self.link_mode:
                self._apply_snapshot_modes()
            os.rename(
                self.skill_name,
                self.skill_name,
                src_dir_fd=transaction_fd,
                dst_dir_fd=skills_fd,
            )
            self.staged_present = False
            self.activated = True

    def _install_signal_handlers(self) -> None:
        for signum in HANDLED_SIGNALS:
            self._old_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, self._handle_signal)

    def _restore_signal_handlers(self) -> None:
        for signum, handler in self._old_handlers.items():
            signal.signal(signum, handler)
        self._old_handlers.clear()

    def _ignore_transaction_signals(self) -> None:
        for signum in HANDLED_SIGNALS:
            signal.signal(signum, signal.SIG_IGN)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        raise InstallationSignal(signum)

    def _cleanup_transaction(self) -> None:
        if self.transaction_name is None or self.staging_fd is None:
            return
        if self.transaction_fd is not None:
            os.close(self.transaction_fd)
            self.transaction_fd = None
        _remove_entry_at(self.staging_fd, self.transaction_name)
        self.transaction_name = None
        self.staged_present = False
        # Creation and removal of the shared staging root use the same short
        # registry lock. If another Skill is staging, rmdir simply reports
        # ENOTEMPTY and the shared root remains available to it.
        with self._lock_registry():
            os.close(self.staging_fd)
            self.staging_fd = None
            self.child_identities.pop(".install-staging", None)
            try:
                os.rmdir(
                    ".install-staging",
                    dir_fd=self._require_fd(self.agents_fd, "agents root"),
                )
            except OSError as error:
                if error.errno not in (errno.ENOTEMPTY, errno.EEXIST, errno.ENOENT):
                    raise

    def rollback(self) -> list[str]:
        messages: list[str] = []
        self._ignore_transaction_signals()
        if self.committed:
            return messages
        skills_fd = self.skills_fd
        transaction_fd = self.transaction_fd
        backups_fd = self.backups_fd
        try:
            if self.activated:
                if skills_fd is None or transaction_fd is None:
                    raise InstallError("Cannot access directories needed to roll back activation")
                if _lexists_at(transaction_fd, self.skill_name):
                    raise InstallError("Rollback staging destination is unexpectedly occupied")
                os.rename(
                    self.skill_name,
                    self.skill_name,
                    src_dir_fd=skills_fd,
                    dst_dir_fd=transaction_fd,
                )
                self.activated = False
                self.staged_present = True
            if self.active_backup is not None:
                if skills_fd is None or backups_fd is None:
                    raise InstallError("Cannot access directories needed to restore active Skill")
                if _lexists_at(skills_fd, self.skill_name):
                    raise InstallError("Cannot restore previous Skill because active destination exists")
                backup_name = self.active_backup
                os.rename(
                    backup_name,
                    self.skill_name,
                    src_dir_fd=backups_fd,
                    dst_dir_fd=skills_fd,
                )
                self.active_backup = None
                messages.append(
                    f"Restored previous installation after activation failed: {self.destination_path}"
                )
        except (InstallError, OSError) as error:
            messages.append(
                "Could not restore previous installation. "
                f"Its backup remains at {self.agents_path / 'backups' / (self.active_backup or '')}: {error}"
            )
        try:
            self._cleanup_transaction()
        except OSError as error:
            messages.append(f"Could not clean installation staging directory: {error}")
        return messages

    def _commit_transaction(self) -> None:
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, HANDLED_SIGNALS)
        try:
            self.committed = True
            self.active_backup = None
            self.activated = False
            try:
                self._cleanup_transaction()
            except (InstallError, OSError) as error:
                print(
                    f"Warning: could not clean installation staging directory: {error}",
                    file=sys.stderr,
                )
            # A pending signal is delivered with the caller's original
            # disposition only after the committed transaction is clean.
            self._restore_signal_handlers()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)

    def _source_summary(self, install_state: str | None) -> str:
        if self.source_state == "head":
            short_oid = self.display_oid or "unknown"
            if self.link_mode:
                return f"Git HEAD {short_oid}; linked Skill follows the live source"
            if install_state == "clean":
                return f"Git commit {short_oid}"
            return f"Git HEAD {short_oid}; copied Skill differs from the committed tree"
        if self.source_state == "unborn":
            return "unborn Git worktree; copied content has no commit ID"
        if self.source_state == "non-git":
            return "non-Git directory; no commit ID is available"
        return "Git unavailable; no commit ID is available"

    def _run_transaction(self) -> tuple[str | None, str]:
        self.validate_layout()
        self.acquire_lock()
        self.validate_layout_under_lock()
        # Test checkpoint: layout validated under lock.
        self.resolve_short_oid()
        skills_fd = self._require_fd(self.skills_fd, "skills")
        if _lexists_at(skills_fd, self.skill_name) and not self.force:
            raise InstallError(
                f"Destination exists: {self.destination_path}. Re-run with --force to replace it."
            )
        self._open_transaction_roots()
        self.verify_roots()

        install_state: str | None = None
        if self.link_mode:
            self.stage_link()
        else:
            self.stage_copy()
            if self.source_state == "head":
                install_state = self.classify_copy()
            else:
                install_state = self.source_state
            self.stamp_copy(install_state)
            self.capture_final_fingerprint()

        self.verify_roots()
        self.migrate_legacy_backups()
        self.backup_active_skill()
        # Test checkpoint: active Skill backed up.
        self.verify_roots()
        self.activate_staged_skill()
        # Test checkpoint: staged Skill activated.
        self.verify_roots()
        summary = self._source_summary(install_state)
        self._commit_transaction()
        return install_state, summary

    def run(self) -> int:
        try:
            self.prepare_roots()
        except BaseException:
            self.close()
            raise
        self._install_signal_handlers()
        try:
            try:
                _install_state, source_summary = self._run_transaction()
            except InstallationSignal as interruption:
                for message in self.rollback():
                    print(message, file=sys.stderr)
                print(
                    f"Installation interrupted by signal {interruption.signum}.",
                    file=sys.stderr,
                )
                return 128 + interruption.signum
            except BaseException:
                for message in self.rollback():
                    print(message, file=sys.stderr)
                raise
            finally:
                self._restore_signal_handlers()

            if self.link_mode:
                print(
                    f"Linked {self.source_path} -> {self.destination_path} "
                    f"for {self.agent} ({self.scope} scope)."
                )
                print(
                    "The description is not revision-stamped because --link follows "
                    f"the live source. Current source: {source_summary}."
                )
            else:
                print(
                    f"Installed {self.skill_name} to {self.destination_path} "
                    f"for {self.agent} ({self.scope} scope)."
                )
                print(f"Installed description source: {source_summary}.")
            return 0
        finally:
            self.close()

    def close(self) -> None:
        if self.lock_fd is not None:
            if self.locks_fd is not None:
                with self._lock_registry():
                    try:
                        named = os.stat(
                            self.skill_name,
                            dir_fd=self.locks_fd,
                            follow_symlinks=False,
                        )
                    except FileNotFoundError:
                        named = None
                    if named is not None and _identity(named) == _identity(
                        os.fstat(self.lock_fd)
                    ):
                        # Unlink only after every protected operation. A new
                        # installer may now lock a new inode, but this process
                        # has no transactional work left to overlap with it.
                        os.unlink(self.skill_name, dir_fd=self.locks_fd)
                    fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                    os.close(self.lock_fd)
                    self.lock_fd = None
            else:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                self.lock_fd = None
        for attribute in (
            "transaction_fd",
            "staging_fd",
            "backups_fd",
            "locks_fd",
            "skills_fd",
            "agents_fd",
            "repo_fd",
            "source_fd",
        ):
            descriptor = getattr(self, attribute)
            if descriptor is not None:
                os.close(descriptor)
                setattr(self, attribute, None)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install a local Skill transactionally.")
    commands = parser.add_subparsers(dest="command", required=True)
    install = commands.add_parser("install")
    install.add_argument("source_dir")
    install.add_argument("repo_dir")
    install.add_argument("agents_root")
    install.add_argument("skill_name")
    install.add_argument(
        "--source-state",
        required=True,
        choices=("head", "unborn", "non-git", "git-unavailable"),
    )
    install.add_argument("--oid")
    install.add_argument("--link", action="store_true")
    install.add_argument("--force", action="store_true")
    install.add_argument("--agent", default="codex", choices=("codex", "github-copilot"))
    install.add_argument("--scope", default="project", choices=("user", "project"))
    arguments = parser.parse_args(argv)
    if not SKILL_NAME_PATTERN.fullmatch(arguments.skill_name):
        parser.error(f"invalid Skill name: {arguments.skill_name}")
    if arguments.source_state == "head":
        if arguments.oid is None or not OID_PATTERN.fullmatch(arguments.oid):
            parser.error("--source-state head requires a full 40- or 64-character --oid")
    elif arguments.oid is not None:
        parser.error("--oid is only valid with --source-state head")
    return arguments


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    installer = LocalInstaller(arguments)
    try:
        return installer.run()
    except (InstallError, OSError, StampError, UnicodeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
