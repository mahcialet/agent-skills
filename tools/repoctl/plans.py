"""ExecPlanの構造と明示的なlocal Git到達性検査。状態変更はしない。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from .docs import diagnostic, metadata

SECTIONS = ("Purpose / Big Picture", "Progress", "Surprises & Discoveries", "Decision Log",
            "Outcomes & Retrospective", "Context and Orientation", "Plan of Work", "Concrete Steps",
            "Validation and Acceptance", "Idempotence and Recovery", "Artifacts and Notes",
            "Interfaces and Dependencies")
FIELDS = ("status", "owner", "last_verified", "plan_id", "plan_type", "base_branch", "branch", "merge_policy")
STATES = {"draft", "active", "paused", "completed", "abandoned"}
PAIR_FIELDS = (*FIELDS, "depends_on", "parent", "children", "execution_mode", "merge_commit")


def list_plans(repo: Path) -> list[dict]:
    result = []
    for path in sorted((repo / "docs/exec-plans").glob("*/*.md")):
        if path.name.endswith(".en.md"):
            continue
        try:
            info = metadata(path)
            result.append({"path": str(path.relative_to(repo)), "plan_id": info.get("plan_id"),
                           "status": info.get("status"), "plan_type": info.get("plan_type"),
                           "automatic_execution": False})
        except (ValueError, OSError):
            result.append({"path": str(path.relative_to(repo)), "status": "INVALID", "automatic_execution": False})
    return result


def validate(repo: Path, *, check_git: bool = False) -> list[dict]:
    errors: list[dict] = []
    records: dict[str, tuple[Path, dict]] = {}
    def add(code: str, path: Path, reason: str, *, blocked: bool = False) -> None:
        item = diagnostic(code, str(path.relative_to(repo)), reason, "plans")
        if blocked:
            item["blocked"] = True
        errors.append(item)
    paths = sorted((repo / "docs/exec-plans").rglob("*.md"))
    for path in paths:
        if not path.resolve().is_relative_to(repo.resolve()):
            add("PLAN-PATH", path, "plan source resolves outside repository")
            continue
        try:
            info = metadata(path)
        except (ValueError, OSError) as exc:
            add("PLAN-METADATA", path, str(exc))
            continue
        if any(not info.get(key) for key in FIELDS):
            add("PLAN-METADATA", path, "required metadata missing")
        headings = re.findall(r"(?m)^## (.+)$", path.read_text(encoding="utf-8"))
        for heading in SECTIONS:
            if headings.count(heading) != 1:
                add("PLAN-SECTIONS", path, f"required section must occur once: {heading}")
        state = info.get("status")
        if state not in STATES or path.parent.name != state or path.parent.parent != repo / "docs/exec-plans":
            add("PLAN-STATE", path, "status and lifecycle directory must agree")
        if info.get("plan_type") not in {"implementation", "review", "human-validation"}:
            add("PLAN-TYPE", path, "unsupported plan_type")
        if info.get("merge_policy") != "manual":
            add("PLAN-POLICY", path, "merge_policy must remain manual")
        if info.get("plan_type") == "human-validation" and info.get("execution_mode") != "human-kick":
            add("PLAN-HUMAN", path, "human-validation requires human-kick")
        if state == "paused" and not (info.get("pause_reason") and info.get("resume_criteria")):
            add("PLAN-PAUSED", path, "paused plan needs pause_reason and resume_criteria")
        if state == "abandoned" and not info.get("abandon_reason"):
            add("PLAN-ABANDONED", path, "abandoned plan needs abandon_reason")
        if state == "completed" and not re.fullmatch(r"[0-9a-f]{40}", str(info.get("merge_commit", ""))):
            add("PLAN-MERGE", path, "completed requires actual full delivery merge_commit")
        if path.name.endswith(".en.md"):
            source = path.with_name(path.name[:-6] + ".md")
            if not source.is_file():
                add("PLAN-PAIR", path, "missing Japanese source plan")
            continue
        translated = path.with_name(path.stem + ".en.md")
        if not translated.is_file():
            add("PLAN-PAIR", path, "missing English plan")
        else:
            try:
                peer = metadata(translated)
                if any(info.get(field) != peer.get(field) for field in PAIR_FIELDS):
                    add("PLAN-PAIR", path, "translation metadata differs")
            except ValueError:
                add("PLAN-PAIR", translated, "invalid translation metadata")
        plan_id = info.get("plan_id")
        if not isinstance(plan_id, str) or not re.fullmatch(r"EP-[A-Z0-9-]+", plan_id):
            add("PLAN-ID", path, "invalid plan_id")
            continue
        if plan_id in records:
            add("PLAN-ID-DUPLICATE", path, f"unrelated duplicate logical plan ID: {plan_id}")
        records[plan_id] = (path, info)
    graph: dict[str, list[str]] = {}
    parents: dict[str, list[str]] = {}
    child_graph: dict[str, list[str]] = {}
    for plan_id, (path, info) in records.items():
        deps = info.get("depends_on", [])
        children = info.get("children", [])
        parent = info.get("parent")
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            add("PLAN-REFERENCE", path, "depends_on must be a list of plan IDs")
            deps = []
        if not isinstance(children, list) or not all(isinstance(d, str) for d in children):
            add("PLAN-REFERENCE", path, "children must be a list of plan IDs")
            children = []
        if parent is not None and not isinstance(parent, str):
            add("PLAN-REFERENCE", path, "parent must be a plan ID")
            parent = None
        for ref in deps + children + ([parent] if parent else []):
            if ref == plan_id or ref not in records:
                add("PLAN-REFERENCE", path, f"missing or self reference: {ref}")
        graph[plan_id] = deps
        parents[plan_id] = [parent] if parent else []
        child_graph[plan_id] = children
        parent_children = records[parent][1].get("children", []) if parent in records else []
        if parent in records and (not isinstance(parent_children, list) or plan_id not in parent_children):
            add("PLAN-REFERENCE", path, "parent/children references must be reciprocal")
        for child in children:
            if child in records and records[child][1].get("parent") != plan_id:
                add("PLAN-REFERENCE", path, "children/parent references must be reciprocal")
        if check_git and info.get("status") == "completed" and info.get("merge_commit"):
            git = shutil.which("git")
            if not git:
                add("PLAN-HISTORY", path, "Git is unavailable", blocked=True)
                continue
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            try:
                result = subprocess.run([git, "merge-base", "--is-ancestor", str(info["merge_commit"]),
                                         f"refs/remotes/origin/{info['base_branch']}"], cwd=repo, env=env,
                                        capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.TimeoutExpired):
                add("PLAN-HISTORY", path, "local Git history check unavailable", blocked=True)
                continue
            if result.returncode:
                shallow = False
                if result.returncode == 1:
                    try:
                        history = subprocess.run([git, "rev-parse", "--is-shallow-repository"],
                                                 cwd=repo, env=env, capture_output=True, text=True,
                                                 timeout=30, check=False)
                        shallow = history.returncode != 0 or history.stdout.strip() == "true"
                    except (OSError, subprocess.TimeoutExpired):
                        shallow = True
                add("PLAN-HISTORY", path, "delivery commit is not proven reachable from local remote base; fetch/history may be required",
                    blocked=result.returncode != 1 or shallow)
    def cycle(graph: dict[str, list[str]]) -> bool:
        active: set[str] = set()
        done: set[str] = set()
        def visit(node: str) -> bool:
            if node in active:
                return True
            if node in done:
                return False
            active.add(node)
            if any(visit(dep) for dep in graph.get(node, [])):
                return True
            active.remove(node)
            done.add(node)
            return False
        return any(visit(node) for node in graph)
    if cycle(graph) or cycle(parents) or cycle(child_graph):
        add("PLAN-CYCLE", repo / "docs/exec-plans", "dependency or parent cycle")
    return errors
