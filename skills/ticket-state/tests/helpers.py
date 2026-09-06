from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in os.sys.path:
    os.sys.path.insert(0, str(SCRIPTS))

from ticket_state.errors import RemoteError
from ticket_state.transport import HttpRequest, HttpResponse


def write_config(
    path: Path,
    *,
    backlog_permissions: str = '["description:write", "comment:append"]',
    redmine_permissions: str = '["description:write", "comment:append"]',
    backlog_allowlist_id: str = "PROJ-1",
    concurrency: str = "best_effort",
) -> None:
    path.write_text(
        f"""schema_version = 1

[instances.backlog]
provider = "backlog"
base_url = "https://example.backlog.com"
api_key_env = "BACKLOG_TEST_KEY"

[instances.redmine]
provider = "redmine"
base_url = "https://redmine.example.invalid/redmine"
api_key_env = "REDMINE_TEST_KEY"

[profiles.backlog]
instance = "backlog"
project_id = 10
project_key = "PROJ"
read_scope = "project"
format = "markdown"
concurrency = "{concurrency}"

[profiles.backlog.write_allowlist]
"{backlog_allowlist_id}" = {backlog_permissions}

[profiles.redmine]
instance = "redmine"
project_id = 20
read_scope = "project"
format = "textile"

[profiles.redmine.write_allowlist]
"7" = {redmine_permissions}
""",
        encoding="utf-8",
    )


def snapshot() -> dict[str, str]:
    return {
        "goal": "安全に共有状態を更新する",
        "current_state": "実装中",
        "decisions": "dry-runはremote mutation 0",
        "constraints": "既存記述を保持する",
        "progress": "coreを実装した",
        "blockers": "なし",
        "unresolved_issues": "live API未検証",
        "next_actions": "mock testを実行する",
        "verification_status": "単体テスト中",
    }


def update_request(*, profile: str = "backlog", ticket: str | None = None) -> dict[str, object]:
    if profile == "backlog":
        base = "# Current State\nold\n\n# Notes\nkeep\n"
        proposed = "# Current State\nnew\n\n# Notes\nkeep\n"
        target = ticket or "PROJ-1"
    else:
        base = "h1. Current State\nold\n\nh1. Notes\nkeep\n"
        proposed = "h1. Current State\nnew\n\nh1. Notes\nkeep\n"
        target = ticket or "7"
    from ticket_state.model import sha256_text

    return {
        "schema_version": 1,
        "operation": "update-state",
        "profile": profile,
        "ticket": target,
        "base_description_sha256": sha256_text(base),
        "proposed_description": proposed,
        "edited_sections": ["Current State"],
        "change_summary": ["現在地を更新"],
        "snapshot": snapshot(),
        "snapshot_description_sha256": sha256_text(proposed),
        "state_changed": True,
        "visibility_confirmed": True,
        "source_visibility": "public-only",
    }


