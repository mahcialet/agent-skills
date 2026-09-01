#!/usr/bin/env python3
"""Markdown DB定義表から明示peer group内の少数値候補を列挙する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from reader_first.db_consistency import (
    DatabaseConsistencyError,
    PeerGroupSpec,
    analyze_peer_groups,
    extract_markdown_tables,
)
from reader_first.state import TOOL_VERSION


def _source_group(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="確認するMarkdown text")
    source.add_argument("--file", type=Path, help="確認するUTF-8 Markdown file")


def _parse_group(value: str) -> PeerGroupSpec:
    parts = value.split("=", 2)
    if len(parts) not in {2, 3} or not all(parts):
        raise argparse.ArgumentTypeError(
            "peer groupはNAME=COLUMN_REGEXまたはNAME=COLUMN_REGEX=TABLE_REGEXで指定します"
        )
    return PeerGroupSpec(
        name=parts[0],
        column_pattern=parts[1],
        table_pattern=parts[2] if len(parts) == 3 else None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="DB定義表の構造とpeer group内の少数値をcandidate-only JSONで返す"
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    _source_group(parser)
    parser.add_argument("--dialect", choices=("generic", "postgresql"), default="generic")
    parser.add_argument(
        "--peer-group",
        action="append",
        type=_parse_group,
        default=[],
        help="NAME=COLUMN_REGEX[=TABLE_REGEX]。意味上のgroupを先に明示する",
    )
    parser.add_argument(
        "--attribute",
        action="append",
        choices=("type", "nullable", "default", "constraint"),
    )
    parser.add_argument("--min-group-size", type=int, default=4)
    parser.add_argument("--dominance-ratio", type=float, default=0.75)
    return parser


def _read_source(args: argparse.Namespace) -> tuple[str, str]:
    if args.text is not None:
        return "<text>", args.text
    try:
        return str(args.file), args.file.read_text(encoding="utf-8")
    except OSError as exc:
        raise DatabaseConsistencyError(f"入力fileを読み込めません: {args.file}: {exc}") from exc


def main() -> int:
    args = build_parser().parse_args()
    try:
        source, text = _read_source(args)
        extraction = extract_markdown_tables(text, source=source, dialect=args.dialect)
        result = analyze_peer_groups(
            extraction,
            args.peer_group,
            attributes=tuple(args.attribute or ("type", "nullable", "default", "constraint")),
            min_group_size=args.min_group_size,
            dominance_ratio=args.dominance_ratio,
        )
    except DatabaseConsistencyError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
