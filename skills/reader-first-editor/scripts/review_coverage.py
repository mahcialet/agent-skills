#!/usr/bin/env python3
"""Markdown構造inventoryとcoverage reportの検証を行う。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from reader_first.review_coverage import (
    CoverageError,
    build_markdown_inventory,
    build_report_skeleton,
    validate_coverage_report,
)
from reader_first.state import TOOL_VERSION


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CoverageError(f"JSONを読み込めません: {path}: {exc}") from exc


def _read_source(text: str | None, file: Path | None) -> tuple[str, str]:
    if text is not None:
        return "<text>", text
    assert file is not None
    try:
        return str(file), file.read_text(encoding="utf-8")
    except OSError as exc:
        raise CoverageError(f"入力fileを読み込めません: {file}: {exc}") from exc


def _source_group(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="inventory化するMarkdown text")
    source.add_argument("--file", type=Path, help="inventory化するUTF-8 Markdown file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="coverage-driven reviewの補助ツール")
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="Markdownの構造chunkをJSONで返す")
    _source_group(inventory)
    inventory.add_argument("--max-chars", type=int, default=12_000)

    skeleton = subparsers.add_parser("new-report", help="未確認状態のcoverage reportを作る")
    skeleton.add_argument("--inventory", type=Path, required=True)
    skeleton.add_argument("--dimension", action="append", dest="dimensions")

    validate = subparsers.add_parser("validate-report", help="coverage reportの整合を検証する")
    validate.add_argument("report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "inventory":
            label, text = _read_source(args.text, args.file)
            result = build_markdown_inventory(text, source=label, max_chars=args.max_chars)
        elif args.command == "new-report":
            inventory = _read_json(args.inventory)
            if not isinstance(inventory, dict):
                raise CoverageError("inventory rootはobjectである必要があります")
            keyword = {"dimensions": args.dimensions} if args.dimensions else {}
            result = build_report_skeleton(inventory, **keyword)
        else:
            report = _read_json(args.report)
            errors = validate_coverage_report(report)
            if errors:
                print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False, indent=2))
                return 1
            result = {"valid": True, "errors": []}
    except CoverageError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