class FakeTrackerTransport:
    def __init__(self) -> None:
        self.backlog_description = "# Current State\nold\n\n# Notes\nkeep\n"
        self.redmine_description = "h1. Current State\nold\n\nh1. Notes\nkeep\n"
        self.backlog_comments: list[dict[str, object]] = []
        self.redmine_journals: list[dict[str, object]] = []
        self.requests: list[HttpRequest] = []
        self.mutation_requests = 0
        self.timeout_after_mutation = False
        self.partial_description_only = False
        self.project_id_override: int | None = None
        self.redirect_next = False
        self.mutation_status: int | None = None
        self.issue_key_override: str | None = None
        self.issue_numeric_id_override: int | None = None
        self.change_description_after_comment_lookup = False
        self.backlog_formatting_rule = "markdown"
        self.redmine_private_notes = False
        self.redmine_success_status = 204

    def send(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        if request.is_mutation:
            self.mutation_requests += 1
            if self.mutation_status is not None:
                return self._json(self.mutation_status, {"errors": [{"message": "simulated"}]})
        if self.redirect_next:
            self.redirect_next = False
            return HttpResponse(302, {"Location": "https://evil.invalid/"}, b"")
        parsed = urlsplit(request.url)
        path = parsed.path
        query = parse_qs(parsed.query)
        if "example.backlog.com" == parsed.hostname:
            response = self._backlog(request, path, query)
        elif "redmine.example.invalid" == parsed.hostname:
            response = self._redmine(request, path, query)
        else:
            raise AssertionError(f"unexpected host: {parsed.hostname}")
        if request.is_mutation and self.timeout_after_mutation:
            self.timeout_after_mutation = False
            raise RemoteError("simulated timeout", result_unknown=True, mutation_attempted=True)
        return response

    def _backlog(self, request: HttpRequest, path: str, query: dict[str, list[str]]) -> HttpResponse:
        if path == "/api/v2/projects/10" and request.method == "GET":
            return self._json(
                200,
                {
                    "id": 10,
                    "projectKey": "PROJ",
                    "textFormattingRule": self.backlog_formatting_rule,
                },
            )
        if path.endswith("/comments") and request.method == "GET":
            comments = sorted(self.backlog_comments, key=lambda item: int(item["id"]), reverse=True)
            if "maxId" in query:
                limit = int(query["maxId"][0])
                comments = [item for item in comments if int(item["id"]) <= limit]
            if self.change_description_after_comment_lookup and any(
                "ticket-state/" in str(item.get("content", "")) for item in comments
            ):
                self.change_description_after_comment_lookup = False
                self.backlog_description += "external change\n"
            return self._json(200, comments[: int(query.get("count", ["100"])[0])])
        if path.endswith("/comments") and request.method == "POST":
            values = parse_qs((request.body or b"").decode("utf-8"), keep_blank_values=True)
            comment = {"id": len(self.backlog_comments) + 1, "content": values["content"][0], "created": "2026-09-06T00:00:00Z"}
            self.backlog_comments.append(comment)
            return self._json(201, comment)
        if "/api/v2/issues/" in path and request.method == "GET":
            ticket = unquote(path.rsplit("/", 1)[-1])
            return self._json(
                200,
                {
                    "id": self.issue_numeric_id_override or 101,
                    "issueKey": self.issue_key_override or ("PROJ-1" if ticket in {"101", "PROJ-1"} else ticket),
                    "projectId": self.project_id_override or 10,
                    "description": self.backlog_description,
                    "updated": "2026-09-06T00:00:00Z",
                },
            )
        if "/api/v2/issues/" in path and request.method == "PATCH":
            values = parse_qs((request.body or b"").decode("utf-8"), keep_blank_values=True)
            self.backlog_description = values["description"][0]
            if not self.partial_description_only:
                self.backlog_comments.append(
                    {"id": len(self.backlog_comments) + 1, "content": values["comment"][0], "created": "2026-09-06T00:00:00Z"}
                )
            return self._json(200, {"id": 101, "issueKey": "PROJ-1", "projectId": 10, "description": self.backlog_description})
        raise AssertionError(f"unexpected Backlog request: {request.method} {path}")

    def _redmine(self, request: HttpRequest, path: str, query: dict[str, list[str]]) -> HttpResponse:
        if path == "/redmine/issues/7.json" and request.method == "GET":
            return self._json(
                200,
                {
                    "issue": {
                        "id": 7,
                        "project": {"id": self.project_id_override or 20},
                        "description": self.redmine_description,
                        "updated_on": "2026-09-06T00:00:00Z",
                        "journals": self.redmine_journals,
                    }
                },
            )
        if path == "/redmine/issues/7.json" and request.method == "PUT":
            payload = json.loads((request.body or b"").decode("utf-8"))["issue"]
            if "description" in payload:
                self.redmine_description = payload["description"]
            if "notes" in payload and not self.partial_description_only:
                self.redmine_journals.append(
                    {
                        "id": len(self.redmine_journals) + 1,
                        "notes": payload["notes"],
                        "created_on": "2026-09-06T00:00:00Z",
                        "private_notes": self.redmine_private_notes,
                    }
                )
            return HttpResponse(self.redmine_success_status, {}, b"")
        raise AssertionError(f"unexpected Redmine request: {request.method} {path} {query}")

    @staticmethod
    def _json(status: int, value: object) -> HttpResponse:
        return HttpResponse(status, {"Content-Type": "application/json"}, json.dumps(value).encode("utf-8"))
