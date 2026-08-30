"""GiNZAをoptionalな構造sensorとして扱い、provider-neutralなA/B結果を集約する。"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

REQUIRED_PROVIDERS = ["codex", "github-copilot"]
CONDITIONS = ["llm-only", "llm-plus-signals"]
CONDITION_MARKERS = {
    "なら",
    "ならば",
    "ば",
    "たら",
    "場合",
    "時",
    "とき",
    "際",
    "条件",
    "限り",
}
EXCEPTION_MARKERS = {"ただし", "除く", "除き", "以外", "例外", "一方"}
NEGATION_LEMMAS = {"ない", "ぬ", "ず", "まい"}
DEMONSTRATIVES = {
    "これ",
    "それ",
    "あれ",
    "この",
    "その",
    "あの",
    "ここ",
    "そこ",
    "あそこ",
    "こう",
    "そう",
    "ああ",
    "当該",
    "前者",
    "後者",
}
MODIFIER_DEPS = {"acl", "advcl", "advmod", "amod", "nmod"}
ADNOMINAL_DEPS = {"acl", "amod", "nmod"}


class SyntaxAnalysisError(ValueError):
    """syntax artifactまたはA/B入力が不正である。"""


class BackendUnavailable(RuntimeError):
    """optional backendを利用できない。"""

    def __init__(
        self,
        reason: str,
        *,
        backend_version: str | None = None,
        model_version: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.backend_version = backend_version
        self.model_version = model_version
        self.detail = detail


@dataclass(frozen=True)
class GinzaBackend:
    nlp: Callable[[str], Any]
    bunsetu_spans: Callable[[Any], Iterable[Any]]
    backend_version: str
    model_version: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_ginza(model: str) -> GinzaBackend:
    try:
        import ginza
        import spacy
    except ModuleNotFoundError as exc:
        raise BackendUnavailable(
            "dependency-not-installed",
            detail=exc.name,
        ) from exc

    try:
        backend_version = importlib.metadata.version("ginza")
    except importlib.metadata.PackageNotFoundError:
        backend_version = "unknown"
    try:
        model_version = importlib.metadata.version(model.replace("_", "-"))
    except importlib.metadata.PackageNotFoundError as exc:
        raise BackendUnavailable(
            "model-not-installed",
            backend_version=backend_version,
            detail=model,
        ) from exc
    try:
        nlp = spacy.load(model)
    except OSError as exc:
        raise BackendUnavailable(
            "model-not-installed",
            backend_version=backend_version,
            model_version=model_version,
            detail=type(exc).__name__,
        ) from exc
    except Exception as exc:
        raise BackendUnavailable(
            "model-load-error",
            backend_version=backend_version,
            model_version=model_version,
            detail=type(exc).__name__,
        ) from exc
    return GinzaBackend(
        nlp=nlp,
        bunsetu_spans=ginza.bunsetu_spans,
        backend_version=backend_version,
        model_version=model_version,
    )


def _ordered_unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _dependency_depth(token: Any, *, modifier_only: bool = False) -> int:
    depth = 0
    current = token
    seen: set[int] = set()
    while current.head is not current and current.i not in seen:
        if modifier_only and current.dep_ not in MODIFIER_DEPS:
            break
        seen.add(current.i)
        depth += 1
        current = current.head
    return depth


def _predicate_ancestor(token: Any) -> int:
    current = token
    seen: set[int] = set()
    while current.i not in seen:
        seen.add(current.i)
        if current.pos_ in {"VERB", "ADJ"} or current.dep_ == "ROOT":
            return current.i
        if current.head is current:
            return current.i
        current = current.head
    return token.i


def _extract_signals(doc: Any, backend: GinzaBackend) -> dict:
    tokens = list(doc)
    sentences = list(doc.sents)
    condition_tokens = [
        token for token in tokens if token.text in CONDITION_MARKERS or token.lemma_ in CONDITION_MARKERS
    ]
    exception_tokens = [
        token for token in tokens if token.text in EXCEPTION_MARKERS or token.lemma_ in EXCEPTION_MARKERS
    ]
    negation_tokens = [
        token
        for token in tokens
        if token.text in NEGATION_LEMMAS
        or token.lemma_ in NEGATION_LEMMAS
        or "Polarity=Neg" in str(token.morph)
    ]
    demonstratives = [
        token.text
        for token in tokens
        if token.text in DEMONSTRATIVES or token.lemma_ in DEMONSTRATIVES
    ]
    conditions_by_predicate = Counter(_predicate_ancestor(token) for token in condition_tokens)
    parallel_widths = [
        1 + sum(child.dep_ == "conj" for child in token.children)
        for token in tokens
    ]
    return {
        "sentence_count": len(sentences),
        "token_count": len(tokens),
        "bunsetu_count": sum(len(list(backend.bunsetu_spans(sentence))) for sentence in sentences),
        "max_main_predicate_distance": max(
            (abs(sentence.root.i - sentence.start) for sentence in sentences),
            default=0,
        ),
        "max_dependency_distance": max(
            (abs(token.i - token.head.i) for token in tokens),
            default=0,
        ),
        "max_modifier_depth": max(
            (_dependency_depth(token, modifier_only=True) for token in tokens),
            default=0,
        ),
        "max_adnominal_dependency_distance": max(
            (
                abs(token.i - token.head.i)
                for token in tokens
                if token.dep_ in ADNOMINAL_DEPS
            ),
            default=0,
        ),
        "condition_marker_count": len(condition_tokens),
        "condition_markers": _ordered_unique(token.text for token in condition_tokens),
        "exception_marker_count": len(exception_tokens),
        "exception_markers": _ordered_unique(token.text for token in exception_tokens),
        "negation_marker_count": len(negation_tokens),
        "negation_markers": _ordered_unique(token.text for token in negation_tokens),
        "demonstratives": _ordered_unique(demonstratives),
        "max_conditions_per_predicate": max(conditions_by_predicate.values(), default=0),
        "max_parallel_width": max(parallel_widths, default=0),
    }


def analyze_japanese(
    text: str,
    *,
    model: str = "ja_ginza",
    loader: Callable[[str], GinzaBackend] = _load_ginza,
    timer: Callable[[], float] = time.perf_counter,
) -> dict:
    """構造観測値を返す。backend不在やparse失敗は非致命resultにする。"""

    if not isinstance(text, str):
        raise SyntaxAnalysisError("textはstringである必要があります")
    if not isinstance(model, str) or not model.strip():
        raise SyntaxAnalysisError("modelは空でないstringである必要があります")
    started = timer()
    base = {
        "schema_version": 1,
        "available": False,
        "backend": "ginza",
        "backend_version": None,
        "model": model,
        "model_version": None,
        "python_version": platform.python_version(),
        "text_hash": f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
        "analysis_ms": 0.0,
        "reason": None,
        "signals": None,
        "warnings": [],
        "interpretation": "observation-only",
    }
    try:
        backend = loader(model)
    except ModuleNotFoundError as exc:
        backend_error = BackendUnavailable("dependency-not-installed", detail=exc.name)
    except BackendUnavailable as exc:
        backend_error = exc
    else:
        base["backend_version"] = backend.backend_version
        base["model_version"] = backend.model_version
        try:
            doc = backend.nlp(text)
            base["signals"] = _extract_signals(doc, backend)
        except Exception as exc:  # noqa: BLE001 -- optional parser failure must remain non-fatal
            base["reason"] = "parse-error"
            base["warnings"] = [f"parse失敗: {type(exc).__name__}"]
        else:
            base["available"] = True
        base["analysis_ms"] = round(max(0.0, (timer() - started) * 1000), 3)
        return validate_syntax_signal(base)

    base["backend_version"] = backend_error.backend_version
    base["model_version"] = backend_error.model_version
    base["reason"] = backend_error.reason
    if backend_error.detail:
        base["warnings"] = [f"optional backendを利用できません: {backend_error.detail}"]
    base["analysis_ms"] = round(max(0.0, (timer() - started) * 1000), 3)
    return validate_syntax_signal(base)


def validate_syntax_signal(value: object) -> dict:
    if not isinstance(value, dict):
        raise SyntaxAnalysisError("syntax signalはobjectである必要があります")
    data = deepcopy(value)
    keys = {
        "schema_version",
        "available",
        "backend",
        "backend_version",
        "model",
        "model_version",
        "python_version",
        "text_hash",
        "analysis_ms",
        "reason",
        "signals",
        "warnings",
        "interpretation",
    }
    if set(data) != keys:
        raise SyntaxAnalysisError("syntax signalのkeyがschema v1と一致しません")
    if data["schema_version"] != 1 or data["backend"] != "ginza":
        raise SyntaxAnalysisError("syntax signalのschemaまたはbackendが不正です")
    if data["interpretation"] != "observation-only":
        raise SyntaxAnalysisError("parser outputを判定として保存できません")
    if not isinstance(data["warnings"], list) or not all(
        isinstance(item, str) for item in data["warnings"]
    ):
        raise SyntaxAnalysisError("syntax warningsが不正です")
    if data["available"]:
        if data["reason"] is not None or not isinstance(data["signals"], dict):
            raise SyntaxAnalysisError("available resultにはsignalsが必要です")
        if not data["backend_version"] or not data["model_version"]:
            raise SyntaxAnalysisError("available resultにはbackend/model versionが必要です")
    elif data["signals"] is not None or data["reason"] not in {
        "dependency-not-installed",
        "model-not-installed",
        "model-load-error",
        "parse-error",
    }:
        raise SyntaxAnalysisError("unavailable resultのreasonまたはsignalsが不正です")
    return data


def _require_ab_input(value: object) -> dict:
    if not isinstance(value, dict):
        raise SyntaxAnalysisError("A/B inputはobjectである必要があります")
    data = deepcopy(value)
    if set(data) != {"schema_version", "experiment", "required_providers", "observations"}:
        raise SyntaxAnalysisError("A/B inputのkeyがschema v1と一致しません")
    if data["schema_version"] != 1 or not isinstance(data["experiment"], str) or not data["experiment"].strip():
        raise SyntaxAnalysisError("A/B inputのschemaまたはexperimentが不正です")
    if data["required_providers"] != REQUIRED_PROVIDERS:
        raise SyntaxAnalysisError("A/B inputにはCodexとGitHub Copilotをこの順で指定してください")
    observations = data["observations"]
    if not isinstance(observations, list) or not observations:
        raise SyntaxAnalysisError("A/B observationsがありません")
    keys = {
        "case_id",
        "provider",
        "model",
        "model_version",
        "host_version",
        "repeat_index",
        "condition",
        "status",
        "expected_risk_present",
        "risk_detected",
        "unnecessary_revision",
        "semantic_preserved",
        "expected_behavior_match",
        "syntax_available",
        "duration_ms",
        "notes",
    }
    seen: set[tuple[str, str, int, str]] = set()
    for item in observations:
        if not isinstance(item, dict) or set(item) != keys:
            raise SyntaxAnalysisError("A/B observationのkeyがschema v1と一致しません")
        for key in ("case_id", "provider", "model", "model_version", "host_version", "notes"):
            if not isinstance(item[key], str) or (key != "notes" and not item[key].strip()):
                raise SyntaxAnalysisError(f"A/B observation.{key}が不正です")
        if item["provider"] not in REQUIRED_PROVIDERS or item["condition"] not in CONDITIONS:
            raise SyntaxAnalysisError("A/B observationのproviderまたはconditionが不正です")
        if item["status"] not in {"completed", "unsupported", "error"}:
            raise SyntaxAnalysisError("A/B observation statusが不正です")
        if not isinstance(item["repeat_index"], int) or isinstance(item["repeat_index"], bool) or item["repeat_index"] < 1:
            raise SyntaxAnalysisError("A/B repeat_indexが不正です")
        if not isinstance(item["expected_risk_present"], bool):
            raise SyntaxAnalysisError("expected_risk_presentはbooleanである必要があります")
        if not isinstance(item["duration_ms"], (int, float)) or isinstance(item["duration_ms"], bool) or item["duration_ms"] < 0:
            raise SyntaxAnalysisError("duration_msが不正です")
        outcome_keys = (
            "risk_detected",
            "unnecessary_revision",
            "semantic_preserved",
            "expected_behavior_match",
        )
        if item["status"] == "completed":
            if any(not isinstance(item[key], bool) for key in outcome_keys):
                raise SyntaxAnalysisError("completed observationにはboolean outcomeが必要です")
        elif any(item[key] is not None for key in outcome_keys):
            raise SyntaxAnalysisError("未完了observationのoutcomeはnullである必要があります")
        if item["condition"] == "llm-only" and item["syntax_available"] is not None:
            raise SyntaxAnalysisError("llm-onlyでsyntax availabilityを指定できません")
        if item["condition"] == "llm-plus-signals" and not isinstance(item["syntax_available"], bool):
            raise SyntaxAnalysisError("signal条件にはsyntax availabilityが必要です")
        identity = (item["case_id"], item["provider"], item["repeat_index"], item["condition"])
        if identity in seen:
            raise SyntaxAnalysisError("A/B observationが重複しています")
        seen.add(identity)
    return data


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _condition_metrics(observations: list[dict], condition: str) -> dict:
    selected = [item for item in observations if item["condition"] == condition]
    completed = [item for item in selected if item["status"] == "completed"]
    positives = [item for item in completed if item["expected_risk_present"]]
    negatives = [item for item in completed if not item["expected_risk_present"]]
    parse_failures = [
        item for item in selected if condition == "llm-plus-signals" and not item["syntax_available"]
    ]
    return {
        "total": len(selected),
        "completed": len(completed),
        "unsupported": sum(item["status"] == "unsupported" for item in selected),
        "errors": sum(item["status"] == "error" for item in selected),
        "rr_recall": _rate(sum(bool(item["risk_detected"]) for item in positives), len(positives)),
        "false_positive_rate": _rate(
            sum(bool(item["risk_detected"]) for item in negatives),
            len(negatives),
        ),
        "unnecessary_revision_rate": _rate(
            sum(bool(item["unnecessary_revision"]) for item in completed),
            len(completed),
        ),
        "semantic_preservation_rate": _rate(
            sum(bool(item["semantic_preserved"]) for item in completed),
            len(completed),
        ),
        "expected_behavior_accuracy": _rate(
            sum(bool(item["expected_behavior_match"]) for item in completed),
            len(completed),
        ),
        "mean_duration_ms": (
            round(sum(item["duration_ms"] for item in selected) / len(selected), 3)
            if selected
            else None
        ),
        "parse_failure_rate": (
            _rate(len(parse_failures), len(selected)) if condition == "llm-plus-signals" else None
        ),
    }


def _difference(after: float | None, before: float | None) -> float | None:
    return round(after - before, 6) if after is not None and before is not None else None


def _provider_metrics(observations: list[dict], condition: str) -> dict:
    completed = [
        item
        for item in observations
        if item["condition"] == condition and item["status"] == "completed"
    ]
    accuracy_by_provider: dict[str, float | None] = {}
    for provider in REQUIRED_PROVIDERS:
        provider_items = [item for item in completed if item["provider"] == provider]
        accuracy_by_provider[provider] = _rate(
            sum(bool(item["expected_behavior_match"]) for item in provider_items),
            len(provider_items),
        )
    available_accuracy = [value for value in accuracy_by_provider.values() if value is not None]
    grouped: dict[tuple[str, int], dict[str, bool]] = defaultdict(dict)
    for item in completed:
        grouped[(item["case_id"], item["repeat_index"])][item["provider"]] = bool(
            item["risk_detected"]
        )
    comparable = [values for values in grouped.values() if set(values) == set(REQUIRED_PROVIDERS)]
    disagreements = sum(len(set(values.values())) > 1 for values in comparable)
    return {
        "expected_behavior_accuracy_by_provider": accuracy_by_provider,
        "expected_behavior_accuracy_spread": (
            round(max(available_accuracy) - min(available_accuracy), 6)
            if len(available_accuracy) == len(REQUIRED_PROVIDERS)
            else None
        ),
        "risk_decision_pairs": len(comparable),
        "risk_decision_disagreements": disagreements,
        "risk_decision_disagreement_rate": _rate(disagreements, len(comparable)),
    }


def build_syntax_ab_report(
    value: object,
    *,
    clock: Callable[[], str] = _utc_now,
) -> dict:
    data = _require_ab_input(value)
    observations = data["observations"]
    indexed = {
        (item["case_id"], item["provider"], item["repeat_index"], item["condition"]): item
        for item in observations
    }
    base_keys = {
        (item["case_id"], item["provider"], item["repeat_index"])
        for item in observations
    }
    complete_pairs = 0
    missing_pairs = 0
    metadata_mismatches = 0
    for case_id, provider, repeat in base_keys:
        pair = [indexed.get((case_id, provider, repeat, condition)) for condition in CONDITIONS]
        if any(item is None for item in pair):
            missing_pairs += 1
            continue
        complete_pairs += 1
        if any(
            pair[0][key] != pair[1][key]
            for key in ("model", "model_version", "host_version", "expected_risk_present")
        ):
            metadata_mismatches += 1

    conditions = {
        condition: _condition_metrics(observations, condition) for condition in CONDITIONS
    }
    baseline = conditions["llm-only"]
    signals = conditions["llm-plus-signals"]
    metric_names = (
        "rr_recall",
        "false_positive_rate",
        "unnecessary_revision_rate",
        "semantic_preservation_rate",
        "expected_behavior_accuracy",
        "mean_duration_ms",
        "parse_failure_rate",
    )
    deltas = {
        name: _difference(signals[name], baseline[name])
        for name in metric_names
    }
    provider_conditions = {
        condition: _provider_metrics(observations, condition) for condition in CONDITIONS
    }
    provider_difference = {
        **provider_conditions,
        "expected_behavior_accuracy_spread_delta": _difference(
            provider_conditions["llm-plus-signals"]["expected_behavior_accuracy_spread"],
            provider_conditions["llm-only"]["expected_behavior_accuracy_spread"],
        ),
        "risk_decision_disagreement_rate_delta": _difference(
            provider_conditions["llm-plus-signals"]["risk_decision_disagreement_rate"],
            provider_conditions["llm-only"]["risk_decision_disagreement_rate"],
        ),
    }
    providers_by_condition = {
        condition: sorted(
            {
                item["provider"]
                for item in observations
                if item["condition"] == condition
            }
        )
        for condition in CONDITIONS
    }
    pairing = {
        "complete_pairs": complete_pairs,
        "missing_pairs": missing_pairs,
        "metadata_mismatches": metadata_mismatches,
        "providers_by_condition": providers_by_condition,
    }
    blockers: list[str] = []
    if missing_pairs:
        blockers.append("paired observationが不足しています")
    if metadata_mismatches:
        blockers.append("A/B pairのmodel・host・期待値metadataが一致しません")
    if any(set(providers_by_condition[condition]) != set(REQUIRED_PROVIDERS) for condition in CONDITIONS):
        blockers.append("CodexとGitHub Copilotの両条件結果が必要です")
    if sum(item["status"] == "unsupported" for item in observations):
        blockers.append("unsupported resultがあります")
    if sum(item["status"] == "error" for item in observations):
        blockers.append("error resultがあります")
    if signals["parse_failure_rate"] not in {0}:
        blockers.append("signal条件にparser unavailableがあります")
    for name in ("rr_recall", "false_positive_rate"):
        if baseline[name] is None or signals[name] is None:
            blockers.append("RR recallとfalse positiveの両方を評価できるcaseが必要です")
            break
    regression_rules = {
        "rr_recall": ("lower", "RR recallが低下しました"),
        "false_positive_rate": ("higher", "false positiveが増加しました"),
        "unnecessary_revision_rate": ("higher", "unnecessary revisionが増加しました"),
        "semantic_preservation_rate": ("lower", "semantic preservationが低下しました"),
        "expected_behavior_accuracy": ("lower", "expected behavior accuracyが低下しました"),
    }
    for name, (direction, message) in regression_rules.items():
        delta = deltas[name]
        if delta is not None and ((direction == "lower" and delta < 0) or (direction == "higher" and delta > 0)):
            blockers.append(message)
    disagreement_delta = provider_difference["risk_decision_disagreement_rate_delta"]
    if disagreement_delta is not None and disagreement_delta > 0:
        blockers.append("provider間のrisk判定差が増加しました")

    improvements: list[str] = []
    improvement_rules = {
        "rr_recall": ("higher", "RR recallが改善しました"),
        "false_positive_rate": ("lower", "false positiveが減少しました"),
        "unnecessary_revision_rate": ("lower", "unnecessary revisionが減少しました"),
        "expected_behavior_accuracy": ("higher", "expected behavior accuracyが改善しました"),
    }
    for name, (direction, message) in improvement_rules.items():
        delta = deltas[name]
        if delta is not None and ((direction == "higher" and delta > 0) or (direction == "lower" and delta < 0)):
            improvements.append(message)
    if disagreement_delta is not None and disagreement_delta < 0:
        improvements.append("provider間のrisk判定差が減少しました")
    if not improvements:
        blockers.append("観測された改善がありません")

    body = {
        "schema_version": 1,
        "experiment": data["experiment"],
        "required_providers": REQUIRED_PROVIDERS,
        "conditions": conditions,
        "deltas": deltas,
        "provider_difference": provider_difference,
        "pairing": pairing,
        "automatic_blockers": list(dict.fromkeys(blockers)),
        "observed_improvements": improvements,
        "recommendation": "do-not-default" if blockers else "human-review-required",
        "default_enabled": False,
    }
    report = {
        "id": f"rfsab-{_canonical_hash(body)[:20]}",
        **body,
        "created_at": clock(),
    }
    return validate_syntax_ab_report(report)


def validate_syntax_ab_report(value: object) -> dict:
    if not isinstance(value, dict):
        raise SyntaxAnalysisError("syntax A/B reportはobjectである必要があります")
    data = deepcopy(value)
    keys = {
        "id",
        "schema_version",
        "experiment",
        "created_at",
        "required_providers",
        "conditions",
        "deltas",
        "provider_difference",
        "pairing",
        "automatic_blockers",
        "observed_improvements",
        "recommendation",
        "default_enabled",
    }
    if set(data) != keys or data.get("schema_version") != 1:
        raise SyntaxAnalysisError("syntax A/B reportのkeyまたはschema versionが不正です")
    body = {key: data[key] for key in keys - {"id", "created_at"}}
    if data.get("id") != f"rfsab-{_canonical_hash(body)[:20]}":
        raise SyntaxAnalysisError("syntax A/B report IDが内容から再計算した値と一致しません")
    if data.get("default_enabled") is not False:
        raise SyntaxAnalysisError("A/B reportからparserを自動で既定化できません")
    expected = "do-not-default" if data.get("automatic_blockers") else "human-review-required"
    if data.get("recommendation") != expected:
        raise SyntaxAnalysisError("A/B recommendationとblockerが一致しません")
    return data


__all__ = [
    "BackendUnavailable",
    "GinzaBackend",
    "SyntaxAnalysisError",
    "analyze_japanese",
    "build_syntax_ab_report",
    "validate_syntax_ab_report",
    "validate_syntax_signal",
]
