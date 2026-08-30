from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from email.message import Message
from pathlib import Path
from typing import Self
from urllib.error import HTTPError

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from reader_first.github import (
    GitHubCollectionError,
    GitHubRestClient,
    build_reference_only_candidates,
    fetch_pull_request_snapshot,
    load_recorded_snapshot,
    validate_snapshot,
)
from reader_first.state import (
    RecordValidationError,
    prepare_candidate_record,
    validate_corpus_record,
)

SKILL_DIR = Path(__file__).resolve().parents[1]
CLI = SKILL_DIR / "scripts" / "corpus_tool.py"
FIXTURE_DIR = SKILL_DIR / "tests" / "fixtures" / "github"
REPOSITORY = "digital-go-jp/design-tokens"


def build_candidates(fixture: str, pr_number: int) -> list[dict]:
    snapshot = load_recorded_snapshot(
        FIXTURE_DIR / fixture,
        repository=REPOSITORY,
        pr_number=pr_number,
    )
    return build_reference_only_candidates(
        snapshot,
        language="ja",
        translation_status="native",
        genre="technical-readme",
        reader_description="design token利用者",
        reader_evidence="利用者がCLIで指定",
    )


class FakeResponse:
    def __init__(self, payload: object, *, link: str | None = None) -> None:
        self.payload = json.dumps(payload).encode("utf-8")
        self.headers = Message()
        if link:
            self.headers["Link"] = link

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


class GitHubRestClientTests(unittest.TestCase):
    def test_pagination_reads_all_pages(self) -> None:
        responses = {
            "https://api.github.test/items?page=1": FakeResponse(
                [{"id": 1}],
                link='<https://api.github.test/items?page=2>; rel="next", '
                '<https://api.github.test/items?page=2>; rel="last"',
            ),
            "https://api.github.test/items?page=2": FakeResponse([{"id": 2}]),
        }
        calls: list[str] = []

        def opener(request: object, *, timeout: int) -> FakeResponse:
            self.assertEqual(timeout, 30)
            url = request.full_url  # type: ignore[attr-defined]
            calls.append(url)
            return responses[url]

        client = GitHubRestClient(api_root="https://api.github.test/", opener=opener)
        self.assertEqual(client.get_paginated("items?page=1"), [{"id": 1}, {"id": 2}])
        self.assertEqual(calls, list(responses))

    def test_pagination_rejects_external_next_url(self) -> None:
        response = FakeResponse(
            [],
            link='<https://example.invalid/capture-token>; rel="next"',
        )
        client = GitHubRestClient(
            api_root="https://api.github.test/",
            opener=lambda request, timeout: response,
        )
        with self.assertRaises(GitHubCollectionError):
            client.get_paginated("items")

    def test_private_repository_stops_before_pr_endpoints(self) -> None:
        class PrivateClient:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def get_object(self, path: str) -> dict:
                self.calls.append(path)
                return {
                    "full_name": "private-owner/private-repo",
                    "private": True,
                    "visibility": "private",
                    "license": None,
                }

            def get_paginated(self, path: str) -> list:
                raise AssertionError(f"private sourceでpaginationしてはいけません: {path}")

        client = PrivateClient()
        with self.assertRaisesRegex(GitHubCollectionError, "private repository"):
            fetch_pull_request_snapshot(  # type: ignore[arg-type]
                client,
                "private-owner/private-repo",
                1,
            )
        self.assertEqual(client.calls, ["repos/private-owner/private-repo"])

    def test_rate_limit_response_has_explicit_error(self) -> None:
        headers = Message()
        headers["X-RateLimit-Remaining"] = "0"
        headers["X-RateLimit-Reset"] = "1234567890"

        def opener(request: object, *, timeout: int) -> FakeResponse:
            raise HTTPError(
                request.full_url,  # type: ignore[attr-defined]
                403,
                "rate limited",
                headers,
                None,
            )

        client = GitHubRestClient(api_root="https://api.github.test/", opener=opener)
        with self.assertRaisesRegex(GitHubCollectionError, "rate limit"):
            client.get_object("resource")


