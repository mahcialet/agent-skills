from __future__ import annotations

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
    InvestigationError,
    build_investigation_bundle,
    build_rule_proposal,
    validate_bundle_against_store,
    validate_investigation_result,
)
from reader_first.state import LocalCorpusStore
from test_corpus_state import sample_record

SKILL_DIR = Path(__file__).resolve().parents[1]
CLI = SKILL_DIR / "scripts" / "corpus_tool.py"


def create_record(
    store: LocalCorpusStore,
    index: int,
    *,
    state: str = "accepted",
    quality: str = "problematic",
    embedded_text: str | None = None,
) -> dict:
    record = sample_record()
    record["source"]["span"] = f"section:{index}"
    record["source"]["correlation_group"] = f"source-group-{index}"
    record["source"]["repository"] = f"example/repository-{index}"
    record["quality_class"] = quality
    if embedded_text is not None:
        record["text"] = {
            "storage": "embedded",
            "content_hash": f"local-hash-{index}",
            "content": embedded_text,
        }
    created = store.create_candidate(record, actor="collector", reason="fixture")
    if state == "rejected":
        return store.transition(
            created["id"],
            "rejected",
            actor="reviewer",
            reason="negative control",
        )
    store.transition(
        created["id"],
        "annotated",
        actor="reviewer",
        reason="annotation confirmed",
    )
    return store.transition(
        created["id"],
        "accepted",
        actor="reviewer",
        reason="accepted fixture",
    )


def valid_result(bundle: dict) -> dict:
    support_ids = bundle["selection"]["support_record_ids"]
    control_ids = bundle["selection"]["control_record_ids"]
    return {
        "id": "draft",
        "bundle_id": bundle["id"],
        "schema_version": 1,
        "created_at": "2026-08-30T12:00:00Z",
        "producer": "adversarial-test-agent",
        "hypothesis": bundle["hypothesis"],
        "scope": deepcopy(bundle["scope"]),
        "record_ids": [*support_ids, *control_ids],
        "source_correlation": deepcopy(bundle["source_analysis"]["correlation_groups"]),
        "support": {
            "independent_sources": 2,
            "examples": support_ids,
            "mechanism": "head predictabilityが低い場合だけ再読が増える",
            "confounders": ["文長だけでは説明できない"],
        },
        "counterexamples": {
            "searched": True,
            "explained": control_ids,
            "unexplained": [],
        },
        "boundary_pairs": [
            {
                "fires": support_ids[0],
                "does_not_fire": control_ids[0],
                "distinguishing_condition": "主要predicateを早期に予測できるか",
                "scope_effect": "technical-readmeに限定する",
            }
        ],
        "existing_rule_analysis": "既存RR labelだけではこの限定条件を表現していない",
        "semantic_risks": ["条件scopeを広げると不要な分割が増える"],
        "provenance_reviewed": True,
        "fixed_threshold_only": False,
        "frequency_only": False,
        "duplicate_rule": False,
        "proposed_evals": {
            "positive": ["eval-positive-1"],
            "negative": ["eval-negative-1"],
            "boundary": ["eval-boundary-1"],
        },
        "decision": {
            "status": "PROMOTE",
            "reason": "反例を説明できるscopeまで縮小した",
        },
    }


class InvestigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"
        self.store = LocalCorpusStore(
            self.data_dir,
            skill_dir=Path(self.temp.name) / "installed-skill",
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        self.support_a = create_record(
            self.store,
            1,
            embedded_text="bundleへコピーしてはいけないlocal raw text",
        )
        self.support_b = create_record(self.store, 2)
        self.control = create_record(
            self.store,
            3,
            state="rejected",
            quality="clean",
        )

    def bundle(self, *, controls: bool = True, supports: int = 2) -> dict:
        support_ids = [self.support_a["id"], self.support_b["id"]][:supports]
        return build_investigation_bundle(
            self.store,
            hypothesis="予測しにくいpredicate配置は再読を増やす",
            support_record_ids=support_ids,
            control_record_ids=[self.control["id"]] if controls else [],
            purposes=["初読理解"],
            actor="reviewer",
            reason="rule investigation",
            clock=lambda: "2026-08-30T12:00:00Z",
        )

    def test_bundle_is_raw_text_free_and_counterexample_first(self) -> None:
        bundle = self.bundle()
        serialized = json.dumps(bundle, ensure_ascii=False)
        self.assertNotIn("bundleへコピーしてはいけないlocal raw text", serialized)
        self.assertTrue(all(not item["text_reference"]["raw_text_copied"] for item in bundle["records"]))
        self.assertEqual(bundle["roles"][0]["name"], "Counterexample Hunter")
        self.assertEqual(bundle["readiness"], {"default_decision": "HOLD", "blockers": []})
        self.assertTrue(bundle["output_contract"]["promote_is_not_apply"])

    def test_bundle_reports_missing_independent_support_and_control(self) -> None:
        bundle = self.bundle(controls=False, supports=1)
        self.assertEqual(bundle["readiness"]["default_decision"], "NEEDS_MORE_EVIDENCE")
        self.assertEqual(len(bundle["readiness"]["blockers"]), 3)

    def test_candidate_cannot_be_used_as_support(self) -> None:
        candidate = sample_record()
        candidate["source"]["span"] = "candidate-only"
        created = self.store.create_candidate(candidate, actor="collector", reason="fixture")
        with self.assertRaisesRegex(InvestigationError, "accepted"):
            build_investigation_bundle(
                self.store,
                hypothesis="unsafe direct promotion",
                support_record_ids=[created["id"]],
                control_record_ids=[],
                purposes=["test"],
                actor="reviewer",
                reason="fixture",
            )

    def test_bundle_tampering_is_detected_against_store(self) -> None:
        bundle = self.bundle()
        bundle["records"][0]["source"]["correlation_group"] = "forged"
        with self.assertRaisesRegex(InvestigationError, "local corpus"):
            validate_bundle_against_store(bundle, self.store)

    def test_valid_promote_result_passes_gate_and_gets_deterministic_id(self) -> None:
        bundle = self.bundle()
        result, blockers = validate_investigation_result(valid_result(bundle), bundle)
        second, second_blockers = validate_investigation_result(valid_result(bundle), bundle)
        self.assertEqual(blockers, [])
        self.assertEqual(second_blockers, [])
        self.assertEqual(result["id"], second["id"])
        self.assertRegex(result["id"], r"^rfi-[0-9a-f]{20}$")

    def test_unexplained_counterexample_blocks_promote(self) -> None:
        bundle = self.bundle()
        result = valid_result(bundle)
        result["counterexamples"]["unexplained"] = [self.control["id"]]
        _, blockers = validate_investigation_result(result, bundle)
        self.assertIn("未説明のcounterexampleが残っている", blockers)

    def test_selected_control_must_be_analyzed(self) -> None:
        bundle = self.bundle()
        result = valid_result(bundle)
        result["counterexamples"]["explained"] = []
        result["boundary_pairs"][0]["does_not_fire"] = "synthetic-boundary"
        _, blockers = validate_investigation_result(result, bundle)
        self.assertTrue(any("未分析のcontrol" in blocker for blocker in blockers))

    def test_positive_only_result_cannot_promote(self) -> None:
        ready_bundle = self.bundle()
        bundle = self.bundle(controls=False)
        result = valid_result(ready_bundle)
        result["bundle_id"] = bundle["id"]
        result["record_ids"] = bundle["selection"]["support_record_ids"]
        result["source_correlation"] = bundle["source_analysis"]["correlation_groups"]
        result["counterexamples"]["explained"] = []
        result["boundary_pairs"][0]["does_not_fire"] = "synthetic-negative"
        _, blockers = validate_investigation_result(result, bundle)
        self.assertIn("counterexample／negative control候補が未選択", blockers)

    def test_threshold_frequency_duplicate_and_provenance_gates(self) -> None:
        bundle = self.bundle()
        result = valid_result(bundle)
        result["provenance_reviewed"] = False
        result["fixed_threshold_only"] = True
        result["frequency_only"] = True
        result["duplicate_rule"] = True
        _, blockers = validate_investigation_result(result, bundle)
        self.assertEqual(len(blockers), 4)

    def test_source_correlation_cannot_be_forged(self) -> None:
        bundle = self.bundle()
        result = valid_result(bundle)
        result["support"]["independent_sources"] = 99
        with self.assertRaisesRegex(InvestigationError, "provenance"):
            validate_investigation_result(result, bundle)

    def test_proposal_is_unapproved_and_has_not_run_regressions(self) -> None:
        bundle = self.bundle()
        result, _ = validate_investigation_result(valid_result(bundle), bundle)
        proposal = build_rule_proposal(
            result,
            bundle,
            "--- a/references/rule.md\n+++ b/references/rule.md\n+限定rule\n",
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        self.assertFalse(proposal["human_approval"]["approved"])
        self.assertEqual(set(proposal["regressions"].values()), {"not-run"})
        self.assertRegex(proposal["id"], r"^rfp-[0-9a-f]{20}$")

    def test_hold_result_cannot_create_proposal(self) -> None:
        bundle = self.bundle()
        result = valid_result(bundle)
        result["decision"] = {"status": "HOLD", "reason": "反例が残る"}
        validated, _ = validate_investigation_result(result, bundle)
        with self.assertRaisesRegex(InvestigationError, "PROMOTE"):
            build_rule_proposal(validated, bundle, "rule diff")


class InvestigationCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data_dir = self.root / "data"
        store = LocalCorpusStore(
            self.data_dir,
            skill_dir=self.root / "installed-skill",
            clock=lambda: "2026-08-30T12:00:00Z",
        )
        self.support_a = create_record(store, 1)
        self.support_b = create_record(store, 2)
        self.control = create_record(store, 3, state="rejected", quality="clean")

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), "--data-dir", str(self.data_dir), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def create_bundle(self) -> dict:
        result = self.run_cli(
            "rules",
            "bundle",
            "--hypothesis",
            "予測しにくいpredicate配置は再読を増やす",
            "--support-record",
            self.support_a["id"],
            "--support-record",
            self.support_b["id"],
            "--control-record",
            self.control["id"],
            "--purpose",
            "初読理解",
            "--actor",
            "reviewer",
            "--reason",
            "CLI fixture",
            "--apply",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_bundle_preview_does_not_write(self) -> None:
        before = {path.relative_to(self.data_dir) for path in self.data_dir.rglob("*")}
        result = self.run_cli(
            "rules",
            "bundle",
            "--hypothesis",
            "予測しにくいpredicate配置は再読を増やす",
            "--support-record",
            self.support_a["id"],
            "--control-record",
            self.control["id"],
            "--purpose",
            "初読理解",
            "--actor",
            "reviewer",
            "--reason",
            "preview",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["dry_run"])
        after = {path.relative_to(self.data_dir) for path in self.data_dir.rglob("*")}
        self.assertEqual(after, before)

    def test_full_local_artifact_lifecycle_does_not_modify_core(self) -> None:
        created_bundle = self.create_bundle()
        bundle_id = created_bundle["created"]
        bundle = json.loads(Path(created_bundle["path"]).read_text(encoding="utf-8"))
        result_path = self.root / "result.json"
        result_path.write_text(json.dumps(valid_result(bundle), ensure_ascii=False), encoding="utf-8")
        validated = self.run_cli(
            "rules",
            "validate-investigation",
            "--bundle-id",
            bundle_id,
            "--result",
            str(result_path),
            "--apply",
        )
        self.assertEqual(validated.returncode, 0, validated.stderr)
        result_id = json.loads(validated.stdout)["created"]
        diff_path = self.root / "rule.diff"
        diff_path.write_text("--- a/rule.md\n+++ b/rule.md\n+限定rule\n", encoding="utf-8")
        proposal = self.run_cli(
            "rules",
            "propose",
            "--bundle-id",
            bundle_id,
            "--result-id",
            result_id,
            "--rule-diff",
            str(diff_path),
            "--apply",
        )
        self.assertEqual(proposal.returncode, 0, proposal.stderr)
        output = json.loads(proposal.stdout)
        self.assertFalse(output["human_approval"])
        self.assertEqual(output["modified_core"], [])
        self.assertTrue(Path(output["path"]).is_file())

    def test_cli_downgrades_invalid_promote_to_hold_without_write(self) -> None:
        created_bundle = self.create_bundle()
        bundle_id = created_bundle["created"]
        bundle = json.loads(Path(created_bundle["path"]).read_text(encoding="utf-8"))
        result = valid_result(bundle)
        result["counterexamples"]["unexplained"] = [self.control["id"]]
        result_path = self.root / "blocked-result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        checked = self.run_cli(
            "rules",
            "validate-investigation",
            "--bundle-id",
            bundle_id,
            "--result",
            str(result_path),
            "--apply",
        )
        self.assertEqual(checked.returncode, 1)
        output = json.loads(checked.stdout)
        self.assertEqual(output["effective_status"], "HOLD")
        self.assertEqual(list((self.data_dir / "investigations" / bundle_id / "results").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
