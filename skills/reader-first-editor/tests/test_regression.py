from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from reader_first.investigation import (
    build_investigation_bundle,
    build_rule_proposal,
    validate_investigation_result,
)
from reader_first.regression import (
    RegressionError,
    apply_rule_patch,
    build_regression_plan,
    build_regression_report,
    build_rule_approval,
    parse_rule_patch,
    preview_rule_apply,
    validate_regression_run,
    validate_regression_plan,
    validate_regression_report,
    validate_report_against_runs,
    validate_rule_approval,
    validate_rule_proposal,
)
from reader_first.state import LocalCorpusStore
from test_investigation import create_record, valid_result
from validate_content import validate as validate_eval_content

SKILL_DIR = Path(__file__).resolve().parents[1]
CLI = SKILL_DIR / "scripts" / "corpus_tool.py"


def persisted_candidate_evals() -> list[dict]:
    cases: list[dict] = []
    for category_cases in candidate_evals().values():
        for candidate in category_cases:
            case = deepcopy(candidate)
            case["must_not_claim"] = case.pop("must_not")
            cases.append(case)
    return cases


def rule_patch(
    *,
    cases: list[dict] | None = None,
    metadata: dict | None = None,
) -> str:
    suite: dict[str, object] = {
        "suite": "regression-test-rule",
        "cases": persisted_candidate_evals() if cases is None else cases,
    }
    if metadata is not None:
        suite["metadata"] = metadata
    eval_lines = json.dumps(suite, ensure_ascii=False, indent=2).splitlines()
    added_eval = "\n".join(f"+{line}" for line in eval_lines)
    return f"""diff --git a/skills/reader-first-editor/references/core/regression-test-rule.md b/skills/reader-first-editor/references/core/regression-test-rule.md
new file mode 100644
--- /dev/null
+++ b/skills/reader-first-editor/references/core/regression-test-rule.md
@@ -0,0 +1,3 @@
+# 限定rule
+
+head predictabilityが低いtechnical READMEだけを観察する。
diff --git a/skills/reader-first-editor/evals/regression-test-rule.yaml b/skills/reader-first-editor/evals/regression-test-rule.yaml
new file mode 100644
--- /dev/null
+++ b/skills/reader-first-editor/evals/regression-test-rule.yaml
@@ -0,0 +1,{len(eval_lines)} @@
{added_eval}
"""


def provider_matrix(repeats: int = 2) -> dict:
    return {
        "providers": [
            {
                "provider": "codex",
                "model": "test-codex-model",
                "model_version": "2026-08-30",
                "host_version": "codex-test-host",
                "repeats": repeats,
            },
            {
                "provider": "github-copilot",
                "model": "test-copilot-model",
                "model_version": "2026-08-30",
                "host_version": "copilot-test-host",
                "repeats": repeats,
            },
        ]
    }


def candidate_evals() -> dict:
    def case(case_id: str, expected_behavior: str) -> dict:
        return {
            "id": case_id,
            "mode": "review" if expected_behavior == "no-change" else "revise-safe",
            "language": "ja",
            "input": f"synthetic input for {case_id}",
            "expected": f"synthetic expectation for {case_id}",
            "expected_behavior": expected_behavior,
            "must_preserve": ["technical literal"],
            "must_not": ["invented condition"],
        }

    return {
        "positive": [case("eval-positive-1", "change")],
        "negative": [case("eval-negative-1", "no-change")],
        "boundary": [case("eval-boundary-1", "context-dependent")],
    }


def passing_run(plan: dict, provider: dict, repeat: int) -> dict:
    def passing_case(case: dict) -> dict:
        result = {
            "id": case["id"],
            "status": "pass",
            "expected_behavior_match": True,
            "dimensions": {
                "semantic_preservation": "pass",
                "unnecessary_revision": "pass",
                "literal": "pass",
                "register": "pass",
            },
            "notes": "",
        }
        for expected_key, observed_key in (
            ("expected_risks", "observed_risks"),
            ("expected_statuses", "observed_statuses"),
            ("expected_evidence_types", "observed_evidence_types"),
        ):
            if expected_key in case:
                result[observed_key] = deepcopy(case[expected_key])
        return result

    return {
        "id": "draft",
        "schema_version": plan["schema_version"],
        "plan_id": plan["id"],
        "provider": provider["provider"],
        "model": provider["model"],
        "model_version": provider["model_version"],
        "host_version": provider["host_version"],
        "repeat_index": repeat,
        "created_at": f"2026-08-30T12:00:0{repeat}Z",
        "cases": [passing_case(case) for case in plan["cases"]],
    }


class RegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = LocalCorpusStore(
            self.root / "data",
            skill_dir=self.root / "installed-skill",
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        support_a = create_record(
            self.store,
            1,
            embedded_text="regression planへcopyしてはいけないlocal corpus text",
        )
        support_b = create_record(self.store, 2)
        control = create_record(self.store, 3, state="rejected", quality="clean")
        self.promoted = self.store.promote_local(
            support_a["id"],
            actor="reviewer",
            reason="regression corpus",
        )
        bundle = build_investigation_bundle(
            self.store,
            hypothesis="予測しにくいpredicate配置は再読を増やす",
            support_record_ids=[support_a["id"], support_b["id"]],
            control_record_ids=[control["id"]],
            purposes=["初読理解"],
            actor="reviewer",
            reason="regression fixture",
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        investigation, blockers = validate_investigation_result(valid_result(bundle), bundle)
        self.assertEqual(blockers, [])
        self.bundle = bundle
        self.investigation = investigation
        self.proposal = build_rule_proposal(
            investigation,
            bundle,
            rule_patch(),
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        self.plan = build_regression_plan(
            self.proposal,
            self.store,
            eval_dir=SKILL_DIR / "evals",
            provider_matrix=provider_matrix(),
            candidate_evals=candidate_evals(),
            corpus_record_ids=[self.promoted["id"]],
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        self.runs = [
            validate_regression_run(passing_run(self.plan, provider, repeat), self.plan)
            for provider in self.plan["providers"]
            for repeat in range(1, provider["repeats"] + 1)
        ]

    def test_plan_covers_all_eval_sources_without_copying_corpus_text(self) -> None:
        categories = {case["category"] for case in self.plan["cases"]}
        self.assertEqual(categories, {"existing", "corpus", "positive", "negative", "boundary"})
        existing_source_count = sum(
            len(json.loads(path.read_text(encoding="utf-8"))["cases"])
            for path in (SKILL_DIR / "evals").glob("*.yaml")
        )
        self.assertEqual(
            sum(case["category"] == "existing" for case in self.plan["cases"]),
            existing_source_count,
        )
        serialized = json.dumps(self.plan, ensure_ascii=False)
        self.assertNotIn("regression planへcopyしてはいけないlocal corpus text", serialized)
        corpus_case = next(case for case in self.plan["cases"] if case["category"] == "corpus")
        self.assertEqual(corpus_case["input"]["kind"], "record-reference")
        self.assertIsNone(corpus_case["input"]["value"])

    def test_plan_preserves_bundled_structured_oracles(self) -> None:
        self.assertEqual(self.plan["schema_version"], 2)
        by_id = {case["id"]: case for case in self.plan["cases"]}
        ambiguous = by_id[
            "bundled:prose-pacing:natural-sounding-ambiguous-action-is-finding"
        ]
        self.assertEqual(ambiguous["expected_risks"], ["RR-12"])

        contradicted = by_id[
            "bundled:repository-grounded-review:"
            "natural-prose-still-contradicts-config-default"
        ]
        self.assertEqual(contradicted["expected_statuses"], ["CONTRADICTED"])
        self.assertEqual(contradicted["expected_evidence_types"], ["DOC↔CONFIG"])

    def test_plan_preserves_explicit_bundled_no_change_behavior(self) -> None:
        expected_ids = {
            "bundled:prose-pacing:clear-ai-associated-phrase-is-no-change",
            "bundled:prose-pacing:repeated-safety-steps-remain-predictable",
            "bundled:prose-pacing:repeated-technical-literal-is-not-varied",
        }
        no_change_ids = {
            case["id"]
            for case in self.plan["cases"]
            if case["expected_behavior"] == "no-change"
        }
        self.assertTrue(expected_ids <= no_change_ids)

    def test_plan_rejects_invalid_expected_behavior(self) -> None:
        plan = deepcopy(self.plan)
        plan["cases"][0]["expected_behavior"] = "always-change"
        with self.assertRaisesRegex(RegressionError, "expected_behavior"):
            validate_regression_plan(plan)

    def test_plan_rejects_non_string_expected_behavior(self) -> None:
        plan = deepcopy(self.plan)
        plan["cases"][0]["expected_behavior"] = []
        with self.assertRaisesRegex(RegressionError, "expected_behavior"):
            validate_regression_plan(plan)

    def test_content_validation_reports_non_string_expected_behavior(self) -> None:
        eval_dir = self.root / "invalid-evals"
        eval_dir.mkdir()
        (eval_dir / "invalid.yaml").write_text(
            json.dumps(
                {
                    "suite": "invalid-behavior",
                    "cases": [
                        {
                            "id": "list-behavior",
                            "mode": "review",
                            "language": "ja",
                            "input": "入力",
                            "expected": "期待",
                            "expected_behavior": [],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        errors = validate_eval_content(eval_dir)
        self.assertTrue(any("invalid expected_behavior []" in error for error in errors))

    def test_plan_rejects_invalid_structured_oracle_type(self) -> None:
        plan = deepcopy(self.plan)
        bundled = next(case for case in plan["cases"] if case["source"] == "bundled")
        bundled["expected_risks"] = "RR-12"
        with self.assertRaisesRegex(RegressionError, "expected_risks"):
            validate_regression_plan(plan)

    def test_plan_rejects_repository_review_with_empty_oracles(self) -> None:
        plan = deepcopy(self.plan)
        bundled = next(
            case for case in plan["cases"] if case["mode"] == "repository-review"
        )
        bundled["expected_statuses"] = []
        bundled["expected_evidence_types"] = []
        with self.assertRaisesRegex(RegressionError, "requires expected_statuses"):
            validate_regression_plan(plan)

    def test_plan_rejects_unsupported_without_evidence_gap(self) -> None:
        plan = deepcopy(self.plan)
        bundled = next(
            case for case in plan["cases"] if case["mode"] == "repository-review"
        )
        bundled["expected_statuses"] = ["UNSUPPORTED"]
        bundled["expected_evidence_types"] = ["DOC↔CODE"]
        with self.assertRaisesRegex(RegressionError, "UNSUPPORTED requires EVIDENCE-GAP"):
            validate_regression_plan(plan)

    def test_run_requires_planned_structured_oracles(self) -> None:
        run = passing_run(self.plan, self.plan["providers"][0], 1)
        case = next(
            item
            for item in run["cases"]
            if item.get("observed_statuses") == ["CONTRADICTED"]
        )
        case["observed_statuses"] = ["VERIFIED"]
        with self.assertRaisesRegex(RegressionError, "期待値と完全一致"):
            validate_regression_run(run, self.plan)

    def test_passing_run_rejects_additional_structured_oracles(self) -> None:
        run = passing_run(self.plan, self.plan["providers"][0], 1)
        case = next(
            item
            for item in run["cases"]
            if item.get("observed_statuses") == ["CONTRADICTED"]
        )
        self.assertEqual(case["observed_statuses"], ["CONTRADICTED"])
        case["observed_statuses"].append("VERIFIED")

        with self.assertRaisesRegex(RegressionError, "期待値と完全一致"):
            validate_regression_run(run, self.plan)

    def test_failed_run_preserves_actual_structured_oracles(self) -> None:
        run = passing_run(self.plan, self.plan["providers"][0], 1)
        case = next(item for item in run["cases"] if "observed_statuses" in item)
        case["status"] = "fail"
        case["observed_statuses"] = ["VERIFIED"]

        validated = validate_regression_run(run, self.plan)
        self.assertEqual(case["observed_statuses"], ["VERIFIED"])
        self.assertEqual(validated["cases"], run["cases"])

    def test_unsupported_or_error_run_may_omit_structured_observations(self) -> None:
        for status in ("unsupported", "error"):
            with self.subTest(status=status):
                run = passing_run(self.plan, self.plan["providers"][0], 1)
                case = next(item for item in run["cases"] if "observed_statuses" in item)
                case["status"] = status
                case.pop("observed_statuses")

                validated = validate_regression_run(run, self.plan)
                self.assertNotIn("observed_statuses", validated["cases"][run["cases"].index(case)])

    def test_complete_repeated_runs_pass_all_gates(self) -> None:
        report = build_regression_report(
            self.plan,
            self.runs,
            clock=lambda: "2026-08-30T13:00:00Z",
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(set(report["gates"].values()), {"pass"})
        self.assertEqual(report["metrics"]["no_change_accuracy"], 1.0)
        self.assertEqual(validate_report_against_runs(report, self.plan, self.runs), report)

    def test_all_regression_artifacts_reject_boolean_schema_version(self) -> None:
        report = build_regression_report(
            self.plan,
            self.runs,
            clock=lambda: "2026-08-30T13:00:00Z",
        )
        approval = build_rule_approval(
            self.proposal,
            self.plan,
            report,
            reviewer="human-reviewer",
            reason="all gates passed",
            clock=lambda: "2026-08-30T14:00:00Z",
        )
        artifacts = (
            ("proposal", validate_rule_proposal, self.proposal),
            ("plan", validate_regression_plan, self.plan),
            ("report", validate_regression_report, report),
            ("approval", validate_rule_approval, approval),
        )
        for label, validator, artifact in artifacts:
            with self.subTest(label=label):
                invalid = deepcopy(artifact)
                invalid["schema_version"] = True
                with self.assertRaisesRegex(RegressionError, "schema"):
                    validator(invalid)

        invalid_run = passing_run(self.plan, self.plan["providers"][0], 1)
        invalid_run["schema_version"] = True
        with self.assertRaisesRegex(RegressionError, "schema"):
            validate_regression_run(invalid_run, self.plan)

    def test_legacy_plan_and_run_without_structured_oracles_remain_readable(self) -> None:
        plan = deepcopy(self.plan)
        plan["schema_version"] = 1
        for case in plan["cases"]:
            for expected_key in (
                "expected_risks",
                "expected_statuses",
                "expected_evidence_types",
            ):
                case.pop(expected_key, None)
        body = {
            key: plan[key]
            for key in (
                "schema_version",
                "proposal_id",
                "diff_hash",
                "providers",
                "cases",
                "requirements",
            )
        }
        plan["id"] = "rfrp-" + hashlib.sha256(
            json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:20]

        validated_plan = validate_regression_plan(plan)
        run = passing_run(validated_plan, validated_plan["providers"][0], 1)
        validated_run = validate_regression_run(run, validated_plan)
        self.assertEqual(validated_run["schema_version"], 1)

        report = build_regression_report(validated_plan, [validated_run])
        with self.assertRaisesRegex(RegressionError, "legacy planは再生成"):
            build_rule_approval(
                self.proposal,
                validated_plan,
                report,
                reviewer="human-reviewer",
                reason="legacy regression passed",
            )

    def test_run_schema_version_must_match_plan(self) -> None:
        run = passing_run(self.plan, self.plan["providers"][0], 1)
        run["schema_version"] = 1
        with self.assertRaisesRegex(RegressionError, "schema"):
            validate_regression_run(run, self.plan)

    def test_proposal_rejects_eval_id_reused_across_categories(self) -> None:
        proposal = deepcopy(self.proposal)
        proposal["evals"]["negative"] = deepcopy(proposal["evals"]["positive"])
        with self.assertRaisesRegex(RegressionError, "category間で重複"):
            validate_rule_proposal(proposal)

    def test_missing_repeat_fails_report(self) -> None:
        report = build_regression_report(self.plan, self.runs[:-1])
        self.assertEqual(report["status"], "fail")
        self.assertEqual(report["gates"]["repeat_completeness"], "fail")
        self.assertTrue(any("required run" in blocker for blocker in report["blockers"]))

    def test_semantic_regression_blocks_report(self) -> None:
        runs = deepcopy(self.runs)
        runs[0]["cases"][0]["dimensions"]["semantic_preservation"] = "fail"
        runs[0] = validate_regression_run(runs[0], self.plan)
        report = build_regression_report(self.plan, runs)
        self.assertEqual(report["gates"]["semantic_preservation"], "fail")
        self.assertEqual(report["status"], "fail")

    def test_unsupported_is_reported_separately_and_fails(self) -> None:
        runs = deepcopy(self.runs)
        runs[0]["cases"][0]["status"] = "unsupported"
        runs[0] = validate_regression_run(runs[0], self.plan)
        report = build_regression_report(self.plan, runs)
        self.assertEqual(report["metrics"]["unsupported"], 1)
        self.assertEqual(report["metrics"]["failed"], 0)
        self.assertEqual(report["status"], "fail")

    def test_no_change_mismatch_fails_accuracy_gate(self) -> None:
        runs = deepcopy(self.runs)
        no_change_id = next(
            case["id"] for case in self.plan["cases"] if case["expected_behavior"] == "no-change"
        )
        case = next(item for item in runs[0]["cases"] if item["id"] == no_change_id)
        case["expected_behavior_match"] = False
        runs[0] = validate_regression_run(runs[0], self.plan)
        report = build_regression_report(self.plan, runs)
        self.assertEqual(report["gates"]["no_change_accuracy"], "fail")
        self.assertLess(report["metrics"]["no_change_accuracy"], 1.0)

    def test_run_metadata_must_match_plan(self) -> None:
        run = passing_run(self.plan, self.plan["providers"][0], 1)
        run["model_version"] = "different"
        with self.assertRaisesRegex(RegressionError, "provider matrix"):
            validate_regression_run(run, self.plan)

    def test_human_approval_requires_passing_exact_report(self) -> None:
        failed = build_regression_report(self.plan, self.runs[:-1])
        with self.assertRaisesRegex(RegressionError, "通過"):
            build_rule_approval(
                self.proposal,
                self.plan,
                failed,
                reviewer="human-reviewer",
                reason="reviewed",
            )
        passed = build_regression_report(self.plan, self.runs)
        approval = build_rule_approval(
            self.proposal,
            self.plan,
            passed,
            reviewer="human-reviewer",
            reason="exact diff and report reviewed",
            clock=lambda: "2026-08-30T14:00:00Z",
        )
        self.assertTrue(approval["approved"])
        self.assertEqual(approval["diff_hash"], passed["diff_hash"])

    def test_approval_records_caller_supplied_reviewer_without_authentication(self) -> None:
        passed = build_regression_report(self.plan, self.runs)
        approval = build_rule_approval(
            self.proposal,
            self.plan,
            passed,
            reviewer="automation-bot",
            reason="caller supplied attestation",
        )
        self.assertTrue(approval["approved"])
        self.assertEqual(approval["reviewer"], "automation-bot")

    def test_patch_parser_requires_rule_and_eval_targets(self) -> None:
        self.assertEqual(len(parse_rule_patch(self.proposal["rule_diff"])), 2)
        unsafe = self.proposal["rule_diff"].replace(
            "skills/reader-first-editor/references/core/regression-test-rule.md",
            "../outside.md",
        )
        with self.assertRaises(RegressionError):
            parse_rule_patch(unsafe)

    def _apply_artifacts_for_patch(self, patch: str) -> tuple[dict, dict, dict, dict]:
        proposal = build_rule_proposal(self.investigation, self.bundle, patch)
        plan = build_regression_plan(
            proposal,
            self.store,
            eval_dir=SKILL_DIR / "evals",
            provider_matrix=provider_matrix(repeats=1),
            candidate_evals=candidate_evals(),
            corpus_record_ids=[self.promoted["id"]],
        )
        runs = [
            validate_regression_run(passing_run(plan, provider, 1), plan)
            for provider in plan["providers"]
        ]
        report = build_regression_report(plan, runs)
        approval = build_rule_approval(
            proposal,
            plan,
            report,
            reviewer="reviewer-attestation",
            reason="exact diff reviewed outside the tool",
        )
        return proposal, plan, report, approval

    def test_patch_rejects_eval_id_not_declared_by_proposal(self) -> None:
        cases = persisted_candidate_evals()
        extra = deepcopy(cases[0])
        extra["id"] = "eval-extra"
        patch = rule_patch(cases=[*cases, extra])
        proposal, plan, report, approval = self._apply_artifacts_for_patch(patch)
        with self.assertRaisesRegex(RegressionError, "proposalにないeval ID"):
            preview_rule_apply(
                proposal,
                plan,
                report,
                approval,
                repository_root=self._test_repository(),
            )

    def test_patch_rejects_missing_proposal_eval_id(self) -> None:
        cases = [
            case
            for case in persisted_candidate_evals()
            if case["id"] != "eval-boundary-1"
        ]
        proposal, plan, report, approval = self._apply_artifacts_for_patch(
            rule_patch(cases=cases)
        )
        with self.assertRaisesRegex(RegressionError, "proposal eval IDがありません"):
            preview_rule_apply(
                proposal,
                plan,
                report,
                approval,
                repository_root=self._test_repository(),
            )

    def test_patch_rejects_ids_present_only_in_metadata(self) -> None:
        metadata = {
            "ids": ["eval-positive-1", "eval-negative-1", "eval-boundary-1"]
        }
        proposal, plan, report, approval = self._apply_artifacts_for_patch(
            rule_patch(cases=[], metadata=metadata)
        )
        with self.assertRaisesRegex(RegressionError, "proposal eval IDがありません"):
            preview_rule_apply(
                proposal,
                plan,
                report,
                approval,
                repository_root=self._test_repository(),
            )

    def test_patch_rejects_proposal_eval_content_mismatch(self) -> None:
        cases = persisted_candidate_evals()
        cases[0]["expected"] = "different expectation"
        proposal, plan, report, approval = self._apply_artifacts_for_patch(
            rule_patch(cases=cases)
        )
        with self.assertRaisesRegex(RegressionError, "caseの内容が一致しません"):
            preview_rule_apply(
                proposal,
                plan,
                report,
                approval,
                repository_root=self._test_repository(),
            )

    def _test_repository(self, *, validators_pass: bool = True) -> Path:
        repository = self.root / ("apply-pass" if validators_pass else "apply-fail")
        (repository / "skills/reader-first-editor/scripts").mkdir(parents=True)
        (repository / "scripts").mkdir()
        validator = repository / "skills/reader-first-editor/scripts/validate_content.py"
        validator.write_text(
            "raise SystemExit(0)\n" if validators_pass else "raise SystemExit(1)\n",
            encoding="utf-8",
        )
        validate_skills = repository / "scripts/validate-skills.sh"
        validate_skills.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        validate_skills.chmod(0o755)
        subprocess.run(["git", "init", "--quiet"], cwd=repository, check=True)
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Regression Test",
                "-c",
                "user.email=test@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "fixture",
            ],
            cwd=repository,
            check=True,
        )
        return repository

    def test_explicit_apply_changes_only_approved_targets(self) -> None:
        report = build_regression_report(self.plan, self.runs)
        approval = build_rule_approval(
            self.proposal,
            self.plan,
            report,
            reviewer="human-reviewer",
            reason="approved",
        )
        repository = self._test_repository()
        preview = preview_rule_apply(
            self.proposal,
            self.plan,
            report,
            approval,
            repository_root=repository,
        )
        self.assertFalse(preview["will_commit"])
        self.assertFalse(preview["will_push"])
        self.assertEqual(preview["reviewer_attestation"], "human-reviewer")
        self.assertNotIn("human_reviewer", preview)
        applied = apply_rule_patch(
            self.proposal,
            self.plan,
            report,
            approval,
            repository_root=repository,
        )
        self.assertTrue(applied["validated"])
        for target in preview["targets"]:
            self.assertTrue((repository / target).is_file())
        with self.assertRaises(RegressionError):
            preview_rule_apply(
                self.proposal,
                self.plan,
                report,
                approval,
                repository_root=repository,
            )

    def test_failed_post_apply_validation_rolls_back(self) -> None:
        report = build_regression_report(self.plan, self.runs)
        approval = build_rule_approval(
            self.proposal,
            self.plan,
            report,
            reviewer="human-reviewer",
            reason="approved",
        )
        repository = self._test_repository(validators_pass=False)
        targets = parse_rule_patch(self.proposal["rule_diff"])
        with self.assertRaisesRegex(RegressionError, "rollback"):
            apply_rule_patch(
                self.proposal,
                self.plan,
                report,
                approval,
                repository_root=repository,
            )
        self.assertTrue(all(not (repository / target).exists() for target in targets))
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repository,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(status.stdout, "")


class RegressionCliTests(unittest.TestCase):
    def test_phase6_commands_are_exposed(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "rules", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "regression-plan",
            "regression-ingest",
            "regression-report",
            "approve",
            "apply",
        ):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
