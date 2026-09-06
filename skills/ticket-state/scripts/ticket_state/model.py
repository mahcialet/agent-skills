"""Provider-neutral data types and stable hashing helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return sha256_text(stable_json(value))


@dataclass(frozen=True, slots=True)
class TicketIdentity:
    provider: str
    base_url: str
    project_id: int
    ticket_id: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def key(self) -> str:
        return sha256_json(self.as_dict())


@dataclass(frozen=True, slots=True)
class RemoteComment:
    comment_id: str
    content: str
    created_at: str | None = None
    visibility: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TicketRecord:
    identity: TicketIdentity
    description: str
    updated_at: str | None
    retrieved_at: str
    comments: tuple[RemoteComment, ...] = field(default_factory=tuple)
    comments_complete: bool = False
    provider_ticket_numeric_id: str | None = None
    markup: str = "unknown"

    @property
    def description_sha256(self) -> str:
        return sha256_text(self.description)

    def as_dict(self, *, include_content: bool = True) -> dict[str, Any]:
        result: dict[str, Any] = {
            "identity": self.identity.as_dict(),
            "updated_at": self.updated_at,
            "retrieved_at": self.retrieved_at,
            "description_sha256": self.description_sha256,
            "comments_complete": self.comments_complete,
            "provider_ticket_numeric_id": self.provider_ticket_numeric_id,
            "markup": self.markup,
        }
        if include_content:
            result["description"] = self.description
            result["comments"] = [comment.as_dict() for comment in self.comments]
        return result


def ticket_context_sha256(record: TicketRecord) -> str:
    comments = sorted(
        (
            comment.comment_id,
            sha256_text(comment.content),
            comment.created_at,
            comment.visibility,
        )
        for comment in record.comments
    )
    return sha256_json(
        {
            "identity": record.identity.as_dict(),
            "description_sha256": record.description_sha256,
            "updated_at": record.updated_at,
            "comments_complete": record.comments_complete,
            "comments": comments,
            "markup": record.markup,
        }
    )


@dataclass(frozen=True, slots=True)
class MutationPlan:
    operation: str
    identity: TicketIdentity
    description: str | None
    comment: str
    required_permissions: tuple[str, ...]
    operation_id: str
    payload_sha256: str
    provider_ticket_numeric_id: str | None = None
    base_context_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    combined_update: bool
    conditional_update: str
    comment_visibility: str
    markup: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
