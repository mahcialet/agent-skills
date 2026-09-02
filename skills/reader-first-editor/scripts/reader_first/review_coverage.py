from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable

from .schema_validation import is_schema_version


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
REVIEW_MODES = {"review", "repository-review"}
REPOSITORY_DIMENSION = "repository-consistency"
INVENTORY_STATUSES = {"complete", "partial"}
BLOCK_KINDS = {"heading", "paragraph", "table", "list", "code-fence"}
COVERAGE_SCHEMA_VERSION = 2

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


def _is_fence_close(line: str, marker: str) -> bool:
    return bool(re.fullmatch(rf"\s*{re.escape(marker[0])}{{{len(marker)},}}\s*", line))


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
            index += 1
            closed = False
            while index < len(lines):
                if _is_fence_close(lines[index], marker):
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
    if not isinstance(text, str):
        raise CoverageError("Markdown textは文字列である必要があります")
    if not isinstance(source, str) or not source:
        raise CoverageError("sourceは空でない文字列である必要があります")
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars <= 0:
        raise CoverageError("max_charsは正の整数である必要があります")
    if not text.strip():
        raise CoverageError("空または空白のみのMarkdownはinventory化できません")
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
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "inventory_type": "markdown-structure",
        "source": source,
        "source_hash": _text_hash(text),
        "status": status,
        "max_chars": max_chars,
        "line_count": len(text.splitlines()),
        "chunk_count": len(chunks),
        "limitations": limitations,
        "chunks": chunks,
    }


def _text_hash(text: str) -> str:
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"


