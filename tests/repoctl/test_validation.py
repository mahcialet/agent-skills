from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tools.repoctl import docs, plans, tasks

ROOT = Path(__file__).resolve().parents[2]


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)

    def write(self, name, text):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def pair(self, name, text):
        text = "---\nstatus: active\nowner: maintainers\nlast_verified: 2026-09-11\n---\n" + text
        self.write(name, text)
        translated = name[:-3] + ".en.md"
        self.write(translated, text)
        return {"source": name, "translation": translated,
                "source_sha256": hashlib.sha256(text.encode()).hexdigest()}

    def docs_fixture(self):
        names = ["AGENTS.md", "docs/architecture.md", "docs/QUALITY.md", "docs/PLANS.md", "docs/index.md"]
        pairs = [self.pair(name, "# Title\n") for name in names]
        for language in ("", ".en"):
            index = self.repo / f"docs/index{language}.md"
            text = index.read_text()
            for name in names[:-1]:
                relative = "../" + name if name == "AGENTS.md" else name[5:]
                text += f"[document]({relative[:-3]}{language}.md)\n"
            index.write_text(text)
        pairs[-1]["source_sha256"] = hashlib.sha256((self.repo / "docs/index.md").read_bytes()).hexdigest()
        self.write("tools/repoctl/doc-manifest.json", json.dumps({"schema_version": 1, "pairs": pairs}))

    def codes(self, diagnostics):
        return {d["code"] for d in diagnostics}

    def test_docs_positive_and_negative_controls(self):
        self.docs_fixture()
        self.assertEqual([], docs.validate(self.repo))
        source = self.repo / "docs/QUALITY.md"
        source.write_text(source.read_text() + "\n[broken](PLANS.md#absent)\n")
        codes = self.codes(docs.validate(self.repo))
        self.assertIn("ASKILLS-DOC-STALE-TRANSLATION", codes)
        self.assertIn("ASKILLS-DOC-ANCHOR", codes)
        (self.repo / "docs/QUALITY.en.md").unlink()
        self.assertIn("ASKILLS-DOC-MISSING-TRANSLATION", self.codes(docs.validate(self.repo)))
        self.write("docs/testing/unpaired.en.md", "# Orphan")
        self.assertIn("ASKILLS-DOC-ORPHAN-TRANSLATION", self.codes(docs.validate(self.repo)))
        self.write("docs/index.md", "# Removed links")
        self.assertIn("ASKILLS-DOC-INDEX", self.codes(docs.validate(self.repo)))

    def plan(self, plan_id="EP-TEST-001", state="active", extra="", name="one"):
        text = (f"---\nstatus: {state}\nowner: maintainers\nlast_verified: 2026-09-11\n"
                f"plan_id: {plan_id}\nplan_type: implementation\nbase_branch: master\n"
                f"branch: feat/test\nmerge_policy: manual\n{extra}---\n"
                + "\n".join(f"## {section}\nContent\n" for section in plans.SECTIONS))
        path = self.write(f"docs/exec-plans/{state}/{name}.md", text)
        self.write(f"docs/exec-plans/{state}/{name}.en.md", text)
        return path

    def test_plan_pair_is_one_logical_plan_no_automatic_execution(self):
        self.plan(state="draft")
        self.assertEqual([], plans.validate(self.repo))
        entries = plans.list_plans(self.repo)
        self.assertEqual(1, len(entries))
        self.assertFalse(entries[0]["automatic_execution"])

    def test_plan_state_sections_duplicates_and_references(self):
        path = self.plan(extra="depends_on: [EP-MISSING-001]\n")
        path.write_text(path.read_text().replace("## Progress", "## Lost").replace("status: active", "status: paused"))
        self.plan(name="duplicate")
        codes = self.codes(plans.validate(self.repo))
        self.assertTrue({"ASKILLS-PLAN-STATE", "ASKILLS-PLAN-SECTIONS", "ASKILLS-PLAN-ID-DUPLICATE",
                         "ASKILLS-PLAN-PAIR", "ASKILLS-PLAN-REFERENCE"}.issubset(codes))

    def test_cycle_and_completed_without_delivery(self):
        self.plan(extra="depends_on: [EP-TEST-002]\n")
        self.plan("EP-TEST-002", extra="depends_on: [EP-TEST-001]\n", name="two")
        self.plan("EP-TEST-003", state="completed", name="three")
        codes = self.codes(plans.validate(self.repo))
        self.assertIn("ASKILLS-PLAN-CYCLE", codes)
        self.assertIn("ASKILLS-PLAN-MERGE", codes)

    def test_human_requires_kick(self):
        path = self.plan()
        path.write_text(path.read_text().replace("plan_type: implementation", "plan_type: human-validation"))
        self.assertIn("ASKILLS-PLAN-HUMAN", self.codes(plans.validate(self.repo)))

    def test_completed_local_git_reachability_and_missing_history(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(GIT_AUTHOR_NAME="Fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid",
                   GIT_COMMITTER_NAME="Fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.repo, env=env, text=True, capture_output=True,
                                  check=True).stdout.strip()
        git("init", "--initial-branch=master")
        git("commit", "--allow-empty", "-m", "fixture")
        commit = git("rev-parse", "HEAD")
        self.plan(state="completed", extra=f"merge_commit: {commit}\n")
        self.assertEqual([], plans.validate(self.repo, check_git=False))
        diagnostics = plans.validate(self.repo, check_git=True)
        self.assertTrue(any(d.get("blocked") for d in diagnostics))
        git("update-ref", "refs/remotes/origin/master", commit)
        self.assertEqual([], plans.validate(self.repo, check_git=True))
        git("commit", "--allow-empty", "-m", "unmerged fixture")
        newer = git("rev-parse", "HEAD")
        for path in (self.repo / "docs/exec-plans/completed").glob("*.md"):
            path.write_text(path.read_text().replace(commit, newer))
        diagnostics = plans.validate(self.repo, check_git=True)
        self.assertTrue(diagnostics)
        self.assertFalse(any(d.get("blocked") for d in diagnostics))
        # A shallow boundary can hide ancestry; never call that definitive FAIL.
        (self.repo / ".git/shallow").write_text(commit + "\n")
        diagnostics = plans.validate(self.repo, check_git=True)
        self.assertTrue(any(d.get("blocked") for d in diagnostics))

    def test_tasks_dynamic_coverage_and_missing_zero_duplicate(self):
        for name in ("scripts/validate_skills.py", "scripts/generate-catalog.py", "tests/test_root.py",
                     "tests/repoctl/test_harness.py", "skills/new-skill/SKILL.md",
                     "skills/new-skill/scripts/validate_content.py", "skills/new-skill/tests/test_new.py"):
            self.write(name, "# fixture\n")
        built = tasks.build_tasks(self.repo, "verify")
        with mock.patch("tools.repoctl.tasks.importlib.util.find_spec", return_value=None):
            self.assertIn("ASKILLS-DEPENDENCY", tasks.build_tasks(self.repo, "check")[0]["blocked_reason"])
        ids = [t["id"] for t in built]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("test:root", ids)
        self.assertIn("test:skill:new-skill", ids)
        self.assertIn("content:new-skill", ids)
        self.assertEqual({t["id"] for t in tasks.build_tasks(self.repo, "check")} |
                         {t["id"] for t in tasks.build_tasks(self.repo, "test")}, set(ids))
        with self.assertRaisesRegex(ValueError, "ASKILLS-TASK-DUPLICATE"):
            tasks.validate_tasks(built + [built[0]], set())
        with self.assertRaisesRegex(ValueError, "ASKILLS-TASK-MISSING"):
            tasks.validate_tasks([t for t in built if t["id"] != "test:root"], {"test:root"})
        (self.repo / "tests/test_root.py").unlink()
        with self.assertRaisesRegex(ValueError, "ASKILLS-TEST-EMPTY"):
            tasks.build_tasks(self.repo, "test")
        shutil.rmtree(self.repo / "tests")
        with self.assertRaisesRegex(ValueError, "ASKILLS-TASK-MISSING"):
            tasks.build_tasks(self.repo, "test")

    def test_runtime_empty_suite_fails(self):
        path = self.write("tests/test_empty.py", "# zero TestCases\n")
        result = subprocess.run([sys.executable, "-m", "tools.repoctl._checks", "suite", str(path.parent)],
                                cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertIn("ASKILLS-TEST-EMPTY", result.stderr)

    def test_generated_staleness_and_idempotence(self):
        for name in ("catalog.json", "README.md", "docs/architecture.md", "scripts/generate-catalog.py"):
            self.write(name, (ROOT / name).read_text(encoding="utf-8"))
        shutil.copytree(ROOT / ".github", self.repo / ".github")
        shutil.copytree(ROOT / "skills", self.repo / "skills")
        command = [sys.executable, str(self.repo / "scripts/generate-catalog.py"), "--repo", str(self.repo)]
        def run(*args):
            return subprocess.run([*command, *args], capture_output=True, check=False)
        result = run()
        self.assertEqual(0, result.returncode, result.stderr.decode())
        first = {p: p.read_bytes() for p in [self.repo / "README.md", self.repo / "docs/architecture.md"]}
        self.assertEqual(0, run().returncode)
        self.assertEqual(first, {p: p.read_bytes() for p in first})
        catalog = self.repo / "README.md"
        stale = catalog.read_text().replace("<!-- BEGIN GENERATED SKILL CATALOG -->", "<!-- BEGIN GENERATED SKILL CATALOG -->\nstale")
        catalog.write_text(stale)
        self.assertNotEqual(0, run("--check").returncode)
        self.assertEqual(stale, catalog.read_text())

    def test_review_malformed_manifest_frontmatter_and_children_cycle(self):
        self.docs_fixture()
        self.write("tools/repoctl/doc-manifest.json", json.dumps({"schema_version": 1, "pairs": [
            {"source": str(self.repo.parent / "external.md"), "translation": "external.en.md", "source_sha256": "x"}]}))
        self.assertIn("ASKILLS-DOC-MANIFEST", self.codes(docs.validate(self.repo)))
        broken = self.write("bad.md", "---\nstatus: active\n---not-a-terminator\nbody")
        with self.assertRaisesRegex(ValueError, "terminator"):
            docs.metadata(broken)
        self.plan(extra="children: [EP-TEST-002]\n")
        self.plan("EP-TEST-002", extra="children: [EP-TEST-001]\n", name="two")
        self.assertIn("ASKILLS-PLAN-CYCLE", self.codes(plans.validate(self.repo)))

    def test_skill_external_copy_closure_and_frontmatter(self):
        from scripts.validate_skills import validate
        shutil.copytree(ROOT / "skills/reader-first-editor", self.repo / "skills/reader-first-editor")
        shutil.copy(ROOT / "README.md", self.repo / "README.md")
        self.write("scripts/generate-catalog.py", "# present but not invoked")
        def run():
            return validate(self.repo, run_content=False, run_tests=False, run_catalog=False, run_links=False)
        self.assertEqual([], run())
        skill = self.repo / "skills/reader-first-editor/SKILL.md"
        skill.write_text(skill.read_text() + "\n[bad](../../tools/private.py)\n")
        self.assertTrue(any("external runtime reference" in error for error in run()))
        skill.write_text(skill.read_text().replace("name: reader-first-editor", "name: INVALID"))
        self.assertTrue(any("invalid name" in error for error in run()))
