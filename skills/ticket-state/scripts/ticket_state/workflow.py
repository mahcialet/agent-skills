"""Read, plan, persist, authorize, apply, verify, and recover ticket updates."""

from __future__ import annotations

import difflib
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from .adapters import BaseAdapter, make_adapter
from .config import Config, normalize_target, permissions_for
from .errors import (
    IdentityError,
    PermissionDenied,
    RemoteError,
    StateError,
    StorageError,
    UnsafeContentError,
)
from .model import (
    MutationPlan,
    TicketIdentity,
    TicketRecord,
    sha256_json,
    sha256_text,
    stable_json,
    ticket_context_sha256,
    utc_now,
)
from .storage import ProposalStore
from .templates import (
    approve_template,
    extract_template_candidate,
    render_snapshot,
    validate_edit_scope,
    validate_template,
)
from .transport import Transport

MUTATING_OPERATIONS = {"update-state", "snapshot", "append-comment"}
REQUIRED_PERMISSIONS = {
    "update-state": ("description:write", "comment:append"),
    "snapshot": ("comment:append",),
    "append-comment": ("comment:append",),
}
NONTERMINAL_APPLY_STATES = {
    "READY",
    "PENDING_PERMISSION",
    "NEEDS_REVIEW",
}


def _json_bytes(value: Any) -> bytes:
    return (stable_json(value) + "\n").encode("utf-8")


