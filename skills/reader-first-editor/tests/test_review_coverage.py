from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from reader_first.review_coverage import (  # noqa: E402
    CoverageError,
    SEVERITIES,
    build_markdown_inventory,
    build_report_skeleton,
    inventory_hash,
    validate_coverage_report,
)


CLI = SCRIPT_DIR / "review_coverage.py"
SCHEMA = SCRIPT_DIR.parent / "schemas" / "review-coverage.schema.json"
INVENTORY_SCHEMA = SCRIPT_DIR.parent / "schemas" / "markdown-inventory.schema.json"
FINDING_TEXT = "# 文書\n\n候補。"


def finding_report(severity: str = "LOW") -> dict[str, object]:
    inventory = finding_inventory()
    report = _report(inventory, FINDING_TEXT, dimensions=["relationship-clarity"])
    report["candidates"] = [
        {
            "candidate_id": "REL-0001",
            "source": "finding.md",
            "line": 3,
            "resolution": "finding",
        }
    ]
    report["chunks"][0].update(
        {"status": "checked", "candidate_ids": ["REL-0001"], "unchecked_scope": []}
    )
    for dimension in report["dimensions"]:
        dimension.update({"status": "checked", "unchecked_scope": []})
    _dimension(report, "relationship-clarity").update(
        {
            "status": "checked",
            "candidate_ids": ["REL-0001"],
            "candidate_count": 1,
            "finding_count": 1,
            "unchecked_scope": [],
        }
    )
    report["global_pass"].update(
        {"status": "checked", "candidate_ids": [], "unchecked_scope": []}
    )
    report["findings"] = [
        {
            "finding_id": "FINDING-0001",
            "candidate_ids": ["REL-0001"],
            "locations": [{"source": "finding.md", "line": 3}],
            "severity": severity,
        }
    ]
    return report


def finding_inventory() -> dict[str, object]:
    return build_markdown_inventory(FINDING_TEXT, source="finding.md")


def _report(
    inventory: dict[str, object],
    source_text: str,
    *,
    mode: str = "review",
    dimensions: list[str] | None = None,
) -> dict[str, object]:
    return build_report_skeleton(
        inventory,
        source_text=source_text,
        source=str(inventory["source"]),
        mode=mode,
        dimensions=dimensions,
    )


def _dimension(report: dict[str, object], name: str) -> dict[str, object]:
    return next(
        item
        for item in report["dimensions"]
        if isinstance(item, dict) and item.get("dimension") == name
    )


def _validate(
    report: dict[str, object],
    inventory: dict[str, object] | None = None,
    source_text: str = FINDING_TEXT,
    expected_mode: str | None = None,
) -> list[str]:
    bound_inventory = inventory or finding_inventory()
    return validate_coverage_report(
        report,
        bound_inventory,
        source_text=source_text,
        source=str(bound_inventory["source"]),
        expected_mode=expected_mode or str(report.get("mode")),
    )