class RecordedFixtureTests(unittest.TestCase):
    def test_pr_138_is_reference_only_positive_reviewed_candidate(self) -> None:
        candidate = prepare_candidate_record(
            build_candidates("pr-138-reference-only.json", 138)[0]
        )
        self.assertEqual(candidate["sample_type"], "positive-reviewed")
        self.assertEqual(candidate["annotations"]["expected_behavior"], "no-change")
        self.assertEqual(candidate["text"]["storage"], "reference-only")
        self.assertIsNone(candidate["text"]["content"])
        self.assertEqual(candidate["rights"]["status"], "unknown")
        self.assertTrue(candidate["rights"]["local_only"])
        self.assertEqual(candidate["github_evidence"]["inline_threads"], [])
        self.assertFalse(candidate["review_signal"]["raw_text_included"])

    def test_pr_187_aligns_inline_thread_with_follow_up_revision(self) -> None:
        candidate = prepare_candidate_record(
            build_candidates("pr-187-reference-only.json", 187)[0]
        )
        self.assertEqual(candidate["sample_type"], "review-directed-revision")
        thread = candidate["github_evidence"]["inline_threads"][0]
        self.assertEqual(thread["reply_count"], 1)
        self.assertEqual(thread["human_comment_count"], 2)
        self.assertEqual(
            thread["original_revision"],
            "5edc14ec75b0db63690f602c0d81ac750bd11275",
        )
        self.assertEqual(
            candidate["source"]["immutable_revision"],
            "2c608edfe3c7395f1e48487ece884b11f9dff190",
        )

    def test_fixture_with_raw_text_field_is_rejected(self) -> None:
        fixture = json.loads(
            (FIXTURE_DIR / "pr-138-reference-only.json").read_text(encoding="utf-8")
        )
        fixture["reviews"][0]["body"] = "保存してはいけないreview text"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unsafe.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with self.assertRaisesRegex(GitHubCollectionError, "raw third-party text"):
                load_recorded_snapshot(path, repository=REPOSITORY, pr_number=138)

    def test_private_repository_is_rejected(self) -> None:
        snapshot = json.loads(
            (FIXTURE_DIR / "pr-138-reference-only.json").read_text(encoding="utf-8")
        )
        snapshot["repository"]["private"] = True
        with self.assertRaisesRegex(GitHubCollectionError, "private repository"):
            validate_snapshot(snapshot, repository=REPOSITORY, pr_number=138)

    def test_partial_inline_thread_is_rejected(self) -> None:
        snapshot = json.loads(
            (FIXTURE_DIR / "pr-187-reference-only.json").read_text(encoding="utf-8")
        )
        snapshot["review_comments"] = snapshot["review_comments"][1:]
        with self.assertRaisesRegex(GitHubCollectionError, "partial response"):
            validate_snapshot(snapshot, repository=REPOSITORY, pr_number=187)

    def test_pr_without_changed_markdown_is_rejected(self) -> None:
        snapshot = load_recorded_snapshot(
            FIXTURE_DIR / "pr-138-reference-only.json",
            repository=REPOSITORY,
            pr_number=138,
        )
        snapshot["files"][0]["path"] = "src/example.py"
        with self.assertRaisesRegex(GitHubCollectionError, "Markdown"):
            build_reference_only_candidates(
                snapshot,
                language="ja",
                translation_status="native",
                genre="technical-readme",
                reader_description="利用者",
                reader_evidence="CLI input",
            )

    def test_github_evidence_cannot_disagree_with_source(self) -> None:
        candidate = prepare_candidate_record(
            build_candidates("pr-138-reference-only.json", 138)[0]
        )
        candidate = deepcopy(candidate)
        candidate["github_evidence"]["pull_request"]["head_revision"] = "a" * 40
        with self.assertRaises(RecordValidationError):
            validate_corpus_record(candidate)


class GitHubCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_dir = Path(self.temp.name) / "data"

    def run_cli(self, *extra: str, fixture: str = "pr-138-reference-only.json") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(CLI),
                "--data-dir",
                str(self.data_dir),
                "corpus",
                "collect-github",
                "--repository",
                REPOSITORY,
                "--pr-number",
                "138",
                "--language",
                "ja",
                "--translation-status",
                "native",
                "--genre",
                "technical-readme",
                "--reader-description",
                "design token利用者",
                "--fixture",
                str(FIXTURE_DIR / fixture),
                "--actor",
                "collector",
                "--reason",
                "recorded fixture",
                *extra,
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dry_run_is_offline_and_does_not_write(self) -> None:
        result = self.run_cli("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertTrue(output["dry_run"])
        self.assertFalse(output["network_accessed"])
        self.assertEqual(output["records"][0]["sample_type"], "positive-reviewed")
        self.assertFalse(self.data_dir.exists())

    def test_apply_creates_candidate_without_modifying_core(self) -> None:
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(output["changes_rule_behavior"])
        self.assertEqual(output["modified_core"], [])
        self.assertEqual(len(output["created"]), 1)
        record_path = self.data_dir / "candidates" / f"{output['created'][0]}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        self.assertEqual(record["text"]["storage"], "reference-only")
        self.assertEqual(record["decision"]["state"], "candidate")


if __name__ == "__main__":
    unittest.main()
