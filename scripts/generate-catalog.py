#!/usr/bin/env python3
"""Generate the README skill catalog from skills and supplemental metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

START = "<!-- BEGIN GENERATED SKILL CATALOG -->"
END = "<!-- END GENERATED SKILL CATALOG -->"
NAME_RE = re.compile(r"^name:\s*([a-z0-9]+(?:-[a-z0-9]+)*)\s*$", re.MULTILINE)


def skill_names(repo: Path) -> set[str]:
    names: set[str] = set()
    for path in sorted((repo / "skills").glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        match = NAME_RE.search(text)
        if not match:
            raise ValueError(f"{path}: frontmatter name is missing or invalid")
        name = match.group(1)
        if name != path.parent.name:
            raise ValueError(f"{path}: name does not match its directory")
        if name in names:
            raise ValueError(f"duplicate skill name: {name}")
        names.add(name)
    return names


def load_catalog(repo: Path, names: set[str]) -> dict[str, dict]:
    path = repo / "catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("catalog.json must be an object keyed by skill name")
    metadata_names = set(data)
    if names != metadata_names:
        missing = sorted(names - metadata_names)
        extra = sorted(metadata_names - names)
        raise ValueError(f"catalog mismatch; missing={missing}, extra={extra}")
    required = {"category", "codex", "copilot", "languages", "stability", "description"}
    for name, metadata in data.items():
        if not isinstance(metadata, dict) or not required <= metadata.keys():
            raise ValueError(f"catalog metadata is incomplete for {name}")
        if not isinstance(metadata["languages"], list) or not metadata["languages"]:
            raise ValueError(f"catalog languages must be a non-empty list for {name}")
    return data


def render(data: dict[str, dict]) -> str:
    groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for name, metadata in data.items():
        groups[metadata["category"]].append((name, metadata))
    if set(groups) != {"Writing and Review"}:
        raise ValueError("initial generator supports the existing Writing and Review section only")
    lines = [
        START,
        "| Skill | Codex | Copilot | Languages | Stability | Description | License |",
        "|---|:---:|:---:|---|---|---|---|",
    ]
    for name, metadata in sorted(groups["Writing and Review"]):
        codex = "✓" if metadata["codex"] else "—"
        copilot = "✓" if metadata["copilot"] else "—"
        languages = ", ".join(metadata["languages"])
        lines.append(
            f"| [{name}](skills/{name}/README.md) | {codex} | {copilot} | "
            f"{languages} | {metadata['stability']} | {metadata['description']} | "
            f"[MIT + notices](skills/{name}/NOTICE.md) |"
        )
    lines.append(END)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail instead of updating README")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        block = render(load_catalog(repo, skill_names(repo)))
        readme_path = repo / "README.md"
        readme = readme_path.read_text(encoding="utf-8")
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
        if not pattern.search(readme):
            raise ValueError("README catalog markers are missing")
        updated = pattern.sub(block, readme, count=1)
        if args.check:
            if updated != readme:
                print("README catalog is stale", file=sys.stderr)
                return 1
            print("README catalog is current")
            return 0
        readme_path.write_text(updated, encoding="utf-8")
        print("updated README catalog")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