class ReviewCoverageTests(unittest.TestCase):
    def test_empty_or_whitespace_markdown_is_rejected_at_inventory(self) -> None:
        for text in ("", " \n\t\n"):
            with self.subTest(text=repr(text)):
                with self.assertRaisesRegex(CoverageError, "空または空白のみ"):
                    build_markdown_inventory(text, source="empty.md")

        result = subprocess.run(
            [sys.executable, str(CLI), "inventory", "--text", " \n\t"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("空または空白のみ", result.stderr)

        for source, max_chars in (("", 100), ("empty.md", True)):
            with self.subTest(source=source, max_chars=max_chars):
                with self.assertRaises(CoverageError):
                    build_markdown_inventory("本文。", source=source, max_chars=max_chars)

    def test_inventory_uses_heading_sections_and_reaches_late_section(self) -> None:
        text = """# 手順

## 前半

目立つ問題が三件あります。

## 後半

config/base.yamlを正本とする。
"""
        inventory = build_markdown_inventory(text, source="guide.md", max_chars=200)
        self.assertEqual(inventory["status"], "complete")
        self.assertEqual(inventory["chunk_count"], 3)
        last = inventory["chunks"][-1]
        self.assertEqual(last["headings"], ["手順", "後半"])
        self.assertIn("正本", last["text"])

    def test_table_list_and_code_fence_are_not_split(self) -> None:
        text = """# 定義

| column | type |
|---|---|
| created_at | timestamptz |
| updated_at | timestamptz |

- first item with a long explanation
  - nested item
- second item

```sql
CREATE TABLE events (
  created_at timestamptz
);
```
"""
        inventory = build_markdown_inventory(text, source="schema.md", max_chars=45)
        chunks = inventory["chunks"]
        table_chunks = [chunk for chunk in chunks if "table" in chunk["block_kinds"]]
        list_chunks = [chunk for chunk in chunks if "list" in chunk["block_kinds"]]
        code_chunks = [chunk for chunk in chunks if "code-fence" in chunk["block_kinds"]]
        self.assertEqual(len(table_chunks), 1)
        self.assertEqual(len(list_chunks), 1)
        self.assertEqual(len(code_chunks), 1)
        self.assertIn("updated_at", table_chunks[0]["text"])
        self.assertIn("second item", list_chunks[0]["text"])
        self.assertIn("created_at timestamptz", code_chunks[0]["text"])
        self.assertEqual(inventory["status"], "partial")
        self.assertTrue(inventory["limitations"])

    def test_checked_zero_is_distinct_from_not_checked(self) -> None:
        text = "# 文書\n\n問題はありません。"
        inventory = build_markdown_inventory(text, source="clean.md")
        report = _report(inventory, text, dimensions=["modality-and-scope"])
        dimension = _dimension(report, "modality-and-scope")
        self.assertEqual(dimension["status"], "not-checked")
        self.assertEqual(dimension["finding_count"], 0)
        self.assertEqual(_validate(report, inventory, text), [])

        dimension["status"] = "checked"
        dimension["unchecked_scope"] = []
        report["chunks"][0]["status"] = "checked"
        report["chunks"][0]["unchecked_scope"] = []
        for item in report["dimensions"]:
            item.update({"status": "checked", "unchecked_scope": []})
        report["global_pass"]["status"] = "checked"
        report["global_pass"]["unchecked_scope"] = []
        self.assertEqual(_validate(report, inventory, text), [])

    def test_partial_requires_unchecked_scope(self) -> None:
        text = "# 文書\n\n本文。"
        inventory = build_markdown_inventory(text, source="partial.md")
        report = _report(inventory, text, dimensions=["repository-consistency"])
        _dimension(report, "repository-consistency")["status"] = "partial"
        _dimension(report, "repository-consistency")["unchecked_scope"] = []
        errors = _validate(report, inventory, text)
        self.assertTrue(any("partialには未確認範囲" in error for error in errors))

    def test_finding_candidate_cannot_be_omitted_by_consolidator(self) -> None:
        text = "# 文書\n\n後半に候補。"
        inventory = build_markdown_inventory(text, source="finding.md")
        report = _report(inventory, text, dimensions=["relationship-clarity"])
        report["candidates"] = [
            {
                "candidate_id": "REL-0001",
                "source": "finding.md",
                "line": 3,
                "resolution": "finding",
            }
        ]
        report["chunks"][0]["candidate_ids"] = ["REL-0001"]
        dimension = _dimension(report, "relationship-clarity")
        dimension.update(
            {
                "status": "checked",
                "candidate_ids": ["REL-0001"],
                "candidate_count": 1,
                "finding_count": 1,
                "unchecked_scope": [],
            }
        )
        errors = _validate(report, inventory, text)
        self.assertTrue(any("保持されていないcandidate" in error for error in errors))

        report["findings"] = [
            {
                "finding_id": "FINDING-0001",
                "candidate_ids": ["REL-0001"],
                "locations": [{"source": "finding.md", "line": 3}],
                "severity": "LOW",
            }
        ]
        self.assertFalse(
            any(
                "保持されていないcandidate" in error
                for error in _validate(report, inventory, text)
            )
        )

    def test_all_schema_severities_are_accepted(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        schema_severities = set(
            schema["$defs"]["finding"]["properties"]["severity"]["enum"]
        )
        self.assertEqual(SEVERITIES, schema_severities)
        for severity in schema_severities:
            with self.subTest(severity=severity):
                self.assertEqual(_validate(finding_report(severity)), [])

    def test_invalid_or_missing_severity_is_rejected(self) -> None:
        invalid = finding_report("CRITICAL")
        errors = _validate(invalid)
        self.assertTrue(any("severityが不正" in error for error in errors))

        missing = finding_report()
        del missing["findings"][0]["severity"]
        errors = _validate(missing)
        self.assertTrue(any("severityが不正" in error for error in errors))

        non_string = finding_report()
        non_string["findings"][0]["severity"] = ["HIGH"]
        errors = _validate(non_string)
        self.assertTrue(any("severityが不正" in error for error in errors))

    def test_root_shape_matches_schema_contract(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        required = schema["required"]
        for field in required:
            with self.subTest(missing=field):
                report = finding_report()
                del report[field]
                self.assertTrue(_validate(report))

        report = finding_report()
        report["unexpected"] = True
        errors = _validate(report)
        self.assertTrue(any("未知のfield" in error for error in errors))

    def test_inventory_shape_matches_schema_contract_and_source(self) -> None:
        schema = json.loads(INVENTORY_SCHEMA.read_text(encoding="utf-8"))
        inventory = finding_inventory()
        self.assertEqual(set(schema["required"]), set(inventory))
        self.assertEqual(set(schema["$defs"]["chunk"]["required"]), set(inventory["chunks"][0]))

        forged = json.loads(json.dumps(inventory))
        del forged["chunks"][0]["text"]
        report = finding_report()
        errors = _validate(report, forged)
        self.assertTrue(any("必須field" in error for error in errors))

        old_inventory = finding_inventory()
        old_inventory["schema_version"] = 1
        errors = _validate(finding_report(), old_inventory)
        self.assertTrue(any("schema_versionは2" in error for error in errors))

        replaced_source = _validate(
            finding_report(),
            finding_inventory(),
            "# 文書\n\n置換された本文。",
        )
        self.assertTrue(any("source_hash" in error for error in replaced_source))

        tampered = finding_inventory()
        tampered["chunks"][0]["text"] = "# 文書\n\n省略済み。"
        errors = _validate(finding_report(), tampered)
        self.assertTrue(any("正規inventory" in error for error in errors))

    def test_repository_review_requires_repository_dimension(self) -> None:
        inventory = finding_inventory()
        report = _report(
            inventory,
            FINDING_TEXT,
            mode="repository-review",
            dimensions=["repository-consistency"],
        )
        self.assertIsNotNone(_dimension(report, "repository-consistency"))
        self.assertEqual(
            sum(
                item["dimension"] == "repository-consistency"
                for item in report["dimensions"]
            ),
            1,
        )

        report["dimensions"] = [
            item
            for item in report["dimensions"]
            if item["dimension"] != "repository-consistency"
        ]
        errors = _validate(report, inventory)
        self.assertTrue(any("repository-consistency" in error for error in errors))

        report["mode"] = "review"
        errors = _validate(report, inventory, expected_mode="repository-review")
        self.assertTrue(any("coverage profile" in error for error in errors))

    def test_schema_integer_fields_reject_boolean(self) -> None:
        report = finding_report()
        report["schema_version"] = True
        report["candidates"][0]["line"] = True
        report["findings"][0]["locations"][0]["line"] = True
        _dimension(report, "relationship-clarity")["candidate_count"] = True
        errors = _validate(report)
        self.assertTrue(any("schema_versionは2" in error for error in errors))
        self.assertTrue(any("1以上のline" in error for error in errors))
        self.assertTrue(any("candidate_countは0以上の整数" in error for error in errors))
        self.assertTrue(any("locationにはsourceと1以上のline" in error for error in errors))

        old_report = finding_report()
        old_report["schema_version"] = 1
        self.assertTrue(any("schema_versionは2" in error for error in _validate(old_report)))

        non_integer = finding_report()
        non_integer["candidates"][0]["line"] = "3"
        errors = _validate(non_integer)
        self.assertTrue(any("1以上のline" in error for error in errors))

    def test_closed_nested_objects_reject_unknown_fields(self) -> None:
        mutations = (
            ("chunk", lambda report: report["chunks"][0].update({"unexpected": True})),
            ("dimension", lambda report: report["dimensions"][0].update({"unexpected": True})),
            ("global_pass", lambda report: report["global_pass"].update({"unexpected": True})),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                report = finding_report()
                mutate(report)
                self.assertTrue(
                    any("未知のfield" in error for error in _validate(report))
                )

    def test_report_is_bound_to_inventory_and_required_coverage(self) -> None:
        text = "# 前半\n\n本文。\n\n# 後半\n\n本文。"
        inventory = build_markdown_inventory(
            text,
            source="complete.md",
        )
        report = _report(inventory, text)

        missing_chunk = json.loads(json.dumps(report))
        missing_chunk["chunks"].pop()
        self.assertTrue(
            any("chunk IDと順序" in error for error in _validate(missing_chunk, inventory, text))
        )

        substituted_source = json.loads(json.dumps(report))
        substituted_source["sources"] = ["other.md"]
        self.assertTrue(
            any("sourcesが指定inventory" in error for error in _validate(substituted_source, inventory, text))
        )

        missing_dimension = json.loads(json.dumps(report))
        missing_dimension["dimensions"] = [
            item
            for item in missing_dimension["dimensions"]
            if item["dimension"] != "semantic-preservation"
        ]
        self.assertTrue(
            any("必須dimension" in error for error in _validate(missing_dimension, inventory, text))
        )

        premature_global = json.loads(json.dumps(report))
        premature_global["global_pass"].update(
            {"status": "checked", "unchecked_scope": []}
        )
        self.assertTrue(
            any("全chunkをchecked" in error for error in _validate(premature_global, inventory, text))
        )

        wrong_chunk = json.loads(json.dumps(report))
        wrong_chunk["candidates"] = [
            {
                "candidate_id": "REL-0001",
                "source": "complete.md",
                "line": 7,
                "resolution": "excluded",
                "reason": "fixture",
            }
        ]
        wrong_chunk["chunks"][0]["candidate_ids"] = ["REL-0001"]
        dimension = _dimension(wrong_chunk, "relationship-clarity")
        dimension.update(
            {
                "candidate_ids": ["REL-0001"],
                "candidate_count": 1,
                "excluded_count": 1,
                "exclusion_reasons": ["fixture"],
            }
        )
        self.assertTrue(
            any("lineがchunk範囲外" in error for error in _validate(wrong_chunk, inventory, text))
        )

        partial_text = "# 文書\n\n```\n未完了"
        partial_inventory = build_markdown_inventory(
            partial_text,
            source="partial.md",
        )
        dropped_limitation = _report(partial_inventory, partial_text)
        dropped_limitation["limitations"] = []
        self.assertTrue(
            any(
                "inventoryのlimitationsを保持" in error
                for error in _validate(dropped_limitation, partial_inventory, partial_text)
            )
        )

    def test_candidate_must_belong_to_a_dimension(self) -> None:
        report = finding_report()
        _dimension(report, "relationship-clarity").update(
            {
                "candidate_ids": [],
                "candidate_count": 0,
                "finding_count": 0,
            }
        )
        self.assertTrue(
            any("dimensionへ紐付かないcandidate" in error for error in _validate(report))
        )

    def test_cli_rejects_invalid_severity(self) -> None:
        report = finding_report("CRITICAL")
        inventory = build_markdown_inventory(FINDING_TEXT, source="<text>")
        report["inventory_hash"] = inventory_hash(inventory)
        report["sources"] = ["<text>"]
        report["candidates"][0]["source"] = "<text>"
        report["findings"][0]["locations"][0]["source"] = "<text>"
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            inventory_path = Path(directory) / "inventory.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            inventory_path.write_text(
                json.dumps(inventory, ensure_ascii=False),
                encoding="utf-8",
            )
            validated = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "validate-report",
                    str(report_path),
                    "--inventory",
                    str(inventory_path),
                    "--text",
                    FINDING_TEXT,
                    "--mode",
                    "review",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(validated.returncode, 1, validated.stdout + validated.stderr)
        result = json.loads(validated.stdout)
        self.assertFalse(result["valid"])
        self.assertTrue(any("severityが不正" in error for error in result["errors"]))

    def test_cli_inventory_and_report_validation(self) -> None:
        source_text = "# 文書\n\n本文。"
        result = subprocess.run(
            [sys.executable, str(CLI), "inventory", "--text", source_text],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads(result.stdout)
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            inventory_path = Path(directory) / "inventory.json"
            inventory_path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
            created = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "new-report",
                    "--inventory",
                    str(inventory_path),
                    "--text",
                    source_text,
                    "--mode",
                    "repository-review",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
            report = json.loads(created.stdout)
            self.assertEqual(report["mode"], "repository-review")
            self.assertIsNotNone(_dimension(report, "repository-consistency"))
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            validated = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "validate-report",
                    str(report_path),
                    "--inventory",
                    str(inventory_path),
                    "--text",
                    source_text,
                    "--mode",
                    "repository-review",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        self.assertTrue(json.loads(validated.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