def inventory_hash(inventory: object) -> str:
    if not isinstance(inventory, dict):
        raise CoverageError("inventory rootはobjectである必要があります")
    payload = json.dumps(
        inventory,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _inventory_contract(
    inventory: object,
    *,
    source_text: str,
    source: str,
) -> tuple[str, list[str], int]:
    if not isinstance(inventory, dict):
        raise CoverageError("inventory rootはobjectである必要があります")
    root_keys = {
        "schema_version",
        "inventory_type",
        "source",
        "source_hash",
        "status",
        "max_chars",
        "line_count",
        "chunk_count",
        "limitations",
        "chunks",
    }
    missing = sorted(root_keys - inventory.keys())
    unknown = sorted(inventory.keys() - root_keys)
    if missing:
        raise CoverageError(f"inventoryに必須fieldがありません: {', '.join(missing)}")
    if unknown:
        raise CoverageError(f"inventoryに未知のfieldがあります: {', '.join(unknown)}")
    if not is_schema_version(inventory.get("schema_version"), COVERAGE_SCHEMA_VERSION):
        raise CoverageError("inventory.schema_versionは2である必要があります")
    if inventory.get("inventory_type") != "markdown-structure":
        raise CoverageError("inventory.inventory_typeが不正です")
    inventory_source = inventory.get("source")
    if not isinstance(inventory_source, str) or not inventory_source:
        raise CoverageError("inventory.sourceが必要です")
    if inventory_source != source:
        raise CoverageError("inventory.sourceが指定Markdown sourceと一致しません")
    source_hash = inventory.get("source_hash")
    if source_hash != _text_hash(source_text):
        raise CoverageError("inventory.source_hashが指定Markdown本文と一致しません")
    if inventory.get("status") not in INVENTORY_STATUSES:
        raise CoverageError("inventory.statusが不正です")
    max_chars = inventory.get("max_chars")
    if not _is_integer(max_chars, minimum=1):
        raise CoverageError("inventory.max_charsは1以上のintegerである必要があります")
    line_count = inventory.get("line_count")
    if not isinstance(line_count, int) or isinstance(line_count, bool) or line_count < 1:
        raise CoverageError("inventory.line_countは1以上のintegerである必要があります")
    chunks = inventory.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise CoverageError("inventory.chunksは空でないlistである必要があります")
    chunk_ids: list[str] = []
    previous_end = 0
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            raise CoverageError(f"inventory chunk {index}はobjectである必要があります")
        chunk_keys = {
            "chunk_id",
            "source",
            "start_line",
            "end_line",
            "headings",
            "block_kinds",
            "protected_block",
            "oversized",
            "text",
        }
        missing_chunk = sorted(chunk_keys - chunk.keys())
        unknown_chunk = sorted(chunk.keys() - chunk_keys)
        if missing_chunk:
            raise CoverageError(
                f"inventory chunk {index}に必須fieldがありません: {', '.join(missing_chunk)}"
            )
        if unknown_chunk:
            raise CoverageError(
                f"inventory chunk {index}に未知のfieldがあります: {', '.join(unknown_chunk)}"
            )
        chunk_id = chunk.get("chunk_id")
        expected_chunk_id = f"CHUNK-{index:04d}"
        if chunk_id != expected_chunk_id:
            raise CoverageError(
                f"inventory chunk {index}のchunk_idは{expected_chunk_id}である必要があります"
            )
        if chunk.get("source") != inventory_source:
            raise CoverageError(f"inventory chunk {index}のsourceがinventoryと一致しません")
        start_line = chunk.get("start_line")
        end_line = chunk.get("end_line")
        if not _is_integer(start_line, minimum=1) or not _is_integer(end_line, minimum=1):
            raise CoverageError(f"inventory chunk {index}の行範囲が不正です")
        if start_line > end_line or end_line > line_count or start_line <= previous_end:
            raise CoverageError(f"inventory chunk {index}の行範囲が重複または逆転しています")
        previous_end = end_line
        if not _is_string_list(chunk.get("headings")):
            raise CoverageError(f"inventory chunk {index}のheadingsが不正です")
        block_kinds = chunk.get("block_kinds")
        if (
            not _is_string_list(block_kinds, nonempty_items=True)
            or not block_kinds
            or set(block_kinds) - BLOCK_KINDS
        ):
            raise CoverageError(f"inventory chunk {index}のblock_kindsが不正です")
        for key in ("protected_block", "oversized"):
            if not isinstance(chunk.get(key), bool):
                raise CoverageError(f"inventory chunk {index}の{key}はbooleanである必要があります")
        if not isinstance(chunk.get("text"), str) or not chunk.get("text"):
            raise CoverageError(f"inventory chunk {index}のtextが必要です")
        chunk_ids.append(chunk_id)
    if len(chunk_ids) != len(set(chunk_ids)):
        raise CoverageError("inventory chunk_idが重複しています")
    if inventory.get("chunk_count") != len(chunk_ids):
        raise CoverageError("inventory.chunk_countとchunksが一致しません")
    limitations = inventory.get("limitations")
    if not isinstance(limitations, list) or not all(
        isinstance(item, str) for item in limitations
    ):
        raise CoverageError("inventory.limitationsは文字列listである必要があります")
    regenerated = build_markdown_inventory(
        source_text,
        source=inventory_source,
        max_chars=max_chars,
    )
    if inventory != regenerated:
        raise CoverageError("inventoryが指定Markdownから再生成した正規inventoryと一致しません")
    return inventory_source, chunk_ids, line_count


def build_report_skeleton(
    inventory: dict[str, object],
    *,
    source_text: str,
    source: str,
    mode: str,
    dimensions: Iterable[str] | None = None,
) -> dict[str, object]:
    inventory_source, _, _ = _inventory_contract(
        inventory,
        source_text=source_text,
        source=source,
    )
    if mode not in REVIEW_MODES:
        raise CoverageError(f"modeが不正です: {mode!r}")
    chunks = inventory.get("chunks")
    assert isinstance(chunks, list)
    extras = list(dimensions or ())
    if any(not isinstance(name, str) or not name for name in extras):
        raise CoverageError("dimension名が必要です")
    if len(extras) != len(set(extras)):
        raise CoverageError("dimension名が重複しています")
    names = [*DEFAULT_DIMENSIONS]
    if mode == "repository-review":
        names.append(REPOSITORY_DIMENSION)
    names.extend(name for name in extras if name not in names)
    return {
        "schema_version": COVERAGE_SCHEMA_VERSION,
        "report_type": "coverage-driven-review",
        "mode": mode,
        "inventory_hash": inventory_hash(inventory),
        "sources": [inventory_source],
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


def _validate_exact_keys(
    record: dict[str, object],
    required: set[str],
    label: str,
    errors: list[str],
) -> None:
    missing = sorted(required - record.keys())
    unknown = sorted(record.keys() - required)
    if missing:
        errors.append(f"{label}: 必須fieldがありません: {', '.join(missing)}")
    if unknown:
        errors.append(f"{label}: 未知のfieldがあります: {', '.join(unknown)}")


def _is_integer(value: object, *, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _is_string_list(value: object, *, nonempty_items: bool = False) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and (not nonempty_items or bool(item.strip()))
        for item in value
    )


def validate_coverage_report(
    report: object,
    inventory: object,
    *,
    source_text: str,
    source: str,
    expected_mode: str,
) -> list[str]:
    errors: list[str] = []
    if expected_mode not in REVIEW_MODES:
        return [f"expected_modeが不正です: {expected_mode!r}"]
    try:
        inventory_source, inventory_chunk_ids, inventory_line_count = _inventory_contract(
            inventory,
            source_text=source_text,
            source=source,
        )
        expected_inventory_hash = inventory_hash(inventory)
    except CoverageError as exc:
        return [str(exc)]
    if not isinstance(report, dict):
        return ["report rootはobjectである必要があります"]
    root_keys = {
        "schema_version",
        "report_type",
        "mode",
        "inventory_hash",
        "sources",
        "chunks",
        "dimensions",
        "global_pass",
        "candidates",
        "findings",
        "limitations",
    }
    _validate_exact_keys(report, root_keys, "report", errors)
    if not is_schema_version(report.get("schema_version"), COVERAGE_SCHEMA_VERSION):
        errors.append("schema_versionは2である必要があります")
    if report.get("report_type") != "coverage-driven-review":
        errors.append("report_typeが不正です")
    mode = report.get("mode")
    if mode not in REVIEW_MODES:
        errors.append(f"modeが不正です: {mode!r}")
    elif mode != expected_mode:
        errors.append("modeが指定coverage profileと一致しません")
    if report.get("inventory_hash") != expected_inventory_hash:
        errors.append("inventory_hashが指定inventoryと一致しません")
    sources = report.get("sources")
    if not _is_string_list(sources, nonempty_items=True) or not sources:
        errors.append("sourcesは空でない文字列listである必要があります")
    elif sources != [inventory_source]:
        errors.append("sourcesが指定inventoryと一致しません")
    limitations = report.get("limitations")
    if not _is_string_list(limitations):
        errors.append("limitationsは文字列listである必要があります")
    else:
        inventory_limitations = inventory.get("limitations", [])
        assert isinstance(inventory_limitations, list)
        missing_limitations = [
            item for item in inventory_limitations if item not in limitations
        ]
        if missing_limitations:
            errors.append(
                f"inventoryのlimitationsを保持していません: {missing_limitations}"
            )

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
        required_candidate_keys = {"candidate_id", "source", "line", "resolution"}
        missing_candidate_keys = sorted(required_candidate_keys - candidate.keys())
        if missing_candidate_keys:
            errors.append(
                f"{label}: 必須fieldがありません: {', '.join(missing_candidate_keys)}"
            )
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
        if not _is_integer(candidate.get("line"), minimum=1):
            errors.append(f"{label}: 1以上のlineが必要です")
        elif candidate.get("line", 0) > inventory_line_count:
            errors.append(f"{label}: lineがinventoryの範囲外です")
        if candidate.get("source") != inventory_source:
            errors.append(f"{label}: sourceが指定inventoryと一致しません")
        if "reason" in candidate and not isinstance(candidate.get("reason"), str):
            errors.append(f"{label}: reasonは文字列である必要があります")
        if candidate.get("resolution") in {"excluded", "unresolved"} and (
            not isinstance(candidate.get("reason"), str)
            or not candidate["reason"].strip()
        ):
            errors.append(f"{label}: excluded/unresolvedにはreasonが必要です")

    covered_candidate_ids: set[str] = set()

    def validate_candidate_refs(record: dict[str, object], label: str) -> None:
        candidate_ids = record.get("candidate_ids")
        if not _is_string_list(candidate_ids, nonempty_items=True):
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
    report_chunk_ids: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        if not isinstance(chunk, dict):
            errors.append(f"chunk {index}: objectである必要があります")
            continue
        _validate_exact_keys(
            chunk,
            {"chunk_id", "status", "candidate_ids", "unchecked_scope"},
            f"chunk {index}",
            errors,
        )
        chunk_id = chunk.get("chunk_id")
        if not isinstance(chunk_id, str) or not chunk_id:
            errors.append(f"chunk {index}: chunk_idが必要です")
        elif chunk_id in chunk_ids:
            errors.append(f"chunk {index}: chunk_idが重複しています")
        else:
            chunk_ids.add(chunk_id)
            report_chunk_ids.append(chunk_id)
        _validate_status(chunk, f"chunk {index}", errors)
        validate_candidate_refs(chunk, f"chunk {index}")
        inventory_chunk = next(
            (
                item
                for item in inventory.get("chunks", [])
                if isinstance(item, dict) and item.get("chunk_id") == chunk_id
            ),
            None,
        )
        if isinstance(inventory_chunk, dict):
            start_line = inventory_chunk.get("start_line")
            end_line = inventory_chunk.get("end_line")
            if _is_integer(start_line, minimum=1) and _is_integer(end_line, minimum=1):
                for candidate_id in chunk.get("candidate_ids", []):
                    candidate = candidate_map.get(candidate_id, {})
                    line = candidate.get("line")
                    if _is_integer(line, minimum=1) and not start_line <= line <= end_line:
                        errors.append(
                            f"chunk {index}: candidate {candidate_id}のlineがchunk範囲外です"
                        )
    if report_chunk_ids != inventory_chunk_ids:
        errors.append("chunk IDと順序が指定inventoryと一致しません")

    dimensions = report.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        errors.append("dimensionsは空でないlistである必要があります")
        dimensions = []
    dimension_names: set[str] = set()
    dimension_candidate_ids: set[str] = set()
    dimension_statuses: dict[str, object] = {}
    for index, dimension in enumerate(dimensions, start=1):
        label = f"dimension {index}"
        if not isinstance(dimension, dict):
            errors.append(f"{label}: objectである必要があります")
            continue
        _validate_exact_keys(
            dimension,
            {
                "dimension",
                "status",
                "candidate_ids",
                "candidate_count",
                "finding_count",
                "excluded_count",
                "unresolved_count",
                "exclusion_reasons",
                "unchecked_scope",
            },
            label,
            errors,
        )
        name = dimension.get("dimension")
        if not isinstance(name, str) or not name:
            errors.append(f"{label}: dimension名が必要です")
        elif name in dimension_names:
            errors.append(f"{label}: dimension名が重複しています")
        else:
            dimension_names.add(name)
            dimension_statuses[name] = dimension.get("status")
        _validate_status(dimension, label, errors)
        candidate_ids = dimension.get("candidate_ids")
        if not _is_string_list(candidate_ids, nonempty_items=True):
            errors.append(f"{label}: candidate_idsは文字列listである必要があります")
            candidate_ids = []
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append(f"{label}: candidate_idsが重複しています")
        unknown = set(candidate_ids) - candidate_map.keys()
        if unknown:
            errors.append(f"{label}: 未定義candidateがあります: {sorted(unknown)}")
        dimension_candidate_ids.update(candidate_ids)
        counts: dict[str, int] = {}
        for key in ("candidate_count", "finding_count", "excluded_count", "unresolved_count"):
            value = dimension.get(key)
            if not _is_integer(value, minimum=0):
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
        if not _is_string_list(reasons, nonempty_items=True):
            errors.append(f"{label}: exclusion_reasonsは文字列listである必要があります")
        elif counts["excluded_count"] and not reasons:
            errors.append(f"{label}: excluded candidateには除外理由が必要です")
    required_dimensions = set(DEFAULT_DIMENSIONS)
    if expected_mode == "repository-review":
        required_dimensions.add(REPOSITORY_DIMENSION)
    missing_dimensions = required_dimensions - dimension_names
    if missing_dimensions:
        errors.append(f"必須dimensionがありません: {sorted(missing_dimensions)}")

    global_pass = report.get("global_pass")
    if not isinstance(global_pass, dict):
        errors.append("global_passはobjectである必要があります")
    else:
        _validate_exact_keys(
            global_pass,
            {"status", "candidate_ids", "unchecked_scope"},
            "global_pass",
            errors,
        )
        _validate_status(global_pass, "global_pass", errors)
        validate_candidate_refs(global_pass, "global_pass")
        if global_pass.get("status") == "checked" and any(
            isinstance(chunk, dict) and chunk.get("status") != "checked"
            for chunk in chunks
        ):
            errors.append("global_passをcheckedにする前に全chunkをcheckedにする必要があります")
        if global_pass.get("status") == "checked" and any(
            dimension_statuses.get(name) != "checked" for name in dimension_names
        ):
            errors.append("global_passをcheckedにする前に全dimensionをcheckedにする必要があります")

    untracked_candidates = candidate_map.keys() - covered_candidate_ids
    if untracked_candidates:
        errors.append(
            f"chunkまたはglobal passへ紐付かないcandidateがあります: {sorted(untracked_candidates)}"
        )
    missing_dimension_candidates = candidate_map.keys() - dimension_candidate_ids
    if missing_dimension_candidates:
        errors.append(
            f"dimensionへ紐付かないcandidateがあります: {sorted(missing_dimension_candidates)}"
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
        if not _is_string_list(linked, nonempty_items=True) or not linked:
            errors.append(f"{label}: candidate_idsが必要です")
            continue
        if len(linked) != len(set(linked)):
            errors.append(f"{label}: candidate_idsが重複しています")
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
        valid_location_count = 0
        for location in locations:
            if (
                not isinstance(location, dict)
                or not isinstance(location.get("source"), str)
                or not location.get("source")
                or not _is_integer(location.get("line"), minimum=1)
            ):
                errors.append(f"{label}: locationにはsourceと1以上のlineが必要です")
                continue
            valid_location_count += 1
            location_pairs.add((location["source"], location["line"]))
        if valid_location_count != len(location_pairs):
            errors.append(f"{label}: locationsが重複しています")
        expected_locations = {
            (candidate["source"], candidate["line"])
            for candidate_id in linked
            if candidate_id in candidate_map
            for candidate in (candidate_map[candidate_id],)
            if isinstance(candidate.get("source"), str)
            and bool(candidate.get("source"))
            and _is_integer(candidate.get("line"), minimum=1)
        }
        missing_locations = expected_locations - location_pairs
        if missing_locations:
            errors.append(f"{label}: candidateのlocationを保持していません: {sorted(missing_locations)}")
        extra_locations = location_pairs - expected_locations
        if extra_locations:
            errors.append(f"{label}: candidateにないlocationがあります: {sorted(extra_locations)}")

    expected_finding_candidates = {
        candidate_id for candidate_id, candidate in candidate_map.items()
        if candidate.get("resolution") == "finding"
    }
    omitted = expected_finding_candidates - finding_candidate_ids
    if omitted:
        errors.append(f"findingへ保持されていないcandidateがあります: {sorted(omitted)}")
    return errors
