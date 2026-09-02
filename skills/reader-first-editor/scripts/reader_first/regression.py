"""Provider-neutralなregression plan、run、report、rule apply gate。"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .eval_validation import STRUCTURED_ORACLE_VALUES, validate_eval_oracles
from .schema_validation import is_schema_version
from .state import STATE_DIRECTORIES, LocalCorpusStore, StoreError

REQUIRED_PROVIDERS = ["codex", "github-copilot"]
DIMENSIONS = {
    "semantic_preservation",
    "unnecessary_revision",
    "literal",
    "register",
}
CATEGORIES = {"existing", "corpus", "positive", "negative", "boundary"}
EXPECTED_BEHAVIORS = {"change", "no-change", "review-only", "context-dependent"}
STRUCTURED_ORACLES = {
    "expected_risks": (
        "observed_risks",
        STRUCTURED_ORACLE_VALUES["expected_risks"],
    ),
    "expected_statuses": (
        "observed_statuses",
        STRUCTURED_ORACLE_VALUES["expected_statuses"],
    ),
    "expected_evidence_types": (
        "observed_evidence_types",
        STRUCTURED_ORACLE_VALUES["expected_evidence_types"],
    ),
}
ALLOWED_RULE_TARGETS = (
    re.compile(r"skills/reader-first-editor/SKILL\.md"),
    re.compile(r"skills/reader-first-editor/references/(?:[^/]+/)*[^/]+\.md"),
)
ALLOWED_EVAL_TARGET = re.compile(r"skills/reader-first-editor/evals/[^/]+\.yaml")


class RegressionError(StoreError):
    """Regression artifactまたはrule apply gateが不正である。"""


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


def _hash_id(prefix: str, value: object) -> str:
    return f"{prefix}-{_canonical_hash(value)[:20]}"


def rule_diff_hash(rule_diff: str) -> str:
    return f"sha256:{hashlib.sha256(rule_diff.strip().encode('utf-8')).hexdigest()}"


def _require_dict(value: object, context: str) -> dict:
    if not isinstance(value, dict):
        raise RegressionError(f"{context}はobjectである必要があります")
    return value


def _exact_keys(value: dict, keys: set[str], context: str) -> None:
    if missing := sorted(keys - value.keys()):
        raise RegressionError(f"{context}に必須keyがありません: {', '.join(missing)}")
    if unknown := sorted(value.keys() - keys):
        raise RegressionError(f"{context}に未知のkeyがあります: {', '.join(unknown)}")


def _string(value: dict, key: str, context: str, *, empty: bool = False) -> str:
    item = value.get(key)
    if not isinstance(item, str) or (not empty and not item.strip()):
        raise RegressionError(f"{context}.{key}はstringである必要があります")
    return item


def _strings(
    value: dict,
    key: str,
    context: str,
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> list[str]:
    items = value.get(key)
    if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
        raise RegressionError(f"{context}.{key}はstring arrayである必要があります")
    if nonempty and not items:
        raise RegressionError(f"{context}.{key}は1件以上必要です")
    if unique and len(items) != len(set(items)):
        raise RegressionError(f"{context}.{key}に重複があります")
    return items


def validate_rule_proposal(proposal: object) -> dict:
    data = deepcopy(_require_dict(proposal, "proposal"))
    keys = {
        "id",
        "schema_version",
        "investigation_id",
        "created_at",
        "status",
        "hypothesis",
        "scope",
        "mechanism",
        "support",
        "counterexamples",
        "boundary_pairs",
        "existing_rule_analysis",
        "semantic_risks",
        "provenance_reviewed",
        "fixed_threshold_only",
        "frequency_only",
        "duplicate_rule",
        "rule_diff",
        "evals",
        "regressions",
        "human_approval",
    }
    _exact_keys(data, keys, "proposal")
    if not is_schema_version(data.get("schema_version")) or data.get("status") != "PROMOTE":
        raise RegressionError("PROMOTE statusのschema v1 proposalが必要です")
    if not data.get("provenance_reviewed"):
        raise RegressionError("proposalのprovenance reviewが未完了です")
    for key in ("fixed_threshold_only", "frequency_only", "duplicate_rule"):
        if data.get(key) is not False:
            raise RegressionError(f"proposal.{key}によりapplyできません")
    scope = _require_dict(data.get("scope"), "proposal.scope")
    for key in ("languages", "genres", "readers", "purposes"):
        _strings(scope, key, "proposal.scope", nonempty=True)
    support = _require_dict(data.get("support"), "proposal.support")
    record_ids = _strings(support, "record_ids", "proposal.support", nonempty=True, unique=True)
    correlations = _strings(
        support,
        "correlation_groups",
        "proposal.support",
        nonempty=True,
        unique=True,
    )
    if support.get("independent_sources") != len(correlations) or len(record_ids) < 2:
        raise RegressionError("proposalのindependent supportが不足しています")
    counter = _require_dict(data.get("counterexamples"), "proposal.counterexamples")
    if counter.get("searched") is not True or counter.get("unexplained") != []:
        raise RegressionError("proposalに未探索・未説明のcounterexampleがあります")
    if not isinstance(data.get("boundary_pairs"), list) or not data["boundary_pairs"]:
        raise RegressionError("proposalにboundary pairがありません")
    _string(data, "mechanism", "proposal")
    _string(data, "existing_rule_analysis", "proposal")
    if not isinstance(data.get("semantic_risks"), list) or not data["semantic_risks"]:
        raise RegressionError("proposalにsemantic risk分析がありません")
    rule_diff = data.get("rule_diff")
    if not isinstance(rule_diff, str) or not rule_diff.strip():
        raise RegressionError("proposalにrule diffがありません")
    evals = _require_dict(data.get("evals"), "proposal.evals")
    categorized_eval_ids: dict[str, list[str]] = {}
    for key in ("positive", "negative", "boundary"):
        categorized_eval_ids[key] = _strings(
            evals,
            key,
            "proposal.evals",
            nonempty=True,
            unique=True,
        )
    eval_categories_by_id: dict[str, list[str]] = {}
    for category, eval_ids in categorized_eval_ids.items():
        for eval_id in eval_ids:
            eval_categories_by_id.setdefault(eval_id, []).append(category)
    cross_category_duplicates = {
        eval_id: categories
        for eval_id, categories in eval_categories_by_id.items()
        if len(categories) > 1
    }
    if cross_category_duplicates:
        details = ", ".join(
            f"{eval_id} ({'/'.join(categories)})"
            for eval_id, categories in sorted(cross_category_duplicates.items())
        )
        raise RegressionError(f"proposal eval IDをcategory間で重複指定できません: {details}")
    regressions = _require_dict(data.get("regressions"), "proposal.regressions")
    if set(regressions) != {
        "existing_evals",
        "semantic_preservation",
        "unnecessary_revision",
        "literal",
        "register",
    } or set(regressions.values()) != {"not-run"}:
        raise RegressionError("proposal draftのregression statusはnot-runである必要があります")
    approval = _require_dict(data.get("human_approval"), "proposal.human_approval")
    if approval != {"approved": False, "reviewer": None, "approved_at": None}:
        raise RegressionError("proposal draftへhuman approvalを直接書き込めません")
    identity = {
        "investigation_id": data["investigation_id"],
        "rule_diff": rule_diff.strip(),
        "evals": evals,
    }
    if data.get("id") != _hash_id("rfp", identity):
        raise RegressionError("proposal IDが内容から再計算した値と一致しません")
    return data


def _read_json(path: Path, context: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegressionError(f"{context}を読み込めません: {path}: {exc}") from exc


def _provider_matrix(value: object) -> list[dict]:
    data = _require_dict(value, "provider matrix")
    _exact_keys(data, {"providers"}, "provider matrix")
    providers = data.get("providers")
    if not isinstance(providers, list) or not providers:
        raise RegressionError("provider matrix.providersがありません")
    normalized: list[dict] = []
    keys = {"provider", "model", "model_version", "host_version", "repeats"}
    seen: set[tuple[str, str, str, str]] = set()
    for entry in providers:
        item = _require_dict(entry, "provider matrix.providers[]")
        _exact_keys(item, keys, "provider matrix.providers[]")
        for key in ("provider", "model", "model_version", "host_version"):
            _string(item, key, "provider matrix.providers[]")
        repeats = item.get("repeats")
        if not isinstance(repeats, int) or isinstance(repeats, bool) or repeats < 1:
            raise RegressionError("provider repeatsは1以上のintegerである必要があります")
        identity = tuple(item[key] for key in ("provider", "model", "model_version", "host_version"))
        if identity in seen:
            raise RegressionError("provider matrix entryが重複しています")
        seen.add(identity)
        normalized.append(deepcopy(item))
    return sorted(
        normalized,
        key=lambda item: (
            item["provider"],
            item["model"],
            item["model_version"],
            item["host_version"],
        ),
    )


def _bundled_cases(eval_dir: Path) -> list[dict]:
    cases: list[dict] = []
    for path in sorted(eval_dir.glob("*.yaml")):
        suite_data = _require_dict(_read_json(path, "bundled eval"), str(path))
        suite = _string(suite_data, "suite", str(path))
        raw_cases = suite_data.get("cases")
        if not isinstance(raw_cases, list):
            raise RegressionError(f"{path}: casesがありません")
        for raw in raw_cases:
            case = _require_dict(raw, f"{path}: case")
            case_id = _string(case, "id", f"{path}: case")
            mode = _string(case, "mode", f"{path}: {case_id}")
            expected_behavior = case.get(
                "expected_behavior",
                "review-only"
                if mode in {"review", "repository-review"}
                else "context-dependent",
            )
            if expected_behavior not in EXPECTED_BEHAVIORS:
                raise RegressionError(f"{path}: {case_id}のexpected_behaviorが不正です")
            if oracle_errors := validate_eval_oracles(case):
                raise RegressionError(
                    f"{path}: {case_id}のstructured oracleが不正です: "
                    + "; ".join(oracle_errors)
                )
            must_preserve = case.get("must_preserve", [])
            must_not = [
                *case.get("must_not_add", []),
                *case.get("must_not_claim", []),
            ]
            if not all(isinstance(item, str) for item in [*must_preserve, *must_not]):
                raise RegressionError(f"{path}: {case_id}のconstraintが不正です")
            structured_oracles: dict[str, list[str]] = {}
            for key, (_, allowed_values) in STRUCTURED_ORACLES.items():
                if key in case:
                    value = case[key]
                    if not isinstance(value, list) or not all(
                        isinstance(item, str) for item in value
                    ):
                        raise RegressionError(f"{path}: {case_id}の{key}が不正です")
                    if unknown := sorted(set(value) - allowed_values):
                        raise RegressionError(
                            f"{path}: {case_id}の{key}に未知の値があります: "
                            f"{', '.join(unknown)}"
                        )
                    structured_oracles[key] = list(value)
            cases.append(
                {
                    "id": f"bundled:{suite}:{case_id}",
                    "source": "bundled",
                    "category": "existing",
                    "suite": suite,
                    "mode": mode,
                    "language": case["language"],
                    "expected_behavior": expected_behavior,
                    "input": {
                        "kind": "embedded",
                        "value": case["input"],
                        "record_id": None,
                        "record_path": None,
                        "content_hash": f"sha256:{hashlib.sha256(case['input'].encode('utf-8')).hexdigest()}",
                        "requires_network": False,
                    },
                    "expected": case["expected"],
                    "must_preserve": list(must_preserve),
                    "must_not": must_not,
                    **structured_oracles,
                }
            )
    return cases


def _corpus_case(store: LocalCorpusStore, record_id: str) -> dict:
    record = store.load_record(record_id)
    if record["decision"]["state"] != "promoted":
        raise RegressionError("corpus regressionにはpromoted recordが必要です")
    state_path = store.root / STATE_DIRECTORIES["promoted"] / f"{record_id}.json"
    storage = record["text"]["storage"]
    return {
        "id": f"corpus:{record_id}",
        "source": "corpus",
        "category": "corpus",
        "suite": "local-corpus",
        "mode": (
            "revise-safe"
            if record["annotations"]["expected_behavior"] == "change"
            else "review"
        ),
        "language": record["language"],
        "expected_behavior": record["annotations"]["expected_behavior"],
        "input": {
            "kind": "immutable-reference" if storage == "reference-only" else "record-reference",
            "value": None,
            "record_id": record_id,
            "record_path": str(state_path),
            "content_hash": record["text"]["content_hash"],
            "requires_network": storage == "reference-only",
        },
        "expected": record["annotations"]["rationale"],
        "must_preserve": deepcopy(record["annotations"]["semantic_invariants"]),
        "must_not": deepcopy(record["annotations"]["do_not_change"]),
    }


def _proposal_cases(value: object, proposal: dict) -> list[dict]:
    data = _require_dict(value, "candidate evals")
    _exact_keys(data, {"positive", "negative", "boundary"}, "candidate evals")
    cases: list[dict] = []
    keys = {
        "id",
        "mode",
        "language",
        "input",
        "expected",
        "expected_behavior",
        "must_preserve",
        "must_not",
    }
    for category in ("positive", "negative", "boundary"):
        entries = data.get(category)
        if not isinstance(entries, list):
            raise RegressionError(f"candidate evals.{category}はarrayである必要があります")
        ids: list[str] = []
        for entry in entries:
            item = _require_dict(entry, f"candidate evals.{category}[]")
            _exact_keys(item, keys, f"candidate evals.{category}[]")
            case_id = _string(item, "id", f"candidate evals.{category}[]")
            ids.append(case_id)
            for key in ("mode", "language", "input", "expected", "expected_behavior"):
                _string(item, key, f"candidate evals.{category}[]")
            for key in ("must_preserve", "must_not"):
                _strings(item, key, f"candidate evals.{category}[]")
            if item["language"] not in {"ja", "en"}:
                raise RegressionError("candidate eval languageが不正です")
            if item["expected_behavior"] not in {
                "change",
                "no-change",
                "review-only",
                "context-dependent",
            }:
                raise RegressionError("candidate eval expected_behaviorが不正です")
            cases.append(
                {
                    "id": f"proposal:{category}:{case_id}",
                    "source": "proposal",
                    "category": category,
                    "suite": f"proposal-{proposal['id']}",
                    "mode": item["mode"],
                    "language": item["language"],
                    "expected_behavior": item["expected_behavior"],
                    "input": {
                        "kind": "embedded",
                        "value": item["input"],
                        "record_id": None,
                        "record_path": None,
                        "content_hash": f"sha256:{hashlib.sha256(item['input'].encode('utf-8')).hexdigest()}",
                        "requires_network": False,
                    },
                    "expected": item["expected"],
                    "must_preserve": deepcopy(item["must_preserve"]),
                    "must_not": deepcopy(item["must_not"]),
                }
            )
        if ids != proposal["evals"][category]:
            raise RegressionError(
                f"candidate evals.{category}のIDとproposalが順序を含め一致しません"
            )
    return cases


def build_regression_plan(
    proposal: dict,
    store: LocalCorpusStore,
    *,
    eval_dir: Path,
    provider_matrix: object,
    candidate_evals: object,
    corpus_record_ids: list[str],
    clock: Callable[[], str] = _utc_now,
) -> dict:
    proposal = validate_rule_proposal(proposal)
    if not corpus_record_ids:
        raise RegressionError("new corpus evalを1件以上指定してください")
    providers = _provider_matrix(provider_matrix)
    cases = [
        *_bundled_cases(eval_dir),
        *[_corpus_case(store, record_id) for record_id in sorted(set(corpus_record_ids))],
        *_proposal_cases(candidate_evals, proposal),
    ]
    case_ids = [case["id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise RegressionError("regression case IDが重複しています")
    body = {
        "schema_version": 1,
        "proposal_id": proposal["id"],
        "diff_hash": rule_diff_hash(proposal["rule_diff"]),
        "providers": providers,
        "cases": cases,
        "requirements": {
            "required_providers": REQUIRED_PROVIDERS,
            "all_repeats_required": True,
            "all_cases_required": True,
            "unsupported_is_failure": True,
        },
    }
    plan = {"id": _hash_id("rfrp", body), **body, "created_at": clock()}
    return validate_regression_plan(plan)


def validate_regression_plan(plan: object) -> dict:
    data = deepcopy(_require_dict(plan, "regression plan"))
    keys = {
        "id",
        "schema_version",
        "proposal_id",
        "diff_hash",
        "created_at",
        "providers",
        "cases",
        "requirements",
    }
    _exact_keys(data, keys, "regression plan")
    if not is_schema_version(data.get("schema_version")):
        raise RegressionError("regression plan schema_versionが未対応です")
    _string(data, "created_at", "regression plan")
    providers = _provider_matrix({"providers": data.get("providers")})
    if providers != data["providers"]:
        raise RegressionError("regression plan provider順がcanonicalではありません")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RegressionError("regression planにcaseがありません")
    case_ids: list[str] = []
    for case in cases:
        item = _require_dict(case, "regression plan.cases[]")
        case_ids.append(_string(item, "id", "regression plan.cases[]"))
        if item.get("category") not in CATEGORIES:
            raise RegressionError("regression case categoryが不正です")
        if item.get("expected_behavior") not in EXPECTED_BEHAVIORS:
            raise RegressionError("regression case expected_behaviorが不正です")
        if oracle_errors := validate_eval_oracles(item):
            raise RegressionError(
                "regression plan.cases[]のstructured oracleが不正です: "
                + "; ".join(oracle_errors)
            )
        for key, (_, allowed_values) in STRUCTURED_ORACLES.items():
            if key in item:
                values = _strings(item, key, "regression plan.cases[]", unique=True)
                if unknown := sorted(set(values) - allowed_values):
                    raise RegressionError(
                        f"regression plan.cases[].{key}に未知の値があります: "
                        f"{', '.join(unknown)}"
                    )
    if len(case_ids) != len(set(case_ids)):
        raise RegressionError("regression plan case IDが重複しています")
    if {case["category"] for case in cases} != CATEGORIES:
        raise RegressionError("existing/corpus/positive/negative/boundary caseが全て必要です")
    requirements = _require_dict(data.get("requirements"), "regression plan.requirements")
    if requirements != {
        "required_providers": REQUIRED_PROVIDERS,
        "all_repeats_required": True,
        "all_cases_required": True,
        "unsupported_is_failure": True,
    }:
        raise RegressionError("regression planのapply requirementsが不正です")
    body = {key: data[key] for key in keys - {"id", "created_at"}}
    if data.get("id") != _hash_id("rfrp", body):
        raise RegressionError("regression plan IDが内容から再計算した値と一致しません")
    return data


def validate_regression_run(run: object, plan: dict) -> dict:
    plan = validate_regression_plan(plan)
    data = deepcopy(_require_dict(run, "regression run"))
    keys = {
        "id",
        "schema_version",
        "plan_id",
        "provider",
        "model",
        "model_version",
        "host_version",
        "repeat_index",
        "created_at",
        "cases",
    }
    _exact_keys(data, keys, "regression run")
    if not is_schema_version(data.get("schema_version")) or data.get("plan_id") != plan["id"]:
        raise RegressionError("regression runのschemaまたはplan IDが不正です")
    for key in ("provider", "model", "model_version", "host_version", "created_at"):
        _string(data, key, "regression run")
    matching = [
        provider
        for provider in plan["providers"]
        if all(
            provider[key] == data[key]
            for key in ("provider", "model", "model_version", "host_version")
        )
    ]
    if len(matching) != 1:
        raise RegressionError("regression run metadataがprovider matrixと一致しません")
    repeat_index = data.get("repeat_index")
    if not isinstance(repeat_index, int) or isinstance(repeat_index, bool) or not 1 <= repeat_index <= matching[0]["repeats"]:
        raise RegressionError("regression run repeat_indexがplan範囲外です")
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise RegressionError("regression run.casesはarrayである必要があります")
    case_ids: list[str] = []
    required_case_keys = {"id", "status", "expected_behavior_match", "dimensions", "notes"}
    optional_case_keys = {
        observed_key for observed_key, _ in STRUCTURED_ORACLES.values()
    }
    plan_cases = {case["id"]: case for case in plan["cases"]}
    for case in cases:
        item = _require_dict(case, "regression run.cases[]")
        if missing := sorted(required_case_keys - item.keys()):
            raise RegressionError(
                "regression run.cases[]に必須keyがありません: " + ", ".join(missing)
            )
        if unknown := sorted(item.keys() - required_case_keys - optional_case_keys):
            raise RegressionError(
                "regression run.cases[]に未知のkeyがあります: " + ", ".join(unknown)
            )
        case_id = _string(item, "id", "regression run.cases[]")
        case_ids.append(case_id)
        status = item.get("status")
        if status not in {"pass", "fail", "unsupported", "error"}:
            raise RegressionError("regression case statusが不正です")
        if not isinstance(item.get("expected_behavior_match"), bool):
            raise RegressionError("expected_behavior_matchはbooleanである必要があります")
        dimensions = _require_dict(item.get("dimensions"), "regression case.dimensions")
        _exact_keys(dimensions, DIMENSIONS, "regression case.dimensions")
        if any(value not in {"pass", "fail", "not-applicable"} for value in dimensions.values()):
            raise RegressionError("regression dimension statusが不正です")
        _string(item, "notes", "regression case", empty=True)
        planned_case = plan_cases.get(case_id)
        if planned_case is None:
            continue
        for expected_key, (observed_key, allowed_values) in STRUCTURED_ORACLES.items():
            if expected_key not in planned_case:
                if observed_key in item:
                    observed = _strings(
                        item,
                        observed_key,
                        "regression run.cases[]",
                        unique=True,
                    )
                    if unknown := sorted(set(observed) - allowed_values):
                        raise RegressionError(
                            f"regression run.cases[].{observed_key}に未知の値があります: "
                            f"{', '.join(unknown)}"
                        )
                continue
            if status in {"unsupported", "error"} and observed_key not in item:
                continue
            observed = _strings(
                item,
                observed_key,
                "regression run.cases[]",
                unique=True,
            )
            if unknown := sorted(set(observed) - allowed_values):
                raise RegressionError(
                    f"regression run.cases[].{observed_key}に未知の値があります: "
                    f"{', '.join(unknown)}"
                )
            expected_values = set(planned_case[expected_key])
            observed_values = set(observed)
            if status == "pass" and expected_values != observed_values:
                raise RegressionError(
                    f"regression run.cases[].{observed_key}が期待値と完全一致しません: "
                    f"expected={', '.join(sorted(expected_values))}; "
                    f"observed={', '.join(sorted(observed_values))}"
                )
    expected_ids = [case["id"] for case in plan["cases"]]
    if case_ids != expected_ids:
        raise RegressionError("regression runはplanの全caseを同じ順序で含める必要があります")
    body = {key: data[key] for key in keys - {"id"}}
    data["id"] = _hash_id("rfrr", body)
    return data


def build_regression_report(
    plan: dict,
    runs: list[dict],
    *,
    clock: Callable[[], str] = _utc_now,
) -> dict:
    plan = validate_regression_plan(plan)
    validated_runs = [validate_regression_run(run, plan) for run in runs]
    expected_keys = {
        (
            provider["provider"],
            provider["model"],
            provider["model_version"],
            provider["host_version"],
            repeat,
        )
        for provider in plan["providers"]
        for repeat in range(1, provider["repeats"] + 1)
    }
    actual_keys = [
        (
            run["provider"],
            run["model"],
            run["model_version"],
            run["host_version"],
            run["repeat_index"],
        )
        for run in validated_runs
    ]
    blockers: list[str] = []
    if duplicates := [key for key, count in Counter(actual_keys).items() if count > 1]:
        blockers.append(f"同じprovider/repeatのrunが重複しています: {len(duplicates)}件")
    missing = expected_keys - set(actual_keys)
    if missing:
        blockers.append(f"required runが{len(missing)}件不足しています")

    plan_cases = {case["id"]: case for case in plan["cases"]}
    results = [case for run in validated_runs for case in run["cases"]]
    status_counts = Counter(result["status"] for result in results)
    no_change = [
        result
        for run in validated_runs
        for result in run["cases"]
        if plan_cases[result["id"]]["expected_behavior"] == "no-change"
    ]
    no_change_matched = sum(
        result["status"] == "pass" and result["expected_behavior_match"]
        for result in no_change
    )

    def category_gate(category: str) -> str:
        ids = {case["id"] for case in plan["cases"] if case["category"] == category}
        selected = [result for result in results if result["id"] in ids]
        expected_count = len(ids) * len(expected_keys)
        return (
            "pass"
            if ids
            and len(selected) == expected_count
            and all(
                result["status"] == "pass" and result["expected_behavior_match"]
                for result in selected
            )
            else "fail"
        )

    def dimension_gate(dimension: str) -> str:
        values = [result["dimensions"][dimension] for result in results]
        return "pass" if "pass" in values and "fail" not in values else "fail"

    completed_providers = {run["provider"] for run in validated_runs}
    repeat_complete = not missing and len(actual_keys) == len(expected_keys) and not duplicates
    gates = {
        "existing_evals": category_gate("existing"),
        "corpus_evals": category_gate("corpus"),
        "positive": category_gate("positive"),
        "negative": category_gate("negative"),
        "boundary": category_gate("boundary"),
        "semantic_preservation": dimension_gate("semantic_preservation"),
        "unnecessary_revision": dimension_gate("unnecessary_revision"),
        "literal": dimension_gate("literal"),
        "register": dimension_gate("register"),
        "no_change_accuracy": (
            "pass" if no_change and no_change_matched == len(no_change) else "fail"
        ),
        "provider_compatibility": (
            "pass"
            if set(plan["requirements"]["required_providers"]) <= completed_providers
            else "fail"
        ),
        "repeat_completeness": "pass" if repeat_complete else "fail",
    }
    for gate, status in gates.items():
        if status == "fail":
            blockers.append(f"regression gate failed: {gate}")
    metrics = {
        "case_results": len(results),
        "passed": status_counts["pass"],
        "failed": status_counts["fail"],
        "unsupported": status_counts["unsupported"],
        "errors": status_counts["error"],
        "no_change_total": len(no_change),
        "no_change_matched": no_change_matched,
        "no_change_accuracy": (
            round(no_change_matched / len(no_change), 6) if no_change else None
        ),
    }
    body = {
        "schema_version": 1,
        "plan_id": plan["id"],
        "proposal_id": plan["proposal_id"],
        "diff_hash": plan["diff_hash"],
        "run_ids": sorted(run["id"] for run in validated_runs),
        "coverage": {
            "providers_planned": len(plan["providers"]),
            "providers_completed": len(completed_providers),
            "runs_planned": len(expected_keys),
            "runs_completed": len(validated_runs),
            "cases_per_run": len(plan["cases"]),
        },
        "metrics": metrics,
        "gates": gates,
        "status": "pass" if not blockers else "fail",
        "blockers": list(dict.fromkeys(blockers)),
    }
    report = {"id": _hash_id("rfrt", body), **body, "created_at": clock()}
    return validate_regression_report(report)


def validate_regression_report(report: object) -> dict:
    data = deepcopy(_require_dict(report, "regression report"))
    keys = {
        "id",
        "schema_version",
        "plan_id",
        "proposal_id",
        "diff_hash",
        "created_at",
        "run_ids",
        "coverage",
        "metrics",
        "gates",
        "status",
        "blockers",
    }
    _exact_keys(data, keys, "regression report")
    if not is_schema_version(data.get("schema_version")):
        raise RegressionError("regression report schema_versionが未対応です")
    _string(data, "created_at", "regression report")
    run_ids = _strings(data, "run_ids", "regression report", nonempty=True, unique=True)
    if any(not re.fullmatch(r"rfrr-[0-9a-f]{20}", run_id) for run_id in run_ids):
        raise RegressionError("regression report run IDが不正です")
    gates = _require_dict(data.get("gates"), "regression report.gates")
    if set(gates) != {
        "existing_evals",
        "corpus_evals",
        "positive",
        "negative",
        "boundary",
        "semantic_preservation",
        "unnecessary_revision",
        "literal",
        "register",
        "no_change_accuracy",
        "provider_compatibility",
        "repeat_completeness",
    } or any(status not in {"pass", "fail"} for status in gates.values()):
        raise RegressionError("regression report gateが不正です")
    blockers = _strings(data, "blockers", "regression report")
    expected_status = "pass" if all(status == "pass" for status in gates.values()) and not blockers else "fail"
    if data.get("status") != expected_status:
        raise RegressionError("regression report statusとgateが一致しません")
    body = {key: data[key] for key in keys - {"id", "created_at"}}
    if data.get("id") != _hash_id("rfrt", body):
        raise RegressionError("regression report IDが内容から再計算した値と一致しません")
    return data


def validate_report_against_runs(report: object, plan: dict, runs: list[dict]) -> dict:
    """Stored reportを、そのreportが参照するplanとrunから再計算する。"""

    data = validate_regression_report(report)
    rebuilt = build_regression_report(
        plan,
        runs,
        clock=lambda: data["created_at"],
    )
    if rebuilt != data:
        raise RegressionError("regression reportがstored plan/runの再集計と一致しません")
    return data


def build_rule_approval(
    proposal: dict,
    report: dict,
    *,
    reviewer: str,
    reason: str,
    clock: Callable[[], str] = _utc_now,
) -> dict:
    proposal = validate_rule_proposal(proposal)
    report = validate_regression_report(report)
    if report["status"] != "pass":
        raise RegressionError("全regression gateを通過したreportだけを承認できます")
    diff_hash = rule_diff_hash(proposal["rule_diff"])
    if report["proposal_id"] != proposal["id"] or report["diff_hash"] != diff_hash:
        raise RegressionError("reportとproposalのdiff identityが一致しません")
    if not reviewer.strip() or not reason.strip():
        raise RegressionError("reviewer attestationと承認理由が必要です")
    identity = {
        "proposal_id": proposal["id"],
        "report_id": report["id"],
        "diff_hash": diff_hash,
        "reviewer": reviewer.strip(),
        "reason": reason.strip(),
    }
    approval = {
        "id": _hash_id("rfa", identity),
        "schema_version": 1,
        "proposal_id": proposal["id"],
        "report_id": report["id"],
        "diff_hash": diff_hash,
        "approved": True,
        "reviewer": reviewer.strip(),
        "approved_at": clock(),
        "reason": reason.strip(),
    }
    return validate_rule_approval(approval)


def validate_rule_approval(approval: object) -> dict:
    data = deepcopy(_require_dict(approval, "rule approval"))
    keys = {
        "id",
        "schema_version",
        "proposal_id",
        "report_id",
        "diff_hash",
        "approved",
        "reviewer",
        "approved_at",
        "reason",
    }
    _exact_keys(data, keys, "rule approval")
    if not is_schema_version(data.get("schema_version")) or data.get("approved") is not True:
        raise RegressionError("approved schema v1 artifactが必要です")
    for key in ("reviewer", "approved_at", "reason"):
        _string(data, key, "rule approval")
    identity = {
        key: data[key]
        for key in ("proposal_id", "report_id", "diff_hash", "reviewer", "reason")
    }
    if data.get("id") != _hash_id("rfa", identity):
        raise RegressionError("approval IDが内容から再計算した値と一致しません")
    return data


def validate_apply_artifacts(
    proposal: dict,
    plan: dict,
    report: dict,
    approval: dict,
) -> tuple[dict, dict, dict, dict]:
    proposal = validate_rule_proposal(proposal)
    plan = validate_regression_plan(plan)
    report = validate_regression_report(report)
    approval = validate_rule_approval(approval)
    diff_hash = rule_diff_hash(proposal["rule_diff"])
    if report["status"] != "pass":
        raise RegressionError("regression reportがpassではありません")
    if (
        report["proposal_id"] != proposal["id"]
        or plan["proposal_id"] != proposal["id"]
        or report["plan_id"] != plan["id"]
        or plan["diff_hash"] != diff_hash
        or report["diff_hash"] != diff_hash
        or approval["proposal_id"] != proposal["id"]
        or approval["report_id"] != report["id"]
        or approval["diff_hash"] != diff_hash
    ):
        raise RegressionError("proposal、report、approvalのidentityが一致しません")
    return proposal, plan, report, approval


def parse_rule_patch(rule_diff: str) -> list[str]:
    if any(marker in rule_diff for marker in ("GIT binary patch", "Binary files ", "deleted file mode", "rename from ", "rename to ")):
        raise RegressionError("binary、削除、renameをrule patchへ含められません")
    targets: list[str] = []
    for line in rule_diff.splitlines():
        match = re.fullmatch(r"diff --git a/(\S+) b/(\S+)", line)
        if match:
            old, new = match.groups()
            if old != new:
                raise RegressionError("renameをrule patchへ含められません")
            path = Path(new)
            if path.is_absolute() or ".." in path.parts:
                raise RegressionError("rule patchのpath traversalを拒否しました")
            targets.append(new)
    if not targets or len(targets) != len(set(targets)):
        raise RegressionError("rule patchには重複のないdiff --git sectionが必要です")
    if any(
        not any(pattern.fullmatch(path) for pattern in (*ALLOWED_RULE_TARGETS, ALLOWED_EVAL_TARGET))
        for path in targets
    ):
        raise RegressionError("rule patchに許可されていないtargetがあります")
    if not any(any(pattern.fullmatch(path) for pattern in ALLOWED_RULE_TARGETS) for path in targets):
        raise RegressionError("rule patchにSKILL.mdまたはreferenceの変更がありません")
    if not any(ALLOWED_EVAL_TARGET.fullmatch(path) for path in targets):
        raise RegressionError("rule patchにeval updateがありません")
    return targets


def _read_eval_cases(root: Path) -> list[dict]:
    cases: list[dict] = []
    eval_dir = root / "skills/reader-first-editor/evals"
    if not eval_dir.is_dir():
        return cases
    for path in sorted(eval_dir.glob("*.yaml")):
        try:
            suite = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegressionError(f"eval suiteをJSON-compatible YAMLとして読めません: {path}: {exc}") from exc
        if not isinstance(suite, dict) or not isinstance(suite.get("cases"), list):
            raise RegressionError(f"eval suiteにcases arrayがありません: {path}")
        for case in suite["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
                raise RegressionError(f"eval caseにIDがありません: {path}")
            cases.append(case)
    return cases


def _expected_proposal_eval_cases(proposal: dict, plan: dict) -> dict[str, dict]:
    planned = {case["id"]: case for case in plan["cases"] if case.get("source") == "proposal"}
    expected: dict[str, dict] = {}
    for category in ("positive", "negative", "boundary"):
        for eval_id in proposal["evals"][category]:
            planned_id = f"proposal:{category}:{eval_id}"
            case = planned.get(planned_id)
            if case is None:
                raise RegressionError(f"regression planにproposal evalがありません: {eval_id}")
            expected[eval_id] = {
                "id": eval_id,
                "language": case["language"],
                "mode": case["mode"],
                "input": case["input"]["value"],
                "expected": case["expected"],
                "expected_behavior": case["expected_behavior"],
                "must_preserve": case["must_preserve"],
                "must_not_claim": case["must_not"],
            }
    return expected


def _validate_proposal_eval_cases(
    root: Path,
    targets: list[str],
    rule_diff: str,
    proposal: dict,
    plan: dict,
) -> None:
    before = _read_eval_cases(root)
    with tempfile.TemporaryDirectory(prefix="reader-first-editor-evals-") as temporary:
        staged_root = Path(temporary)
        eval_source = root / "skills/reader-first-editor/evals"
        if eval_source.is_dir():
            shutil.copytree(
                eval_source,
                staged_root / "skills/reader-first-editor/evals",
            )
        for relative in targets:
            source = root / relative
            destination = staged_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_file() and not ALLOWED_EVAL_TARGET.fullmatch(relative):
                shutil.copy2(source, destination)
        applied = _git(
            staged_root,
            ["apply", "--whitespace=error-all", "-"],
            input_text=_git_patch_input(rule_diff),
        )
        if applied.returncode:
            raise RegressionError(f"一時領域へrule patchを適用できません: {applied.stderr.strip()}")
        after = _read_eval_cases(staged_root)

    before_ids = {case["id"] for case in before}
    after_counts = Counter(case["id"] for case in after)
    expected = _expected_proposal_eval_cases(proposal, plan)
    added = {case["id"]: case for case in after if case["id"] not in before_ids}
    duplicates = sorted(eval_id for eval_id, count in after_counts.items() if count > 1)
    missing = sorted(set(expected) - set(added))
    unexpected = sorted(set(added) - set(expected))
    mismatched = sorted(
        eval_id
        for eval_id in set(expected) & set(added)
        if added[eval_id] != expected[eval_id]
    )
    errors: list[str] = []
    if missing:
        errors.append("proposal eval IDがありません: " + ", ".join(missing))
    if unexpected:
        errors.append("proposalにないeval IDがあります: " + ", ".join(unexpected))
    if duplicates:
        errors.append("eval IDが重複しています: " + ", ".join(duplicates))
    if mismatched:
        errors.append("proposal eval caseの内容が一致しません: " + ", ".join(mismatched))
    if errors:
        raise RegressionError("rule patchのeval caseがproposalと一致しません: " + "; ".join(errors))


def _git(root: Path, args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def _git_patch_input(rule_diff: str) -> str:
    """Gitへ渡すpatchの末尾に、必要な改行を補う。"""
    return rule_diff if rule_diff.endswith("\n") else rule_diff + "\n"


def preview_rule_apply(
    proposal: dict,
    plan: dict,
    report: dict,
    approval: dict,
    *,
    repository_root: Path,
) -> dict:
    proposal, plan, report, approval = validate_apply_artifacts(
        proposal, plan, report, approval
    )
    root = repository_root.expanduser().resolve()
    top = _git(root, ["rev-parse", "--show-toplevel"])
    if top.returncode or Path(top.stdout.strip()).resolve() != root:
        raise RegressionError("repository_rootにはGit worktree rootを指定してください")
    targets = parse_rule_patch(proposal["rule_diff"])
    for relative in targets:
        target = root / relative
        current = root
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise RegressionError(f"rule patch targetにsymlinkがあります: {relative}")
        if not target.resolve().is_relative_to(root):
            raise RegressionError("rule patch targetがrepository外を指しています")
    status = _git(root, ["status", "--porcelain", "--", *targets])
    if status.returncode or status.stdout.strip():
        raise RegressionError("rule patch対象fileに未commit変更があります")
    check = _git(
        root,
        ["apply", "--check", "--whitespace=error-all", "-"],
        input_text=_git_patch_input(proposal["rule_diff"]),
    )
    if check.returncode:
        raise RegressionError(f"rule patchが適用不能またはno-opです: {check.stderr.strip()}")
    _validate_proposal_eval_cases(
        root,
        targets,
        proposal["rule_diff"],
        proposal,
        plan,
    )
    return {
        "proposal_id": proposal["id"],
        "report_id": report["id"],
        "approval_id": approval["id"],
        "diff_hash": rule_diff_hash(proposal["rule_diff"]),
        "targets": targets,
        "reviewer_attestation": approval["reviewer"],
        "will_commit": False,
        "will_push": False,
    }


def apply_rule_patch(
    proposal: dict,
    plan: dict,
    report: dict,
    approval: dict,
    *,
    repository_root: Path,
) -> dict:
    preview = preview_rule_apply(
        proposal,
        plan,
        report,
        approval,
        repository_root=repository_root,
    )
    root = repository_root.expanduser().resolve()
    applied = _git(
        root,
        ["apply", "--whitespace=error-all", "-"],
        input_text=_git_patch_input(proposal["rule_diff"]),
    )
    if applied.returncode:
        raise RegressionError(f"rule patchを適用できません: {applied.stderr.strip()}")
    validation_commands = [
        [sys.executable, "skills/reader-first-editor/scripts/validate_content.py"],
        [str(root / "scripts" / "validate-skills.sh")],
    ]
    errors: list[str] = []
    for command in validation_commands:
        result = subprocess.run(
            command,
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            errors.append(result.stderr.strip() or result.stdout.strip() or "validation failed")
    if errors:
        patch_input = _git_patch_input(proposal["rule_diff"])
        reverse_check = _git(root, ["apply", "-R", "--check", "-"], input_text=patch_input)
        reverse = (
            _git(root, ["apply", "-R", "-"], input_text=patch_input)
            if reverse_check.returncode == 0
            else reverse_check
        )
        if reverse.returncode:
            raise RegressionError(
                "post-apply validationとrollbackに失敗しました。worktreeを手動確認してください: "
                + "; ".join(errors)
            )
        raise RegressionError("post-apply validationに失敗したためpatchをrollbackしました: " + "; ".join(errors))
    return {**preview, "applied": True, "validated": True}


__all__ = [
    "RegressionError",
    "apply_rule_patch",
    "build_regression_plan",
    "build_regression_report",
    "build_rule_approval",
    "parse_rule_patch",
    "preview_rule_apply",
    "rule_diff_hash",
    "validate_apply_artifacts",
    "validate_regression_plan",
    "validate_regression_report",
    "validate_regression_run",
    "validate_report_against_runs",
    "validate_rule_approval",
    "validate_rule_proposal",
]
