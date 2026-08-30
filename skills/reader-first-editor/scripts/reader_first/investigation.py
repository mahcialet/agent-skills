"""Adversarial rule investigation bundleとproposal draftを扱う。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .state import STATE_DIRECTORIES, LocalCorpusStore, StoreError

DECISIONS = {"PROMOTE", "REJECT", "HOLD", "NEEDS_MORE_EVIDENCE"}
RESULT_KEYS = {
    "id",
    "bundle_id",
    "schema_version",
    "created_at",
    "producer",
    "hypothesis",
    "scope",
    "record_ids",
    "source_correlation",
    "support",
    "counterexamples",
    "boundary_pairs",
    "existing_rule_analysis",
    "semantic_risks",
    "provenance_reviewed",
    "fixed_threshold_only",
    "frequency_only",
    "duplicate_rule",
    "proposed_evals",
    "decision",
}


class InvestigationError(StoreError):
    """Investigation artifactが安全契約を満たさない。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_id(prefix: str, value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:20]}"


def _require_dict(value: object, context: str) -> dict:
    if not isinstance(value, dict):
        raise InvestigationError(f"{context}はobjectである必要があります")
    return value


def _require_string(container: dict, key: str, context: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvestigationError(f"{context}.{key}は空でないstringである必要があります")
    return value


def _require_string_list(
    container: dict,
    key: str,
    context: str,
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> list[str]:
    value = container.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise InvestigationError(f"{context}.{key}はstring arrayである必要があります")
    if nonempty and not value:
        raise InvestigationError(f"{context}.{key}は1件以上必要です")
    if unique and len(value) != len(set(value)):
        raise InvestigationError(f"{context}.{key}に重複があります")
    return value


def _require_exact_keys(container: dict, keys: set[str], context: str) -> None:
    missing = sorted(keys - container.keys())
    unknown = sorted(container.keys() - keys)
    if missing:
        raise InvestigationError(f"{context}に必須keyがありません: {', '.join(missing)}")
    if unknown:
        raise InvestigationError(f"{context}に未知のkeyがあります: {', '.join(unknown)}")


def _record_summary(store: LocalCorpusStore, record: dict, role: str) -> dict:
    source = record["source"]
    state = record["decision"]["state"]
    record_path = store.root / STATE_DIRECTORIES[state] / f"{record['id']}.json"
    return {
        "id": record["id"],
        "role": role,
        "state": state,
        "language": record["language"],
        "translation_status": record["translation_status"],
        "genre": record["genre"],
        "reader": record["reader"]["description"],
        "sample_type": record["sample_type"],
        "quality_class": record["quality_class"],
        "expected_behavior": record["annotations"]["expected_behavior"],
        "source": {
            "type": source["type"],
            "repository": source["repository"],
            "pr_number": source["pr_number"],
            "revision": source["immutable_revision"],
            "file": source["file"],
            "url": source["url"],
            "correlation_group": source["correlation_group"],
        },
        "rights": {
            "status": record["rights"]["status"],
            "local_only": record["rights"]["local_only"],
        },
        "text_reference": {
            "storage": record["text"]["storage"],
            "content_hash": record["text"]["content_hash"],
            "record_path": str(record_path),
            "raw_text_copied": False,
        },
    }


def _role_contracts() -> list[dict]:
    return [
        {
            "name": "Counterexample Hunter",
            "priority": 1,
            "instructions": [
                "clean・borderline・rejected recordから反例を最優先で探す",
                "支持件数が多くても未説明の反例を多数決で無視しない",
                "reference-only recordのraw textをbundleへ複製しない",
            ],
            "required_output": [
                "searched",
                "explained counterexamples",
                "unexplained counterexamples",
            ],
        },
        {
            "name": "Pattern Miner",
            "priority": 2,
            "instructions": [
                "共通特徴をruleではなく仮説として扱う",
                "source correlation、confounder、既存ruleで説明可能かを示す",
            ],
            "required_output": ["mechanism", "confounders", "independent sources"],
        },
        {
            "name": "Boundary Tester",
            "priority": 3,
            "instructions": [
                "発火すべき例と似ているが発火すべきでない例のminimal pairを作る",
                "隠れた条件までscopeを狭める",
            ],
            "required_output": ["boundary pairs", "distinguishing condition", "scope effect"],
        },
        {
            "name": "Regression Analyst",
            "priority": 4,
            "instructions": [
                "semantic preservation、unnecessary revision、literal、registerのriskを列挙する",
                "positive・negative・boundary eval候補を分ける",
            ],
            "required_output": ["semantic risks", "positive evals", "negative evals", "boundary evals"],
        },
        {
            "name": "Rule Reviewer",
            "priority": 5,
            "instructions": [
                "既定判断をHOLDとし、既存ruleで十分ならduplicateとして止める",
                "固定閾値・頻度だけの一般化をPROMOTEしない",
                "PROMOTEはproposal review可能という意味でありapplyではない",
            ],
            "required_output": ["existing rule analysis", "decision", "decision reason"],
        },
    ]


def build_investigation_bundle(
    store: LocalCorpusStore,
    *,
    hypothesis: str,
    support_record_ids: list[str],
    control_record_ids: list[str],
    purposes: list[str],
    actor: str,
    reason: str,
    clock: Callable[[], str] = _utc_now,
) -> dict:
    """明示選択されたlocal recordのmetadataからraw-text-free bundleを作る。"""

    if not hypothesis.strip():
        raise InvestigationError("hypothesisが必要です")
    if not support_record_ids:
        raise InvestigationError("support recordを1件以上指定してください")
    if not purposes or any(not purpose.strip() for purpose in purposes):
        raise InvestigationError("purposeを1件以上指定してください")
    if not actor.strip() or not reason.strip():
        raise InvestigationError("bundle作成者と理由が必要です")
    support_ids = sorted(set(support_record_ids))
    control_ids = sorted(set(control_record_ids))
    if len(support_ids) != len(support_record_ids) or len(control_ids) != len(control_record_ids):
        raise InvestigationError("record IDを重複指定できません")
    if overlap := set(support_ids) & set(control_ids):
        raise InvestigationError("supportとcontrolを兼用できません: " + ", ".join(sorted(overlap)))

    summaries: list[dict] = []
    records: dict[str, dict] = {}
    for role, record_ids in (("support", support_ids), ("control", control_ids)):
        for record_id in record_ids:
            record = store.load_record(record_id)
            state = record["decision"]["state"]
            if role == "support" and state not in {"accepted", "promoted"}:
                raise InvestigationError("supportにはacceptedまたはpromoted recordが必要です")
            if role == "control" and state not in {"accepted", "promoted", "rejected"}:
                raise InvestigationError("controlにはaccepted、promoted、rejected recordが必要です")
            records[record_id] = record
            summaries.append(_record_summary(store, record, role))

    all_records = list(records.values())
    scope = {
        "languages": sorted({record["language"] for record in all_records}),
        "genres": sorted({record["genre"] for record in all_records}),
        "readers": sorted({record["reader"]["description"] for record in all_records}),
        "purposes": sorted(set(purposes)),
        "translation_status": sorted({record["translation_status"] for record in all_records}),
    }
    correlation_groups = sorted(
        {record["source"]["correlation_group"] for record in all_records}
    )
    repositories = sorted(
        {
            record["source"]["repository"] or f"source:{record['source']['type']}"
            for record in all_records
        }
    )
    support_groups = {
        records[record_id]["source"]["correlation_group"] for record_id in support_ids
    }
    blockers: list[str] = []
    if len(support_groups) < 2:
        blockers.append("独立したsupport correlation groupが2件未満")
    if not control_ids:
        blockers.append("counterexample／negative control候補が未選択")
    if not any(records[record_id]["quality_class"] in {"clean", "borderline"} for record_id in control_ids):
        blockers.append("cleanまたはborderline controlが未選択")

    identity = {
        "hypothesis": hypothesis.strip(),
        "scope": scope,
        "support_record_ids": support_ids,
        "control_record_ids": control_ids,
    }
    bundle = {
        "id": _hash_id("rfb", identity),
        "schema_version": 1,
        "created_at": clock(),
        "actor": actor.strip(),
        "reason": reason.strip(),
        "hypothesis": hypothesis.strip(),
        "scope": scope,
        "selection": {
            "support_record_ids": support_ids,
            "control_record_ids": control_ids,
        },
        "records": sorted(summaries, key=lambda item: (item["role"], item["id"])),
        "source_analysis": {
            "record_count": len(all_records),
            "correlation_groups": correlation_groups,
            "repositories": repositories,
            "independent_sources": len(correlation_groups),
        },
        "roles": _role_contracts(),
        "readiness": {
            "default_decision": "NEEDS_MORE_EVIDENCE" if blockers else "HOLD",
            "blockers": blockers,
        },
        "output_contract": {
            "schema": "schemas/investigation.schema.json",
            "default_decision": "HOLD",
            "promote_is_not_apply": True,
        },
    }
    validate_investigation_bundle(bundle)
    return bundle


def validate_investigation_bundle(bundle: object) -> dict:
    data = deepcopy(_require_dict(bundle, "bundle"))
    expected_keys = {
        "id",
        "schema_version",
        "created_at",
        "actor",
        "reason",
        "hypothesis",
        "scope",
        "selection",
        "records",
        "source_analysis",
        "roles",
        "readiness",
        "output_contract",
    }
    _require_exact_keys(data, expected_keys, "bundle")
    if data["schema_version"] != 1:
        raise InvestigationError("bundle.schema_versionが未対応です")
    _require_string(data, "created_at", "bundle")
    _require_string(data, "actor", "bundle")
    _require_string(data, "reason", "bundle")
    hypothesis = _require_string(data, "hypothesis", "bundle")
    scope = _validate_scope(data.get("scope"), "bundle.scope")
    selection = _require_dict(data.get("selection"), "bundle.selection")
    _require_exact_keys(
        selection,
        {"support_record_ids", "control_record_ids"},
        "bundle.selection",
    )
    support_ids = _require_string_list(
        selection,
        "support_record_ids",
        "bundle.selection",
        nonempty=True,
        unique=True,
    )
    control_ids = _require_string_list(
        selection,
        "control_record_ids",
        "bundle.selection",
        unique=True,
    )
    expected_id = _hash_id(
        "rfb",
        {
            "hypothesis": hypothesis,
            "scope": scope,
            "support_record_ids": support_ids,
            "control_record_ids": control_ids,
        },
    )
    if data["id"] != expected_id:
        raise InvestigationError("bundle IDが内容から再計算した値と一致しません")
    if not isinstance(data.get("records"), list) or not data["records"]:
        raise InvestigationError("bundle.recordsがありません")
    record_ids = [item.get("id") for item in data["records"] if isinstance(item, dict)]
    if sorted(record_ids) != sorted([*support_ids, *control_ids]):
        raise InvestigationError("bundle.recordsとselectionが一致しません")
    if not isinstance(data.get("roles"), list) or {
        item.get("name") for item in data["roles"] if isinstance(item, dict)
    } != {item["name"] for item in _role_contracts()}:
        raise InvestigationError("bundleに必須Agent roleがありません")
    output = _require_dict(data.get("output_contract"), "bundle.output_contract")
    if output.get("default_decision") != "HOLD" or output.get("promote_is_not_apply") is not True:
        raise InvestigationError("bundleのconservative output contractが不正です")
    return data


def validate_bundle_against_store(bundle: object, store: LocalCorpusStore) -> dict:
    """Bundle summaryをauthoritativeなlocal recordと再照合する。"""

    data = validate_investigation_bundle(bundle)
    if data["roles"] != _role_contracts():
        raise InvestigationError("bundleのAgent role contractが変更されています")
    expected_records: list[dict] = []
    records: dict[str, dict] = {}
    for role, ids in (
        ("support", data["selection"]["support_record_ids"]),
        ("control", data["selection"]["control_record_ids"]),
    ):
        for record_id in ids:
            record = store.load_record(record_id)
            records[record_id] = record
            expected_records.append(_record_summary(store, record, role))
    expected_records.sort(key=lambda item: (item["role"], item["id"]))
    if data["records"] != expected_records:
        raise InvestigationError("bundle record summaryがlocal corpusと一致しません")
    correlations = sorted(
        {record["source"]["correlation_group"] for record in records.values()}
    )
    repositories = sorted(
        {
            record["source"]["repository"] or f"source:{record['source']['type']}"
            for record in records.values()
        }
    )
    expected_analysis = {
        "record_count": len(records),
        "correlation_groups": correlations,
        "repositories": repositories,
        "independent_sources": len(correlations),
    }
    if data["source_analysis"] != expected_analysis:
        raise InvestigationError("bundle source analysisがlocal corpusと一致しません")
    support_groups = {
        records[record_id]["source"]["correlation_group"]
        for record_id in data["selection"]["support_record_ids"]
    }
    control_ids = data["selection"]["control_record_ids"]
    blockers: list[str] = []
    if len(support_groups) < 2:
        blockers.append("独立したsupport correlation groupが2件未満")
    if not control_ids:
        blockers.append("counterexample／negative control候補が未選択")
    if not any(
        records[record_id]["quality_class"] in {"clean", "borderline"}
        for record_id in control_ids
    ):
        blockers.append("cleanまたはborderline controlが未選択")
    expected_readiness = {
        "default_decision": "NEEDS_MORE_EVIDENCE" if blockers else "HOLD",
        "blockers": blockers,
    }
    if data["readiness"] != expected_readiness:
        raise InvestigationError("bundle readinessがlocal corpusと一致しません")
    return data


def _validate_scope(value: object, context: str) -> dict:
    scope = _require_dict(value, context)
    keys = {"languages", "genres", "readers", "purposes", "translation_status"}
    _require_exact_keys(scope, keys, context)
    for key in keys:
        _require_string_list(scope, key, context, nonempty=True, unique=True)
    if not set(scope["languages"]) <= {"ja", "en"}:
        raise InvestigationError(f"{context}.languagesが不正です")
    return scope


def validate_investigation_result(result: object, bundle: dict) -> tuple[dict, list[str]]:
    """Agent outputを検証し、PROMOTEを止めるblockerを返す。"""

    data = deepcopy(_require_dict(result, "investigation"))
    _require_exact_keys(data, RESULT_KEYS, "investigation")
    if data.get("schema_version") != 1:
        raise InvestigationError("investigation.schema_versionが未対応です")
    if data.get("bundle_id") != bundle["id"]:
        raise InvestigationError("investigation.bundle_idがbundleと一致しません")
    _require_string(data, "created_at", "investigation")
    _require_string(data, "producer", "investigation")
    if _require_string(data, "hypothesis", "investigation") != bundle["hypothesis"]:
        raise InvestigationError("investigation.hypothesisがbundleと一致しません")
    scope = _validate_scope(data.get("scope"), "investigation.scope")
    if scope != bundle["scope"]:
        raise InvestigationError("investigation.scopeをbundleより拡大・変更できません")
    record_ids = _require_string_list(
        data,
        "record_ids",
        "investigation",
        nonempty=True,
        unique=True,
    )
    selected = {
        *bundle["selection"]["support_record_ids"],
        *bundle["selection"]["control_record_ids"],
    }
    if not set(record_ids) <= selected:
        raise InvestigationError("bundleで明示選択していないrecordをresultへ追加できません")
    records_by_id = {record["id"]: record for record in bundle["records"]}
    expected_correlations = sorted(
        {records_by_id[record_id]["source"]["correlation_group"] for record_id in record_ids}
    )
    correlations = _require_string_list(
        data,
        "source_correlation",
        "investigation",
        unique=True,
    )
    if sorted(correlations) != expected_correlations:
        raise InvestigationError("source_correlationがrecord provenanceと一致しません")

    support = _require_dict(data.get("support"), "investigation.support")
    support_keys = {"independent_sources", "examples", "mechanism", "confounders"}
    _require_exact_keys(support, support_keys, "investigation.support")
    examples = _require_string_list(
        support,
        "examples",
        "investigation.support",
        unique=True,
    )
    if not set(examples) <= set(bundle["selection"]["support_record_ids"]):
        raise InvestigationError("support.examplesにはsupport record IDだけを指定できます")
    if not set(examples) <= set(record_ids):
        raise InvestigationError("support.examplesはrecord_idsにも含める必要があります")
    example_groups = {
        records_by_id[record_id]["source"]["correlation_group"] for record_id in examples
    }
    if support.get("independent_sources") != len(example_groups):
        raise InvestigationError("support.independent_sourcesがprovenanceからの集計と一致しません")
    if not isinstance(support.get("mechanism"), str):
        raise InvestigationError("support.mechanismはstringである必要があります")
    _require_string_list(support, "confounders", "investigation.support")

    counterexamples = _require_dict(
        data.get("counterexamples"),
        "investigation.counterexamples",
    )
    counter_keys = {"searched", "explained", "unexplained"}
    _require_exact_keys(counterexamples, counter_keys, "investigation.counterexamples")
    if not isinstance(counterexamples.get("searched"), bool):
        raise InvestigationError("counterexamples.searchedはbooleanである必要があります")
    _require_string_list(counterexamples, "explained", "investigation.counterexamples")
    unexplained = _require_string_list(
        counterexamples,
        "unexplained",
        "investigation.counterexamples",
    )

    pairs = data.get("boundary_pairs")
    if not isinstance(pairs, list):
        raise InvestigationError("boundary_pairsはarrayである必要があります")
    pair_keys = {"fires", "does_not_fire", "distinguishing_condition", "scope_effect"}
    for pair in pairs:
        item = _require_dict(pair, "boundary_pairs[]")
        _require_exact_keys(item, pair_keys, "boundary_pairs[]")
        for key in pair_keys:
            _require_string(item, key, "boundary_pairs[]")

    if not isinstance(data.get("existing_rule_analysis"), str):
        raise InvestigationError("existing_rule_analysisはstringである必要があります")
    semantic_risks = _require_string_list(data, "semantic_risks", "investigation")
    for key in ("provenance_reviewed", "fixed_threshold_only", "frequency_only", "duplicate_rule"):
        if not isinstance(data.get(key), bool):
            raise InvestigationError(f"investigation.{key}はbooleanである必要があります")
    evals = _require_dict(data.get("proposed_evals"), "investigation.proposed_evals")
    eval_keys = {"positive", "negative", "boundary"}
    _require_exact_keys(evals, eval_keys, "investigation.proposed_evals")
    for key in eval_keys:
        _require_string_list(evals, key, "investigation.proposed_evals")
    decision = _require_dict(data.get("decision"), "investigation.decision")
    _require_exact_keys(decision, {"status", "reason"}, "investigation.decision")
    if decision.get("status") not in DECISIONS:
        raise InvestigationError("investigation.decision.statusが不正です")
    _require_string(decision, "reason", "investigation.decision")

    blockers: list[str] = []
    if decision["status"] == "PROMOTE":
        blockers.extend(bundle["readiness"]["blockers"])
        if not data["provenance_reviewed"]:
            blockers.append("provenance reviewが未完了")
        if data["fixed_threshold_only"]:
            blockers.append("固定閾値だけを根拠にしている")
        if data["frequency_only"]:
            blockers.append("頻度だけを根拠にしている")
        if data["duplicate_rule"]:
            blockers.append("既存ruleのduplicateである")
        if not counterexamples["searched"]:
            blockers.append("counterexample searchが未実施")
        if unexplained:
            blockers.append("未説明のcounterexampleが残っている")
        if len(examples) < 2 or len(example_groups) < 2:
            blockers.append("独立したsupport exampleが2件未満")
        if not bundle["selection"]["control_record_ids"]:
            blockers.append("negative controlが未選択")
        selected_controls = set(bundle["selection"]["control_record_ids"])
        if not selected_controls <= set(record_ids):
            blockers.append("選択したcontrolがresult.record_idsに含まれていない")
        accounted_controls = set(counterexamples["explained"]) | {
            pair["does_not_fire"] for pair in pairs
        }
        if missing_controls := selected_controls - accounted_controls:
            blockers.append(
                "未分析のcontrolが残っている: " + ", ".join(sorted(missing_controls))
            )
        if not pairs:
            blockers.append("boundary pairがない")
        if not support["mechanism"].strip():
            blockers.append("頻度以外のmechanismが説明されていない")
        if not data["existing_rule_analysis"].strip():
            blockers.append("existing rule analysisがない")
        if not semantic_risks:
            blockers.append("semantic risk分析がない")
        for key in eval_keys:
            if not evals[key]:
                blockers.append(f"{key} eval proposalがない")

    identity = {key: value for key, value in data.items() if key != "id"}
    data["id"] = _hash_id("rfi", identity)
    return data, list(dict.fromkeys(blockers))


def build_rule_proposal(result: dict, bundle: dict, rule_diff: str, *, clock: Callable[[], str] = _utc_now) -> dict:
    validated, blockers = validate_investigation_result(result, bundle)
    if validated["decision"]["status"] != "PROMOTE":
        raise InvestigationError("PROMOTEと判断されたinvestigationだけがproposalを作成できます")
    if blockers:
        raise InvestigationError("proposal gateを通過できません: " + "; ".join(blockers))
    if not rule_diff.strip():
        raise InvestigationError("review対象のrule diffが必要です")
    support_ids = validated["support"]["examples"]
    records_by_id = {record["id"]: record for record in bundle["records"]}
    correlation_groups = sorted(
        {records_by_id[record_id]["source"]["correlation_group"] for record_id in support_ids}
    )
    identity = {
        "investigation_id": validated["id"],
        "rule_diff": rule_diff.strip(),
        "evals": validated["proposed_evals"],
    }
    proposal = {
        "id": _hash_id("rfp", identity),
        "schema_version": 1,
        "investigation_id": validated["id"],
        "created_at": clock(),
        "status": "PROMOTE",
        "hypothesis": validated["hypothesis"],
        "scope": {
            key: deepcopy(validated["scope"][key])
            for key in ("languages", "genres", "readers", "purposes")
        },
        "mechanism": validated["support"]["mechanism"],
        "support": {
            "independent_sources": validated["support"]["independent_sources"],
            "record_ids": deepcopy(support_ids),
            "correlation_groups": correlation_groups,
        },
        "counterexamples": deepcopy(validated["counterexamples"]),
        "boundary_pairs": deepcopy(validated["boundary_pairs"]),
        "existing_rule_analysis": validated["existing_rule_analysis"],
        "semantic_risks": deepcopy(validated["semantic_risks"]),
        "provenance_reviewed": validated["provenance_reviewed"],
        "fixed_threshold_only": validated["fixed_threshold_only"],
        "frequency_only": validated["frequency_only"],
        "duplicate_rule": validated["duplicate_rule"],
        "rule_diff": rule_diff.strip(),
        "evals": deepcopy(validated["proposed_evals"]),
        "regressions": {
            "existing_evals": "not-run",
            "semantic_preservation": "not-run",
            "unnecessary_revision": "not-run",
            "literal": "not-run",
            "register": "not-run",
        },
        "human_approval": {
            "approved": False,
            "reviewer": None,
            "approved_at": None,
        },
    }
    return proposal


def read_json_file(path: Path, context: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvestigationError(f"{context}を読み込めません: {path}: {exc}") from exc
    return _require_dict(data, context)


__all__ = [
    "InvestigationError",
    "build_investigation_bundle",
    "build_rule_proposal",
    "read_json_file",
    "validate_bundle_against_store",
    "validate_investigation_bundle",
    "validate_investigation_result",
]
