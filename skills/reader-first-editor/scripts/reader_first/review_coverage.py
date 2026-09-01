from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


COVERAGE_STATUSES = {"checked", "partial", "not-checked"}
RESOLUTIONS = {"finding", "excluded", "unresolved"}
SEVERITIES = {"HIGH", "MEDIUM", "LOW"}
DEFAULT_DIMENSIONS = (
    "semantic-preservation",
    "information-structure",
    "syntax-and-reread-risk",
    "relationship-clarity",
    "modality-and-scope",
    "local-consistency",
)

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


class CoverageError(ValueError):
    """構造inventoryまたはcoverage reportが不正な場合のエラー。"""


@dataclass(frozen=True)
class MarkdownBlock:
    kind: str
    start_line: int
    end_line: int
    text: str


def _table_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def _is_table_separator(line: str) -> bool:
    cells = _table_cells(line)
    return len(cells) >= 2 and all(TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def _starts_special(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip():
        return True
    if HEADING_RE.match(line) or FENCE_RE.match(line) or LIST_RE.match(line):
        return True
    return index + 1 < len(lines) and "|" in line and _is_table_separator(lines[index + 1])


def parse_markdown_blocks(text: str) -> tuple[list[MarkdownBlock], list[str]]:
    """Markdownの分割してはいけないblockを保ったinventoryを返す。"""

    lines = text.splitlines()
    blocks: list[MarkdownBlock] = []
    limitations: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        start = index
        line = lines[index]
        fence_match = FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            marker_char = marker[0]
            marker_length = len(marker)
            index += 1
            closed = False
            while index < len(lines):
                closing = FENCE_RE.match(lines[index])
                if (
                    closing
                    and closing.group(1)[0] == marker_char
                    and len(closing.group(1)) >= marker_length
                ):
                    index += 1
                    closed = True
                    break
                index += 1
            if not closed:
                limitations.append(f"{start + 1}行目からのcode fenceが閉じていません")
            blocks.append(
                MarkdownBlock("code-fence", start + 1, index, "\n".join(lines[start:index]))
            )
            continue
        if index + 1 < len(lines) and "|" in line and _is_table_separator(lines[index + 1]):
            index += 2
            while index < len(lines) and lines[index].strip() and "|" in lines[index]:
                index += 1
            blocks.append(MarkdownBlock("table", start + 1, index, "\n".join(lines[start:index])))
            continue
        heading_match = HEADING_RE.match(line)
        if heading_match:
            index += 1
            blocks.append(MarkdownBlock("heading", start + 1, index, line))
            continue
        if LIST_RE.match(line):
            index += 1
            while index < len(lines):
                current = lines[index]
                if not current.strip():
                    lookahead = index + 1
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    if lookahead < len(lines) and (
                        LIST_RE.match(lines[lookahead]) or lines[lookahead].startswith((" ", "\t"))
                    ):
                        index = lookahead
                        continue
                    break
                if HEADING_RE.match(current) or FENCE_RE.match(current):
                    break
                if (
                    index + 1 < len(lines)
                    and "|" in current
                    and _is_table_separator(lines[index + 1])
                ):
                    break
                if LIST_RE.match(current) or current.startswith((" ", "\t")):
                    index += 1
                    continue
                break
            blocks.append(MarkdownBlock("list", start + 1, index, "\n".join(lines[start:index])))
            continue

        index += 1
        while index < len(lines) and not _starts_special(lines, index):
            index += 1
        blocks.append(MarkdownBlock("paragraph", start + 1, index, "\n".join(lines[start:index])))
    return blocks, limitations


def _heading_chain(blocks: Iterable[MarkdownBlock]) -> dict[int, tuple[str, ...]]:
    chain: list[str] = []
    result: dict[int, tuple[str, ...]] = {}
    for block in blocks:
        if block.kind == "heading":
            match = HEADING_RE.match(block.text)
            if match:
                level = len(match.group(1))
                chain = chain[: level - 1]
                chain.append(match.group(2))
        result[block.start_line] = tuple(chain)
    return result


def build_markdown_inventory(
    text: str,
    *,
    source: str,
    max_chars: int = 12_000,
) -> dict[str, object]:
    if max_chars <= 0:
        raise CoverageError("max_charsは正の整数である必要があります")
    blocks, limitations = parse_markdown_blocks(text)
    chains = _heading_chain(blocks)
    chunks: list[dict[str, object]] = []
    current: list[MarkdownBlock] = []
    current_size = 0

    def flush() -> None:
        nonlocal current, current_size
        if not current:
            return
        chunk_id = f"CHUNK-{len(chunks) + 1:04d}"
        protected = any(block.kind in {"table", "list", "code-fence"} for block in current)
        oversized = sum(len(block.text) for block in current) > max_chars
        chunks.append(
            {
                "chunk_id": chunk_id,
                "source": source,
                "start_line": current[0].start_line,
                "end_line": current[-1].end_line,
                "headings": list(chains[current[-1].start_line]),
                "block_kinds": [block.kind for block in current],
                "protected_block": protected,
                "oversized": oversized,
                "text": "\n\n".join(block.text for block in current),
            }
        )
        current = []
        current_size = 0

    for block in blocks:
        starts_section = block.kind == "heading"
        addition = len(block.text) + (2 if current else 0)
        if starts_section and current:
            flush()
        elif current and current_size + addition > max_chars:
            flush()
        current.append(block)
        current_size += addition
        if len(block.text) > max_chars and block.kind in {"table", "list", "code-fence"}:
            limitations.append(
                f"{block.start_line}-{block.end_line}行の{block.kind}を分割せず上限超過chunkにしました"
            )
            flush()
    flush()

    status = "partial" if limitations else "complete"
    return {
        "schema_version": 1,
        "inventory_type": "markdown-structure",
        "source": source,
        "status": status,
        "max_chars": max_chars,
        "line_count": len(text.splitlines()),
        "chunk_count": len(chunks),
        "limitations": limitations,
        "chunks": chunks,
    }


def build_report_skeleton(
    inventory: dict[str, object],
    *,
    dimensions: Iterable[str] = DEFAULT_DIMENSIONS,
) -> dict[str, object]:
    chunks = inventory.get("chunks")
    if not isinstance(chunks, list):
        raise CoverageError("inventory.chunksが必要です")
    names = list(dimensions)
    if not names or any(not isinstance(name, str) or not name for name in names):
        raise CoverageError("dimension名が必要です")
    if len(names) != len(set(names)):
        raise CoverageError("dimension名が重複しています")
    return {
        "schema_version": 1,
        "report_type": "coverage-driven-review",
        "sources": [inventory.get("source")],
        "chunks": [
            {
                "chunk_id": chunk.get("chunk_id"),
                "status": "not-checked",
                "candidate_ids": [],
                "unchecked_scope": ["局所passを未実施"],
            }
            for chunk in chunks
            if isinstance(chunk, dict)
        ],
        "dimensions": [
            {
                "dimension": name,
                "status": "not-checked",
                "candidate_ids": [],
                "candidate_count": 0,
                "finding_count": 0,
                "excluded_count": 0,
                "unresolved_count": 0,
                "exclusion_reasons": [],
                "unchecked_scope": ["観点別passを未実施"],
            }
            for name in names
        ],
        "global_pass": {
            "status": "not-checked",
            "candidate_ids": [],
            "unchecked_scope": ["global passを未実施"],
        },
        "candidates": [],
        "findings": [],
        "limitations": list(inventory.get("limitations", [])),
    }


def _validate_status(record: dict[str, object], label: str, errors: list[str]) -> None:
    status = record.get("status")
    unchecked = record.get("unchecked_scope")
    if status not in COVERAGE_STATUSES:
        errors.append(f"{label}: statusが不正です: {status!r}")
    if not isinstance(unchecked, list) or not all(isinstance(item, str) for item in unchecked):
        errors.append(f"{label}: unchecked_scopeは文字列listである必要があります")
        return
    if status == "checked" and unchecked:
        errors.append(f"{label}: checkedに未確認範囲を残せません")
    if status in {"partial", "not-checked"} and not unchecked:
        errors.append(f"{label}: {status}には未確認範囲が必要です")


def validate_coverage_report(report: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["report rootはobjectである必要があります"]
    if report.get("schema_version") != 1:
        errors.append("schema_versionは1である必要があります")
    if report.get("report_type") != "coverage-driven-review":
        errors.append("report_typeが不正です")

    candidates = report.get("candidates")
    candidate_map: dict[str, dict[str, object]] = {}
    if not isinstance(candidates, list):
        errors.append("candidatesはlistである必要があります")
        candidates = []
    for index, candidate in enumerate(candidates, start=1):
        label = f"candidate {index}"
        if not isinstance(candidate, dict):
            errors.append(f"{label}: objectである必要があります")
            continue
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            errors.append(f"{label}: candidate_idが必要です")
            continue
        if candidate_id in candidate_map:
            errors.append(f"{label}: candidate_idが重複しています: {candidate_id}")
        candidate_map[candidate_id] = candidate
        if candidate.get("resolution") not in RESOLUTIONS:
            errors.append(f"{label}: resolutionが不正です")
        if not isinstance(candidate.get("source"), str) or not candidate.get("source"):
            errors.append(f"{label}: sourceが必要です")
        if not isinstance(candidate.get("line"), int) or candidate.get("line", 0) < 1:
            errors.append(f"{label}: 1以上のlineが必要です")
        if candidate.get("resolution") in {"excluded", "unresolved"} and not candidate.get("reason"):
            errors.append(f"{label}: excluded/unresolvedにはreasonが必要です")

    covered_candidate_ids: set[str] = set()

    def validate_candidate_refs(record: dict[str, object], label: str) -> None:
        candidate_ids = record.get("candidate_ids")
        if not isinstance(candidate_ids, list) or not all(
            isinstance(item, str) for item in candidate_ids
        ):
            errors.append(f"{label}: candidate_idsは文字列listである必要があります")
            return
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append(f"{label}: candidate_idsが重複しています")
        unknown = set(candidate_ids) - candidate_map.keys()
        if unknown:
            errors.append(f"{label}: 未定義candidateがあります: {sorted(unknown)}")
        covered_candidate_ids.update(candidate_ids)

    chunks = report.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        errors.append("chunksは空でないlistである必要があります")
        chunks = []
    chunk_ids: set[str] = set()
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            errors.append(f"chunk {index}: objectである必要があります")
            continue
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            errors.append(f"chunk {index}: chunk_idが必要です")
        elif chunk_id in chunk_ids:
            errors.append(f"chunk {index}: chunk_idが重複しています")
        else:
            chunk_ids.add(chunk_id)
        _validate_status(chunk, f"chunk {index}", errors)
        validate_candidate_refs(chunk, f"chunk {index}")

    dimensions = report.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("dimensionsは空でないlistである必要があります")
        dimensions = []
    dimension_names: set[str] = set()
    for index, dimension in enumerate(dimensions, start=1):
        label = f"dimension {index}"
        if not isinstance(dimension, dict):
            errors.append(f"{label}: objectである必要があります")
            continue
        name = dimension.get("dimension")
        if not isinstance(name, str) or not name:
            errors.append(f"{label}: dimension名が必要です")
        elif name in dimension_names:
            errors.append(f"{label}: dimension名が重複しています")
        else:
            dimension_names.add(name)
        _validate_status(dimension, label, errors)
        candidate_ids = dimension.get("candidate_ids")
        if not isinstance(candidate_ids, list) or not all(
            isinstance(item, str) for item in candidate_ids
        ):
            errors.append(f"{label}: candidate_idsは文字列listである必要があります")
            candidate_ids = []
        unknown = set(candidate_ids) - candidate_map.keys()
        if unknown:
            errors.append(f"{label}: 未定義candidateがあります: {sorted(unknown)}")
        counts: dict[str, int] = {}
        for key in ("candidate_count", "finding_count", "excluded_count", "unresolved_count"):
            value = dimension.get(key)
            if not isinstance(value, int) or value < 0:
                errors.append(f"{label}: {key}は0以上の整数である必要があります")
                value = 0
            counts[key] = value
        if counts["candidate_count"] != len(candidate_ids):
            errors.append(f"{label}: candidate_countとcandidate_idsが一致しません")
        classified = {
            resolution: sum(
                1 for candidate_id in candidate_ids
                if candidate_map.get(candidate_id, {}).get("resolution") == resolution
            )
            for resolution in RESOLUTIONS
        }
        if counts["finding_count"] != classified["finding"]:
            errors.append(f"{label}: finding_countがcandidateの分類と一致しません")
        if counts["excluded_count"] != classified["excluded"]:
            errors.append(f"{label}: excluded_countがcandidateの分類と一致しません")
        if counts["unresolved_count"] != classified["unresolved"]:
            errors.append(f"{label}: unresolved_countがcandidateの分類と一致しません")
        if counts["candidate_count"] != sum(classified.values()):
            errors.append(f"{label}: candidateが未分類です")
        reasons = dimension.get("exclusion_reasons")
        if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
            errors.append(f"{label}: exclusion_reasonsは文字列listである必要があります")
        elif counts["excluded_count"] and not reasons:
            errors.append(f"{label}: excluded candidateには除外理由が必要です")

    global_pass = report.get("global_pass")
    if not isinstance(global_pass, dict):
        errors.append("global_passはobjectである必要があります")
    else:
        _validate_status(global_pass, "global_pass", errors)
        validate_candidate_refs(global_pass, "global_pass")

    untracked_candidates = candidate_map.keys() - covered_candidate_ids
    if untracked_candidates:
        errors.append(
            f"chunkまたはglobal passへ紐付かないcandidateがあります: {sorted(untracked_candidates)}"
        )

    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append("findingsはlistである必要があります")
        findings = []
    finding_candidate_ids: set[str] = set()
    finding_ids: set[str] = set()
    for index, finding in enumerate(findings, start=1):
        label = f"finding {index}"
        if not isinstance(finding, dict):
            errors.append(f"{label}: objectである必要があります")
            continue
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            errors.append(f"{label}: finding_idが必要です")
        elif finding_id in finding_ids:
            errors.append(f"{label}: finding_idが重複しています")
        else:
            finding_ids.add(finding_id)
        severity = finding.get("severity")
        if not isinstance(severity, str) or severity not in SEVERITIES:
            errors.append(f"{label}: severityが不正です: {severity!r}")
        linked = finding.get("candidate_ids")
        if not isinstance(linked, list) or not linked:
            errors.append(f"{label}: candidate_idsが必要です")
            continue
        for candidate_id in linked:
            if candidate_id not in candidate_map:
                errors.append(f"{label}: 未定義candidateです: {candidate_id}")
            elif candidate_map[candidate_id].get("resolution") != "finding":
                errors.append(f"{label}: finding以外のcandidateを参照しています: {candidate_id}")
            finding_candidate_ids.add(candidate_id)
        locations = finding.get("locations")
        if not isinstance(locations, list) or not locations:
            errors.append(f"{label}: locationsが必要です")
            continue
        location_pairs: set[tuple[str, int]] = set()
        for location in locations:
            if (
                not isinstance(location, dict)
                or not isinstance(location.get("source"), str)
                or not isinstance(location.get("line"), int)
                or location.get("line", 0) < 1
            ):
                errors.append(f"{label}: locationにはsourceと1以上のlineが必要です")
                continue
            location_pairs.add((location["source"], location["line"]))
        missing_locations = {
            (str(candidate_map[candidate_id].get("source")), int(candidate_map[candidate_id].get("line", 0)))
            for candidate_id in linked
            if candidate_id in candidate_map
        } - location_pairs
        if missing_locations:
            errors.append(f"{label}: candidateのlocationを保持していません: {sorted(missing_locations)}")

    expected_finding_candidates = {
        candidate_id for candidate_id, candidate in candidate_map.items()
        if candidate.get("resolution") == "finding"
    }
    omitted = expected_finding_candidates - finding_candidate_ids
    if omitted:
        errors.append(f"findingへ保持されていないcandidateがあります: {sorted(omitted)}")
    return errors
