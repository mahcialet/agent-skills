"""Backlog and Redmine adapters with policy checks at the mutation boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode, urlsplit

from .config import ProfileConfig, canonical_identity, require_permissions
from .errors import IdentityError, PermissionDenied, RemoteError, UnsafeContentError
from .model import (
    MutationPlan,
    ProviderCapabilities,
    RemoteComment,
    TicketIdentity,
    TicketRecord,
    ticket_context_sha256,
    utc_now,
)
from .transport import HttpRequest, HttpResponse, Transport


def _json_object(response: HttpResponse) -> dict[str, Any]:
    value = response.json()
    if not isinstance(value, dict):
        raise RemoteError("remote response must be a JSON object")
    return value


def _json_list(response: HttpResponse) -> list[dict[str, Any]]:
    value = response.json()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise RemoteError("remote response must be a JSON array of objects")
    return value


@dataclass(slots=True)
class BaseAdapter:
    profile: ProfileConfig
    transport: Transport

    @property
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    def _url(self, relative: str, query: dict[str, object] | None = None) -> str:
        base = self.profile.instance.base_url.rstrip("/")
        url = f"{base}/{relative.lstrip('/')}"
        parsed_base = urlsplit(base)
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != parsed_base.netloc:
            raise IdentityError("adapter generated a URL outside the configured instance")
        prefix = parsed_base.path.rstrip("/")
        if prefix and parsed.path != prefix and not parsed.path.startswith(prefix + "/"):
            raise IdentityError("adapter generated a URL outside the configured subpath")
        if query:
            url = f"{url}?{urlencode(query)}"
        return url

    def _send(
        self,
        method: str,
        relative: str,
        *,
        headers: dict[str, str],
        body: bytes | None = None,
        query: dict[str, object] | None = None,
        is_mutation: bool = False,
        expected_statuses: frozenset[int] = frozenset({200}),
    ) -> HttpResponse:
        response = self.transport.send(
            HttpRequest(
                method=method,
                url=self._url(relative, query),
                headers=headers,
                body=body,
                is_mutation=is_mutation,
            )
        )
        if response.status not in expected_statuses:
            raise RemoteError(
                f"remote request failed with HTTP {response.status}",
                status=response.status,
                result_unknown=is_mutation
                and (200 <= response.status < 400 or response.status >= 500),
                mutation_attempted=is_mutation,
            )
        return response

    def _refuse_api_key_in_content(self, record: TicketRecord) -> None:
        secret = self.profile.instance.api_key()
        if secret and (
            secret in record.description
            or any(secret in comment.content for comment in record.comments)
        ):
            raise UnsafeContentError(
                "remote ticket content matches the configured API key; content was not returned or saved"
            )

    def read_ticket(self, raw_ticket_id: str) -> TicketRecord:
        raise NotImplementedError

    def find_comment(self, ticket_id: str, expected_content: str) -> RemoteComment | None:
        raise NotImplementedError

    def apply(self, plan: MutationPlan, *, dry_run: bool) -> None:
        if dry_run:
            raise PermissionDenied("mutation boundary refuses dry-run requests")
        operation_permissions = {
            "update-state": ("description:write", "comment:append"),
            "snapshot": ("comment:append",),
            "append-comment": ("comment:append",),
        }
        expected_permissions = operation_permissions.get(plan.operation)
        if expected_permissions is None or plan.required_permissions != expected_permissions:
            raise PermissionDenied("mutation plan permissions do not match the operation contract")
        if (
            self.profile.concurrency == "strict"
            and plan.operation == "update-state"
            and self.capabilities.conditional_update != "supported"
        ):
            raise PermissionDenied(
                "mutation boundary refuses update-state without confirmed conditional update support"
            )
        fresh = self.read_ticket(plan.identity.ticket_id)
        if fresh.identity != plan.identity:
            raise IdentityError("mutation boundary identity revalidation failed")
        if fresh.provider_ticket_numeric_id != plan.provider_ticket_numeric_id:
            raise IdentityError("mutation boundary numeric ticket mapping changed")
        if not plan.base_context_sha256 or ticket_context_sha256(fresh) != plan.base_context_sha256:
            raise PermissionDenied("mutation boundary remote context changed; remerge is required")
        aliases = (fresh.provider_ticket_numeric_id,) if fresh.provider_ticket_numeric_id else ()
        require_permissions(self.profile, fresh.identity, set(expected_permissions), aliases)
        if plan.operation == "update-state":
            if plan.description is None:
                raise PermissionDenied("update-state requires a description")
            self._combined_update(plan.identity.ticket_id, plan.description, plan.comment)
        elif plan.operation in {"snapshot", "append-comment"}:
            if plan.description is not None:
                raise PermissionDenied("comment-only operation cannot update description")
            self._append_comment(plan.identity.ticket_id, plan.comment)
        else:
            raise PermissionDenied("unsupported mutation operation")

    def _combined_update(self, ticket_id: str, description: str, comment: str) -> None:
        raise NotImplementedError

    def _append_comment(self, ticket_id: str, comment: str) -> None:
        raise NotImplementedError


class BacklogAdapter(BaseAdapter):
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(True, "unknown", "public", self.profile.markup)

    def _headers(self, *, form: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Backlog-API-Key": self.profile.instance.api_key(),
        }
        if form:
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=utf-8"
        return headers

    def read_ticket(self, raw_ticket_id: str) -> TicketRecord:
        issue = _json_object(
            self._send(
                "GET",
                f"api/v2/issues/{quote(raw_ticket_id, safe='')}",
                headers=self._headers(),
            )
        )
        project_id = issue.get("projectId")
        if project_id != self.profile.project_id:
            raise IdentityError("Backlog issue belongs to a different project")
        issue_key = issue.get("issueKey")
        if not isinstance(issue_key, str):
            raise RemoteError("Backlog issue response is missing issueKey")
        canonical = issue_key.upper()
        if raw_ticket_id.isdigit():
            if issue.get("id") != int(raw_ticket_id):
                raise IdentityError("Backlog response numeric ID does not match requested ticket")
        elif canonical != raw_ticket_id.upper():
            raise IdentityError("Backlog response issueKey does not match requested ticket")
        expected_prefix = f"{self.profile.project_key}-"
        if not canonical.startswith(expected_prefix):
            raise IdentityError("Backlog issueKey does not match configured project_key")
        project = _json_object(
            self._send(
                "GET",
                f"api/v2/projects/{self.profile.project_id}",
                headers=self._headers(),
            )
        )
        if project.get("id") != self.profile.project_id or str(project.get("projectKey", "")).upper() != self.profile.project_key:
            raise IdentityError("Backlog project ID and key mapping does not match config")
        comments_raw = _json_list(
            self._send(
                "GET",
                f"api/v2/issues/{quote(canonical, safe='')}/comments",
                headers=self._headers(),
                query={"count": 100, "order": "desc"},
            )
        )
        description = issue.get("description", "")
        if not isinstance(description, str):
            raise RemoteError("Backlog description must be text")
        comments = tuple(
            RemoteComment(
                comment_id=str(item.get("id", "")),
                content=item.get("content", "") if isinstance(item.get("content", ""), str) else "",
                created_at=item.get("created"),
                visibility="public",
            )
            for item in comments_raw
        )
        formatting = project.get("textFormattingRule")
        if formatting not in {"markdown", "backlog"}:
            raise IdentityError("Backlog project returned an unsupported text formatting rule")
        markup = str(formatting)
        if markup != self.profile.markup:
            raise IdentityError("Backlog project text formatting rule does not match trusted profile")
        record = TicketRecord(
            identity=canonical_identity(self.profile, canonical),
            description=description,
            updated_at=issue.get("updated"),
            retrieved_at=utc_now(),
            comments=comments,
            comments_complete=len(comments_raw) < 100,
            provider_ticket_numeric_id=str(issue.get("id")) if issue.get("id") is not None else None,
            markup=markup,
        )
        self._refuse_api_key_in_content(record)
        return record

    def find_comment(self, ticket_id: str, expected_content: str) -> RemoteComment | None:
        max_id: int | None = None
        seen: set[int] = set()
        while len(seen) < 1000:
            query: dict[str, object] = {"count": 100, "order": "desc"}
            if max_id is not None:
                query["maxId"] = max_id
            page = _json_list(
                self._send(
                    "GET",
                    f"api/v2/issues/{quote(ticket_id, safe='')}/comments",
                    headers=self._headers(),
                    query=query,
                )
            )
            for item in page:
                content = item.get("content", "")
                if isinstance(content, str) and content == expected_content:
                    return RemoteComment(
                        comment_id=str(item.get("id", "")),
                        content=content,
                        created_at=item.get("created"),
                        visibility="public",
                    )
            if len(page) < 100:
                return None
            ids = {item.get("id") for item in page if isinstance(item.get("id"), int)}
            new_ids = ids - seen
            if not new_ids:
                raise RemoteError("comment pagination made no progress")
            seen.update(new_ids)
            max_id = min(new_ids) - 1
        raise RemoteError("comment verification reached pagination safety limit")

    def _combined_update(self, ticket_id: str, description: str, comment: str) -> None:
        body = urlencode({"description": description, "comment": comment}).encode("utf-8")
        self._send(
            "PATCH",
            f"api/v2/issues/{quote(ticket_id, safe='')}",
            headers=self._headers(form=True),
            body=body,
            is_mutation=True,
            expected_statuses=frozenset({200}),
        )

    def _append_comment(self, ticket_id: str, comment: str) -> None:
        body = urlencode({"content": comment}).encode("utf-8")
        self._send(
            "POST",
            f"api/v2/issues/{quote(ticket_id, safe='')}/comments",
            headers=self._headers(form=True),
            body=body,
            is_mutation=True,
            expected_statuses=frozenset({201}),
        )


class RedmineAdapter(BaseAdapter):
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(True, "unknown", "public", self.profile.markup)

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-Redmine-API-Key": self.profile.instance.api_key(),
        }
        if json_body:
            headers["Content-Type"] = "application/json; charset=utf-8"
        return headers

    def read_ticket(self, raw_ticket_id: str) -> TicketRecord:
        response = _json_object(
            self._send(
                "GET",
                f"issues/{quote(raw_ticket_id, safe='')}.json",
                headers=self._headers(),
                query={"include": "journals"},
            )
        )
        issue = response.get("issue")
        if not isinstance(issue, dict):
            raise RemoteError("Redmine response is missing issue")
        project = issue.get("project")
        if not isinstance(project, dict) or project.get("id") != self.profile.project_id:
            raise IdentityError("Redmine issue belongs to a different project")
        issue_id = issue.get("id")
        if not isinstance(issue_id, int) or isinstance(issue_id, bool) or issue_id <= 0:
            raise RemoteError("Redmine response has an invalid issue ID")
        if str(issue_id) != raw_ticket_id:
            raise IdentityError("Redmine response ID does not match requested ticket")
        journals = issue.get("journals", [])
        if not isinstance(journals, list):
            raise RemoteError("Redmine journals must be a list")
        comments: list[RemoteComment] = []
        for journal in journals:
            if not isinstance(journal, dict):
                continue
            notes = journal.get("notes", "")
            if isinstance(notes, str) and notes:
                comments.append(
                    RemoteComment(
                        comment_id=str(journal.get("id", "")),
                        content=notes,
                        created_at=journal.get("created_on"),
                        visibility="private" if journal.get("private_notes") is True else "public",
                    )
                )
        description = issue.get("description", "")
        if not isinstance(description, str):
            raise RemoteError("Redmine description must be text")
        record = TicketRecord(
            identity=canonical_identity(self.profile, str(issue_id)),
            description=description,
            updated_at=issue.get("updated_on"),
            retrieved_at=utc_now(),
            comments=tuple(comments),
            comments_complete=True,
            provider_ticket_numeric_id=str(issue_id),
            markup=self.profile.markup,
        )
        self._refuse_api_key_in_content(record)
        return record

    def find_comment(self, ticket_id: str, expected_content: str) -> RemoteComment | None:
        ticket = self.read_ticket(ticket_id)
        return next(
            (
                comment
                for comment in ticket.comments
                if comment.content == expected_content and comment.visibility == "public"
            ),
            None,
        )

    def _put_issue(self, ticket_id: str, issue_fields: dict[str, str | bool]) -> None:
        body = json.dumps({"issue": issue_fields}, ensure_ascii=False).encode("utf-8")
        self._send(
            "PUT",
            f"issues/{quote(ticket_id, safe='')}.json",
            headers=self._headers(json_body=True),
            body=body,
            is_mutation=True,
            expected_statuses=frozenset({204}),
        )

    def _combined_update(self, ticket_id: str, description: str, comment: str) -> None:
        self._put_issue(
            ticket_id,
            {"description": description, "notes": comment, "private_notes": False},
        )

    def _append_comment(self, ticket_id: str, comment: str) -> None:
        self._put_issue(ticket_id, {"notes": comment, "private_notes": False})


def make_adapter(profile: ProfileConfig, transport: Transport) -> BaseAdapter:
    if profile.instance.provider == "backlog":
        return BacklogAdapter(profile, transport)
    if profile.instance.provider == "redmine":
        return RedmineAdapter(profile, transport)
    raise ValueError(f"unsupported provider: {profile.instance.provider}")
