from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


TRIPWIRE_START = "<!-- relationship-tripwires:start -->"
TRIPWIRE_END = "<!-- relationship-tripwires:end -->"


class RelationshipScanError(ValueError):
    """候補語sourceまたは入力を読み取れない場合のエラー。"""


@dataclass(frozen=True)
class SourceText:
    label: str
    text: str


def load_tripwires(reference_path: Path) -> tuple[str, ...]:
    try:
        text = reference_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RelationshipScanError(
            f"候補語sourceを読み込めません: {reference_path}: {exc}"
        ) from exc

    start = text.find(TRIPWIRE_START)
    end = text.find(TRIPWIRE_END)
    if start < 0 or end < 0 or end <= start:
        raise RelationshipScanError("候補語sourceのmarkerが不正です")

    values: list[str] = []
    for raw_line in text[start + len(TRIPWIRE_START) : end].splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if not (line.startswith("- `") and line.endswith("`")):
            raise RelationshipScanError(f"候補語sourceの行形式が不正です: {line}")
        value = line[3:-1]
        if not value or value in values:
            raise RelationshipScanError(f"候補語sourceが空または重複しています: {value!r}")
        values.append(value)
    if not values:
        raise RelationshipScanError("候補語sourceが空です")
    return tuple(values)


def _find_literal(line: str, literal: str) -> list[tuple[int, str]]:
    ascii_only = literal.isascii()
    flags = re.IGNORECASE if ascii_only else 0
    matches = [
        (match.start(), match.group(0))
        for match in re.finditer(re.escape(literal), line, flags)
    ]
    if literal != "場":
        return matches

    # 「判断の場」のような独立した関係語だけを候補にする。「場合」
    # 「場所」「会場」など、別の語に含まれる文字は候補にしない。
    preceding_boundaries = set("のをはがにへと、。！？：；（［【「『( [\t")
    following_boundaries = set("、。！？：；（［【「『）］】」』()[] \t")
    return [
        (index, matched)
        for index, matched in matches
        if (
            index == 0
            or line[index - 1] in preceding_boundaries
            or "ぁ" <= line[index - 1] <= "ゖ"
        )
        and (
            index + len(matched) == len(line)
            or line[index + len(matched)] in following_boundaries
            or "ぁ" <= line[index + len(matched)] <= "ゖ"
        )
    ]


def build_candidate_report(
    sources: list[SourceText],
    tripwires: tuple[str, ...],
    *,
    vocabulary_source: str,
) -> dict[str, object]:
    if not sources:
        raise RelationshipScanError("確認するsourceがありません")
    candidates: list[dict[str, object]] = []
    for source in sources:
        source_hits: list[tuple[int, int, str, str]] = []
        for line_number, line in enumerate(source.text.splitlines(), start=1):
            for literal in tripwires:
                for index, matched in _find_literal(line, literal):
                    source_hits.append((line_number, index + 1, literal, matched))
        source_hits.sort(key=lambda item: (item[0], item[1], item[2]))
        for line_number, column, literal, matched in source_hits:
            candidates.append(
                {
                    "candidate_id": f"REL-{len(candidates) + 1:04d}",
                    "source": source.label,
                    "line": line_number,
                    "column": column,
                    "end_column": column + len(matched),
                    "term": literal,
                    "matched_text": matched,
                }
            )

    return {
        "schema_version": 1,
        "scanner": "relationship-tripwires",
        "interpretation": "candidate-only",
        "vocabulary_source": vocabulary_source,
        "sources": [source.label for source in sources],
        "candidate_count": len(candidates),
        "candidates": candidates,
        "limitations": [],
    }
