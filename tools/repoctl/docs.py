"""限定されたsource文書と翻訳参照のread-only検査。"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote

LINK = re.compile(r"(?<!!)\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
EXCLUDED = {".git", ".venv", "__pycache__", ".agents", ".codex", ".tokensave", "tests"}


def diagnostic(code: str, path: str, reason: str, task: str = "docs") -> dict:
    return {"code": f"ASKILLS-{code}", "task_id": task, "path": path,
            "reason": reason, "repair": "Correct the source document and review its paired translation"}


def source_files(repo: Path) -> list[Path]:
    roots = [*repo.glob("*.md"), *repo.glob("docs/**/*.md"), *repo.glob("skills/**/*.md")]
    return sorted(p for p in roots if not set(p.relative_to(repo).parts) & EXCLUDED
                  and p.name != "execplan_agent_skills_repository_harness.md")


def prose(text: str) -> str:
    return re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)


def anchors(text: str) -> set[str]:
    result = set(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    seen: dict[str, int] = {}
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$", prose(text)):
        slug = re.sub(r"[^\w\- ]", "", re.sub(r"<[^>]+>", "", heading).lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


def metadata(path: Path) -> dict:
    import yaml
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    parts = re.split(r"\n---[ \t]*\n", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("missing frontmatter terminator")
    try:
        node = yaml.compose(parts[0][4:])
        if isinstance(node, yaml.MappingNode):
            keys = [key.value for key, _ in node.value]
            if len(keys) != len(set(keys)):
                raise ValueError("duplicate frontmatter key")
        value = yaml.safe_load(parts[0][4:])
    except yaml.YAMLError as exc:
        raise ValueError("invalid frontmatter YAML") from exc
    if not isinstance(value, dict):
        raise ValueError("frontmatter must be a mapping")
    return value


def validate(repo: Path) -> list[dict]:
    repo = repo.resolve()
    errors: list[dict] = []
    def add(code: str, path: Path, reason: str) -> None:
        errors.append(diagnostic(code, str(path.relative_to(repo)), reason))

    for path in source_files(repo):
        if not path.resolve().is_relative_to(repo):
            add("DOC-PATH", path, "source document resolves outside repository")
            continue
        for target in LINK.findall(prose(path.read_text(encoding="utf-8"))):
            target = unquote(target.strip("<>"))
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            name, _, fragment = target.partition("#")
            dest = (path.parent / name).resolve() if name else path
            if not dest.is_relative_to(repo) or not dest.exists():
                add("DOC-LINK", path, f"broken or external local link: {target}")
            elif fragment and dest.is_file() and dest.suffix == ".md":
                if fragment not in anchors(dest.read_text(encoding="utf-8")):
                    add("DOC-ANCHOR", path, f"missing anchor: {target}")
    agents = repo / "AGENTS.md"
    if (not agents.resolve().is_relative_to(repo) or not agents.is_file()
            or len(agents.read_text(encoding="utf-8").splitlines()) > 150):
        add("DOC-AGENTS", agents, "AGENTS.md is required and limited to 150 lines")
    manifest = repo / "tools/repoctl/doc-manifest.json"
    if not manifest.resolve().is_relative_to(repo):
        add("DOC-MANIFEST", manifest, "manifest resolves outside repository")
        return errors
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        if data.get("schema_version") != 1 or not isinstance(data.get("pairs"), list):
            raise ValueError("expected schema_version 1 and pairs list")
    except (OSError, ValueError, AttributeError) as exc:
        add("DOC-MANIFEST", manifest, str(exc))
        return errors
    paired: set[str] = set()
    for pair in data["pairs"]:
        if not isinstance(pair, dict) or not all(isinstance(pair.get(k), str) for k in ("source", "translation", "source_sha256")):
            add("DOC-MANIFEST", manifest, "invalid pair record")
            continue
        src, translated = repo / pair["source"], repo / pair["translation"]
        if any(Path(pair[key]).is_absolute() or not (repo / pair[key]).resolve().is_relative_to(repo)
               for key in ("source", "translation")):
            add("DOC-MANIFEST", manifest, "pair paths must remain inside repository")
            continue
        if pair["source"].endswith(".en.md") or pair["translation"] != pair["source"][:-3] + ".en.md":
            add("DOC-PAIR", manifest, "translation must be source basename.en.md")
        for path in (src, translated):
            rel = str(path.relative_to(repo))
            if rel in paired:
                add("DOC-PAIR", manifest, f"duplicate pair path: {rel}")
            paired.add(rel)
            if not path.resolve().is_relative_to(repo) or not path.is_file():
                add("DOC-MISSING-TRANSLATION", manifest, f"missing pair member: {rel}")
                continue
            try:
                meta = metadata(path)
                if not all(meta.get(key) for key in ("status", "owner", "last_verified")):
                    raise ValueError("status, owner and last_verified required")
            except ValueError as exc:
                add("DOC-METADATA", path, str(exc))
        if src.is_file() and src.resolve().is_relative_to(repo):
            digest = hashlib.sha256(src.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            if digest != pair["source_sha256"]:
                add("DOC-STALE-TRANSLATION", src, "source changed since translation review")
    required = {"AGENTS.md", "AGENTS.en.md", "docs/index.md", "docs/index.en.md",
                "docs/architecture.md", "docs/architecture.en.md", "docs/QUALITY.md", "docs/QUALITY.en.md",
                "docs/PLANS.md", "docs/PLANS.en.md"}
    required.update(str(p.relative_to(repo)) for root in ("adr", "testing", "exec-plans")
                    for p in (repo / "docs" / root).rglob("*.md"))
    required.update(str(p.relative_to(repo)) for p in source_files(repo) if p.name.endswith(".en.md"))
    for missing in sorted(required - paired):
        errors.append(diagnostic("DOC-ORPHAN-TRANSLATION", missing, "document has no registered translation pair"))
    for index_name, suffix in (("docs/index.md", ".md"), ("docs/index.en.md", ".en.md")):
        index = repo / index_name
        if not index.is_file():
            add("DOC-INDEX", index, "required documentation index missing")
            continue
        links = {(index.parent / raw.split("#", 1)[0].strip("<>")).resolve()
                 for raw in LINK.findall(prose(index.read_text(encoding="utf-8")))}
        for rel in paired:
            if rel == index_name or (rel.endswith(".en.md") != (suffix == ".en.md")):
                continue
            if (repo / rel).resolve() not in links:
                add("DOC-INDEX", index, f"paired document not indexed: {rel}")
    return errors
