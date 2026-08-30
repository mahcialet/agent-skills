#!/usr/bin/env python3
"""reader-first-editorのprovider-neutralなlocal corpus CLI。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from reader_first.github import (
    GitHubRestClient,
    build_reference_only_candidates,
    default_github_token,
    fetch_pull_request_snapshot,
    load_recorded_snapshot,
)
from reader_first.state import (
    STATE_DIRECTORIES,
    TOOL_VERSION,
    TRANSLATION_STATUSES,
    LocalCorpusStore,
    StoreError,
    prepare_candidate_record,
    resolve_data_dir,
)

SKILL_DIR = Path(__file__).resolve().parent.parent


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(f"JSON fileを読み込めません: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise StoreError(f"JSON fileのtop levelはobjectである必要があります: {path}")
    return data


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))


def _data_dir(args: argparse.Namespace) -> Path:
    return resolve_data_dir(
        explicit=args.data_dir,
        scope=args.scope,
        project_root=args.project_root,
    )


def _ensure_project_write_safe(args: argparse.Namespace, data_dir: Path) -> None:
    if args.allow_unignored_project_data:
        return
    probe = data_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=probe,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        if args.scope == "project":
            raise StoreError("project scopeのwriteにはGit worktreeが必要です")
        return
    project_root = Path(result.stdout.strip()).resolve()
    try:
        relative = data_dir.relative_to(project_root)
    except ValueError as exc:
        if args.scope == "project":
            raise StoreError("project data directoryがGit worktree外にあります") from exc
        return
    check_path = f"{relative.as_posix().rstrip('/')}/"
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", check_path],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise StoreError(
            "project scopeへwriteする前に .reader-first-editor/ を.gitignoreへ追加してください。"
            "確認済みの場合だけ --allow-unignored-project-data で明示overrideできます"
        )


def _add_actor_reason(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor", required=True, help="auditへ記録する実施者")
    parser.add_argument("--reason", required=True, help="auditへ記録する理由")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="reader-first-editor local corpus tool")
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    parser.add_argument("--data-dir", type=Path, help="local data directoryを明示する")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--allow-unignored-project-data",
        action="store_true",
        help="project dataがgitignoreされていないwriteを明示的に許可する",
    )
    domains = parser.add_subparsers(dest="domain", required=True)
    corpus = domains.add_parser("corpus", help="local corpusを操作する")
    commands = corpus.add_subparsers(dest="command", required=True)

    list_parser = commands.add_parser("list", help="record一覧を表示する")
    list_parser.add_argument("--state", action="append", choices=sorted(STATE_DIRECTORIES))

    inspect_parser = commands.add_parser("inspect", help="recordを表示する")
    inspect_parser.add_argument("record_id")

    collect_parser = commands.add_parser("collect", help="manual JSON recordをcandidateとして収集する")
    collect_parser.add_argument("--record", type=Path, required=True)
    collect_parser.add_argument("--dry-run", action="store_true")
    _add_actor_reason(collect_parser)

    github_parser = commands.add_parser(
        "collect-github",
        help="明示指定したpublic GitHub PRからreference-only candidateを収集する",
    )
    github_parser.add_argument("--repository", required=True, help="owner/name形式のpublic repository")
    github_parser.add_argument("--pr-number", type=int, required=True)
    github_parser.add_argument("--file", action="append", dest="files", help="対象Markdown fileを限定する")
    github_parser.add_argument("--language", choices=("ja", "en"), required=True)
    github_parser.add_argument(
        "--translation-status",
        choices=sorted(TRANSLATION_STATUSES),
        default="unknown",
    )
    github_parser.add_argument("--genre", required=True)
    github_parser.add_argument("--reader-description", required=True)
    github_parser.add_argument(
        "--reader-evidence",
        default="CLIで利用者が明示したreader metadata",
    )
    github_parser.add_argument(
        "--fixture",
        type=Path,
        help="networkを使わず、raw textを除いたrecorded snapshotを読む",
    )
    github_parser.add_argument("--dry-run", action="store_true")
    _add_actor_reason(github_parser)

    annotate_parser = commands.add_parser("annotate", help="candidateへannotationを保存する")
    annotate_parser.add_argument("record_id")
    annotate_parser.add_argument("--annotation", type=Path, required=True)
    _add_actor_reason(annotate_parser)

    accept_parser = commands.add_parser("accept", help="annotated recordをacceptする")
    accept_parser.add_argument("record_id")
    _add_actor_reason(accept_parser)

    reject_parser = commands.add_parser("reject", help="candidateまたはannotated recordをrejectする")
    reject_parser.add_argument("record_id")
    _add_actor_reason(reject_parser)

    commands.add_parser("validate", help="storeをread-onlyで検証する")

    promote_parser = commands.add_parser("promote", help="accepted recordのlocal promotionをpreviewする")
    promote_parser.add_argument("record_id")
    promote_parser.add_argument("--apply", action="store_true")
    promote_parser.add_argument("--actor", help="--apply時にauditへ記録する実施者")
    promote_parser.add_argument("--reason", help="--apply時にauditへ記録する理由")
    return parser


def run(args: argparse.Namespace) -> int:
    data_dir = _data_dir(args)
    store = LocalCorpusStore(data_dir, skill_dir=SKILL_DIR)
    command = args.command

    if command == "list":
        states = set(args.state) if args.state else None
        _print_json({"data_dir": str(data_dir), "records": store.list_records(states)})
        return 0
    if command == "inspect":
        _print_json(store.load_record(args.record_id))
        return 0
    if command == "validate":
        errors = store.validate_store()
        _print_json({"data_dir": str(data_dir), "valid": not errors, "errors": errors})
        return 1 if errors else 0
    if command == "collect":
        record = _read_json(args.record)
        prepared = prepare_candidate_record(record)
        if args.dry_run:
            _print_json(
                {
                    "dry_run": True,
                    "record_id": prepared["id"],
                    "data_dir": str(data_dir),
                    "will_modify": [],
                }
            )
            return 0
        _ensure_project_write_safe(args, data_dir)
        created = store.create_candidate(record, actor=args.actor, reason=args.reason)
        _print_json({"created": created["id"], "state": "candidate", "data_dir": str(data_dir)})
        return 0
    if command == "collect-github":
        if not args.dry_run:
            _ensure_project_write_safe(args, data_dir)
        if args.fixture is not None:
            snapshot = load_recorded_snapshot(
                args.fixture,
                repository=args.repository,
                pr_number=args.pr_number,
            )
        else:
            snapshot = fetch_pull_request_snapshot(
                GitHubRestClient(token=default_github_token()),
                args.repository,
                args.pr_number,
            )
        records = build_reference_only_candidates(
            snapshot,
            language=args.language,
            translation_status=args.translation_status,
            genre=args.genre,
            reader_description=args.reader_description,
            reader_evidence=args.reader_evidence,
            selected_files=args.files,
        )
        records = [prepare_candidate_record(record) for record in records]
        if args.dry_run:
            _print_json(
                {
                    "dry_run": True,
                    "network_accessed": args.fixture is None,
                    "repository": snapshot["repository"]["full_name"],
                    "pull_request": snapshot["pull_request"]["number"],
                    "source_revision": snapshot["pull_request"]["head_revision"],
                    "records": records,
                    "will_modify": [],
                }
            )
            return 0
        created = [
            record["id"]
            for record in store.create_candidates(records, actor=args.actor, reason=args.reason)
        ]
        _print_json(
            {
                "created": created,
                "state": "candidate",
                "data_dir": str(data_dir),
                "changes_rule_behavior": False,
                "modified_core": [],
            }
        )
        return 0
    if command == "annotate":
        _ensure_project_write_safe(args, data_dir)
        record = store.annotate(
            args.record_id,
            _read_json(args.annotation),
            actor=args.actor,
            reason=args.reason,
        )
        _print_json({"updated": record["id"], "state": "annotated"})
        return 0
    if command in {"accept", "reject"}:
        _ensure_project_write_safe(args, data_dir)
        target = "accepted" if command == "accept" else "rejected"
        record = store.transition(args.record_id, target, actor=args.actor, reason=args.reason)
        _print_json({"updated": record["id"], "state": target})
        return 0
    if command == "promote":
        preview = store.promotion_preview(args.record_id)
        if not args.apply:
            _print_json({"dry_run": True, **preview})
            return 0
        if not args.actor or not args.reason:
            raise StoreError("--applyには--actorと--reasonが必要です")
        _ensure_project_write_safe(args, data_dir)
        record = store.promote_local(args.record_id, actor=args.actor, reason=args.reason)
        _print_json(
            {
                "promoted": record["id"],
                "state": "promoted",
                "changes_rule_behavior": False,
                "modified_core": [],
            }
        )
        return 0
    raise StoreError(f"未対応commandです: {command}")


def main() -> int:
    parser = build_parser()
    try:
        return run(parser.parse_args())
    except (StoreError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
