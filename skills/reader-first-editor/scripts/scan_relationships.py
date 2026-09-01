#!/usr/bin/env python3
"""関係表現の候補語と位置だけを列挙する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from reader_first.relationship_candidates import (
    RelationshipScanError,
    SourceText,
    build_candidate_report,
    load_tripwires,
)
from reader_first.state import TOOL_VERSION


SKILL_DIR = Path(__file__).resolve().parent.parent
REFERENCE_PATH = SKILL_DIR / "references" / "ja" / "relationship-clarity.md"
VOCABULARY_SOURCE = "references/ja/relationship-clarity.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="関係表現の候補語と位置をcandidate-only JSONで返す"
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="確認するtext")
    source.add_argument(
        "--file",
        action="append",
        type=Path,
        dest="files",
        help="確認するUTF-8 file。複数指定可",
    )
    return parser


def read_sources(args: argparse.Namespace) -> list[SourceText]:
    if args.text is not None:
        return [SourceText(label="<text>", text=args.text)]
    sources: list[SourceText] = []
    for path in args.files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RelationshipScanError(f"入力fileを読み込めません: {path}: {exc}") from exc
        sources.append(SourceText(label=str(path), text=text))
    return sources


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = build_candidate_report(
            read_sources(args),
            load_tripwires(REFERENCE_PATH),
            vocabulary_source=VOCABULARY_SOURCE,
        )
    except RelationshipScanError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
