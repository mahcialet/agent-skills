#!/usr/bin/env python3
"""Dependency-free structural validator for the skills monorepo."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"(?<!!)\[[^]]*\]\(([^)]+)\)")
CODE_PATH_RE = re.compile(r"`((?:references|examples|evals|scripts)/[^`\s]+)`")
FORBIDDEN_FRONTMATTER = {"allowed-tools", "model", "version", "tools"}


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("frontmatter must start on the first line")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("frontmatter closing delimiter is missing") from exc
    data: dict[str, str] = {}
    current: str | None = None
    folded: list[str] = []
    for line in lines[1:end]:
        if line.startswith((" ", "\t")):
            if current is None:
                raise ValueError("indented value has no key")
            folded.append(line.strip())
            continue
        if current is not None and folded:
            data[current] = " ".join(folded)
            folded = []
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or key in data:
            raise ValueError(f"invalid or duplicate key: {key!r}")
        current = key
        data[key] = "" if value in {">", ">-", "|", "|-"} else value.strip('"\'')
    if current is not None and folded:
        data[current] = " ".join(folded)
    return data, "\n".join(lines[end + 1 :])


def check_markdown_links(repo: Path, errors: list[str]) -> None:
    for path in repo.rglob("*.md"):
        if any(part in {".git", ".codex", ".tokensave"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        for raw_target in LINK_RE.findall(text):
            target = raw_target.split("#", 1)[0].strip().strip("<>")
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            if not (path.parent / target).resolve().exists():
                errors.append(f"{path.relative_to(repo)}: broken link {raw_target}")


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    skills_dir = repo / "skills"
    skill_files = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else []
    if not skill_files:
        return ["no skills/*/SKILL.md files found"]

    all_skill_files = [
        path for path in repo.rglob("SKILL.md")
        if not any(part in {".git", ".codex", ".tokensave"} for part in path.parts)
    ]
    unexpected = set(all_skill_files) - set(skill_files)
    for path in sorted(unexpected):
        errors.append(f"unexpected duplicate/provider skill: {path.relative_to(repo)}")

    root_readme = (repo / "README.md").read_text(encoding="utf-8")
    seen_names: set[str] = set()
    for skill_file in skill_files:
        skill_dir = skill_file.parent
        rel = skill_file.relative_to(repo)
        try:
            metadata, body = parse_frontmatter(skill_file)
        except (OSError, ValueError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        name = metadata.get("name", "")
        description = metadata.get("description", "")
        if not NAME_RE.fullmatch(name):
            errors.append(f"{rel}: invalid name {name!r}")
        if name != skill_dir.name:
            errors.append(f"{rel}: name must match directory {skill_dir.name!r}")
        if name in seen_names:
            errors.append(f"{rel}: duplicate skill name {name}")
        seen_names.add(name)
        if not 1 <= len(description) <= 1024:
            errors.append(f"{rel}: description must contain 1-1024 characters")
        forbidden = FORBIDDEN_FRONTMATTER & metadata.keys()
        if forbidden:
            errors.append(f"{rel}: non-portable frontmatter: {', '.join(sorted(forbidden))}")
        if not metadata.get("license"):
            errors.append(f"{rel}: license field is required by repository policy")
        for required in ("README.md", "NOTICE.md"):
            if not (skill_dir / required).is_file():
                errors.append(f"{skill_dir.relative_to(repo)}: missing {required}")
        row_count = len(re.findall(rf"^\|\s*\[{re.escape(name)}\]\(", root_readme, re.M))
        if row_count != 1:
            errors.append(f"README.md: catalog must contain exactly one row for {name}")
        for reference in CODE_PATH_RE.findall(body):
            target = (skill_dir / reference).resolve()
            if skill_dir.resolve() not in target.parents or not target.is_file():
                errors.append(f"{rel}: missing or external reference {reference}")
        content_validator = skill_dir / "scripts" / "validate_content.py"
        if not content_validator.is_file():
            errors.append(f"{skill_dir.relative_to(repo)}: missing content validator")
        else:
            result = subprocess.run(
                [sys.executable, str(content_validator)],
                cwd=repo,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                errors.append(f"{content_validator.relative_to(repo)} failed:\n{result.stderr.strip()}")

    if "reader-first-editor" not in seen_names:
        errors.append("reader-first-editor must be the first implemented skill")
    if len(seen_names) == 1 and seen_names != {"reader-first-editor"}:
        errors.append("the initial catalog must contain only reader-first-editor")

    catalog_generator = repo / "scripts" / "generate-catalog.py"
    if not catalog_generator.is_file():
        errors.append("scripts/generate-catalog.py is missing")
    else:
        result = subprocess.run(
            [sys.executable, str(catalog_generator), "--check", "--repo", str(repo)],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            errors.append(f"catalog generator failed:\n{result.stderr.strip()}")

    openai_metadata = skills_dir / "reader-first-editor" / "agents" / "openai.yaml"
    if openai_metadata.is_file():
        text = openai_metadata.read_text(encoding="utf-8")
        for token in ("interface:", "policy:", "allow_implicit_invocation: false"):
            if token not in text:
                errors.append(f"{openai_metadata.relative_to(repo)}: missing {token}")

    check_markdown_links(repo, errors)
    return errors


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    errors = validate(repo)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    count = len(list((repo / "skills").glob("*/SKILL.md")))
    print(f"validated {count} skill(s): structure, catalog, references, notices, and evals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
