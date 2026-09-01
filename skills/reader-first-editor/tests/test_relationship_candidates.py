from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from reader_first.relationship_candidates import (  # noqa: E402
    RelationshipScanError,
    SourceText,
    build_candidate_report,
    load_tripwires,
)


SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCE = SKILL_DIR / "references" / "ja" / "relationship-clarity.md"
CLI = SCRIPT_DIR / "scan_relationships.py"


class RelationshipCandidateTests(unittest.TestCase):
    def test_reference_contains_initial_deterministic_scope(self) -> None:
        self.assertEqual(
            load_tripwires(REFERENCE),
            ("正本", "source of truth", "source-of-truth"),
        )

    def test_late_candidate_is_reported_with_location(self) -> None:
        text = "前半です。\n問題はありません。\nconfig/base.yamlを正本とする。"
        report = build_candidate_report(
            [SourceText(label="guide.md", text=text)],
            load_tripwires(REFERENCE),
            vocabulary_source="references/ja/relationship-clarity.md",
        )
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(
            report["candidates"][0],
            {
                "candidate_id": "REL-0001",
                "source": "guide.md",
                "line": 3,
                "column": 18,
                "end_column": 20,
                "term": "正本",
                "matched_text": "正本",
            },
        )

    def test_all_occurrences_and_english_case_are_reported(self) -> None:
        text = "正本と正本。\nß Source of Truth / source-of-truth"
        report = build_candidate_report(
            [SourceText(label="terms.md", text=text)],
            load_tripwires(REFERENCE),
            vocabulary_source="references/ja/relationship-clarity.md",
        )
        self.assertEqual(report["candidate_count"], 4)
        self.assertEqual(
            [candidate["matched_text"] for candidate in report["candidates"]],
            ["正本", "正本", "Source of Truth", "source-of-truth"],
        )
        self.assertEqual(report["candidates"][2]["column"], 3)

    def test_legal_defined_and_clarified_usages_remain_candidates_only(self) -> None:
        sources = [
            SourceText(label="legal.md", text="署名済み契約書の正本を法務部が保管する。"),
            SourceText(label="defined.md", text="本手順では承認済みPDFを『正本』と呼ぶ。"),
            SourceText(
                label="clear.md",
                text="SKILL.mdを正本とする。変更はSKILL.mdだけに加え、そこから生成する。",
            ),
        ]
        report = build_candidate_report(
            sources,
            load_tripwires(REFERENCE),
            vocabulary_source="references/ja/relationship-clarity.md",
        )
        self.assertEqual(report["candidate_count"], 3)
        self.assertEqual(report["interpretation"], "candidate-only")
        for candidate in report["candidates"]:
            self.assertNotIn("verdict", candidate)
            self.assertNotIn("severity", candidate)
            self.assertNotIn("finding", candidate)

    def test_invalid_vocabulary_marker_fails_explicitly(self) -> None:
        with self.assertRaises(RelationshipScanError):
            load_tripwires(SKILL_DIR / "SKILL.md")

    def test_cli_does_not_emit_finding_judgment(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--text",
                "設定を反映する。契約書の正本を保管する。Source of Truth。",
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["candidate_count"], 2)
        self.assertEqual(output["interpretation"], "candidate-only")
        self.assertNotIn("finding", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
