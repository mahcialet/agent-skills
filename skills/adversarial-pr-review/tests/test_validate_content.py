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

    def test_required_coverage_case_cannot_be_removed(self) -> None:
        def remove_case(data: dict) -> None:
            data["cases"] = [
                case
                for case in data["cases"]
                if case["id"] != "coverage-verification-does-not-replace-blind-pass"
            ]

        errors = self.validate_with_mutation(remove_case)
        self.assertTrue(any("missing required cases" in error for error in errors))

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