def _contains_text(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(
            _contains_text(key, needle) or _contains_text(item, needle)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_text(item, needle) for item in value)
    return False


def unified_diff(before: str, after: str, *, before_name: str, after_name: str) -> str:
    output: list[str] = []
    for line in difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=before_name,
        tofile=after_name,
    ):
        output.append(line)
        if not line.endswith(("\n", "\r")):
            output.append("\n\\ No newline at end of file\n")
    return "".join(output)


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UnsafeContentError(f"cannot read JSON request {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise UnsafeContentError("request must be a JSON object")
    return value


def _identity_from_dict(value: dict[str, Any]) -> TicketIdentity:
    try:
        return TicketIdentity(
            provider=str(value["provider"]),
            base_url=str(value["base_url"]),
            project_id=int(value["project_id"]),
            ticket_id=str(value["ticket_id"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StorageError("stored proposal identity is invalid") from exc


class TicketStateService:
    def __init__(self, config: Config, store: ProposalStore, transport: Transport) -> None:
        self.config = config
        self.store = store
        self.transport = transport

    def _adapter(self, profile_name: str) -> BaseAdapter:
        profile = self.config.profile(profile_name)
        self.store.bind_profile(
            profile_name,
            {
                "provider": profile.instance.provider,
                "base_url": profile.instance.base_url,
                "project_id": profile.project_id,
                "project_key": profile.project_key,
                "read_scope": profile.read_scope,
                "markup": profile.markup,
            },
        )
        return make_adapter(profile, self.transport)

    def _assert_no_configured_secret(self, value: Any, *, context: str) -> None:
        for instance in self.config.instances.values():
            secret = os.environ.get(instance.api_key_env)
            if secret and _contains_text(value, secret):
                raise UnsafeContentError(
                    f"{context} contains a configured API key value; content was not returned or saved"
                )

    def _assert_record_safe(self, record: TicketRecord) -> TicketRecord:
        self._assert_no_configured_secret(record.as_dict(), context="remote ticket")
        return record

    def read(self, profile_name: str, target: str) -> dict[str, Any]:
        profile = self.config.profile(profile_name)
        normalized = normalize_target(profile, target)
        record = self._assert_record_safe(
            self._adapter(profile_name).read_ticket(normalized)
        )
        return {"schema_version": 1, "profile": profile_name, "ticket": record.as_dict()}

    def _validate_request(self, request: dict[str, Any], operation: str) -> None:
        common = {
            "schema_version",
            "operation",
            "profile",
            "ticket",
            "visibility_confirmed",
            "source_visibility",
            "template_id",
            "template_sha256",
        }
        operation_fields = {
            "update-state": {
                "base_description_sha256",
                "proposed_description",
                "edited_sections",
                "change_summary",
                "snapshot",
                "snapshot_description_sha256",
                "state_changed",
            },
            "snapshot": {"base_description_sha256", "change_summary", "snapshot", "snapshot_description_sha256"},
            "append-comment": {"base_description_sha256", "comment"},
        }
        allowed = common | operation_fields[operation]
        unknown = sorted(set(request) - allowed)
        if unknown:
            raise UnsafeContentError(f"request contains unknown fields: {', '.join(unknown)}")
        if request.get("schema_version") != 1:
            raise UnsafeContentError("request schema_version must be 1")
        if request.get("operation", operation) != operation:
            raise UnsafeContentError("request operation does not match command")
        if not isinstance(request.get("profile"), str) or not isinstance(request.get("ticket"), str):
            raise UnsafeContentError("request requires profile and ticket")
        if request.get("visibility_confirmed") is not True or request.get("source_visibility") != "public-only":
            raise UnsafeContentError("posting requires confirmed public-only source visibility")
        if operation == "update-state":
            if not isinstance(request.get("proposed_description"), str):
                raise UnsafeContentError("update-state requires proposed_description")
            if not isinstance(request.get("base_description_sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", request["base_description_sha256"]
            ):
                raise UnsafeContentError(
                    "update-state requires a SHA-256 base_description_sha256 from the source read"
                )
            if not isinstance(request.get("state_changed"), bool):
                raise UnsafeContentError("update-state requires boolean state_changed")
            if not isinstance(request.get("edited_sections", []), list) or any(
                not isinstance(item, str) for item in request.get("edited_sections", [])
            ):
                raise UnsafeContentError("edited_sections must be an array of strings")
        if operation in {"update-state", "snapshot"}:
            if not isinstance(request.get("snapshot"), dict) or not isinstance(request.get("change_summary"), list):
                raise UnsafeContentError("state operations require snapshot and change_summary")
            if not isinstance(request.get("snapshot_description_sha256"), str) or not re.fullmatch(
                r"[0-9a-f]{64}", request["snapshot_description_sha256"]
            ):
                raise UnsafeContentError("state operations require snapshot_description_sha256")
        if operation == "append-comment" and not isinstance(request.get("comment"), str):
            raise UnsafeContentError("append-comment requires comment")
        if request.get("base_description_sha256") is not None and not isinstance(request["base_description_sha256"], str):
            raise UnsafeContentError("base_description_sha256 must be text")
        if request.get("base_description_sha256") is not None and not re.fullmatch(
            r"[0-9a-f]{64}", request["base_description_sha256"]
        ):
            raise UnsafeContentError("base_description_sha256 must be lowercase SHA-256")
        template_id = request.get("template_id")
        template_hash = request.get("template_sha256")
        if (template_id is None) != (template_hash is None):
            raise UnsafeContentError("template_id and template_sha256 must be provided together")

    def _plan(
        self,
        request: dict[str, Any],
        operation: str,
        *,
        existing_proposal_id: str | None = None,
    ) -> tuple[TicketRecord, dict[str, bytes], dict[str, Any], str, str | None, list[str]]:
        self._validate_request(request, operation)
        profile_name = request["profile"]
        profile = self.config.profile(profile_name)
        self._assert_no_configured_secret(request, context="proposal request")
        self._validate_selected_template(profile.template, profile.markup, request)
        normalized = normalize_target(profile, request["ticket"])
        adapter = self._adapter(profile_name)
        record = self._assert_record_safe(adapter.read_ticket(normalized))
        requested_hash = request.get("base_description_sha256")
        stale_input = requested_hash is not None and requested_hash != record.description_sha256
        required = list(REQUIRED_PERMISSIONS[operation])
        aliases = (record.provider_ticket_numeric_id,) if record.provider_ticket_numeric_id else ()
        granted = permissions_for(profile, record.identity, aliases)
        missing = sorted(set(required) - granted)
        operation_id = uuid.uuid4().hex
        prepared_at = utc_now()
        proposed_description: str | None
        comment: str
        snapshot_value: dict[str, Any] | None = None
        protected_sections: set[str] = set()
        if operation == "update-state":
            proposed_description = request["proposed_description"]
            if request["snapshot_description_sha256"] != sha256_text(proposed_description):
                raise UnsafeContentError("snapshot is not bound to the exact proposed description")
            if not stale_input:
                protected_sections = validate_edit_scope(
                    record.description,
                    proposed_description,
                    markup=record.markup,
                    edited_sections=request.get("edited_sections", []),
                )
            if stale_input:
                snapshot_value = request["snapshot"]
                comment = render_snapshot(
                    snapshot_value,
                    request["change_summary"],
                    markup=record.markup,
                    prepared_at=prepared_at,
                    operation_id=operation_id,
                )
                state = "NEEDS_REMERGE"
                reason = "request base hash is stale; semantic remerge is required"
            elif proposed_description == record.description and request["state_changed"] is False:
                comment = ""
                state = "NO_CHANGE"
                reason = "description and declared state are unchanged"
            else:
                snapshot_value = request["snapshot"]
                comment = render_snapshot(
                    snapshot_value,
                    request["change_summary"],
                    markup=record.markup,
                    prepared_at=prepared_at,
                    operation_id=operation_id,
                )
                state, reason = self._initial_state(adapter, profile.concurrency, missing)
        elif operation == "snapshot":
            proposed_description = None
            if request["snapshot_description_sha256"] != record.description_sha256:
                raise UnsafeContentError("snapshot is not bound to the latest remote description")
            snapshot_value = request["snapshot"]
            comment = render_snapshot(
                snapshot_value,
                request["change_summary"],
                markup=record.markup,
                prepared_at=prepared_at,
                operation_id=operation_id,
            )
            state, reason = self._initial_state(adapter, profile.concurrency, missing, comment_only=True)
        else:
            proposed_description = None
            comment = request["comment"].replace("@", "@\u200b")
            if not comment.strip():
                raise UnsafeContentError("append-comment content must not be empty")
            comment = comment.rstrip() + f"\n\nOperation: ticket-state/{operation_id}\n"
            if len(comment.encode("utf-8")) > 60_000:
                raise UnsafeContentError("comment exceeds the conservative 60000-byte limit")
            state, reason = self._initial_state(adapter, profile.concurrency, missing, comment_only=True)

        confirmation_required = bool(protected_sections)
        if state == "READY" and confirmation_required:
            state = "NEEDS_REVIEW"
            reason = "protected changes require confirmation of the prepared revision"
        description_after = record.description if proposed_description is None else proposed_description
        description_diff = unified_diff(
            record.description,
            description_after,
            before_name="remote-description",
            after_name="proposed-description",
        )
        comment_diff = unified_diff("", comment, before_name="/dev/null", after_name="proposed-comment") if comment else ""
        payload = {
            "operation": operation,
            "identity": record.identity.as_dict(),
            "description": proposed_description,
            "comment": comment,
            "operation_id": operation_id,
        }
        metadata = {
            "schema_version": 1,
            "protected_sections": sorted(protected_sections),
            "confirmation_required": confirmation_required,
            "profile": profile_name,
            "operation": operation,
            "operation_id": operation_id,
            "payload_sha256": sha256_json(payload),
            "base_description_sha256": record.description_sha256,
            "base_context_sha256": ticket_context_sha256(record),
            "proposed_description_sha256": sha256_text(description_after),
            "comment_sha256": sha256_text(comment),
            "required_permissions": required,
            "granted_permissions": sorted(granted),
            "missing_permissions": missing,
            "identity": record.identity.as_dict(),
            "markup": record.markup,
            "provider_capabilities": adapter.capabilities.as_dict(),
            "provider_ticket_numeric_id": record.provider_ticket_numeric_id,
            "prepared_at": prepared_at,
            "visibility_confirmed": True,
            "source_visibility": "public-only",
            "template_id": request.get("template_id"),
            "template_sha256": request.get("template_sha256"),
            "supersedes_revision_of": existing_proposal_id,
        }
        base_artifact = record.as_dict()
        intent_artifact = dict(request)
        artifacts = {
            "metadata.json": _json_bytes(metadata),
            "base.json": _json_bytes(base_artifact),
            "intent.json": _json_bytes(intent_artifact),
            "proposed-description.txt": description_after.encode("utf-8"),
            "proposed-comment.txt": comment.encode("utf-8"),
            "snapshot.json": _json_bytes(snapshot_value or {}),
            "planned-payload.json": _json_bytes(payload),
            "description.diff": description_diff.encode("utf-8"),
            "comment.diff": comment_diff.encode("utf-8"),
        }
        return record, artifacts, metadata, state, reason, required

    def _validate_selected_template(
        self,
        configured_template: str | None,
        expected_markup: str,
        request: dict[str, Any],
    ) -> None:
        template_id = request.get("template_id")
        template_hash = request.get("template_sha256")
        if configured_template is not None and template_id != configured_template:
            raise UnsafeContentError("request must select the approved template configured for this profile")
        if template_id is None:
            return
        if not isinstance(template_id, str) or not re.fullmatch(r"[0-9a-f]{32}", template_id):
            raise UnsafeContentError("template_id must identify an approved local template")
        path = self.store.template_path("approved", template_id)
        if path.is_symlink() or not path.is_file():
            raise UnsafeContentError("selected approved template artifact is missing")
        try:
            data = path.read_text(encoding="utf-8")
            value = json.loads(data)
        except (OSError, json.JSONDecodeError) as exc:
            raise UnsafeContentError("selected approved template artifact is unreadable") from exc
        if not isinstance(value, dict):
            raise UnsafeContentError("selected approved template must be an object")
        validate_template(value, require_approved=True)
        if value.get("template_id") != template_id:
            raise UnsafeContentError("approved template ID does not match selection")
        if value.get("markup") != expected_markup:
            raise UnsafeContentError("approved template markup does not match the target profile")
        if sha256_text(data) != template_hash:
            raise UnsafeContentError("approved template artifact hash does not match selection")

    @staticmethod
    def _initial_state(
        adapter: BaseAdapter,
        concurrency: str,
        missing: list[str],
        *,
        comment_only: bool = False,
    ) -> tuple[str, str | None]:
        if missing:
            return "PENDING_PERMISSION", f"missing permissions: {', '.join(missing)}"
        if concurrency == "strict" and not comment_only and adapter.capabilities.conditional_update != "supported":
            return "NEEDS_REVIEW", "strict concurrency requires a confirmed conditional update capability"
        return "READY", None

    def prepare(self, request: dict[str, Any], operation: str | None = None) -> dict[str, Any]:
        selected = operation or request.get("operation")
        if selected not in MUTATING_OPERATIONS:
            raise UnsafeContentError("prepare requires a supported operation")
        record, artifacts, metadata, state, reason, required = self._plan(request, selected)
        proposal = self.store.create_proposal(
            profile_name=request["profile"],
            operation=selected,
            identity=record.identity.as_dict(),
            state="DRAFT",
            required_permissions=required,
            reason="proposal artifacts persisted; validation decision pending",
            artifacts=artifacts,
            metadata=metadata,
        )
        proposal = self.store.transition(
            proposal["proposal_id"],
            "PREPARED",
            event="PROPOSAL_PREPARED",
            reason=None,
        )
        proposal = self.store.transition(
            proposal["proposal_id"],
            state,
            event="PROPOSAL_DECISION_RECORDED",
            reason=reason,
            data={
                "granted_permissions": metadata["granted_permissions"],
                "missing_permissions": metadata["missing_permissions"],
            },
        )
        return self._proposal_result(proposal, mode="prepare", mutation_count=0)

    def update(self, request: dict[str, Any], operation: str, *, dry_run: bool) -> dict[str, Any]:
        prepared = self.prepare(request, operation)
        if prepared["state"] == "NO_CHANGE":
            return prepared | {"mode": "dry-run" if dry_run else "execute", "outcome": "NO_CHANGE"}
        if prepared["state"] in {"NEEDS_REMERGE", "NEEDS_REVIEW"}:
            return prepared | {"mode": "dry-run" if dry_run else "execute", "outcome": prepared["state"]}
        return self.apply(prepared["proposal_id"], dry_run=dry_run)

    def _load_request(self, proposal_id: str) -> dict[str, Any]:
        return self._load_json_artifact(proposal_id, "intent.json")

    def _load_json_artifact(self, proposal_id: str, name: str) -> dict[str, Any]:
        try:
            value = json.loads(self.store.read_artifact(proposal_id, name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StorageError(f"stored proposal artifact {name} is invalid JSON") from exc
        if not isinstance(value, dict):
            raise StorageError(f"stored proposal artifact {name} must be an object")
        return value

    def _load_plan(self, proposal_id: str) -> tuple[dict[str, Any], dict[str, Any], MutationPlan]:
        proposal = self.store.get_proposal(proposal_id)
        revision = self.store.get_revision(proposal_id)
        metadata = revision["metadata"]
        description = self.store.read_artifact(proposal_id, "proposed-description.txt").decode("utf-8")
        comment = self.store.read_artifact(proposal_id, "proposed-comment.txt").decode("utf-8")
        identity = _identity_from_dict(proposal["identity"])
        plan = MutationPlan(
            operation=proposal["operation"],
            identity=identity,
            description=description if proposal["operation"] == "update-state" else None,
            comment=comment,
            required_permissions=tuple(proposal["required_permissions"]),
            operation_id=metadata["operation_id"],
            payload_sha256=metadata["payload_sha256"],
            provider_ticket_numeric_id=metadata.get("provider_ticket_numeric_id"),
            base_context_sha256=metadata.get("base_context_sha256"),
        )
        reconstructed_payload = {
            "operation": plan.operation,
            "identity": plan.identity.as_dict(),
            "description": plan.description,
            "comment": plan.comment,
            "operation_id": plan.operation_id,
        }
        stored_payload = self._load_json_artifact(proposal_id, "planned-payload.json")
        if stored_payload != reconstructed_payload or sha256_json(reconstructed_payload) != plan.payload_sha256:
            raise StorageError("stored payload, metadata hash, and proposal artifacts do not match")
        if metadata.get("proposed_description_sha256") != sha256_text(description):
            raise StorageError("stored proposed description hash does not match")
        if metadata.get("comment_sha256") != sha256_text(comment):
            raise StorageError("stored proposed comment hash does not match")
        return proposal, metadata, plan

    def apply(self, proposal_id: str, *, dry_run: bool) -> dict[str, Any]:
        proposal, metadata, plan = self._load_plan(proposal_id)
        profile = self.config.profile(proposal["profile_name"])
        adapter = self._adapter(proposal["profile_name"])
        with self.store.target_lock(plan.identity.key):
            locked_proposal, metadata, plan = self._load_plan(proposal_id)
            if locked_proposal["state"] == "APPLIED":
                return self._proposal_result(
                    locked_proposal,
                    mode="dry-run" if dry_run else "execute",
                    mutation_count=0,
                    outcome="ALREADY_APPLIED",
                )
            if locked_proposal["state"] in {
                "APPLYING",
                "VERIFYING",
                "UNKNOWN_REMOTE_RESULT",
                "PARTIAL_APPLIED",
            }:
                return self._proposal_result(
                    locked_proposal,
                    mode="dry-run" if dry_run else "execute",
                    mutation_count=0,
                    outcome="RECONCILE_REQUIRED",
                )
            if locked_proposal["state"] not in NONTERMINAL_APPLY_STATES:
                raise StateError(f"proposal changed while waiting for target lock: {locked_proposal['state']}")
            current = self._assert_record_safe(
                adapter.read_ticket(plan.identity.ticket_id)
            )
            self._assert_same_identity(plan.identity, current.identity)
            if (
                current.description_sha256 != metadata["base_description_sha256"]
                or ticket_context_sha256(current) != metadata["base_context_sha256"]
            ):
                return self._record_stale_revision(
                    proposal_id,
                    locked_proposal,
                    current,
                    "remote description, metadata, or comments changed after proposal preparation",
                )
            aliases = (current.provider_ticket_numeric_id,) if current.provider_ticket_numeric_id else ()
            missing = sorted(set(plan.required_permissions) - permissions_for(profile, current.identity, aliases))
            current_granted = sorted(permissions_for(profile, current.identity, aliases))
            if (
                current_granted != sorted(metadata.get("granted_permissions", []))
                or missing != sorted(metadata.get("missing_permissions", []))
                or adapter.capabilities.as_dict() != metadata.get("provider_capabilities")
            ):
                state, reason = self._initial_state(
                    adapter,
                    profile.concurrency,
                    missing,
                    comment_only=plan.operation != "update-state",
                )
                return self._record_decision_revision(
                    proposal_id,
                    locked_proposal,
                    current,
                    state=state,
                    reason=reason or "permission or provider capability decision changed",
                    granted=current_granted,
                    missing=missing,
                    capabilities=adapter.capabilities.as_dict(),
                )
            if missing:
                updated = self.store.transition(
                    proposal_id,
                    "PENDING_PERMISSION",
                    event="PERMISSION_REVOKED",
                    reason=f"missing permissions: {', '.join(missing)}",
                    data={"missing_permissions": missing},
                    mode="dry-run" if dry_run else "execute",
                )
                return self._proposal_result(updated, mode="dry-run" if dry_run else "execute", mutation_count=0)
            if profile.concurrency == "strict" and plan.operation == "update-state" and adapter.capabilities.conditional_update != "supported":
                updated = self.store.transition(
                    proposal_id,
                    "NEEDS_REVIEW",
                    event="STRICT_CONCURRENCY_REFUSED",
                    reason="provider conditional update capability is not confirmed",
                    mode="dry-run" if dry_run else "execute",
                )
                return self._proposal_result(updated, mode="dry-run" if dry_run else "execute", mutation_count=0)
            if self._confirmation_missing(locked_proposal, metadata):
                updated = self.store.transition(
                    proposal_id, "NEEDS_REVIEW", event="CONTENT_CONFIRMATION_REQUIRED",
                    reason="confirm the protected changes in this revision before applying",
                    mode="dry-run" if dry_run else "execute",
                )
                return self._proposal_result(updated, mode="dry-run" if dry_run else "execute", mutation_count=0)
            if dry_run:
                updated = self.store.transition(
                    proposal_id,
                    "READY",
                    event="DRY_RUN_COMPLETED",
                    reason=None,
                    data={"remote_mutation_requests": 0, "payload_sha256": plan.payload_sha256},
                    mode="dry-run",
                )
                return self._proposal_result(updated, mode="dry-run", mutation_count=0, outcome="DRY_RUN")
            if locked_proposal["state"] != "READY":
                self.store.transition(
                    proposal_id,
                    "READY",
                    event="APPLY_GATES_PASSED",
                    reason=None,
                    data={"base_context_sha256": ticket_context_sha256(current)},
                )
            self.store.transition(
                proposal_id,
                "APPLYING",
                event="MUTATION_INTENT_PERSISTED",
                data={"payload_sha256": plan.payload_sha256},
                operation_id=plan.operation_id,
                payload_sha256=plan.payload_sha256,
                mode="execute",
            )
            try:
                adapter.apply(plan, dry_run=False)
            except (PermissionDenied, IdentityError) as exc:
                updated = self.store.transition(
                    proposal_id,
                    "FAILED",
                    event="MUTATION_BOUNDARY_REFUSED",
                    reason=str(exc),
                    data={"remote_mutation_requests": 0},
                )
                return self._proposal_result(updated, mode="execute", mutation_count=0)
            except RemoteError as exc:
                state = "UNKNOWN_REMOTE_RESULT" if exc.result_unknown else "FAILED"
                updated = self.store.transition(
                    proposal_id,
                    state,
                    event="MUTATION_RESULT_UNKNOWN" if exc.result_unknown else "MUTATION_FAILED",
                    reason=str(exc),
                    data={"status": exc.status, "retryable": exc.retryable},
                )
                return self._proposal_result(
                    updated,
                    mode="execute",
                    mutation_count=1 if exc.mutation_attempted else 0,
                )
            self.store.transition(proposal_id, "VERIFYING", event="MUTATION_RESPONSE_RECEIVED")
            return self._verify(proposal_id, plan, adapter, mutation_count=1)

    @staticmethod
    def _assert_same_identity(expected: TicketIdentity, actual: TicketIdentity) -> None:
        if expected != actual:
            raise IdentityError("remote identity changed or does not match proposal")

    def _record_stale_revision(
        self,
        proposal_id: str,
        proposal: dict[str, Any],
        current: TicketRecord,
        reason: str,
    ) -> dict[str, Any]:
        request = self._load_request(proposal_id)
        old_proposed = self.store.read_artifact(proposal_id, "proposed-description.txt").decode("utf-8")
        old_comment = self.store.read_artifact(proposal_id, "proposed-comment.txt").decode("utf-8")
        metadata = {
            "schema_version": 1,
            "profile": proposal["profile_name"],
            "operation": proposal["operation"],
            "identity": current.identity.as_dict(),
            "base_description_sha256": current.description_sha256,
            "base_context_sha256": ticket_context_sha256(current),
            "proposed_description_sha256": sha256_text(old_proposed),
            "comment_sha256": sha256_text(old_comment),
            "remerge_required": True,
            "approval_reusable": False,
            "checked_at": utc_now(),
            "operation_id": self.store.get_revision(proposal_id)["metadata"].get("operation_id"),
            "payload_sha256": self.store.get_revision(proposal_id)["metadata"].get("payload_sha256"),
            "provider_ticket_numeric_id": current.provider_ticket_numeric_id,
        }
        artifacts = {
            "metadata.json": _json_bytes(metadata),
            "base.json": _json_bytes(current.as_dict()),
            "intent.json": _json_bytes(request),
            "proposed-description.txt": old_proposed.encode("utf-8"),
            "proposed-comment.txt": old_comment.encode("utf-8"),
            "snapshot.json": self.store.read_artifact(proposal_id, "snapshot.json"),
            "planned-payload.json": self.store.read_artifact(proposal_id, "planned-payload.json"),
            "description.diff": unified_diff(
                current.description,
                old_proposed,
                before_name="latest-remote-description",
                after_name="stale-proposed-description",
            ).encode("utf-8"),
            "comment.diff": self.store.read_artifact(proposal_id, "comment.diff"),
        }
        updated = self.store.add_revision(
            proposal_id,
            state="NEEDS_REMERGE",
            reason=reason,
            artifacts=artifacts,
            metadata=metadata,
        )
        return self._proposal_result(updated, mode="revalidate", mutation_count=0, outcome="NEEDS_REMERGE")

    def _record_decision_revision(
        self,
        proposal_id: str,
        proposal: dict[str, Any],
        current: TicketRecord,
        *,
        state: str,
        reason: str,
        granted: list[str],
        missing: list[str],
        capabilities: dict[str, Any],
    ) -> dict[str, Any]:
        old_metadata = dict(self.store.get_revision(proposal_id)["metadata"])
        old_metadata.update(
            {
                "granted_permissions": granted,
                "missing_permissions": missing,
                "provider_capabilities": capabilities,
                "base_description_sha256": current.description_sha256,
                "base_context_sha256": ticket_context_sha256(current),
                "decision_changed_at": utc_now(),
                "approval_reusable": False,
            }
        )
        if old_metadata.get("protected_sections"):
            old_metadata["confirmation_required"] = True
            if state == "READY":
                state = "NEEDS_REVIEW"
                reason = "confirm the protected changes in the new revision"
        artifacts = {
            "metadata.json": _json_bytes(old_metadata),
            "base.json": _json_bytes(current.as_dict()),
            "intent.json": self.store.read_artifact(proposal_id, "intent.json"),
            "proposed-description.txt": self.store.read_artifact(proposal_id, "proposed-description.txt"),
            "proposed-comment.txt": self.store.read_artifact(proposal_id, "proposed-comment.txt"),
            "snapshot.json": self.store.read_artifact(proposal_id, "snapshot.json"),
            "planned-payload.json": self.store.read_artifact(proposal_id, "planned-payload.json"),
            "description.diff": self.store.read_artifact(proposal_id, "description.diff"),
            "comment.diff": self.store.read_artifact(proposal_id, "comment.diff"),
        }
        updated = self.store.add_revision(
            proposal_id,
            state=state,
            reason=reason,
            artifacts=artifacts,
            metadata=old_metadata,
        )
        return self._proposal_result(
            updated,
            mode="revalidate",
            mutation_count=0,
            outcome=state,
        )

    def _verify(
        self,
        proposal_id: str,
        plan: MutationPlan,
        adapter: BaseAdapter,
        *,
        mutation_count: int,
    ) -> dict[str, Any]:
        try:
            remote = self._assert_record_safe(
                adapter.read_ticket(plan.identity.ticket_id)
            )
            self._assert_same_identity(plan.identity, remote.identity)
            marker = f"ticket-state/{plan.operation_id}"
            comment_evidence = adapter.find_comment(plan.identity.ticket_id, plan.comment)
            final_remote = self._assert_record_safe(
                adapter.read_ticket(plan.identity.ticket_id)
            )
            self._assert_same_identity(plan.identity, final_remote.identity)
            if plan.operation == "snapshot":
                request = self._load_request(proposal_id)
                description_ok = (
                    final_remote.description_sha256
                    == request["snapshot_description_sha256"]
                )
            else:
                description_ok = plan.description is None or final_remote.description == plan.description
            comment_ok = (
                comment_evidence is not None
                and comment_evidence.content == plan.comment
                and marker in comment_evidence.content
                and comment_evidence.visibility == "public"
            )
        except RemoteError as exc:
            updated = self.store.transition(
                proposal_id,
                "UNKNOWN_REMOTE_RESULT",
                event="VERIFICATION_INCOMPLETE",
                reason=str(exc),
                data={"status": exc.status},
            )
            return self._proposal_result(updated, mode="execute", mutation_count=mutation_count)
        if description_ok and comment_ok:
            receipt = {
                "schema_version": 1,
                "proposal_id": proposal_id,
                "operation_id": plan.operation_id,
                "identity": plan.identity.as_dict(),
                "payload_sha256": plan.payload_sha256,
                "description_sha256": final_remote.description_sha256,
                "comment_marker": marker,
                "comment_id": comment_evidence.comment_id,
                "comment_sha256": sha256_text(comment_evidence.content),
                "remote_updated_at": final_remote.updated_at,
                "remote_retrieved_at": final_remote.retrieved_at,
                "verified_at": utc_now(),
                "result": "APPLIED",
            }
            receipt_path = self.store.save_receipt(plan.operation_id, receipt)
            updated = self.store.transition(
                proposal_id,
                "APPLIED",
                event="REMOTE_RESULT_VERIFIED",
                data={"receipt_path": str(receipt_path)},
            )
            return self._proposal_result(updated, mode="execute", mutation_count=mutation_count, outcome="APPLIED")
        if plan.operation in {"update-state", "snapshot"} and (description_ok or comment_ok):
            state = "PARTIAL_APPLIED"
            event = "PARTIAL_REMOTE_RESULT"
        else:
            state = "UNKNOWN_REMOTE_RESULT"
            event = "REMOTE_RESULT_NOT_CONFIRMED"
        updated = self.store.transition(
            proposal_id,
            state,
            event=event,
            reason="remote description/comment evidence was incomplete",
            data={"description_ok": description_ok, "comment_ok": comment_ok},
        )
        return self._proposal_result(updated, mode="execute", mutation_count=mutation_count)

    def revalidate(self, proposal_id: str) -> dict[str, Any]:
        proposal, metadata, plan = self._load_plan(proposal_id)
        if proposal["state"] in {"APPLYING", "VERIFYING", "UNKNOWN_REMOTE_RESULT", "PARTIAL_APPLIED"}:
            raise StateError("ambiguous or in-flight proposals require reconcile")
        if proposal["state"] == "NEEDS_REMERGE":
            updated = self.store.transition(
                proposal_id,
                "NEEDS_REMERGE",
                event="REMERGE_STILL_REQUIRED",
                reason="a new semantic merge and proposal revision are required",
            )
            return self._proposal_result(updated, mode="revalidate", mutation_count=0)
        profile = self.config.profile(proposal["profile_name"])
        adapter = self._adapter(proposal["profile_name"])
        if proposal["state"] == "DRAFT":
            proposal = self.store.transition(
                proposal_id,
                "PREPARED",
                event="DRAFT_RECOVERED",
                reason="recovered a fully persisted draft after interrupted preparation",
            )
        remote = self._assert_record_safe(adapter.read_ticket(plan.identity.ticket_id))
        self._assert_same_identity(plan.identity, remote.identity)
        if (
            remote.description_sha256 != metadata["base_description_sha256"]
            or ticket_context_sha256(remote) != metadata["base_context_sha256"]
        ):
            return self._record_stale_revision(
                proposal_id,
                proposal,
                remote,
                "remote description, metadata, or comments changed",
            )
        aliases = (remote.provider_ticket_numeric_id,) if remote.provider_ticket_numeric_id else ()
        missing = sorted(set(plan.required_permissions) - permissions_for(profile, remote.identity, aliases))
        granted = sorted(permissions_for(profile, remote.identity, aliases))
        state, reason = self._initial_state(
            adapter,
            profile.concurrency,
            missing,
            comment_only=plan.operation != "update-state",
        )
        if (
            granted != sorted(metadata.get("granted_permissions", []))
            or missing != sorted(metadata.get("missing_permissions", []))
            or adapter.capabilities.as_dict() != metadata.get("provider_capabilities")
        ):
            return self._record_decision_revision(
                proposal_id,
                proposal,
                remote,
                state=state,
                reason=reason or "permission or provider capability decision changed",
                granted=granted,
                missing=missing,
                capabilities=adapter.capabilities.as_dict(),
            )
        if state == "READY" and self._confirmation_missing(proposal, metadata):
            state = "NEEDS_REVIEW"
            reason = "confirm the protected changes in this revision before applying"
        updated = self.store.transition(
            proposal_id,
            state,
            event="PROPOSAL_REVALIDATED",
            reason=reason,
            data={"missing_permissions": missing, "base_description_sha256": remote.description_sha256},
        )
        return self._proposal_result(updated, mode="revalidate", mutation_count=0)

    def reconcile(self, proposal_id: str) -> dict[str, Any]:
        proposal, _metadata, plan = self._load_plan(proposal_id)
        if proposal["state"] not in {"APPLYING", "VERIFYING", "UNKNOWN_REMOTE_RESULT", "PARTIAL_APPLIED"}:
            raise StateError("proposal does not require reconciliation")
        adapter = self._adapter(proposal["profile_name"])
        if proposal["state"] != "VERIFYING":
            self.store.transition(
                proposal_id,
                "VERIFYING",
                event="RECONCILIATION_STARTED",
                reason=None,
            )
        result = self._verify(proposal_id, plan, adapter, mutation_count=0)
        result["mode"] = "reconcile"
        return result

    def classify(self, proposal_id: str, state: str, *, reason: str) -> dict[str, Any]:
        if state not in {"REJECTED", "SUPERSEDED"}:
            raise StateError("unsupported manual classification")
        if not reason.strip():
            raise UnsafeContentError("classification requires a reason")
        updated = self.store.transition(
            proposal_id,
            state,
            event=f"PROPOSAL_{state}",
            reason=reason.strip(),
        )
        return self._proposal_result(updated, mode="classify", mutation_count=0)

    def diff(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.store.get_proposal(proposal_id)
        metadata = self.store.get_revision(proposal_id)["metadata"]
        base = self._load_json_artifact(proposal_id, "base.json")
        return {
            "schema_version": 1,
            "proposal_id": proposal_id,
            "revision": proposal["current_revision"],
            "state": proposal["state"],
            "profile": proposal["profile_name"],
            "identity": proposal["identity"],
            "base_retrieved_at": base.get("retrieved_at"),
            "base_description_sha256": metadata.get("base_description_sha256"),
            "required_permissions": proposal["required_permissions"],
            "granted_permissions": metadata.get("granted_permissions", []),
            "missing_permissions": metadata.get("missing_permissions", []),
            "description_diff": self.store.read_artifact(proposal_id, "description.diff").decode("utf-8"),
            "comment_diff": self.store.read_artifact(proposal_id, "comment.diff").decode("utf-8"),
            "proposed_comment": self.store.read_artifact(proposal_id, "proposed-comment.txt").decode("utf-8"),
        }

    def template_extract(self, profile_name: str, targets: list[str]) -> dict[str, Any]:
        if not targets:
            raise UnsafeContentError("template extract requires ticket targets")
        profile = self.config.profile(profile_name)
        adapter = self._adapter(profile_name)
        samples: list[tuple[dict[str, Any], str, str]] = []
        observed_markup: str | None = None
        for target in targets:
            normalized = normalize_target(profile, target)
            record = self._assert_record_safe(adapter.read_ticket(normalized))
            if observed_markup is None:
                observed_markup = record.markup
            elif observed_markup != record.markup:
                raise UnsafeContentError("template samples use conflicting markup modes")
            samples.append((record.identity.as_dict(), record.retrieved_at, record.description))
        return extract_template_candidate(samples, markup=observed_markup or profile.markup, store=self.store)

    def template_validate(self, path: Path, *, require_approved: bool = False) -> dict[str, Any]:
        data = path.read_text(encoding="utf-8")
        value = _read_json_file(path)
        validate_template(value, require_approved=require_approved)
        return {
            "schema_version": 1,
            "valid": True,
            "template_id": value["template_id"],
            "approved": value["approved"],
            "artifact_sha256": sha256_text(data),
        }

    def template_approve(self, path: Path, *, approved_by: str, reason: str) -> dict[str, Any]:
        return approve_template(path, store=self.store, approved_by=approved_by, reason=reason)

    def _confirmation_missing(self, proposal: dict[str, Any], metadata: dict[str, Any]) -> bool:
        return bool(metadata.get("confirmation_required")) and not self.store.approvals(
            proposal["proposal_id"], proposal["current_revision"]
        )

    def _proposal_result(
        self,
        proposal: dict[str, Any],
        *,
        mode: str,
        mutation_count: int,
        outcome: str | None = None,
    ) -> dict[str, Any]:
        revision_path = Path(proposal["revision_path"])
        revision_metadata = self.store.get_revision(proposal["proposal_id"])["metadata"]
        numeric_id = revision_metadata.get("provider_ticket_numeric_id")
        aliases = (numeric_id,) if isinstance(numeric_id, str) and numeric_id else ()
        granted = permissions_for(
            self.config.profile(proposal["profile_name"]),
            _identity_from_dict(proposal["identity"]),
            aliases,
        )
        return {
            "schema_version": 1,
            "mode": mode,
            "outcome": outcome or proposal["state"],
            "proposal_id": proposal["proposal_id"],
            "proposal_revision": proposal["current_revision"],
            "state": proposal["state"],
            "reason": proposal["reason"],
            "remote_mutation_requests": mutation_count,
            "would_write": (
                proposal["state"] == "READY"
                and set(proposal["required_permissions"]) <= granted
                and not self._confirmation_missing(proposal, revision_metadata)
            ),
            "confirmation_required": self._confirmation_missing(proposal, revision_metadata),
            "protected_sections": revision_metadata.get("protected_sections", []),
            "required_permissions": proposal["required_permissions"],
            "profile": proposal["profile_name"],
            "identity": proposal["identity"],
            "base_description_sha256": revision_metadata.get("base_description_sha256"),
            "base_retrieved_at": self._load_json_artifact(
                proposal["proposal_id"], "base.json"
            ).get("retrieved_at"),
            "granted_permissions": sorted(granted),
            "missing_permissions": sorted(set(proposal["required_permissions"]) - granted),
            "work_dir": str(self.store.workspace),
            "proposal_path": str(self.store.workspace / "proposals" / proposal["proposal_id"] / "proposal.md"),
            "description_diff_path": str(revision_path / "description.diff"),
            "comment_diff_path": str(revision_path / "comment.diff"),
            "comment_path": str(revision_path / "proposed-comment.txt"),
            "planned_payload_path": str(revision_path / "planned-payload.json"),
        }


def load_request(path: Path) -> dict[str, Any]:
    return _read_json_file(path)
