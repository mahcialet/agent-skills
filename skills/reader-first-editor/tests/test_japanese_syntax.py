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

from reader_first.japanese_syntax import (
    BackendUnavailable,
    GinzaBackend,
    SyntaxAnalysisError,
    analyze_japanese,
    build_syntax_ab_report,
    validate_syntax_ab_report,
    validate_syntax_signal,
)

SKILL_DIR = Path(__file__).resolve().parents[1]
CLI = SKILL_DIR / "scripts" / "analyze_ja.py"
FIXTURE = SKILL_DIR / "tests" / "fixtures" / "syntax" / "ginza-5.2.0-ja-ginza-5.2.0.json"


class FakeMorph:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


class FakeToken:
    def __init__(
        self,
        index: int,
        text: str,
        lemma: str,
        dep: str,
        pos: str,
        head_index: int,
        morph: str = "",
    ) -> None:
        self.i = index
        self.text = text
        self.lemma_ = lemma
        self.dep_ = dep
        self.pos_ = pos
        self.head_index = head_index
        self.morph = FakeMorph(morph)
        self.head: FakeToken = self
        self.children: list[FakeToken] = []


class FakeSentence:
    def __init__(self, start: int, root: FakeToken) -> None:
        self.start = start
        self.root = root


class FakeDoc:
    def __init__(self) -> None:
        specs = [
            (0, "その", "其の", "det", "DET", 1, ""),
            (1, "条件", "条件", "obj", "NOUN", 4, ""),
            (2, "の", "の", "case", "ADP", 1, ""),
            (3, "場合", "場合", "obl", "NOUN", 4, ""),
            (4, "続行", "続行", "ROOT", "VERB", 4, ""),
            (5, "し", "する", "aux", "AUX", 4, ""),
            (6, "ない", "ない", "aux", "AUX", 4, "Polarity=Neg"),
            (7, "。", "。", "punct", "PUNCT", 4, ""),
        ]
        self.tokens = [FakeToken(*spec) for spec in specs]
        for token in self.tokens:
            token.head = self.tokens[token.head_index]
            if token.head is not token:
                token.head.children.append(token)
        self.sents = [FakeSentence(0, self.tokens[4])]

    def __iter__(self):
        return iter(self.tokens)


def fake_backend(*, parse_error: bool = False) -> GinzaBackend:
    def nlp(_text: str) -> FakeDoc:
        if parse_error:
            raise RuntimeError("synthetic parser failure")
        return FakeDoc()

    return GinzaBackend(
        nlp=nlp,
        bunsetu_spans=lambda _sentence: ["その条件", "の場合", "続行しない"],
        backend_version="5.2.0",
        model_version="5.2.0",
    )


def observation(
    case_id: str,
    provider: str,
    condition: str,
    *,
    expected_risk: bool,
    risk_detected: bool,
    behavior_match: bool = True,
) -> dict:
    return {
        "case_id": case_id,
        "provider": provider,
        "model": f"{provider}-model",
        "model_version": "2026-08-30",
        "host_version": f"{provider}-host",
        "repeat_index": 1,
        "condition": condition,
        "status": "completed",
        "expected_risk_present": expected_risk,
        "risk_detected": risk_detected,
        "unnecessary_revision": False,
        "semantic_preserved": True,
        "expected_behavior_match": behavior_match,
        "syntax_available": None if condition == "llm-only" else True,
        "duration_ms": 10.0 if condition == "llm-only" else 15.0,
        "notes": "synthetic A/B observation",
    }


def improving_experiment() -> dict:
    observations = []
    for provider in ("codex", "github-copilot"):
        observations.extend(
            [
                observation(
                    "risk-case",
                    provider,
                    "llm-only",
                    expected_risk=True,
                    risk_detected=provider == "codex",
                    behavior_match=provider == "codex",
                ),
                observation(
                    "clean-case",
                    provider,
                    "llm-only",
                    expected_risk=False,
                    risk_detected=False,
                ),
                observation(
                    "risk-case",
                    provider,
                    "llm-plus-signals",
                    expected_risk=True,
                    risk_detected=True,
                ),
                observation(
                    "clean-case",
                    provider,
                    "llm-plus-signals",
                    expected_risk=False,
                    risk_detected=False,
                ),
            ]
        )
    return {
        "schema_version": 1,
        "experiment": "synthetic-provider-comparison",
        "required_providers": ["codex", "github-copilot"],
        "observations": observations,
    }


