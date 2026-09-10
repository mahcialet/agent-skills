#!/usr/bin/env python3
"""Public, shell-free local installer entry; retain the checked POSIX transaction."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Sequence


SKILL_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
OID_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class SourceError(RuntimeError):
    """Git source cannot safely be identified before installation."""


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install a repository Skill locally.", allow_abbrev=False
    )
    parser.add_argument("skill_name")
    parser.add_argument("--scope", choices=("user", "project"), default="project")
    parser.add_argument("--agent", choices=("codex", "github-copilot"), default="codex")
    parser.add_argument("--link", action="store_true")
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args(argv)
    if not SKILL_NAME_PATTERN.fullmatch(arguments.skill_name):
        parser.error(f"Invalid Skill name: {arguments.skill_name}")
    return arguments


def source_git_environment() -> dict[str, str]:
    # Remove indexed GIT_CONFIG_KEY_n / VALUE_n too, not just GIT_CONFIG_COUNT.
    environment = {
        key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")
    }
    environment.update({"GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"})
    return environment


def inspect_source(repository: Path) -> tuple[str, str | None]:
    git = shutil.which("git")
    if git is None:
        return "git-unavailable", None
    if not os.path.lexists(repository / ".git"):
        return "non-git", None

    def run(*arguments: str) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [git, "-C", str(repository), *arguments],
                env=source_git_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as error:
            raise SourceError("Unable to inspect Git metadata; installation stopped.") from error

    root = run("rev-parse", "--show-toplevel")
    if root.returncode:
        raise SourceError("Unable to inspect Git metadata; installation stopped before replacing the active Skill.")
    if Path(root.stdout.strip()).resolve() != repository.resolve():
        raise SourceError("Unexpected Git repository root; installation stopped before replacing the active Skill.")
    head = run("rev-parse", "--verify", "HEAD^{commit}")
    if head.returncode == 0:
        oid = head.stdout.strip()
        if not OID_PATTERN.fullmatch(oid):
            raise SourceError("Git returned an unsupported commit ID.")
        return "head", oid
    if run("symbolic-ref", "-q", "HEAD").returncode == 0:
        return "unborn", None
    raise SourceError("Git metadata exists, but HEAD is not a readable commit; installation stopped.")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    repository = Path(__file__).resolve().parents[1]
    source = repository / "skills" / arguments.skill_name
    if not (source / "SKILL.md").is_file():
        print(f"Skill not found: {source}", file=sys.stderr)
        return 1
    if os.name != "posix":
        print(
            "ASKILLS-INSTALL-PLATFORM: BLOCKED: the protected installer requires "
            "POSIX directory descriptors, flock and signal masks; a native Windows "
            "backend has not been implemented. No installation was attempted.",
            file=sys.stderr,
        )
        return 3
    if arguments.scope == "user":
        user_home = os.environ.get("HOME")
        if not user_home:
            print("HOME must be set for user-scope installation", file=sys.stderr)
            return 1
        agents_root = Path(user_home) / ".agents"
    else:
        agents_root = repository / ".agents"
    try:
        state, oid = inspect_source(repository)
    except (SourceError, OSError) as error:
        print(f"ASKILLS-INSTALL-SOURCE: {error}", file=sys.stderr)
        return 1
    helper = repository / "scripts" / "install_local.py"
    if not helper.is_file():
        print(f"Install helper not found: {helper}", file=sys.stderr)
        return 1
    command = [
        sys.executable, str(helper), "install", str(source), str(repository),
        str(agents_root), arguments.skill_name, "--source-state", state,
        "--scope", arguments.scope, "--agent", arguments.agent,
    ]
    if oid is not None:
        command.extend(("--oid", oid))
    if arguments.link:
        command.append("--link")
    if arguments.force:
        command.append("--force")
    # Preserve ownership of signals, locks and rollback without a shell parent.
    os.execv(sys.executable, command)
    return 1  # pragma: no cover -- execv only returns by raising.


if __name__ == "__main__":
    raise SystemExit(main())
