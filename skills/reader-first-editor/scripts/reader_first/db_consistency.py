from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re


class DatabaseConsistencyError(ValueError):
    """DB定義の抽出またはpeer group指定が不正な場合のエラー。"""


HEADER_ALIASES = {
    "table": {"table", "table name", "テーブル", "テーブル名"},
    "column": {"column", "column name", "field", "列", "列名", "カラム", "カラム名"},
    "type": {"type", "data type", "datatype", "型", "データ型"},
    "nullable": {"nullable", "null", "null allowed", "null許可", "null可"},
    "required": {"必須"},
    "default": {"default", "default value", "既定値", "初期値", "デフォルト"},
    "constraint": {"constraint", "constraints", "制約"},
    "comment": {"comment", "description", "note", "説明", "備考", "コメント"},
}
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True)
class PeerGroupSpec:
    name: str
    column_pattern: str
    table_pattern: str | None = None


def _cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", stripped)]


def _is_separator(line: str) -> bool:
    cells = _cells(line)
    return len(cells) >= 2 and all(TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def _canonical_header(value: str) -> str | None:
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    for canonical, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def normalize_type(value: str, dialect: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip().casefold())
    if dialect == "postgresql":
        aliases = {
            "timestamp with time zone": "timestamptz",
            "timestamptz": "timestamptz",
            "timestamp without time zone": "timestamp",
            "timestamp": "timestamp",
        }
        return aliases.get(normalized, normalized)
    return normalized


def _normalize_nullable(value: str) -> str:
    normalized = value.strip().casefold()
    yes = {"yes", "y", "true", "可", "nullable", "null"}
    no = {"no", "n", "false", "不可", "not null", "必須"}
    if normalized in yes:
        return "nullable"
    if normalized in no:
        return "not-null"
    return normalized or "<missing>"


def _normalize_required(value: str) -> str:
    normalized = value.strip().casefold()
    yes = {"yes", "y", "true", "必須", "required"}
    no = {"no", "n", "false", "任意", "optional"}
    if normalized in yes:
        return "not-null"
    if normalized in no:
        return "nullable"
    return normalized or "<missing>"


def _normalize_default(value: str) -> str:
    """式部分だけを正規化し、quoted literalのcaseと空白を保持する。"""

    segments: list[tuple[bool, str]] = []
    current: list[str] = []
    quote: str | None = None
    index = 0
    while index < len(value):
        char = value[index]
        if quote is None and char in {"'", '"'}:
            if current:
                segments.append((False, "".join(current)))
                current = []
            quote = char
            current.append(char)
        elif quote is not None and char == quote:
            current.append(char)
            if index + 1 < len(value) and value[index + 1] == quote:
                current.append(value[index + 1])
                index += 1
            else:
                segments.append((True, "".join(current)))
                current = []
                quote = None
        else:
            current.append(char)
        index += 1
    if current:
        segments.append((quote is not None, "".join(current)))
    normalized = "".join(
        text if quoted else re.sub(r"\s+", " ", text.casefold())
        for quoted, text in segments
    ).strip()
    return normalized or "<missing>"


def _normalize_value(
    attribute: str,
    value: str,
    dialect: str,
    *,
    nullable_source: str = "nullable",
) -> str:
    if attribute == "type":
        return normalize_type(value, dialect)
    if attribute == "nullable":
        if nullable_source == "required":
            return _normalize_required(value)
        return _normalize_nullable(value)
    if attribute == "default":
        return _normalize_default(value)
    return re.sub(r"\s+", " ", value.strip().casefold()) or "<missing>"


def extract_markdown_tables(
    text: str,
    *,
    source: str,
    dialect: str = "generic",
) -> dict[str, object]:
    if dialect not in {"generic", "postgresql"}:
        raise DatabaseConsistencyError(f"未対応dialectです: {dialect}")
    lines = text.splitlines()
    rows: list[dict[str, object]] = []
    limitations: list[str] = []
    parsed_table_count = 0
    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index] or not _is_separator(lines[index + 1]):
            index += 1
            continue
        header_line = index + 1
        headers = _cells(lines[index])
        mapping = [_canonical_header(header) for header in headers]
        recognized = {value for value in mapping if value is not None}
        index += 2
        table_rows: list[tuple[int, list[str]]] = []
        while index < len(lines) and lines[index].strip() and "|" in lines[index]:
            table_rows.append((index + 1, _cells(lines[index])))
            index += 1
        if not recognized:
            continue
        if "column" not in recognized or "type" not in recognized:
            limitations.append(
                f"{header_line}行目の表はDB定義候補ですがcolumnとtypeの両方を識別できません"
            )
            continue
        if "nullable" in recognized and "required" in recognized:
            limitations.append(
                f"{header_line}行目の表はnullableと必須の両方を持つためnullableを優先し、"
                "必須との整合は確認していません"
            )
        parsed_table_count += 1
        for line_number, cells in table_rows:
            if len(cells) != len(headers):
                limitations.append(
                    f"{line_number}行目のcell数{len(cells)}がheader数{len(headers)}と一致しません"
                )
                continue
            raw = {
                canonical: cells[position]
                for position, canonical in enumerate(mapping)
                if canonical is not None
            }
            if not raw.get("column"):
                limitations.append(f"{line_number}行目のcolumn名が空です")
                continue
            if "nullable" in raw:
                nullable_source = "nullable"
            elif "required" in raw:
                nullable_source = "required"
            else:
                nullable_source = "absent"
            nullable_value = raw.get(nullable_source, "")
            row_id = f"DBROW-{len(rows) + 1:04d}"
            rows.append(
                {
                    "row_id": row_id,
                    "source": source,
                    "line": line_number,
                    "table": raw.get("table") or "<unspecified>",
                    "column": raw["column"],
                    "type": raw.get("type", ""),
                    "nullable": nullable_value,
                    "nullable_source": nullable_source,
                    "default": raw.get("default", ""),
                    "constraint": raw.get("constraint", ""),
                    "comment": raw.get("comment", ""),
                    "normalized": {
                        attribute: _normalize_value(
                            attribute,
                            nullable_value if attribute == "nullable" else raw.get(attribute, ""),
                            dialect,
                            nullable_source=nullable_source,
                        )
                        for attribute in ("type", "nullable", "default", "constraint")
                    },
                }
            )
    if not parsed_table_count:
        limitations.append("columnとtypeを持つ対応Markdown tableを確認できませんでした")
    return {
        "schema_version": 1,
        "parser": "markdown-db-definition-table",
        "dialect": dialect,
        "status": "partial" if limitations else "checked",
        "source": source,
        "parsed_table_count": parsed_table_count,
        "row_count": len(rows),
        "rows": rows,
        "limitations": limitations,
    }


