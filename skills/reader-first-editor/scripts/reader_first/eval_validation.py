"""Eval fixtureとregression artifactで共有するstructured oracle契約。"""

from __future__ import annotations

EXPECTED_RISKS = {f"RR-{index:02d}" for index in range(1, 17)}
EVIDENCE_STATUSES = {
    "VERIFIED",
    "CONTRADICTED",
    "SUPPORTED-BY-CITATION",
    "UNSUPPORTED",
    "UNVERIFIED",
}
EVIDENCE_TYPES = {
    "DOC↔CODE",
    "DOC↔CONFIG",
    "DOC↔TEST",
    "DOC↔DOC",
    "DOC↔HISTORY",
    "CITATION",
    "EVIDENCE-GAP",
    "UNVERIFIED",
}
STRUCTURED_ORACLE_VALUES = {
    "expected_risks": EXPECTED_RISKS,
    "expected_statuses": EVIDENCE_STATUSES,
    "expected_evidence_types": EVIDENCE_TYPES,
}


def validate_eval_oracles(case: dict) -> list[str]:
    """1件のeval caseにあるoracleの型・値・組合せを検証する。"""

    errors: list[str] = []
    valid_values: dict[str, list[str]] = {}
    for key, allowed_values in STRUCTURED_ORACLE_VALUES.items():
        if key not in case:
            continue
        value = case[key]
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            errors.append(f"{key} must be a string list")
            continue
        if not value:
            errors.append(f"{key} must contain at least one value")
            continue
        if len(value) != len(set(value)):
            errors.append(f"{key} must not contain duplicates")
        if unknown := sorted(set(value) - allowed_values):
            errors.append(f"invalid {key}: {unknown}")
        valid_values[key] = value

    statuses = valid_values.get("expected_statuses")
    evidence_types = valid_values.get("expected_evidence_types")
    if case.get("mode") == "repository-review":
        if not statuses:
            errors.append("repository-review requires expected_statuses")
        if not evidence_types:
            errors.append("repository-review requires expected_evidence_types")
    if statuses is not None and evidence_types is not None:
        if "UNSUPPORTED" in statuses and "EVIDENCE-GAP" not in evidence_types:
            errors.append("UNSUPPORTED requires EVIDENCE-GAP evidence type")
        if "UNVERIFIED" in statuses and "UNVERIFIED" not in evidence_types:
            errors.append("UNVERIFIED requires UNVERIFIED evidence type")
    return errors


__all__ = [
    "EVIDENCE_STATUSES",
    "EVIDENCE_TYPES",
    "EXPECTED_RISKS",
    "STRUCTURED_ORACLE_VALUES",
    "validate_eval_oracles",
]