class JapaneseSyntaxTests(unittest.TestCase):
    def test_dependency_absence_is_non_fatal(self) -> None:
        def missing(_model: str) -> GinzaBackend:
            raise BackendUnavailable("dependency-not-installed", detail="ginza")

        result = analyze_japanese("日本語です。", loader=missing, timer=iter([1.0, 1.01]).__next__)
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "dependency-not-installed")
        self.assertIsNone(result["signals"])
        self.assertEqual(result["interpretation"], "observation-only")

    def test_parser_error_is_non_fatal_and_records_versions(self) -> None:
        result = analyze_japanese(
            "解析に失敗します。",
            loader=lambda _model: fake_backend(parse_error=True),
            timer=iter([1.0, 1.02]).__next__,
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["reason"], "parse-error")
        self.assertEqual(result["backend_version"], "5.2.0")
        self.assertEqual(result["model_version"], "5.2.0")

    def test_available_result_contains_observations_not_judgment(self) -> None:
        result = analyze_japanese(
            "その条件の場合は続行しない。",
            loader=lambda _model: fake_backend(),
            timer=iter([1.0, 1.0123]).__next__,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["signals"]["sentence_count"], 1)
        self.assertEqual(result["signals"]["bunsetu_count"], 3)
        self.assertEqual(result["signals"]["condition_markers"], ["条件", "場合"])
        self.assertEqual(result["signals"]["negation_markers"], ["ない"])
        self.assertEqual(result["signals"]["demonstratives"], ["その"])
        self.assertEqual(result["signals"]["max_conditions_per_predicate"], 2)
        self.assertNotIn("text", result)
        self.assertNotIn("risk", result)
        self.assertNotIn("readability", result)

    def test_recorded_fixture_is_a_valid_signal_subset(self) -> None:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        expected = fixture["expected"]
        result = {
            "schema_version": 1,
            **expected,
            "python_version": fixture["recorded_with"]["python"],
            "analysis_ms": 1.0,
        }
        self.assertEqual(validate_syntax_signal(result)["signals"]["token_count"], 29)

    def test_signal_rejects_boolean_schema_version(self) -> None:
        result = analyze_japanese(
            "その条件の場合は続行しない。",
            loader=lambda _model: fake_backend(),
            timer=iter([1.0, 1.01]).__next__,
        )
        result["schema_version"] = True
        with self.assertRaisesRegex(SyntaxAnalysisError, "schema"):
            validate_syntax_signal(result)

    def test_invalid_interpretation_is_rejected(self) -> None:
        result = analyze_japanese(
            "日本語です。",
            loader=lambda _model: fake_backend(),
            timer=iter([1.0, 1.01]).__next__,
        )
        result["interpretation"] = "ground-truth"
        self.assertRaisesRegex(SyntaxAnalysisError, "判定", validate_syntax_signal, result)


