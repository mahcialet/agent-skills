from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "scripts"))

import validate_content as validator  # noqa: E402


class CoverageGapSuiteTestCase(unittest.TestCase):
    def validate_with_mutation(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = Path(temporary) / "adversarial-pr-review"
            shutil.copytree(SKILL_DIR / "evals", skill_dir / "evals")
            coverage_path = skill_dir / "evals" / "coverage-gap-audit.yaml"
            data = json.loads(coverage_path.read_text(encoding="utf-8"))
            mutate(data)
            coverage_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            errors: list[str] = []
            validator.validate_suites(skill_dir, errors)
            return errors

    def validate_eval_tree_with_mutation(self, mutate) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            skill_dir = Path(temporary) / "adversarial-pr-review"
            shutil.copytree(SKILL_DIR / "evals", skill_dir / "evals")
            mutate(skill_dir / "evals")
            errors: list[str] = []
            validator.validate_suites(skill_dir, errors)
            return errors

    def test_historical_cases_preserve_frozen_provenance(self) -> None:
        errors = self.validate_with_mutation(lambda data: None)
        self.assertEqual([], errors)

    def test_historical_case_without_provenance_is_rejected(self) -> None:
        def remove_provenance(data: dict) -> None:
            data["cases"][0].pop("provenance")

        errors = self.validate_with_mutation(remove_provenance)
        self.assertTrue(any("frozen provenance" in error for error in errors))

    def test_historical_case_with_different_comment_is_rejected(self) -> None:
        def replace_comment(data: dict) -> None:
            data["cases"][0]["provenance"] = data["cases"][0][
                "provenance"
            ].replace("discussion_r3917733760", "discussion_r0000000000")

        errors = self.validate_with_mutation(replace_comment)
        self.assertTrue(any("frozen provenance" in error for error in errors))

    def test_historical_case_with_changed_input_is_rejected(self) -> None:
        def replace_input(data: dict) -> None:
            data["cases"][0]["input"] = "unrelated scenario"

        errors = self.validate_with_mutation(replace_input)
        self.assertTrue(
            any("canonical input digest mismatch" in error for error in errors)
        )

    def test_historical_case_with_changed_expected_is_rejected(self) -> None:
        def replace_expected(data: dict) -> None:
            data["cases"][0]["expected"] += " but skip the audit"

        errors = self.validate_with_mutation(replace_expected)
        self.assertTrue(
            any("canonical expected digest mismatch" in error for error in errors)
        )

    def test_new_coverage_cases_with_changed_input_are_rejected(self) -> None:
        historical_ids = set(validator.HISTORICAL_PROVENANCE)
        required_ids = set(validator.CANONICAL_FIXTURE_DIGESTS)
        for case_id in sorted(required_ids - historical_ids):

            def replace_input(data: dict, case_id: str = case_id) -> None:
                case = next(
                    case for case in data["cases"] if case["id"] == case_id
                )
                case["input"] = "unrelated scenario"

            with self.subTest(case_id=case_id):
                errors = self.validate_with_mutation(replace_input)
                self.assertTrue(
                    any(
                        case_id in error and "canonical input digest mismatch" in error
                        for error in errors
                    )
                )

    def test_new_coverage_cases_with_changed_expected_are_rejected(self) -> None:
        historical_ids = set(validator.HISTORICAL_PROVENANCE)
        required_ids = set(validator.CANONICAL_FIXTURE_DIGESTS)
        for case_id in sorted(required_ids - historical_ids):

            def replace_expected(data: dict, case_id: str = case_id) -> None:
                case = next(
                    case for case in data["cases"] if case["id"] == case_id
                )
                case["expected"] = "unrelated expected behavior"

            with self.subTest(case_id=case_id):
                errors = self.validate_with_mutation(replace_expected)
                self.assertTrue(
                    any(
                        case_id in error and "canonical expected digest mismatch" in error
                        for error in errors
                    )
                )

    def test_required_coverage_case_cannot_be_removed(self) -> None:
        def remove_case(data: dict) -> None:
            data["cases"] = [
                case
                for case in data["cases"]
                if case["id"] != "coverage-verification-does-not-replace-blind-pass"
            ]

        errors = self.validate_with_mutation(remove_case)
        self.assertTrue(any("missing required cases" in error for error in errors))

    def test_coverage_cases_must_remain_in_their_required_suite(self) -> None:
        case_id = "coverage-finding-count-is-not-completion"

        def relocate_case(evals_dir: Path) -> None:
            coverage_path = evals_dir / "coverage-gap-audit.yaml"
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            case = next(case for case in coverage["cases"] if case["id"] == case_id)
            coverage["cases"].remove(case)
            coverage_path.write_text(
                json.dumps(coverage, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            levels_path = evals_dir / "adversarial-levels.yaml"
            levels = json.loads(levels_path.read_text(encoding="utf-8"))
            levels["cases"].append(case)
            levels_path.write_text(
                json.dumps(levels, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        errors = self.validate_eval_tree_with_mutation(relocate_case)
        self.assertTrue(
            any(
                "required cases for suite coverage-gap-audit" in error
                for error in errors
            )
        )

    def test_docs_only_counterexample_requires_false_positive_control(self) -> None:
        def weaken_expected(data: dict) -> None:
            case = next(
                case
                for case in data["cases"]
                if case["id"] == "coverage-doc-only-change-no-companion-finding"
            )
            case["expected"] = "Inspect the documentation change."

        errors = self.validate_with_mutation(weaken_expected)
        self.assertTrue(
            any("behavior-change trigger does not apply" in error for error in errors)
        )


class CoverageGapReportOrderTestCase(unittest.TestCase):
    def errors_for_sections(self, sections: list[str]) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.md"
            path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
            errors: list[str] = []
            validator.require_ordered_tokens(
                path, validator.REPORT_SECTION_ORDER, errors
            )
            return errors

    def errors_for_text(self, text: str) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.md"
            path.write_text(text, encoding="utf-8")
            errors: list[str] = []
            validator.require_ordered_tokens(
                path, validator.REPORT_SECTION_ORDER, errors
            )
            return errors

    def test_coverage_gap_section_between_impact_and_findings_is_accepted(self) -> None:
        self.assertEqual([], self.errors_for_sections(list(validator.REPORT_SECTION_ORDER)))

    def test_coverage_gap_section_after_findings_is_rejected(self) -> None:
        sections = list(validator.REPORT_SECTION_ORDER)
        sections.remove("## Coverage gap audit")
        sections.insert(sections.index("## Findings") + 1, "## Coverage gap audit")
        errors = self.errors_for_sections(sections)
        self.assertTrue(any("out of order" in error for error in errors))

    def test_heading_inside_fenced_code_is_not_counted(self) -> None:
        sections = list(validator.REPORT_SECTION_ORDER)
        sections.remove("## Coverage gap audit")
        sections.insert(
            sections.index("## Findings"), "```text\n## Coverage gap audit\n```"
        )
        sections.insert(sections.index("## Findings") + 1, "## Coverage gap audit")
        errors = self.errors_for_sections(sections)
        self.assertTrue(any("out of order" in error for error in errors))

    def test_heading_inside_indented_code_is_not_counted(self) -> None:
        sections = list(validator.REPORT_SECTION_ORDER)
        sections[sections.index("## Coverage gap audit")] = (
            "    ## Coverage gap audit"
        )
        errors = self.errors_for_sections(sections)
        self.assertTrue(any("missing required token" in error for error in errors))

    def test_longer_fence_requires_matching_length(self) -> None:
        text = """## Scope and parameters
````text
not a visible report
```
## Review contract
## Requirement traceability
## Impact comparison
## Coverage gap audit
## Findings
## Hypotheses
## Evidence ledger
## Test evidence
## Unexecuted validation
## Residual risks
````
"""
        errors = self.errors_for_text(text)
        self.assertTrue(
            any(
                "missing required token '## Review contract'" in error
                for error in errors
            )
        )

    def test_duplicate_required_heading_is_rejected(self) -> None:
        sections = list(validator.REPORT_SECTION_ORDER)
        sections.insert(sections.index("## Coverage gap audit") + 1, "## Coverage gap audit")
        errors = self.errors_for_sections(sections)
        self.assertTrue(any("exactly once" in error for error in errors))


class PortableLocationTestCase(unittest.TestCase):
    def errors_for(self, text: str) -> list[str]:
        errors: list[str] = []
        validator.validate_example_location(Path("synthetic.md"), text, errors)
        return errors

    def test_relative_inline_locations_are_accepted(self) -> None:
        for locator in (
            "sample-repo/src/policy.py:1",
            "sample-repo/src/policy.py:16-19",
            "sample-repo/docs/path with spaces.md:16",
        ):
            with self.subTest(locator=locator):
                text = (
                    "- Repository label: `sample-repo`\n"
                    f"- Location: `{locator}`"
                )
                self.assertEqual([], self.errors_for(text))

    def test_unverified_parts_use_explicit_fallback_fields(self) -> None:
        cases = (
            (
                "- Repository label: unverified\n"
                "- Location: `src/policy.py:16`"
            ),
            (
                "- Repository label: `sample-repo`\n"
                "- Location: `sample-repo/src/policy.py`\n"
                "- Confirmed symbol: `PolicyTable`\n"
                "- Location line status: unverified"
            ),
            (
                "- Repository label: unverified\n"
                "- Location: `src/policy.py`\n"
                "- Confirmed symbol: `PolicyTable`\n"
                "- Location line status: unverified"
            ),
            (
                "- Repository label: unverified\n"
                "- Location: `docs/policy.md`\n"
                "- Location line status: unverified"
            ),
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertEqual([], self.errors_for(text))

    def test_api_routes_outside_location_are_accepted(self) -> None:
        route_text = (
            "- Repository label: `sample-repo`\n"
            "- Location: `sample-repo/src/handler.py:16`\n"
            "- Actor / trigger: GET `/v1/export`, `/home/profile`, or "
            "`/v1/export.json:16`"
        )
        self.assertEqual([], self.errors_for(route_text))

    def test_nonportable_or_unverified_location_parts_are_rejected(self) -> None:
        for repository, locator in (
            ("sample-repo", "/srv/work/sample-repo/src/policy.py:16"),
            ("sample-repo", r"C:\work\sample-repo\src\policy.py:16"),
            ("sample-repo", r"\\server\share\policy.py:16"),
            ("sample-repo", "file:///srv/work/sample-repo/policy.py:16"),
            ("sample-repo", "~/sample-repo/policy.py:16"),
            ("sample-repo", "sample-repo/src/../outside.py:16"),
            ("sample-repo", "sample-repo/C:/work/policy.py:16"),
            ("sample-repo", "sample-repo/src/policy.py:0"),
            ("sample-repo", "sample-repo/src/policy.py:19-16"),
            ("other-repo", "sample-repo/src/policy.py:16"),
        ):
            with self.subTest(locator=locator):
                text = (
                    f"- Repository label: `{repository}`\n"
                    f"- Location: `{locator}`"
                )
                self.assertTrue(self.errors_for(text))

        unverified_prefix = (
            "- Repository label: unverified\n"
            "- Location: `unverified/src/policy.py:16`"
        )
        self.assertTrue(self.errors_for(unverified_prefix))

    def test_coverage_example_validates_each_location(self) -> None:
        coverage_path = SKILL_DIR / "examples" / "coverage-gap-audit.md"
        text = coverage_path.read_text(encoding="utf-8")
        errors: list[str] = []
        validator.validate_coverage_example_locations(coverage_path, text, errors)
        self.assertEqual([], errors)

        invalid = text.replace(
            "sample-repo/src/repository_review.py:84",
            "/srv/work/sample-repo/src/repository_review.py:84",
            1,
        )
        errors = []
        validator.validate_coverage_example_locations(coverage_path, invalid, errors)
        self.assertTrue(any("portable relative locator" in error for error in errors))

    def test_location_inside_fenced_code_is_not_counted(self) -> None:
        text = (
            "```text\n"
            "- Repository label: `sample-repo`\n"
            "- Location: `sample-repo/src/fake.py:9`\n"
            "```"
        )
        self.assertTrue(self.errors_for(text))

    def test_location_rejects_trailing_text_links_and_continuations(self) -> None:
        for suffix in (
            ", confirmed source location",
            ", handler for `/v1/export`",
            " [16行目](/srv/work/sample-repo/src/policy.py:16)",
            " [source](src/policy.py#L16)",
            " /srv/work/sample-repo/src/policy.py:16",
            " /etc/passwd",
            " /root/repo/Makefile:16",
            " /etc/passwd:1",
            "\n  [16行目](/srv/work/sample-repo/src/policy.py:16)",
            "\n  [source](src/policy.py#L16)",
            "\n  /srv/work/sample-repo/src/policy.py:16",
            "\n  `/srv/work/sample-repo/src/policy.py:16`",
            "\n  `/custom/checkout/src/policy.py:16`",
            "\n  `/projects/repo/src/main:16-19`",
            "\n  `" r"C:\work\sample-repo\src\policy.py:16" "`",
        ):
            with self.subTest(suffix=suffix):
                text = (
                    "- Repository label: `sample-repo`\n"
                    "- Location: `sample-repo/src/policy.py:16`"
                    f"{suffix}"
                )
                self.assertTrue(self.errors_for(text))

    def test_line_unverified_requires_status_and_validates_optional_symbol(self) -> None:
        for suffix in (
            "",
            "\n- Confirmed symbol: `PolicyTable`",
            "\n- Confirmed symbol: PolicyTable\n- Location line status: unverified",
            "\n- Confirmed symbol: `One`\n- Confirmed symbol: `Two`\n"
            "- Location line status: unverified",
        ):
            with self.subTest(suffix=suffix):
                text = (
                    "- Repository label: `sample-repo`\n"
                    "- Location: `sample-repo/src/policy.py`"
                    f"{suffix}"
                )
                self.assertTrue(self.errors_for(text))

    def test_duplicate_or_line_only_location_is_rejected(self) -> None:
        duplicate = (
            "- Repository label: `sample-repo`\n"
            "- Location: `sample-repo/src/policy.py:16`\n"
            "- Location: [16行目](/srv/work/sample-repo/src/policy.py:16)"
        )
        line_only = (
            "- Repository label: `sample-repo`\n"
            "- Location: [16行目](/srv/work/sample-repo/src/policy.py:16)"
        )
        self.assertTrue(self.errors_for(duplicate))
        self.assertTrue(self.errors_for(line_only))


if __name__ == "__main__":
    unittest.main()