def _compile_spec(spec: PeerGroupSpec) -> tuple[re.Pattern[str], re.Pattern[str] | None]:
    if not spec.name.strip():
        raise DatabaseConsistencyError("peer group名が必要です")
    try:
        column = re.compile(spec.column_pattern)
        table = re.compile(spec.table_pattern) if spec.table_pattern else None
    except re.error as exc:
        raise DatabaseConsistencyError(f"peer groupの正規表現が不正です: {spec.name}: {exc}") from exc
    return column, table


def analyze_peer_groups(
    extraction: dict[str, object],
    specs: list[PeerGroupSpec],
    *,
    attributes: tuple[str, ...] = ("type", "nullable", "default", "constraint"),
    min_group_size: int = 4,
    dominance_ratio: float = 0.75,
) -> dict[str, object]:
    if not specs:
        raise DatabaseConsistencyError("1件以上のpeer groupを指定する必要があります")
    if min_group_size < 2:
        raise DatabaseConsistencyError("min_group_sizeは2以上である必要があります")
    if not 0.5 < dominance_ratio < 1:
        raise DatabaseConsistencyError("dominance_ratioは0.5より大きく1未満である必要があります")
    unknown_attributes = set(attributes) - {"type", "nullable", "default", "constraint"}
    if unknown_attributes:
        raise DatabaseConsistencyError(f"未対応attributeです: {sorted(unknown_attributes)}")
    rows = extraction.get("rows")
    if not isinstance(rows, list):
        raise DatabaseConsistencyError("extraction.rowsが必要です")
    limitations = list(extraction.get("limitations", []))

    candidates: list[dict[str, object]] = []
    groups: list[dict[str, object]] = []
    for spec in specs:
        column_re, table_re = _compile_spec(spec)
        members = [
            row
            for row in rows
            if isinstance(row, dict)
            and column_re.search(str(row.get("column", "")))
            and (table_re is None or table_re.search(str(row.get("table", ""))))
        ]
        if len(members) < min_group_size:
            limitations.append(
                f"peer group {spec.name}はmemberが{len(members)}件で、"
                f"必要な{min_group_size}件に達していません"
            )
        distributions: dict[str, list[dict[str, object]]] = {}
        group_candidates: list[str] = []
        for attribute in attributes:
            values = [str(row.get("normalized", {}).get(attribute, "<missing>")) for row in members]
            counts = Counter(values)
            distributions[attribute] = [
                {"value": value, "count": count}
                for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ]
            if len(members) < min_group_size or len(counts) < 2:
                continue
            dominant_value, dominant_count = sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )[0]
            ratio = dominant_count / len(members)
            if ratio < dominance_ratio:
                continue
            for row in members:
                value = str(row.get("normalized", {}).get(attribute, "<missing>"))
                if value == dominant_value:
                    continue
                candidate_id = f"DB-{len(candidates) + 1:04d}"
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "candidate_type": "peer-group-minority",
                        "peer_group": spec.name,
                        "attribute": attribute,
                        "dominant_value": dominant_value,
                        "dominant_count": dominant_count,
                        "member_count": len(members),
                        "dominance_ratio": round(ratio, 6),
                        "minority_value": value,
                        "row_id": row.get("row_id"),
                        "source": row.get("source"),
                        "line": row.get("line"),
                        "table": row.get("table"),
                        "column": row.get("column"),
                    }
                )
                group_candidates.append(candidate_id)
        groups.append(
            {
                "name": spec.name,
                "selection": {
                    "column_pattern": spec.column_pattern,
                    "table_pattern": spec.table_pattern,
                    "declared_semantic_group": True,
                },
                "member_count": len(members),
                "member_row_ids": [row.get("row_id") for row in members],
                "distributions": distributions,
                "candidate_ids": group_candidates,
            }
        )

    return {
        **extraction,
        "status": "partial" if limitations else "checked",
        "limitations": limitations,
        "analysis": "peer-group-distribution",
        "interpretation": "candidate-only",
        "thresholds": {
            "purpose": "candidate-generation-only",
            "min_group_size": min_group_size,
            "dominance_ratio": dominance_ratio,
        },
        "peer_groups": groups,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
