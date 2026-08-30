#!/usr/bin/env python3
"""optionalな日本語構造sensorとprovider-neutralなA/B集約CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reader_first.japanese_syntax import (
    SyntaxAnalysisError,
    analyze_japanese,
    build_syntax_ab_report,
)
from reader_first.state import TOOL_VERSION


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SyntaxAnalysisError(f"text fileを読み込めません: {path}: {exc}") from exc


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyntaxAnalysisError(f"JSON fileを読み込めません: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SyntaxAnalysisError("JSON rootはobjectである必要があります")
    return value


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="reader-first-editor optional Japanese syntax sensor",
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    analyze = commands.add_parser(
        "analyze",
        help="GiNZAの構造観測値または非致命のavailability resultを返す",
    )
    source = analyze.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="解析する日本語text")
    source.add_argument("--text-file", type=Path, help="UTF-8の入力file")
    analyze.add_argument("--model", default="ja_ginza", help="spaCy model名")

    ab_report = commands.add_parser(
        "ab-report",
        help="LLM-onlyとLLM-plus-signalsのpaired resultを集約する",
    )
    ab_report.add_argument("--input", type=Path, required=True, help="A/B observation JSON")
    return parser


def run(args: argparse.Namespace) -> int:
    if args.command == "analyze":
        text = args.text if args.text is not None else _read_text(args.text_file)
        _print_json(analyze_japanese(text, model=args.model))
        return 0
    if args.command == "ab-report":
        _print_json(build_syntax_ab_report(_read_json(args.input)))
        return 0
    raise SyntaxAnalysisError(f"未対応commandです: {args.command}")


def main() -> int:
    try:
        return run(build_parser().parse_args())
    except SyntaxAnalysisError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
