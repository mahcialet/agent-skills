"""Public GitHub PRからreference-only corpus candidateを組み立てる。"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .state import ID_MATERIAL, StoreError, deterministic_candidate_id

GITHUB_API_VERSION = "2022-11-28"
DEFAULT_API_ROOT = "https://api.github.com/"
MARKDOWN_SUFFIXES = {".md", ".mdx", ".markdown"}
FORBIDDEN_FIXTURE_KEYS = {"body", "content", "diff_hunk", "login", "patch"}


class GitHubCollectionError(StoreError):
    """GitHub sourceを安全かつ完全に収集できない。"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require_dict(value: Any, context: str) -> dict:
    if not isinstance(value, dict):
        raise GitHubCollectionError(f"{context}はobjectである必要があります")
    return value


def _require_list(value: Any, context: str) -> list:
    if not isinstance(value, list):
        raise GitHubCollectionError(f"{context}はarrayである必要があります")
    return value


def _require_string(container: dict, key: str, context: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value.strip():
        raise GitHubCollectionError(f"{context}.{key}がありません")
    return value


def _optional_string(container: dict, key: str, context: str) -> str | None:
    value = container.get(key)
    if value is not None and not isinstance(value, str):
        raise GitHubCollectionError(f"{context}.{key}はstringまたはnullである必要があります")
    return value


def _require_sha(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise GitHubCollectionError(f"{context}には40桁のcommit SHAが必要です")
    return value


def _optional_sha(value: Any, context: str) -> str | None:
    if value is None:
        return None
    return _require_sha(value, context)


def _require_nonnegative_int(value: Any, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise GitHubCollectionError(f"{context}は0以上のintegerである必要があります")
    return value


def _repository_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise GitHubCollectionError("repositoryはowner/name形式で明示してください")
    return value


def _is_markdown(path: str) -> bool:
    return Path(path).suffix.lower() in MARKDOWN_SUFFIXES


def _author_type(user: Any) -> str:
    if not isinstance(user, dict):
        return "unknown"
    account_type = user.get("type")
    login = user.get("login")
    if account_type == "Bot" or (isinstance(login, str) and login.lower().endswith("[bot]")):
        return "bot"
    if account_type in {"User", "Organization"}:
        return "human"
    return "unknown"


def _reject_raw_text_fields(value: Any, context: str = "fixture") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in FORBIDDEN_FIXTURE_KEYS:
                raise GitHubCollectionError(
                    f"{context}にraw third-party text fieldを保存できません: {key}"
                )
            _reject_raw_text_fields(item, f"{context}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_raw_text_fields(item, f"{context}[{index}]")


class GitHubRestClient:
    """標準ライブラリだけでpublic GitHub REST APIを読むclient。"""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_root: str = DEFAULT_API_ROOT,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.token = token
        self.api_root = api_root.rstrip("/") + "/"
        self.opener = opener

    def _safe_url(self, path_or_url: str) -> str:
        url = (
            path_or_url
            if path_or_url.startswith(("https://", "http://"))
            else urljoin(self.api_root, path_or_url.lstrip("/"))
        )
        expected = urlparse(self.api_root)
        actual = urlparse(url)
        if actual.scheme != "https" or actual.netloc != expected.netloc:
            raise GitHubCollectionError("GitHub pagination URLが許可されたAPI host外を指しています")
        return url

    def _request(self, path_or_url: str) -> tuple[Any, Any]:
        url = self._safe_url(path_or_url)
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "reader-first-editor-corpus-tool",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers)
        try:
            with self.opener(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, response.headers
        except HTTPError as exc:
            remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
            if exc.code in {403, 429} and remaining == "0":
                reset = exc.headers.get("X-RateLimit-Reset", "unknown")
                raise GitHubCollectionError(
                    f"GitHub API rate limitに達しました（reset={reset}）"
                ) from exc
            raise GitHubCollectionError(f"GitHub API requestが失敗しました: HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise GitHubCollectionError(f"GitHub API responseを取得できません: {exc}") from exc

    def get_object(self, path: str) -> dict:
        payload, _ = self._request(path)
        return _require_dict(payload, path)

    def get_paginated(self, path: str) -> list:
        items: list = []
        next_url: str | None = path
        seen: set[str] = set()
        while next_url is not None:
            safe_url = self._safe_url(next_url)
            if safe_url in seen:
                raise GitHubCollectionError("GitHub paginationに循環があります")
            seen.add(safe_url)
            payload, headers = self._request(safe_url)
            items.extend(_require_list(payload, path))
            next_url = _next_link(headers.get("Link"))
        return items


def _next_link(link_header: str | None) -> str | None:
    if not link_header:
        return None
    for part in link_header.split(","):
        match = re.fullmatch(r'\s*<([^>]+)>;\s*rel="([^"]+)"\s*', part)
        if match and match.group(2) == "next":
            return match.group(1)
    return None


def _normalize_repository(raw: dict) -> dict:
    license_data = raw.get("license")
    license_spdx = license_data.get("spdx_id") if isinstance(license_data, dict) else None
    if license_spdx == "NOASSERTION":
        license_spdx = None
    return {
        "full_name": _require_string(raw, "full_name", "repository"),
        "private": raw.get("private"),
        "visibility": raw.get("visibility"),
        "license_spdx_id": license_spdx,
    }


def _normalize_pull_request(raw: dict) -> dict:
    head = _require_dict(raw.get("head"), "pull_request.head")
    base = _require_dict(raw.get("base"), "pull_request.base")
    user = raw.get("user")
    return {
        "number": raw.get("number"),
        "url": _require_string(raw, "html_url", "pull_request"),
        "state": _require_string(raw, "state", "pull_request"),
        "draft": raw.get("draft"),
        "merged_at": raw.get("merged_at"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "head_revision": head.get("sha"),
        "base_revision": base.get("sha"),
        "merge_revision": raw.get("merge_commit_sha"),
        "author_type": _author_type(user),
    }


def _normalize_file(raw: Any) -> dict:
    item = _require_dict(raw, "files[]")
    return {
        "path": _require_string(item, "filename", "files[]"),
        "status": _require_string(item, "status", "files[]"),
        "blob_revision": item.get("sha"),
        "previous_path": item.get("previous_filename"),
        "additions": item.get("additions"),
        "deletions": item.get("deletions"),
        "changes": item.get("changes"),
        "url": item.get("blob_url"),
    }


def _normalize_review(raw: Any) -> dict:
    item = _require_dict(raw, "reviews[]")
    return {
        "id": item.get("id"),
        "state": item.get("state"),
        "submitted_at": item.get("submitted_at"),
        "commit_revision": item.get("commit_id"),
        "author_type": _author_type(item.get("user")),
        "body_present": bool(item.get("body")),
    }


def _normalize_review_comment(raw: Any) -> dict:
    item = _require_dict(raw, "review_comments[]")
    return {
        "id": item.get("id"),
        "review_id": item.get("pull_request_review_id"),
        "in_reply_to_id": item.get("in_reply_to_id"),
        "author_type": _author_type(item.get("user")),
        "path": item.get("path"),
        "line": item.get("line"),
        "side": item.get("side"),
        "original_line": item.get("original_line"),
        "commit_revision": item.get("commit_id"),
        "original_revision": item.get("original_commit_id"),
        "created_at": item.get("created_at"),
        "body_present": bool(item.get("body")),
    }


def fetch_pull_request_snapshot(
    client: GitHubRestClient,
    repository: str,
    pr_number: int,
    *,
    clock: Callable[[], str] = _utc_now,
) -> dict:
    """必要な全endpointの成功後に、raw textを除いたsnapshotを返す。"""

    repository = _repository_name(repository)
    if pr_number < 1:
        raise GitHubCollectionError("PR番号は1以上で指定してください")
    base = f"repos/{repository}"
    raw_repository = client.get_object(base)
    normalized_repository = _normalize_repository(raw_repository)
    if normalized_repository["full_name"].lower() != repository.lower():
        raise GitHubCollectionError("GitHub responseのrepositoryが明示指定と一致しません")
    if normalized_repository["private"] is not False:
        raise GitHubCollectionError("private repositoryはこのcollectorでは収集できません")
    if normalized_repository["visibility"] not in {"public", None}:
        raise GitHubCollectionError("public repositoryだけを収集できます")
    raw_pull = client.get_object(f"{base}/pulls/{pr_number}")
    raw_files = client.get_paginated(f"{base}/pulls/{pr_number}/files?per_page=100")
    raw_reviews = client.get_paginated(f"{base}/pulls/{pr_number}/reviews?per_page=100")
    raw_comments = client.get_paginated(f"{base}/pulls/{pr_number}/comments?per_page=100")
    snapshot = {
        "schema_version": 1,
        "retrieved_at": clock(),
        "repository": normalized_repository,
        "pull_request": _normalize_pull_request(raw_pull),
        "files": [_normalize_file(item) for item in raw_files],
        "reviews": [_normalize_review(item) for item in raw_reviews],
        "review_comments": [_normalize_review_comment(item) for item in raw_comments],
    }
    return validate_snapshot(snapshot, repository=repository, pr_number=pr_number)


def load_recorded_snapshot(path: Path, *, repository: str, pr_number: int) -> dict:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GitHubCollectionError(f"recorded fixtureを読み込めません: {path}: {exc}") from exc
    _reject_raw_text_fields(snapshot)
    return validate_snapshot(snapshot, repository=repository, pr_number=pr_number)


def validate_snapshot(snapshot: Any, *, repository: str, pr_number: int) -> dict:
    data = deepcopy(_require_dict(snapshot, "snapshot"))
    _reject_raw_text_fields(data, "snapshot")
    if data.get("schema_version") != 1:
        raise GitHubCollectionError("snapshot.schema_versionが未対応です")
    _require_string(data, "retrieved_at", "snapshot")
    repository_data = _require_dict(data.get("repository"), "snapshot.repository")
    pull = _require_dict(data.get("pull_request"), "snapshot.pull_request")
    files = _require_list(data.get("files"), "snapshot.files")
    reviews = _require_list(data.get("reviews"), "snapshot.reviews")
    comments = _require_list(data.get("review_comments"), "snapshot.review_comments")
    full_name = _require_string(repository_data, "full_name", "snapshot.repository")
    if full_name.lower() != _repository_name(repository).lower():
        raise GitHubCollectionError("fixture/API responseのrepositoryが明示指定と一致しません")
    if repository_data.get("private") is not False:
        raise GitHubCollectionError("private repositoryはこのcollectorでは収集できません")
    if repository_data.get("visibility") not in {"public", None}:
        raise GitHubCollectionError("public repositoryだけを収集できます")
    if pull.get("number") != pr_number:
        raise GitHubCollectionError("fixture/API responseのPR番号が明示指定と一致しません")
    _require_sha(pull.get("head_revision"), "pull_request.head_revision")
    _require_sha(pull.get("base_revision"), "pull_request.base_revision")
    _optional_sha(pull.get("merge_revision"), "pull_request.merge_revision")
    for key in ("url", "state", "created_at", "updated_at"):
        _require_string(pull, key, "snapshot.pull_request")
    if not isinstance(pull.get("draft"), bool):
        raise GitHubCollectionError("snapshot.pull_request.draftはbooleanである必要があります")
    _optional_string(pull, "merged_at", "snapshot.pull_request")
    if pull.get("author_type") not in {"human", "bot", "unknown"}:
        raise GitHubCollectionError("snapshot.pull_request.author_typeが不正です")
    normalized_files = [_validate_file(item) for item in files]
    normalized_reviews = [_validate_review(item) for item in reviews]
    normalized_comments = [_validate_comment(item) for item in comments]
    data["files"] = normalized_files
    data["reviews"] = normalized_reviews
    data["review_comments"] = normalized_comments
    _build_threads(normalized_comments)
    return data


def _validate_file(value: Any) -> dict:
    item = _require_dict(value, "snapshot.files[]")
    _require_string(item, "path", "snapshot.files[]")
    _require_string(item, "status", "snapshot.files[]")
    _require_sha(item.get("blob_revision"), "snapshot.files[].blob_revision")
    _optional_string(item, "previous_path", "snapshot.files[]")
    _require_string(item, "url", "snapshot.files[]")
    for key in ("additions", "deletions", "changes"):
        _require_nonnegative_int(item.get(key), f"snapshot.files[].{key}")
    return item


def _validate_review(value: Any) -> dict:
    item = _require_dict(value, "snapshot.reviews[]")
    _require_nonnegative_int(item.get("id"), "snapshot.reviews[].id")
    _require_string(item, "state", "snapshot.reviews[]")
    _optional_string(item, "submitted_at", "snapshot.reviews[]")
    _optional_sha(item.get("commit_revision"), "snapshot.reviews[].commit_revision")
    if item.get("author_type") not in {"human", "bot", "unknown"}:
        raise GitHubCollectionError("snapshot.reviews[].author_typeが不正です")
    if not isinstance(item.get("body_present"), bool):
        raise GitHubCollectionError("snapshot.reviews[].body_presentはbooleanである必要があります")
    return item


def _validate_comment(value: Any) -> dict:
    item = _require_dict(value, "snapshot.review_comments[]")
    _require_nonnegative_int(item.get("id"), "snapshot.review_comments[].id")
    for key in ("review_id", "in_reply_to_id", "line", "original_line"):
        value = item.get(key)
        if value is not None:
            _require_nonnegative_int(value, f"snapshot.review_comments[].{key}")
    if item.get("author_type") not in {"human", "bot", "unknown"}:
        raise GitHubCollectionError("snapshot.review_comments[].author_typeが不正です")
    _require_string(item, "path", "snapshot.review_comments[]")
    for key in ("side", "created_at"):
        _optional_string(item, key, "snapshot.review_comments[]")
    for key in ("commit_revision", "original_revision"):
        _optional_sha(item.get(key), f"snapshot.review_comments[].{key}")
    if not isinstance(item.get("body_present"), bool):
        raise GitHubCollectionError(
            "snapshot.review_comments[].body_presentはbooleanである必要があります"
        )
    return item


def _build_threads(comments: list[dict]) -> list[dict]:
    by_id = {comment["id"]: comment for comment in comments}
    if len(by_id) != len(comments):
        raise GitHubCollectionError("inline review comment IDが重複しています")
    roots: dict[int, list[dict]] = {}
    for comment in comments:
        parent_id = comment.get("in_reply_to_id")
        if parent_id is None:
            roots[comment["id"]] = [comment]
            continue
        parent = by_id.get(parent_id)
        if parent is None or parent.get("in_reply_to_id") is not None:
            raise GitHubCollectionError("inline review threadがpartial responseで不完全です")
        roots.setdefault(parent_id, [parent]).append(comment)
    threads: list[dict] = []
    for root_id, entries in sorted(roots.items()):
        root = entries[0]
        threads.append(
            {
                "id": root_id,
                "review_id": root.get("review_id"),
                "path": root["path"],
                "line": root.get("line"),
                "side": root.get("side"),
                "original_line": root.get("original_line"),
                "original_revision": root.get("original_revision"),
                "latest_revision": root.get("commit_revision"),
                "created_at": root.get("created_at"),
                "reply_count": len(entries) - 1,
                "human_comment_count": sum(
                    entry["author_type"] == "human" for entry in entries
                ),
                "bot_comment_count": sum(entry["author_type"] == "bot" for entry in entries),
                "body_count": sum(entry["body_present"] for entry in entries),
            }
        )
    return threads


def build_reference_only_candidates(
    snapshot: dict,
    *,
    language: str,
    translation_status: str,
    genre: str,
    reader_description: str,
    reader_evidence: str,
    selected_files: list[str] | None = None,
) -> list[dict]:
    """SnapshotからMarkdown fileごとのcandidate draftを作る。"""

    repository = snapshot["repository"]
    pull = snapshot["pull_request"]
    head_revision = pull["head_revision"]
    markdown_files = {
        item["path"]: item
        for item in snapshot["files"]
        if _is_markdown(item["path"]) and item["status"].lower() != "removed"
    }
    if selected_files:
        unknown = sorted(set(selected_files) - markdown_files.keys())
        if unknown:
            raise GitHubCollectionError(
                "指定fileは変更済みMarkdownに含まれません: " + ", ".join(unknown)
            )
        paths = sorted(set(selected_files))
    else:
        paths = sorted(markdown_files)
    if not paths:
        raise GitHubCollectionError("PRに変更済みMarkdown fileがありません")

    threads = _build_threads(snapshot["review_comments"])
    candidates = []
    for path in paths:
        changed_file = markdown_files[path]
        thread_paths = {path, changed_file.get("previous_path")}
        file_threads = [thread for thread in threads if thread["path"] in thread_paths]
        sample_type, quality, expected, signal_type, confidence = _classify(
            pull=pull,
            reviews=snapshot["reviews"],
            threads=file_threads,
        )
        summary = _review_summary(
            pull=pull,
            reviews=snapshot["reviews"],
            threads=file_threads,
        )
        record = {
            "id": "placeholder",
            "id_material": deepcopy(ID_MATERIAL),
            "schema_version": 1,
            "language": language,
            "translation_status": translation_status,
            "genre": genre,
            "reader": {
                "description": reader_description,
                "evidence_source": reader_evidence,
            },
            "sample_type": sample_type,
            "quality_class": quality,
            "source": {
                "type": "github-pr",
                "repository": repository["full_name"],
                "pr_number": pull["number"],
                "commit": head_revision,
                "file": path,
                "span": "file",
                "url": changed_file["url"],
                "immutable_revision": head_revision,
                "retrieved_at": snapshot["retrieved_at"],
                "correlation_group": f"github:{repository['full_name']}#pr-{pull['number']}",
            },
            "authorship": {
                "initial": pull["author_type"],
                "final": "human-reviewed" if _human_reviews(snapshot["reviews"]) else "unknown",
                "ai_assisted": "unknown",
            },
            "review_signal": {
                "type": signal_type,
                "summary": summary,
                "raw_text_included": False,
            },
            "rights": {
                "status": "unknown",
                "repository_license": repository.get("license_spdx_id"),
                "raw_text_redistribution": "unknown",
                "review_comment_redistribution": "unknown",
                "local_only": True,
                "redacted": False,
                "notes": "repository licenseは観測値であり、PR/review textの権利確認ではない",
            },
            "handling": {
                "anonymized": False,
                "modified": False,
                "redactions": [],
            },
            "text": {
                "storage": "reference-only",
                "content_hash": f"git-blob-sha1:{changed_file['blob_revision']}",
                "content": None,
            },
            "annotations": {
                "expected_behavior": expected,
                "rationale": "",
                "semantic_invariants": [],
                "do_not_change": [],
                "expected_reread_risks": [],
            },
            "decision": {
                "state": "candidate",
                "reviewer": None,
                "decided_at": None,
                "reason": "GitHub metadataからreference-only candidateを生成",
            },
            "confidence": confidence,
            "created_at": snapshot["retrieved_at"],
            "github_evidence": {
                "repository": {
                    "visibility": repository.get("visibility") or "public",
                    "license_spdx_id": repository.get("license_spdx_id"),
                },
                "pull_request": {
                    key: pull.get(key)
                    for key in (
                        "state",
                        "draft",
                        "merged_at",
                        "created_at",
                        "updated_at",
                        "base_revision",
                        "head_revision",
                        "merge_revision",
                    )
                },
                "changed_file": {
                    key: changed_file.get(key)
                    for key in (
                        "status",
                        "previous_path",
                        "blob_revision",
                        "additions",
                        "deletions",
                        "changes",
                    )
                },
                "reviews": deepcopy(snapshot["reviews"]),
                "inline_threads": deepcopy(file_threads),
            },
        }
        record["id"] = deterministic_candidate_id(record)
        candidates.append(record)
    return candidates


def _human_reviews(reviews: list[dict]) -> list[dict]:
    return [review for review in reviews if review["author_type"] == "human"]


def _classify(
    *, pull: dict, reviews: list[dict], threads: list[dict]
) -> tuple[str, str, str, str, str]:
    head = pull["head_revision"]
    human_reviews = _human_reviews(reviews)
    final_approvals = [
        review
        for review in human_reviews
        if review["state"].upper() == "APPROVED" and review["commit_revision"] == head
    ]
    revised_after_review = any(
        review["state"].upper() == "CHANGES_REQUESTED"
        and review["commit_revision"] is not None
        and review["commit_revision"] != head
        for review in human_reviews
    ) or any(
        thread["original_revision"] is not None and thread["original_revision"] != head
        for thread in threads
        if thread["human_comment_count"]
    )
    if pull["merged_at"] and final_approvals and revised_after_review:
        return (
            "review-directed-revision",
            "borderline",
            "review-only",
            "human-inline-review-followed-by-final-approval",
            "medium",
        )
    if pull["merged_at"] and final_approvals:
        return (
            "positive-reviewed",
            "clean",
            "no-change",
            "human-approval-on-final-head",
            "medium",
        )
    return (
        "human-revision",
        "borderline",
        "review-only",
        "insufficient-human-review-signal",
        "low",
    )


def _review_summary(*, pull: dict, reviews: list[dict], threads: list[dict]) -> str:
    head = pull["head_revision"]
    human = _human_reviews(reviews)
    approvals = sum(review["state"].upper() == "APPROVED" for review in human)
    final_approvals = sum(
        review["state"].upper() == "APPROVED" and review["commit_revision"] == head
        for review in human
    )
    human_comments = sum(thread["human_comment_count"] for thread in threads)
    return (
        f"merged={pull['merged_at'] is not None}; human_reviews={len(human)}; "
        f"approvals={approvals}; final_head_approvals={final_approvals}; "
        f"inline_threads={len(threads)}; human_inline_comments={human_comments}; "
        "raw_text_included=false"
    )


def default_github_token() -> str | None:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")


__all__ = [
    "GitHubCollectionError",
    "GitHubRestClient",
    "build_reference_only_candidates",
    "default_github_token",
    "fetch_pull_request_snapshot",
    "load_recorded_snapshot",
    "validate_snapshot",
]
