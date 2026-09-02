from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from reader_first.db_consistency import (  # noqa: E402
    DatabaseConsistencyError,
    PeerGroupSpec,
    analyze_peer_groups,
    extract_markdown_tables,
)


CLI = SCRIPT_DIR / "scan_db_consistency.py"


def definition_table(rows: list[tuple[str, str, str, str, str, str]]) -> str:
    lines = [
        "| table | column | type | nullable | default | constraint | comment |",
        "|---|---|---|---|---|---|---|",
    ]
    for table, column, data_type, nullable, default, constraint in rows:
        lines.append(
            f"| {table} | {column} | {data_type} | {nullable} | {default} | {constraint} | 説明 |"
        )
    return "\n".join(lines)


class DatabaseConsistencyTests(unittest.TestCase):
    def test_extracts_required_database_attributes_and_locations(self) -> None:
        text = definition_table(
            [("users", "created_at", "TIMESTAMPTZ", "NO", "now()", "NOT NULL")]
        )
        result = extract_markdown_tables(text, source="database.md", dialect="postgresql")
        self.assertEqual(result["status"], "checked")
        self.assertEqual(result["row_count"], 1)
        row = result["rows"][0]
        self.assertEqual(row["table"], "users")
        self.assertEqual(row["column"], "created_at")
        self.assertEqual(row["type"], "TIMESTAMPTZ")
        self.assertEqual(row["nullable"], "NO")
        self.assertEqual(row["default"], "now()")
        self.assertEqual(row["constraint"], "NOT NULL")
        self.assertEqual(row["comment"], "説明")
        self.assertEqual(row["normalized"]["type"], "timestamptz")
        self.assertEqual(row["line"], 3)

    def test_postgresql_aliases_are_normalized_without_cross_dialect_assumption(self) -> None:
        text = definition_table(
            [
                ("events", "created_at", "timestamp with time zone", "NO", "", ""),
                ("events", "updated_at", "TIMESTAMPTZ", "NO", "", ""),
                ("events", "published_at", "timestamp without time zone", "NO", "", ""),
            ]
        )
        postgres = extract_markdown_tables(text, source="db.md", dialect="postgresql")
        generic = extract_markdown_tables(text, source="db.md", dialect="generic")
        self.assertEqual(
            [row["normalized"]["type"] for row in postgres["rows"]],
            ["timestamptz", "timestamptz", "timestamp"],
        )
        self.assertEqual(generic["rows"][0]["normalized"]["type"], "timestamp with time zone")

    def test_required_header_uses_opposite_polarity_from_nullable(self) -> None:
        text = """| column | type | 必須 |
|---|---|---|
| created_at | timestamptz | yes |
| updated_at | timestamptz | yes |
| deleted_at | timestamptz | yes |
| published_at | timestamptz | no |"""
        extraction = extract_markdown_tables(text, source="required.md")
        self.assertEqual(
            [row["normalized"]["nullable"] for row in extraction["rows"]],
            ["not-null", "not-null", "not-null", "nullable"],
        )
        self.assertTrue(
            all(row["nullable_source"] == "required" for row in extraction["rows"])
        )

        report = analyze_peer_groups(
            extraction,
            [PeerGroupSpec(name="audit-timestamps", column_pattern=r"_at$")],
            attributes=("nullable",),
        )
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["column"], "published_at")
        self.assertEqual(report["candidates"][0]["minority_value"], "nullable")

    def test_english_required_header_uses_required_polarity(self) -> None:
        text = """| Column | Type | Required |
|---|---|---|
| created_at | timestamptz | Yes |
| updated_at | timestamptz | Yes |
| deleted_at | timestamptz | Yes |
| published_at | timestamptz | No |"""
        extraction = extract_markdown_tables(text, source="required-en.md")
        self.assertEqual(
            [row["normalized"]["nullable"] for row in extraction["rows"]],
            ["not-null", "not-null", "not-null", "nullable"],
        )

    def test_inline_code_is_unwrapped_for_matching_and_normalization(self) -> None:
        text = definition_table(
            [
                ("`events`", "`created_at`", "`TIMESTAMPTZ`", "NO", "`now()`", ""),
                ("`events`", "`updated_at`", "`TIMESTAMPTZ`", "NO", "`now()`", ""),
                ("`events`", "`deleted_at`", "`TIMESTAMPTZ`", "NO", "`now()`", ""),
                ("`events`", "`published_at`", "`TIMESTAMP`", "NO", "`now()`", ""),
            ]
        )
        extraction = extract_markdown_tables(text, source="inline-code.md", dialect="postgresql")
        self.assertEqual(extraction["rows"][0]["column"], "`created_at`")
        self.assertEqual(extraction["rows"][0]["normalized"]["type"], "timestamptz")
        report = analyze_peer_groups(
            extraction,
            [PeerGroupSpec(name="timestamps", column_pattern=r"_at$")],
            attributes=("type",),
        )
        self.assertEqual(report["peer_groups"][0]["member_count"], 4)
        self.assertEqual(report["candidate_count"], 1)

    def test_quoted_default_literal_preserves_case_and_whitespace(self) -> None:
        rows = [
            ("events", "created_at", "text", "NO", "'active'", ""),
            ("events", "updated_at", "text", "NO", "'active'", ""),
            ("events", "deleted_at", "text", "NO", "'active'", ""),
            ("events", "published_at", "text", "NO", "'ACTIVE'", ""),
        ]
        report = analyze_peer_groups(
            extract_markdown_tables(definition_table(rows), source="defaults.md"),
            [PeerGroupSpec(name="timestamps", column_pattern=r"_at$")],
            attributes=("default",),
        )
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["candidates"][0]["minority_value"], "'ACTIVE'")

        spaced = definition_table(
            [
                ("events", "a_at", "text", "NO", "'a b'", ""),
                ("events", "b_at", "text", "NO", "'a b'", ""),
                ("events", "c_at", "text", "NO", "'a b'", ""),
                ("events", "d_at", "text", "NO", "'a  b'", ""),
            ]
        )
        spaced_report = analyze_peer_groups(
            extract_markdown_tables(spaced, source="spaces.md"),
            [PeerGroupSpec(name="timestamps", column_pattern=r"_at$")],
            attributes=("default",),
        )
        self.assertEqual(spaced_report["candidate_count"], 1)
        self.assertEqual(spaced_report["candidates"][0]["minority_value"], "'a  b'")

    def test_nullable_header_keeps_nullable_polarity(self) -> None:
        text = """| column | type | nullable |
|---|---|---|
| created_at | timestamptz | yes |
| updated_at | timestamptz | no |"""
        extraction = extract_markdown_tables(text, source="nullable.md")
        self.assertEqual(
            [row["normalized"]["nullable"] for row in extraction["rows"]],
            ["nullable", "not-null"],
        )
        self.assertTrue(
            all(row["nullable_source"] == "nullable" for row in extraction["rows"])
        )

    def test_nullable_and_required_headers_are_partial(self) -> None:
        text = """| column | type | nullable | 必須 |
|---|---|---|---|
| created_at | timestamptz | no | yes |"""
        extraction = extract_markdown_tables(text, source="ambiguous.md")
        self.assertEqual(extraction["status"], "partial")
        self.assertTrue(any("nullableと必須の両方" in item for item in extraction["limitations"]))
        row = extraction["rows"][0]
        self.assertEqual(row["nullable_source"], "nullable")
        self.assertEqual(row["normalized"]["nullable"], "not-null")

    def test_twenty_two_vs_two_creates_candidates_not_verdicts(self) -> None:
        rows: list[tuple[str, str, str, str, str, str]] = []
        for index in range(22):
            rows.append(("events", f"audit_{index:02d}_at", "timestamptz", "NO", "", ""))
        rows.extend(
            [
                ("events", "published_at", "timestamp", "NO", "", ""),
                ("events", "completed_at", "timestamp", "NO", "", ""),
            ]
        )
        extraction = extract_markdown_tables(
            definition_table(rows), source="database.md", dialect="postgresql"
        )
        report = analyze_peer_groups(
            extraction,
            [PeerGroupSpec(name="event-timestamps", column_pattern=r"_at$")],
            attributes=("type",),
        )
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["interpretation"], "candidate-only")
        self.assertEqual(
            {candidate["column"] for candidate in report["candidates"]},
            {"published_at", "completed_at"},
        )
        self.assertEqual(report["peer_groups"][0]["distributions"]["type"], [
            {"value": "timestamptz", "count": 22},
            {"value": "timestamp", "count": 2},
        ])
        for candidate in report["candidates"]:
            self.assertNotIn("verdict", candidate)
            self.assertNotIn("anomaly_status", candidate)

    def test_different_semantic_peer_group_is_not_flagged(self) -> None:
        text = definition_table(
            [
                ("people", "created_at", "timestamptz", "NO", "", ""),
                ("people", "updated_at", "timestamptz", "NO", "", ""),
                ("people", "deleted_at", "timestamptz", "YES", "", ""),
                ("people", "published_at", "timestamptz", "YES", "", ""),
                ("people", "birth_date", "date", "NO", "", ""),
                ("people", "local_time", "timestamp", "NO", "", ""),
            ]
        )
        extraction = extract_markdown_tables(text, source="people.md", dialect="postgresql")
        report = analyze_peer_groups(
            extraction,
            [PeerGroupSpec(name="lifecycle-timestamps", column_pattern=r"_at$")],
            attributes=("type",),
        )
        self.assertEqual(report["peer_groups"][0]["member_count"], 4)
        self.assertEqual(report["candidate_count"], 0)

    def test_parser_failure_is_partial_not_no_findings(self) -> None:
        result = extract_markdown_tables("# 設計\n\n対応していない本文。", source="plain.md")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["row_count"], 0)
        self.assertTrue(result["limitations"])

    def test_peer_group_is_required_for_analysis(self) -> None:
        extraction = extract_markdown_tables(
            definition_table(
                [("events", "created_at", "timestamptz", "NO", "", "")]
            ),
            source="database.md",
        )
        with self.assertRaisesRegex(DatabaseConsistencyError, "1件以上のpeer group"):
            analyze_peer_groups(extraction, [])

    def test_unmatched_or_small_peer_group_is_partial(self) -> None:
        extraction = extract_markdown_tables(
            definition_table(
                [("events", "created_at", "timestamptz", "NO", "", "")]
            ),
            source="database.md",
        )
        for pattern, expected_count in ((r"^missing$", 0), (r"_at$", 1)):
            with self.subTest(pattern=pattern):
                report = analyze_peer_groups(
                    extraction,
                    [PeerGroupSpec(name="timestamps", column_pattern=pattern)],
                )
                self.assertEqual(report["status"], "partial")
                self.assertEqual(report["peer_groups"][0]["member_count"], expected_count)
                self.assertTrue(any("必要な4件" in item for item in report["limitations"]))

    def test_cli_requires_peer_group(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "--text", definition_table([])],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--peer-group", result.stderr)

    def test_cli_emits_candidate_only_report(self) -> None:
        text = definition_table(
            [
                ("events", "created_at", "timestamptz", "NO", "", ""),
                ("events", "updated_at", "timestamptz", "NO", "", ""),
                ("events", "deleted_at", "timestamptz", "YES", "", ""),
                ("events", "published_at", "timestamp", "YES", "", ""),
            ]
        )
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--text",
                text,
                "--dialect",
                "postgresql",
                "--peer-group",
                r"timestamps=_at$",
                "--attribute",
                "type",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["interpretation"], "candidate-only")


if __name__ == "__main__":
    unittest.main()