class SyntaxAbTests(unittest.TestCase):
    def test_input_and_report_reject_boolean_schema_version(self) -> None:
        experiment = improving_experiment()
        invalid_experiment = deepcopy(experiment)
        invalid_experiment["schema_version"] = True
        with self.assertRaisesRegex(SyntaxAnalysisError, "schema"):
            build_syntax_ab_report(invalid_experiment)

        report = build_syntax_ab_report(experiment)
        report["schema_version"] = True
        with self.assertRaisesRegex(SyntaxAnalysisError, "schema"):
            validate_syntax_ab_report(report)

    def test_improvement_requires_human_review_and_never_defaults(self) -> None:
        report = build_syntax_ab_report(
            improving_experiment(),
            clock=lambda: "2026-08-30T15:00:00Z",
        )
        self.assertEqual(report["recommendation"], "human-review-required")
        self.assertFalse(report["default_enabled"])
        self.assertEqual(report["deltas"]["rr_recall"], 0.5)
        self.assertEqual(
            report["provider_difference"]["risk_decision_disagreement_rate_delta"],
            -0.5,
        )

    def test_no_observed_improvement_does_not_default(self) -> None:
        data = improving_experiment()
        baseline = {
            (item["case_id"], item["provider"]): item
            for item in data["observations"]
            if item["condition"] == "llm-only"
        }
        for item in data["observations"]:
            if item["condition"] == "llm-plus-signals":
                source = baseline[(item["case_id"], item["provider"])]
                for key in ("risk_detected", "expected_behavior_match"):
                    item[key] = source[key]
        report = build_syntax_ab_report(data)
        self.assertEqual(report["recommendation"], "do-not-default")
        self.assertIn("観測された改善がありません", report["automatic_blockers"])

    def test_semantic_regression_blocks_default(self) -> None:
        data = improving_experiment()
        next(
            item
            for item in data["observations"]
            if item["condition"] == "llm-plus-signals"
        )["semantic_preserved"] = False
        report = build_syntax_ab_report(data)
        self.assertEqual(report["recommendation"], "do-not-default")
        self.assertIn("semantic preservationが低下しました", report["automatic_blockers"])

    def test_parser_unavailable_blocks_default(self) -> None:
        data = improving_experiment()
        next(
            item
            for item in data["observations"]
            if item["condition"] == "llm-plus-signals"
        )["syntax_available"] = False
        report = build_syntax_ab_report(data)
        self.assertIn("signal条件にparser unavailableがあります", report["automatic_blockers"])

    def test_provider_disagreement_increase_blocks_default(self) -> None:
        data = improving_experiment()
        for item in data["observations"]:
            if item["case_id"] == "risk-case" and item["condition"] == "llm-only":
                item["risk_detected"] = True
                item["expected_behavior_match"] = True
            if (
                item["case_id"] == "risk-case"
                and item["condition"] == "llm-plus-signals"
                and item["provider"] == "github-copilot"
            ):
                item["risk_detected"] = False
                item["expected_behavior_match"] = False
        report = build_syntax_ab_report(data)
        self.assertIn("provider間のrisk判定差が増加しました", report["automatic_blockers"])
        self.assertEqual(report["recommendation"], "do-not-default")

    def test_provider_accuracy_spread_increase_blocks_default(self) -> None:
        data = improving_experiment()
        for item in data["observations"]:
            if item["condition"] == "llm-only":
                item["expected_behavior_match"] = item["case_id"] == "risk-case"
            else:
                item["expected_behavior_match"] = item["provider"] == "codex"
        report = build_syntax_ab_report(data)
        self.assertEqual(
            report["provider_difference"]["expected_behavior_accuracy_spread_delta"],
            1.0,
        )
        self.assertIn(
            "provider間のexpected behavior accuracy差が増加しました",
            report["automatic_blockers"],
        )
        self.assertEqual(report["recommendation"], "do-not-default")

    def test_provider_accuracy_uses_only_matched_case_repeat_sets(self) -> None:
        data = improving_experiment()
        data["observations"].extend(
            [
                observation(
                    "codex-only-case",
                    "codex",
                    condition,
                    expected_risk=False,
                    risk_detected=False,
                    behavior_match=condition == "llm-only",
                )
                for condition in ("llm-only", "llm-plus-signals")
            ]
        )
        report = build_syntax_ab_report(data)
        signals = report["provider_difference"]["llm-plus-signals"]
        self.assertEqual(signals["risk_decision_pairs"], 2)
        self.assertEqual(
            signals["expected_behavior_accuracy_by_provider"],
            {"codex": 1.0, "github-copilot": 1.0},
        )
        self.assertEqual(signals["expected_behavior_accuracy_spread"], 0.0)

    def test_unsupported_result_is_counted_and_blocks_default(self) -> None:
        data = improving_experiment()
        item = next(
            item
            for item in data["observations"]
            if item["condition"] == "llm-plus-signals"
        )
        item["status"] = "unsupported"
        for key in (
            "risk_detected",
            "unnecessary_revision",
            "semantic_preserved",
            "expected_behavior_match",
        ):
            item[key] = None
        report = build_syntax_ab_report(data)
        self.assertEqual(report["conditions"]["llm-plus-signals"]["unsupported"], 1)
        self.assertIn("unsupported resultがあります", report["automatic_blockers"])

    def test_missing_pair_and_metadata_mismatch_are_reported(self) -> None:
        data = improving_experiment()
        data["observations"].pop()
        pair = next(
            item
            for item in data["observations"]
            if item["provider"] == "codex" and item["condition"] == "llm-plus-signals"
        )
        pair["model_version"] = "different"
        report = build_syntax_ab_report(data)
        self.assertEqual(report["pairing"]["missing_pairs"], 1)
        self.assertEqual(report["pairing"]["metadata_mismatches"], 1)
        self.assertEqual(report["recommendation"], "do-not-default")

    def test_duplicate_observation_is_rejected(self) -> None:
        data = improving_experiment()
        data["observations"].append(deepcopy(data["observations"][0]))
        self.assertRaisesRegex(SyntaxAnalysisError, "重複", build_syntax_ab_report, data)


class SyntaxCliTests(unittest.TestCase):
    def test_analyze_without_optional_dependency_returns_availability_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "analyze", "--text", "日本語です。"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["available"])
        self.assertIn(output["reason"], {"dependency-not-installed", "model-not-installed"})

    def test_ab_report_cli_is_provider_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "ab-input.json"
            path.write_text(json.dumps(improving_experiment(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(CLI), "ab-report", "--input", str(path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["required_providers"], ["codex", "github-copilot"])
        self.assertFalse(output["default_enabled"])


if __name__ == "__main__":
    unittest.main()
