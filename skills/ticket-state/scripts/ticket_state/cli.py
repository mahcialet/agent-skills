"""Command-line contract shared by Codex and GitHub Copilot CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .adapters import make_adapter
from .config import (
    Config,
    RepositoryConfig,
    default_config_path,
    default_state_root,
    load_config,
    normalize_target,
)
from .errors import ConfigurationError, StorageError, TicketStateError, UnsafeContentError
from .model import sha256_text
from .storage import ProposalStore
from .templates import approve_template, validate_template
from .transport import FixtureTransport, UrlLibTransport, redact
from .workflow import TicketStateService, load_request

VERSION = "0.1.0"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket-state",
        description=(
            "Backlog/Redmineの状態更新案を永続化し、許可・鮮度を検証して反映する。"
            " --dry-runはremote mutationを0件にし、local proposal/diff/journalは保存する。"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--work-dir", type=Path, default=default_state_root())
    parser.add_argument("--workspace-id")
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument(
        "--fixture",
        type=Path,
        help="eval専用のexact-match HTTPS GET fixture。remote mutationは常に拒否する",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    read = commands.add_parser("read", help="最新チケットとcomments/journalsを読み取る")
    read.add_argument("--profile")
    read.add_argument("--ticket", required=True)

    commands.add_parser("context", help="current Git repositoryのprofileとworkspaceを解決する")

    prepare = commands.add_parser("prepare", help="requestからproposalとdiffを保存する")
    prepare.add_argument("--request", required=True, type=Path)

    for name, help_text in (
        ("update-state", "descriptionとcurrent state snapshotを一つの操作として更新する"),
        ("snapshot", "current state snapshotコメントを追記する"),
        ("append-comment", "明示された補足コメントを追記する"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--request", required=True, type=Path)
        command.add_argument(
            "--dry-run",
            action="store_true",
            help="remote mutationは0件。local proposal/diff/journalは保存する",
        )

    diff = commands.add_parser("diff", help="保存済みproposalのdiffと予定コメントを表示する")
    diff.add_argument("proposal_id")

    apply = commands.add_parser("apply", help="proposalを最新remoteで再検証して反映する")
    apply.add_argument("proposal_id")
    apply.add_argument(
        "--dry-run",
        action="store_true",
        help="remote mutationは0件。再検証結果をjournalへ保存する",
    )

    commands.add_parser("pending", help="未反映proposalを一覧する")
    show = commands.add_parser("show", help="proposal metadataを表示する")
    show.add_argument("proposal_id")
    history = commands.add_parser("history", help="operation historyを表示する")
    history.add_argument("proposal_id", nargs="?")
    recover_local = commands.add_parser("recover-local", help="crashで残ったorphan artifactを削除せず隔離する")
    recover_local.add_argument("--reason", required=True)
    approve_content = commands.add_parser("approve", help="特定proposal revision/hashへの人間の承認を記録する")
    approve_content.add_argument("proposal_id")
    approve_content.add_argument("--revision", type=int, required=True)
    approve_content.add_argument("--content-sha256", required=True)
    approve_content.add_argument("--approved-by", default="conversation-user",
                                 help="任意の確認者名。省略時は会話のユーザーという役割を記録し、本人識別はしない")
    approve_content.add_argument("--reason", required=True)
    revalidate = commands.add_parser("revalidate", help="remoteと権限を再検証する")
    revalidate.add_argument("proposal_id")
    reconcile = commands.add_parser("reconcile", help="結果不明/部分成功をremote evidenceと照合する")
    reconcile.add_argument("proposal_id")
    for name in ("reject", "supersede"):
        command = commands.add_parser(name, help=f"proposalを{name}分類し履歴を保持する")
        command.add_argument("proposal_id")
        command.add_argument("--reason", required=True)

    template = commands.add_parser("template", help="template候補を抽出・検証・承認する")
    template_commands = template.add_subparsers(dest="template_command", required=True)
    extract = template_commands.add_parser("extract", help="既存ticketからlocal candidateだけを生成する")
    extract.add_argument("--profile")
    extract.add_argument("--tickets", nargs="+", required=True)
    validate = template_commands.add_parser("validate", help="candidate/approved templateを検証する")
    validate.add_argument("--file", type=Path, required=True)
    validate.add_argument("--require-approved", action="store_true")
    approve = template_commands.add_parser("approve", help="人間の明示判断を別artifactとして保存する")
    approve.add_argument("--candidate", type=Path, required=True)
    approve.add_argument("--approved-by", required=True)
    approve.add_argument("--reason", required=True)
    return parser


def _workspace_id(
    value: str | None,
    repository: RepositoryConfig | None = None,
) -> str:
    if value:
        return value
    if repository is not None:
        return repository.workspace_id
    return "workspace-" + sha256_text(str(Path.cwd().resolve()))[:16]


def _profile_name(
    value: str | None,
    repository: RepositoryConfig | None,
) -> str:
    if value is not None:
        return value
    if repository is not None:
        return repository.profile
    raise ConfigurationError(
        "profile is required when the current Git repository has no configured binding"
    )


def _request_with_profile(
    request: dict[str, Any],
    repository: RepositoryConfig | None,
) -> dict[str, Any]:
    if "profile" in request:
        return request
    resolved = dict(request)
    resolved["profile"] = _profile_name(None, repository)
    return resolved


def _state_exit_code(result: dict[str, Any]) -> int:
    state = result.get("state")
    outcome = result.get("outcome")
    if outcome in {"DRY_RUN", "APPLIED", "NO_CHANGE"} or state in {None, "READY", "APPLIED", "NO_CHANGE"}:
        return 0
    if state in {"PENDING_PERMISSION", "NEEDS_REVIEW", "NEEDS_REMERGE"}:
        return 2
    if state in {"UNKNOWN_REMOTE_RESULT", "PARTIAL_APPLIED", "FAILED", "APPLYING", "VERIFYING"}:
        return 3
    return 0


def _print_text(result: Any, command: str) -> None:
    if command == "diff" and isinstance(result, dict):
        identity = result.get("identity", {})
        print(
            f"Target: {result.get('profile')} / {identity.get('ticket_id')} "
            f"({identity.get('base_url')}, project {identity.get('project_id')})"
        )
        print(
            f"Base: {result.get('base_description_sha256')} at {result.get('base_retrieved_at')} | "
            f"required={result.get('required_permissions')} missing={result.get('missing_permissions')}"
        )
        sys.stdout.write(result.get("description_diff", ""))
        if result.get("comment_diff"):
            if result.get("description_diff") and not str(result["description_diff"]).endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.write(result["comment_diff"])
        if result.get("proposed_comment"):
            sys.stdout.write("\n予定コメント全文:\n")
            sys.stdout.write(result["proposed_comment"])
        return
    if isinstance(result, dict) and result.get("proposal_id"):
        print(
            f"{result['proposal_id']}: {result.get('outcome', result.get('state'))} "
            f"(remote mutation requests: {result.get('remote_mutation_requests', 0)})"
        )
        if result.get("reason"):
            print(f"理由: {result['reason']}")
        identity = result.get("identity") or {}
        if identity:
            print(
                f"対象: {identity.get('ticket_id')} "
                f"({identity.get('base_url')}, project {identity.get('project_id')})"
            )
        if result.get("state") == "PENDING_PERMISSION":
            print("remoteは更新していません。")
            print(f"必要な権限: {result.get('missing_permissions') or result.get('required_permissions')}")
            print("許可後もrevalidateまたはapplyで最新ticketと権限を再検証してください。")
        if result.get("confirmation_required"):
            print("目的・制約の変更案を確認してください。確認者名の入力は不要です。")
        if result.get("proposal_path"):
            print(f"保存先: {result['proposal_path']}")
        if result.get("description_diff_path"):
            print(f"差分: {result['description_diff_path']}")
        if result.get("planned_payload_path"):
            print(f"予定payload: {result['planned_payload_path']}")
        return
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def _secrets(config: Any | None) -> tuple[str, ...]:
    if config is None:
        return ()
    return tuple(
        value
        for instance in config.instances.values()
        if (value := os.environ.get(instance.api_key_env))
    )


def _stored_object(store: ProposalStore, proposal_id: str, name: str) -> dict[str, Any]:
    try:
        value = json.loads(store.read_artifact(proposal_id, name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageError(f"stored proposal artifact {name} is invalid JSON") from exc
    if not isinstance(value, dict):
        raise StorageError(f"stored proposal artifact {name} must be an object")
    return value


def _contains_text(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return needle in value
    if isinstance(value, dict):
        return any(
            _contains_text(key, needle) or _contains_text(item, needle)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_text(item, needle) for item in value)
    return False


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    config: Config | None = None
    try:
        state_only = args.command in {"approve", "diff", "pending", "show", "history", "recover-local"} or (
            args.command == "template" and args.template_command == "approve"
        )
        config_free = args.command == "template" and args.template_command == "validate"
        if not config_free and (
            not state_only or (args.workspace_id is None and args.config.is_file())
        ):
            config = load_config(args.config)
        repository = config.repository_for_path() if config is not None else None
        workspace_id = _workspace_id(args.workspace_id, repository)
        transport = FixtureTransport(args.fixture) if args.fixture else UrlLibTransport()
        if args.command == "context":
            if config is None or repository is None:
                raise ConfigurationError(
                    "current Git repository has no configured repository binding"
                )
            result: Any = {
                "schema_version": 1,
                "repository": repository.name,
                "profile": repository.profile,
                "workspace_id": workspace_id,
            }
        elif args.command == "read":
            if config is None:
                raise ConfigurationError("read requires config")
            profile_name = _profile_name(args.profile, repository)
            profile = config.profile(profile_name)
            normalized = normalize_target(profile, args.ticket)
            record = make_adapter(profile, transport).read_ticket(normalized)
            if any(
                _contains_text(record.as_dict(), secret)
                for secret in _secrets(config)
            ):
                raise UnsafeContentError(
                    "remote ticket contains a configured API key value; content was not returned"
                )
            result = {
                "schema_version": 1,
                "profile": profile_name,
                "config_path": str(config.path),
                "ticket": record.as_dict(),
            }
        elif args.command == "template" and args.template_command == "validate":
            value = load_request(args.file)
            validate_template(value, require_approved=args.require_approved)
            result = {
                "schema_version": 1,
                "valid": True,
                "template_id": value["template_id"],
                "approved": value["approved"],
                "artifact_sha256": sha256_text(args.file.read_text(encoding="utf-8")),
            }
        elif state_only:
            store = ProposalStore(
                args.work_dir,
                workspace_id=workspace_id,
                audit_on_open=args.command != "recover-local",
            )
            if args.command == "diff":
                proposal = store.get_proposal(args.proposal_id)
                metadata = store.get_revision(args.proposal_id)["metadata"]
                base = _stored_object(store, args.proposal_id, "base.json")
                result = {
                    "schema_version": 1,
                    "proposal_id": args.proposal_id,
                    "revision": proposal["current_revision"],
                    "state": proposal["state"],
                    "profile": proposal["profile_name"],
                    "identity": proposal["identity"],
                    "base_retrieved_at": base.get("retrieved_at"),
                    "base_description_sha256": metadata.get("base_description_sha256"),
                    "required_permissions": proposal["required_permissions"],
                    "granted_permissions": metadata.get("granted_permissions", []),
                    "missing_permissions": metadata.get("missing_permissions", []),
                    "protected_sections": metadata.get("protected_sections", []),
                    "confirmation_required": bool(metadata.get("confirmation_required")) and not store.approvals(args.proposal_id),
                    "description_diff": store.read_artifact(args.proposal_id, "description.diff").decode("utf-8"),
                    "comment_diff": store.read_artifact(args.proposal_id, "comment.diff").decode("utf-8"),
                    "proposed_comment": store.read_artifact(args.proposal_id, "proposed-comment.txt").decode("utf-8"),
                }
            elif args.command == "pending":
                result = {"schema_version": 1, "workspace": str(store.workspace), "proposals": store.list_pending()}
            elif args.command == "show":
                proposal = store.get_proposal(args.proposal_id)
                result = {
                    "schema_version": 1,
                    "proposal": proposal,
                    "revision": store.get_revision(args.proposal_id),
                    "current_revision_approvals": store.approvals(args.proposal_id),
                }
            elif args.command == "history":
                result = {"schema_version": 1, "events": store.history(args.proposal_id)}
            elif args.command == "approve":
                result = store.record_approval(
                    args.proposal_id,
                    revision=args.revision,
                    content_sha256=args.content_sha256,
                    approved_by=args.approved_by,
                    reason=args.reason,
                )
            elif args.command == "recover-local":
                result = store.recover_orphans(reason=args.reason)
            else:
                result = approve_template(
                    args.candidate,
                    store=store,
                    approved_by=args.approved_by,
                    reason=args.reason,
                )
        else:
            if config is None:
                raise ConfigurationError("command requires config")
            store = ProposalStore(args.work_dir, workspace_id=workspace_id)
            service = TicketStateService(config, store, transport)
            if args.command == "prepare":
                request = _request_with_profile(load_request(args.request), repository)
                result = service.prepare(request)
            elif args.command in {"update-state", "snapshot", "append-comment"}:
                if args.fixture and not args.dry_run:
                    raise TicketStateError("fixture transport can only be used with --dry-run for mutating commands")
                request = _request_with_profile(load_request(args.request), repository)
                result = service.update(request, args.command, dry_run=args.dry_run)
            elif args.command == "diff":
                result = service.diff(args.proposal_id)
            elif args.command == "apply":
                if args.fixture and not args.dry_run:
                    raise TicketStateError("fixture transport can only be used with --dry-run for apply")
                result = service.apply(args.proposal_id, dry_run=args.dry_run)
            elif args.command == "revalidate":
                result = service.revalidate(args.proposal_id)
            elif args.command == "reconcile":
                result = service.reconcile(args.proposal_id)
            elif args.command in {"reject", "supersede"}:
                result = service.classify(args.proposal_id, args.command.upper() + ("D" if args.command == "supersede" else "ED"), reason=args.reason)
            elif args.command == "template" and args.template_command == "extract":
                profile_name = _profile_name(args.profile, repository)
                result = service.template_extract(profile_name, args.tickets)
            else:
                parser.error("unsupported command")
                return 2
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        else:
            _print_text(result, args.command)
        return _state_exit_code(result if isinstance(result, dict) else {})
    except TicketStateError as exc:
        message = redact(str(exc), _secrets(config))
        payload = {"schema_version": 1, "error": exc.code, "message": message}
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        else:
            print(f"{exc.code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
