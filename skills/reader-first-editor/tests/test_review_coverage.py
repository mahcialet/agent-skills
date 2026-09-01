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
    SEVERITIES,
    build_markdown_inventory,
    build_report_skeleton,
    validate_coverage_report,
)


CLI = SCRIPT_DIR / "review_coverage.py"
SCHEMA = SCRIPT_DIR.parent / "schemas" / "review-coverage.schema.json"


def finding_report(severity: str = "LOW") -> dict[str, object]:
    inventory = build_markdown_inventory("# 文書\n\n候補。", source="finding.md")
    report = build_report_skeleton(inventory, dimensions=["relationship-clarity"])
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
    report["dimensions"][0].update(
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


class ReviewCoverageTests(unittest.TestCase):
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
        inventory = build_markdown_inventory("# 文書\n\n問題はありません。", source="clean.md")
        report = build_report_skeleton(inventory, dimensions=["modality-and-scope"])
        dimension = report["dimensions"][0]
        self.assertEqual(dimension["status"], "not-checked")
        self.assertEqual(dimension["finding_count"], 0)
        self.assertEqual(validate_coverage_report(report), [])

        dimension["status"] = "checked"
        dimension["unchecked_scope"] = []
        report["chunks"][0]["status"] = "checked"
        report["chunks"][0]["unchecked_scope"] = []
        report["global_pass"]["status"] = "checked"
        report["global_pass"]["unchecked_scope"] = []
        self.assertEqual(validate_coverage_report(report), [])

    def test_partial_requires_unchecked_scope(self) -> None:
        inventory = build_markdown_inventory("# 文書\n\n本文。", source="partial.md")
        report = build_report_skeleton(inventory, dimensions=["repository-consistency"])
        report["dimensions"][0]["status"] = "partial"
        report["dimensions"][0]["unchecked_scope"] = []
        errors = validate_coverage_report(report)
        self.assertTrue(any("partialには未確認範囲" in error for error in errors))

    def test_finding_candidate_cannot_be_omitted_by_consolidator(self) -> None:
        inventory = build_markdown_inventory("# 文書\n\n後半に候補。", source="finding.md")
        report = build_report_skeleton(inventory, dimensions=["relationship-clarity"])
        report["candidates"] = [
            {
                "candidate_id": "REL-0001",
                "source": "finding.md",
                "line": 3,
                "resolution": "finding",
            }
        ]
        report["chunks"][0]["candidate_ids"] = ["REL-0001"]
        dimension = report["dimensions"][0]
        dimension.update(
            {
                "status": "checked",
                "candidate_ids": ["REL-0001"],
                "candidate_count": 1,
                "finding_count": 1,
                "unchecked_scope": [],
            }
        )
        errors = validate_coverage_report(report)
        self.assertTrue(any("保持されていないcandidate" in error for error in errors))

        report["findings"] = [
            {
                "finding_id": "FINDING-0001",
                "candidate_ids": ["REL-0001"],
                "locations": [{"source": "finding.md", "line": 3}],
                "severity": "LOW",
            }
        ]
        self.assertFalse(any("保持されていないcandidate" in error for error in validate_coverage_report(report)))

    def test_all_schema_severities_are_accepted(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        schema_severities = set(
            schema["$defs"]["finding"]["properties"]["severity"]["enum"]
        )
        self.assertEqual(SEVERITIES, schema_severities)
        for severity in schema_severities:
            with self.subTest(severity=severity):
                self.assertEqual(validate_coverage_report(finding_report(severity)), [])

    def test_invalid_or_missing_severity_is_rejected(self) -> None:
        invalid = finding_report("CRITICAL")
        errors = validate_coverage_report(invalid)
        self.assertTrue(any("severityが不正" in error for error in errors))

        missing = finding_report()
        del missing["findings"][0]["severity"]
        errors = validate_coverage_report(missing)
        self.assertTrue(any("severityが不正" in error for error in errors))

        non_string = finding_report()
        non_string["findings"][0]["severity"] = ["HIGH"]
        errors = validate_coverage_report(non_string)
        self.assertTrue(any("severityが不正" in error for error in errors))

    def test_cli_rejects_invalid_severity(self) -> None:
        report = finding_report("CRITICAL")
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            validated = subprocess.run(
                [sys.executable, str(CLI), "validate-report", str(report_path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(validated.returncode, 1, validated.stdout + validated.stderr)
        result = json.loads(validated.stdout)
        self.assertFalse(result["valid"])
        self.assertTrue(any("severityが不正" in error for error in result["errors"]))

    def test_cli_inventory_and_report_validation(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "inventory", "--text", "# 文書\n\n本文。"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        inventory = json.loads(result.stdout)
        report = build_report_skeleton(inventory)
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            validated = subprocess.run(
                [sys.executable, str(CLI), "validate-report", str(report_path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)
        self.assertTrue(json.loads(validated.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
