"""ローカルcorpus recordのpath解決、検証、状態遷移、audit記録。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
TOOL_VERSION = "0.5.0"
STATE_DIRECTORIES = {
    "candidate": "candidates",
    "annotated": "annotated",
    "accepted": "accepted",
    "rejected": "rejected",
    "promoted": "promoted",
}
ALLOWED_TRANSITIONS = {
    "candidate": {"annotated", "rejected"},
    "annotated": {"accepted", "rejected"},
    "accepted": set(),
    "rejected": set(),
    "promoted": set(),
}
AUDIT_ALLOWED_TRANSITIONS = {
    **ALLOWED_TRANSITIONS,
    "accepted": {"promoted"},
}
AUDIT_ACTION_BY_TRANSITION = {
    ("candidate", "annotated"): "annotate",
    ("candidate", "rejected"): "transition",
    ("annotated", "accepted"): "transition",
    ("annotated", "rejected"): "transition",
    ("accepted", "promoted"): "promote-local",
}
SAMPLE_TYPES = {
    "positive-reviewed",
    "review-directed-revision",
    "human-revision",
    "rejected-suggestion",
    "manual",
}
QUALITY_CLASSES = {"problematic", "clean", "borderline"}
TEXT_STORAGE = {"embedded", "redacted", "reference-only"}
RIGHTS_STATUSES = {"verified", "unknown", "unlicensed", "restricted"}
REDISTRIBUTION_STATUSES = {"allowed", "unknown", "restricted", "not-applicable"}
EXPECTED_BEHAVIORS = {"change", "no-change", "review-only", "context-dependent"}
TRANSLATION_STATUSES = {"native", "translated", "mixed", "unknown"}
SOURCE_TYPES = {"github-pr", "local-file", "manual"}
ID_FIELDS = [
    "schema_version",
    "sample_type",
    "source.type",
    "source.repository",
    "source.pr_number",
    "source.immutable_revision",
    "source.file",
    "source.span",
]
ID_MATERIAL = {
    "algorithm": "sha256",
    "canonicalization_version": 1,
    "fields": ID_FIELDS,
}


class StoreError(RuntimeError):
    """Local storeを安全に操作できない場合の基底error。"""


class RecordValidationError(StoreError):
    """Recordがcorpus schema契約を満たさない。"""


class DuplicateRecordError(StoreError):
    """同じdeterministic IDのrecordがすでに存在する。"""


class InvalidTransitionError(StoreError):
    """許可されていないstate transitionである。"""


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_data_dir(
    *,
    explicit: Path | str | None = None,
    scope: str = "user",
    project_root: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    home: Path | str | None = None,
    platform: str | None = None,
) -> Path:
    """書込みを行わず、local data directoryを決定する。"""

    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    if scope not in {"user", "project"}:
        raise ValueError("scopeは'user'または'project'で指定してください")
    if scope == "project":
        if project_root is None:
            raise ValueError("project scopeにはproject_rootが必要です")
        return (Path(project_root).expanduser().resolve() / ".reader-first-editor")

    env = os.environ if environ is None else environ
    platform_name = sys.platform if platform is None else platform
    home_path = Path.home() if home is None else Path(home)
    if xdg_data_home := env.get("XDG_DATA_HOME"):
        base = Path(xdg_data_home).expanduser()
    elif platform_name == "win32":
        base = Path(env.get("LOCALAPPDATA") or env.get("APPDATA") or home_path / "AppData" / "Local")
    elif platform_name == "darwin":
        base = home_path / "Library" / "Application Support"
    else:
        base = home_path / ".local" / "share"
    return (base / "reader-first-editor").resolve()


def _require_object(record: dict, key: str) -> dict:
    value = record.get(key)
    if not isinstance(value, dict):
        raise RecordValidationError(f"{key}はobjectである必要があります")
    return value


def _require_string(container: dict, key: str, *, allow_empty: bool = False) -> str:
    value = container.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise RecordValidationError(f"{key}は空でないstringである必要があります")
    return value


def _require_keys(container: dict, keys: set[str], context: str) -> None:
    missing = sorted(keys - container.keys())
    if missing:
        raise RecordValidationError(f"{context}に必須keyがありません: {', '.join(missing)}")


def _reject_unknown_keys(container: dict, keys: set[str], context: str) -> None:
    unknown = sorted(container.keys() - keys)
    if unknown:
        raise RecordValidationError(f"{context}に未知のkeyがあります: {', '.join(unknown)}")


def _require_nonnegative_int(container: dict, key: str, context: str) -> int:
    value = container.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RecordValidationError(f"{context}.{key}は0以上のintegerである必要があります")
    return value


def _require_optional_string(container: dict, key: str, context: str) -> str | None:
    value = container.get(key)
    if value is not None and not isinstance(value, str):
        raise RecordValidationError(f"{context}.{key}はstringまたはnullである必要があります")
    return value


def _require_optional_sha(container: dict, key: str, context: str) -> str | None:
    value = _require_optional_string(container, key, context)
    if value is not None and not re.fullmatch(r"[0-9a-f]{40}", value):
        raise RecordValidationError(f"{context}.{key}は40桁のSHAまたはnullである必要があります")
    return value


def validate_corpus_record(record: dict) -> None:
    """依存libraryなしでcorpus recordの主要invariantを検証する。"""

    if not isinstance(record, dict):
        raise RecordValidationError("recordはobjectである必要があります")
    required = {
        "id",
        "id_material",
        "schema_version",
        "language",
        "translation_status",
        "genre",
        "reader",
        "sample_type",
        "quality_class",
        "source",
        "authorship",
        "review_signal",
        "rights",
        "handling",
        "text",
        "annotations",
        "decision",
        "confidence",
        "created_at",
    }
    _require_keys(record, required, "record")
    _reject_unknown_keys(record, required | {"github_evidence"}, "record")
    record_id = _require_string(record, "id")
    if not re.fullmatch(r"rfe-[0-9a-f]{20}", record_id):
        raise RecordValidationError("idはdeterministic candidate ID形式である必要があります")
    if record["schema_version"] != SCHEMA_VERSION:
        raise RecordValidationError(f"未対応のschema_versionです: {record['schema_version']!r}")
    if record["language"] not in {"ja", "en"}:
        raise RecordValidationError("languageは'ja'または'en'である必要があります")
    if record["translation_status"] not in TRANSLATION_STATUSES:
        raise RecordValidationError("translation_statusが未対応です")
    _require_string(record, "genre")
    if record["sample_type"] not in SAMPLE_TYPES:
        raise RecordValidationError("sample_typeが未対応です")
    if record["quality_class"] not in QUALITY_CLASSES:
        raise RecordValidationError("quality_classが未対応です")
    _require_string(record, "created_at")
    if record["confidence"] not in {"low", "medium", "high", "unknown"}:
        raise RecordValidationError("confidenceが未対応です")

    id_material = _require_object(record, "id_material")
    id_material_keys = {"algorithm", "canonicalization_version", "fields"}
    _require_keys(id_material, id_material_keys, "id_material")
    _reject_unknown_keys(id_material, id_material_keys, "id_material")
    if id_material != ID_MATERIAL:
        raise RecordValidationError("id_materialがcanonicalization契約と一致しません")

    reader = _require_object(record, "reader")
    reader_keys = {"description", "evidence_source"}
    _require_keys(reader, reader_keys, "reader")
    _reject_unknown_keys(reader, reader_keys, "reader")
    _require_string(reader, "description")
    _require_string(reader, "evidence_source")

    source = _require_object(record, "source")
    source_keys = {
        "type", "repository", "pr_number", "commit", "file", "span", "url",
        "immutable_revision", "retrieved_at", "correlation_group",
    }
    _require_keys(
        source,
        source_keys,
        "source",
    )
    _reject_unknown_keys(source, source_keys, "source")
    if source["type"] not in SOURCE_TYPES:
        raise RecordValidationError("source.typeが未対応です")
    immutable_revision = _require_string(source, "immutable_revision")
    _require_string(source, "retrieved_at")
    _require_string(source, "correlation_group")
    for key in ("repository", "commit", "file", "span", "url"):
        if source[key] is not None and not isinstance(source[key], str):
            raise RecordValidationError(f"source.{key}はstringまたはnullである必要があります")
    if source["pr_number"] is not None and (
        not isinstance(source["pr_number"], int)
        or isinstance(source["pr_number"], bool)
        or source["pr_number"] < 1
    ):
        raise RecordValidationError("source.pr_numberは1以上のintegerまたはnullである必要があります")
    if source["commit"] is not None and not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise RecordValidationError("source.commitは40桁のcommit SHAまたはnullである必要があります")
    if source["type"] == "github-pr":
        for key in ("repository", "file", "url"):
            _require_string(source, key)
        if source["pr_number"] is None:
            raise RecordValidationError("github-pr sourceにはpr_numberが必要です")
        if not re.fullmatch(r"[0-9a-f]{40}", immutable_revision):
            raise RecordValidationError("github-pr sourceにはimmutable commit SHAが必要です")
    elif not re.fullmatch(r"[0-9a-f]{64}", immutable_revision):
        raise RecordValidationError("manual/local-file sourceには64桁のcontent hashが必要です")

    authorship = _require_object(record, "authorship")
    authorship_keys = {"initial", "final", "ai_assisted"}
    _require_keys(authorship, authorship_keys, "authorship")
    _reject_unknown_keys(authorship, authorship_keys, "authorship")
    for key in ("initial", "final", "ai_assisted"):
        if not isinstance(authorship[key], str) or not authorship[key]:
            raise RecordValidationError(f"authorship.{key}は空でないstringである必要があります")

    review_signal = _require_object(record, "review_signal")
    review_signal_keys = {"type", "summary", "raw_text_included"}
    _require_keys(review_signal, review_signal_keys, "review_signal")
    _reject_unknown_keys(review_signal, review_signal_keys, "review_signal")
    _require_string(review_signal, "type")
    if not isinstance(review_signal["summary"], str):
        raise RecordValidationError("review_signal.summaryはstringである必要があります")
    if not isinstance(review_signal["raw_text_included"], bool):
        raise RecordValidationError("review_signal.raw_text_includedはbooleanである必要があります")

    rights = _require_object(record, "rights")
    rights_keys = {
        "status", "repository_license", "raw_text_redistribution",
        "review_comment_redistribution", "local_only", "redacted", "notes",
    }
    _require_keys(
        rights,
        rights_keys,
        "rights",
    )
    _reject_unknown_keys(rights, rights_keys, "rights")
    if rights["status"] not in RIGHTS_STATUSES:
        raise RecordValidationError("rights.statusが未対応です")
    for key in ("raw_text_redistribution", "review_comment_redistribution"):
        if rights[key] not in REDISTRIBUTION_STATUSES:
            raise RecordValidationError(f"rights.{key}が未対応です")
    for key in ("local_only", "redacted"):
        if not isinstance(rights[key], bool):
            raise RecordValidationError(f"rights.{key}はbooleanである必要があります")
    for key in ("repository_license", "notes"):
        if rights[key] is not None and not isinstance(rights[key], str):
            raise RecordValidationError(f"rights.{key}はstringまたはnullである必要があります")

    handling = _require_object(record, "handling")
    handling_keys = {"anonymized", "modified", "redactions"}
    _require_keys(handling, handling_keys, "handling")
    _reject_unknown_keys(handling, handling_keys, "handling")
    for key in ("anonymized", "modified"):
        if not isinstance(handling[key], bool):
            raise RecordValidationError(f"handling.{key}はbooleanである必要があります")
    if not isinstance(handling["redactions"], list) or not all(
        isinstance(item, str) for item in handling["redactions"]
    ):
        raise RecordValidationError("handling.redactionsはstring listである必要があります")

    text = _require_object(record, "text")
    text_keys = {"storage", "content_hash", "content"}
    _require_keys(text, text_keys, "text")
    _reject_unknown_keys(text, text_keys, "text")
    if text["storage"] not in TEXT_STORAGE:
        raise RecordValidationError("text.storageが未対応です")
    _require_string(text, "content_hash")
    if text["content"] is not None and not isinstance(text["content"], str):
        raise RecordValidationError("text.contentはstringまたはnullである必要があります")
    if text["storage"] == "reference-only" and text["content"] is not None:
        raise RecordValidationError("reference-only recordへraw textを保存できません")
    if text["storage"] in {"embedded", "redacted"} and text["content"] is None:
        raise RecordValidationError("embeddedまたはredacted recordにはtext.contentが必要です")
    if not rights["local_only"]:
        if rights["status"] != "verified":
            raise RecordValidationError("public候補にはverified rightsが必要です")
        if text["storage"] != "reference-only" and rights["raw_text_redistribution"] != "allowed":
            raise RecordValidationError("public候補のraw textにはredistribution permissionが必要です")
        if review_signal["raw_text_included"] and rights["review_comment_redistribution"] != "allowed":
            raise RecordValidationError("public候補のreview textにはredistribution permissionが必要です")

    annotations = _require_object(record, "annotations")
    annotation_keys = {
        "expected_behavior", "rationale", "semantic_invariants", "do_not_change",
        "expected_reread_risks",
    }
    _require_keys(
        annotations,
        annotation_keys,
        "annotations",
    )
    _reject_unknown_keys(annotations, annotation_keys, "annotations")
    if annotations["expected_behavior"] not in EXPECTED_BEHAVIORS:
        raise RecordValidationError("annotations.expected_behaviorが未対応です")
    if not isinstance(annotations["rationale"], str):
        raise RecordValidationError("annotations.rationaleはstringである必要があります")
    for key in ("semantic_invariants", "do_not_change", "expected_reread_risks"):
        value = annotations[key]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise RecordValidationError(f"annotations.{key}はstring listである必要があります")

    decision = _require_object(record, "decision")
    decision_keys = {"state", "reviewer", "decided_at", "reason"}
    _require_keys(decision, decision_keys, "decision")
    _reject_unknown_keys(decision, decision_keys, "decision")
    if decision["state"] not in STATE_DIRECTORIES:
        raise RecordValidationError("decision.stateが未対応です")
    for key in ("reviewer", "decided_at"):
        if decision[key] is not None and not isinstance(decision[key], str):
            raise RecordValidationError(f"decision.{key}はstringまたはnullである必要があります")
    if not isinstance(decision["reason"], str):
        raise RecordValidationError("decision.reasonはstringである必要があります")
    if decision["state"] != "candidate":
        for key in ("reviewer", "decided_at", "reason"):
            if not isinstance(decision[key], str) or not decision[key].strip():
                raise RecordValidationError(
                    f"{decision['state']} recordには空でないdecision.{key}が必要です"
                )
    if record_id != deterministic_candidate_id(record):
        raise RecordValidationError("idがsource identityから再計算した値と一致しません")
    if "github_evidence" in record:
        _validate_github_evidence(record)


def _validate_github_evidence(record: dict) -> None:
    source = record["source"]
    if source["type"] != "github-pr":
        raise RecordValidationError("github_evidenceはgithub-pr sourceだけに使用できます")
    evidence = _require_object(record, "github_evidence")
    evidence_keys = {"repository", "pull_request", "changed_file", "reviews", "inline_threads"}
    _require_keys(evidence, evidence_keys, "github_evidence")
    _reject_unknown_keys(evidence, evidence_keys, "github_evidence")

    repository = _require_object(evidence, "repository")
    repository_keys = {"visibility", "license_spdx_id"}
    _require_keys(repository, repository_keys, "github_evidence.repository")
    _reject_unknown_keys(repository, repository_keys, "github_evidence.repository")
    if repository["visibility"] != "public":
        raise RecordValidationError("github_evidenceはpublic repositoryだけを記録できます")
    _require_optional_string(repository, "license_spdx_id", "github_evidence.repository")

    pull = _require_object(evidence, "pull_request")
    pull_keys = {
        "state",
        "draft",
        "merged_at",
        "created_at",
        "updated_at",
        "base_revision",
        "head_revision",
        "merge_revision",
    }
    _require_keys(pull, pull_keys, "github_evidence.pull_request")
    _reject_unknown_keys(pull, pull_keys, "github_evidence.pull_request")
    _require_string(pull, "state")
    if not isinstance(pull["draft"], bool):
        raise RecordValidationError("github_evidence.pull_request.draftはbooleanである必要があります")
    for key in ("merged_at", "created_at", "updated_at"):
        _require_optional_string(pull, key, "github_evidence.pull_request")
    for key in ("base_revision", "head_revision", "merge_revision"):
        _require_optional_sha(pull, key, "github_evidence.pull_request")
    if pull["head_revision"] != source["immutable_revision"] or source["commit"] != pull["head_revision"]:
        raise RecordValidationError("github_evidenceのhead revisionとsourceが一致しません")

    changed_file = _require_object(evidence, "changed_file")
    changed_file_keys = {
        "status",
        "previous_path",
        "blob_revision",
        "additions",
        "deletions",
        "changes",
    }
    _require_keys(changed_file, changed_file_keys, "github_evidence.changed_file")
    _reject_unknown_keys(changed_file, changed_file_keys, "github_evidence.changed_file")
    _require_string(changed_file, "status")
    _require_optional_string(changed_file, "previous_path", "github_evidence.changed_file")
    blob_revision = _require_string(changed_file, "blob_revision")
    if not re.fullmatch(r"[0-9a-f]{40}", blob_revision):
        raise RecordValidationError("github_evidence.changed_file.blob_revisionが不正です")
    for key in ("additions", "deletions", "changes"):
        _require_nonnegative_int(changed_file, key, "github_evidence.changed_file")
    if record["text"]["content_hash"] != f"git-blob-sha1:{blob_revision}":
        raise RecordValidationError("github_evidenceのblob revisionとcontent hashが一致しません")

    reviews = evidence["reviews"]
    if not isinstance(reviews, list):
        raise RecordValidationError("github_evidence.reviewsはarrayである必要があります")
    review_ids: set[int] = set()
    review_keys = {
        "id",
        "state",
        "submitted_at",
        "commit_revision",
        "author_type",
        "body_present",
    }
    for review in reviews:
        if not isinstance(review, dict):
            raise RecordValidationError("github_evidence.reviews[]はobjectである必要があります")
        _require_keys(review, review_keys, "github_evidence.reviews[]")
        _reject_unknown_keys(review, review_keys, "github_evidence.reviews[]")
        review_id = _require_nonnegative_int(review, "id", "github_evidence.reviews[]")
        if review_id in review_ids:
            raise RecordValidationError("github_evidenceのreview IDが重複しています")
        review_ids.add(review_id)
        _require_string(review, "state")
        _require_optional_string(review, "submitted_at", "github_evidence.reviews[]")
        _require_optional_sha(review, "commit_revision", "github_evidence.reviews[]")
        if review["author_type"] not in {"human", "bot", "unknown"}:
            raise RecordValidationError("github_evidence.reviews[].author_typeが不正です")
        if not isinstance(review["body_present"], bool):
            raise RecordValidationError("github_evidence.reviews[].body_presentが不正です")

    threads = evidence["inline_threads"]
    if not isinstance(threads, list):
        raise RecordValidationError("github_evidence.inline_threadsはarrayである必要があります")
    thread_ids: set[int] = set()
    thread_keys = {
        "id",
        "review_id",
        "path",
        "line",
        "side",
        "original_line",
        "original_revision",
        "latest_revision",
        "created_at",
        "reply_count",
        "human_comment_count",
        "bot_comment_count",
        "body_count",
    }
    for thread in threads:
        if not isinstance(thread, dict):
            raise RecordValidationError("github_evidence.inline_threads[]はobjectである必要があります")
        _require_keys(thread, thread_keys, "github_evidence.inline_threads[]")
        _reject_unknown_keys(thread, thread_keys, "github_evidence.inline_threads[]")
        thread_id = _require_nonnegative_int(thread, "id", "github_evidence.inline_threads[]")
        if thread_id in thread_ids:
            raise RecordValidationError("github_evidenceのthread IDが重複しています")
        thread_ids.add(thread_id)
        for key in ("review_id", "line", "original_line"):
            if thread[key] is not None:
                _require_nonnegative_int(thread, key, "github_evidence.inline_threads[]")
        thread_path = _require_string(thread, "path")
        if thread_path not in {source["file"], changed_file["previous_path"]}:
            raise RecordValidationError(
                "github_evidence inline threadのpathが現在または変更前のfileと一致しません"
            )
        for key in ("side", "created_at"):
            _require_optional_string(thread, key, "github_evidence.inline_threads[]")
        for key in ("original_revision", "latest_revision"):
            _require_optional_sha(thread, key, "github_evidence.inline_threads[]")
        for key in ("reply_count", "human_comment_count", "bot_comment_count", "body_count"):
            _require_nonnegative_int(thread, key, "github_evidence.inline_threads[]")


def _canonical_identity(record: dict) -> dict:
    source = _require_object(record, "source")
    return {
        "schema_version": record.get("schema_version"),
        "sample_type": record.get("sample_type"),
        "source": {
            "type": source.get("type"),
            "repository": source.get("repository"),
            "pr_number": source.get("pr_number"),
            "immutable_revision": source.get("immutable_revision"),
            "file": source.get("file"),
            "span": source.get("span"),
        },
    }


def deterministic_candidate_id(record: dict) -> str:
    """Source identityから安定したcandidate IDを生成する。"""

    payload = json.dumps(
        _canonical_identity(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"rfe-{hashlib.sha256(payload).hexdigest()[:20]}"


def prepare_candidate_record(record: dict) -> dict:
    """入力recordをcanonicalなcandidateへ正規化し、schemaを検証する。"""

    prepared = deepcopy(record)
    prepared["id_material"] = deepcopy(ID_MATERIAL)
    prepared["id"] = deterministic_candidate_id(prepared)
    decision = _require_object(prepared, "decision")
    if decision.get("state") != "candidate":
        raise InvalidTransitionError("新規recordのstateはcandidateである必要があります")
    validate_corpus_record(prepared)
    return prepared


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class LocalCorpusStore:
    """Installed Skillから分離したlocal corpus store。"""

    def __init__(
        self,
        data_dir: Path | str,
        *,
        skill_dir: Path | str | None = None,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self.root = Path(data_dir).expanduser().resolve()
        self.skill_dir = (
            Path(skill_dir).expanduser().resolve()
            if skill_dir is not None
            else Path(__file__).resolve().parents[2]
        )
        if _is_relative_to(self.root, self.skill_dir):
            raise StoreError("local dataをinstalled Skill directory内へ保存できません")
        self.clock = clock

    @property
    def audit_path(self) -> Path:
        return self.root / "audit" / "events.jsonl"

    @property
    def pending_dir(self) -> Path:
        return self.root / "audit" / "pending"

    @contextmanager
    def _store_lock(self):
        self.root.mkdir(parents=True, exist_ok=True)
        lock_path = self.root / ".store.lock"
        if lock_path.is_symlink():
            raise StoreError("store lockをsymlinkにできません")
        with lock_path.open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                if handle.read(1) == b"":
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def _read_lock(self):
        lock_path = self.root / ".store.lock"
        if not lock_path.exists():
            yield
            return
        if lock_path.is_symlink():
            raise StoreError("store lockをsymlinkにできません")
        mode = "r+b" if os.name == "nt" else "rb"
        with lock_path.open(mode) as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def initialize(self) -> None:
        with self._store_lock():
            for directory in (
                *STATE_DIRECTORIES.values(),
                "investigations",
                "proposals",
                "regressions",
                "approvals",
                "cache",
                "audit",
            ):
                self._ensure_directory(self.root / directory)
            self._ensure_directory(self.pending_dir)
            self._recover_pending()

    def _ensure_directory(self, path: Path) -> None:
        if path.is_symlink():
            raise StoreError(f"store内部directoryをsymlinkにできません: {path}")
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir() or not _is_relative_to(path.resolve(), self.root):
            raise StoreError(f"store root外のdirectoryは使用できません: {path}")

    def _assert_safe_layout(self) -> None:
        for directory in (
            *STATE_DIRECTORIES.values(),
            "investigations",
            "proposals",
            "regressions",
            "approvals",
            "cache",
            "audit",
        ):
            path = self.root / directory
            if path.is_symlink():
                raise StoreError(f"store内部directoryをsymlinkにできません: {path}")
            if path.exists() and not _is_relative_to(path.resolve(), self.root):
                raise StoreError(f"store root外へ解決されるdirectoryがあります: {path}")

    def _assert_safe_path(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root)
        except ValueError as exc:
            raise StoreError(f"store root外のpathは使用できません: {path}") from exc
        current = self.root
        for part in relative.parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise StoreError(f"store内部pathにsymlinkがあります: {current}")
        if not _is_relative_to(path.parent.resolve(), self.root):
            raise StoreError(f"store root外へ解決されるpathは使用できません: {path}")

    def _state_path(self, state: str, record_id: str) -> Path:
        if state not in STATE_DIRECTORIES:
            raise StoreError(f"未知のstateです: {state}")
        if not re.fullmatch(r"rfe-[0-9a-f]{20}", record_id):
            raise StoreError("record IDの形式が不正です")
        path = self.root / STATE_DIRECTORIES[state] / f"{record_id}.json"
        self._assert_safe_path(path)
        return path

    def investigation_bundle_path(self, bundle_id: str) -> Path:
        if not re.fullmatch(r"rfb-[0-9a-f]{20}", bundle_id):
            raise StoreError("bundle IDの形式が不正です")
        path = self.root / "investigations" / bundle_id / "bundle.json"
        self._assert_safe_path(path)
        return path

    def investigation_result_path(self, bundle_id: str, result_id: str) -> Path:
        if not re.fullmatch(r"rfb-[0-9a-f]{20}", bundle_id):
            raise StoreError("bundle IDの形式が不正です")
        if not re.fullmatch(r"rfi-[0-9a-f]{20}", result_id):
            raise StoreError("investigation result IDの形式が不正です")
        path = self.root / "investigations" / bundle_id / "results" / f"{result_id}.json"
        self._assert_safe_path(path)
        return path

    def rule_proposal_path(self, proposal_id: str) -> Path:
        if not re.fullmatch(r"rfp-[0-9a-f]{20}", proposal_id):
            raise StoreError("proposal IDの形式が不正です")
        path = self.root / "proposals" / f"{proposal_id}.json"
        self._assert_safe_path(path)
        return path

    def regression_plan_path(self, plan_id: str) -> Path:
        if not re.fullmatch(r"rfrp-[0-9a-f]{20}", plan_id):
            raise StoreError("regression plan IDの形式が不正です")
        path = self.root / "regressions" / "plans" / f"{plan_id}.json"
        self._assert_safe_path(path)
        return path

    def regression_run_path(self, plan_id: str, run_id: str) -> Path:
        if not re.fullmatch(r"rfrp-[0-9a-f]{20}", plan_id):
            raise StoreError("regression plan IDの形式が不正です")
        if not re.fullmatch(r"rfrr-[0-9a-f]{20}", run_id):
            raise StoreError("regression run IDの形式が不正です")
        path = self.root / "regressions" / "runs" / plan_id / f"{run_id}.json"
        self._assert_safe_path(path)
        return path

    def regression_report_path(self, report_id: str) -> Path:
        if not re.fullmatch(r"rfrt-[0-9a-f]{20}", report_id):
            raise StoreError("regression report IDの形式が不正です")
        path = self.root / "regressions" / "reports" / f"{report_id}.json"
        self._assert_safe_path(path)
        return path

    def rule_approval_path(self, approval_id: str) -> Path:
        if not re.fullmatch(r"rfa-[0-9a-f]{20}", approval_id):
            raise StoreError("rule approval IDの形式が不正です")
        path = self.root / "approvals" / f"{approval_id}.json"
        self._assert_safe_path(path)
        return path

    def list_regression_run_paths(self, plan_id: str) -> list[Path]:
        directory = self.regression_run_path(plan_id, "rfrr-" + "0" * 20).parent
        if not directory.exists():
            return []
        self._assert_safe_layout()
        self._assert_safe_path(directory / "placeholder.json")
        return sorted(directory.glob("rfrr-*.json"))

    def read_artifact(self, path: Path) -> dict:
        if not self.root.exists():
            raise StoreError(f"artifactが見つかりません: {path.name}")
        self._assert_safe_layout()
        self._assert_safe_path(path)
        with self._read_lock():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise StoreError(f"artifactが見つかりません: {path}") from exc
            except (OSError, json.JSONDecodeError) as exc:
                raise StoreError(f"artifactを読み込めません: {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise StoreError(f"artifactのtop levelはobjectである必要があります: {path}")
        return data

    def write_artifact(self, path: Path, data: dict) -> None:
        self.initialize()
        self._assert_safe_path(path)
        with self._store_lock():
            if path.exists():
                raise StoreError(f"immutable artifactは上書きできません: {path}")
            self._atomic_write(path, data)

    def _locations(self, record_id: str) -> list[tuple[str, Path]]:
        return [
            (state, path)
            for state in STATE_DIRECTORIES
            if (path := self._state_path(state, record_id)).exists()
        ]

    def _atomic_write(self, path: Path, data: dict) -> None:
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self._atomic_write_text(path, text)

    def _atomic_write_text(self, path: Path, text: str) -> None:
        self._assert_safe_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

    def _audit_events(self) -> list[dict]:
        self._assert_safe_path(self.audit_path)
        if not self.audit_path.exists():
            return []
        events: list[dict] = []
        try:
            for number, line in enumerate(self.audit_path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip():
                    event = json.loads(line)
                    if not isinstance(event, dict) or not isinstance(event.get("event_id"), str):
                        raise StoreError(f"audit event {number}が不正です")
                    events.append(event)
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"audit logを読み込めません: {exc}") from exc
        return events

    def _make_event(
        self,
        *,
        action: str,
        record_id: str,
        actor: str,
        reason: str,
        old_state: str | None,
        new_state: str,
        timestamp: str | None = None,
    ) -> dict:
        return {
            "event_id": str(uuid.uuid4()),
            "timestamp": timestamp or self.clock(),
            "action": action,
            "record_id": record_id,
            "actor": actor,
            "reason": reason,
            "old_state": old_state,
            "new_state": new_state,
            "schema_version": SCHEMA_VERSION,
            "tool_version": TOOL_VERSION,
        }

    def _atomic_append_audit(self, event: dict) -> None:
        events = self._audit_events()
        if any(item["event_id"] == event["event_id"] for item in events):
            return
        lines = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in (*events, event)]
        self._atomic_write_text(self.audit_path, "\n".join(lines) + "\n")

    def _remove_record_locations(self, record_id: str) -> None:
        for _, path in self._locations(record_id):
            path.unlink()

    def _place_record(self, record: dict) -> None:
        record_id = record["id"]
        self._remove_record_locations(record_id)
        self._atomic_write(self._state_path(record["decision"]["state"], record_id), record)

    def _recover_pending(self) -> None:
        committed_ids = {event["event_id"] for event in self._audit_events()}
        for path in sorted(self.pending_dir.glob("*.json")):
            try:
                journal = json.loads(path.read_text(encoding="utf-8"))
                event = journal["event"]
                before = journal["before"]
                after = journal["after"]
                record_id = event["record_id"]
                if event["event_id"] in committed_ids:
                    self._place_record(after)
                else:
                    self._remove_record_locations(record_id)
                    if before is not None:
                        self._place_record(before)
                path.unlink()
            except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
                raise StoreError(f"pending transactionを回復できません: {path}: {exc}") from exc

    def _commit_transaction(self, *, before: dict | None, after: dict, event: dict) -> None:
        pending_path = self.pending_dir / f"{event['event_id']}.json"
        self._atomic_write(pending_path, {"event": event, "before": before, "after": after})
        try:
            self._place_record(after)
            self._atomic_append_audit(event)
            pending_path.unlink()
        except Exception:
            self._recover_pending()
            raise

    def create_candidate(self, record: dict, *, actor: str, reason: str) -> dict:
        return self.create_candidates([record], actor=actor, reason=reason)[0]

    def create_candidates(self, records: list[dict], *, actor: str, reason: str) -> list[dict]:
        """Batch全体のduplicateを先に確認し、candidateを同じlock内で作成する。"""

        if not actor.strip() or not reason.strip():
            raise StoreError("audit用のactorとreasonが必要です")
        if not records:
            raise StoreError("作成するcandidateがありません")
        self.initialize()
        prepared_records = [prepare_candidate_record(record) for record in records]
        record_ids = [record["id"] for record in prepared_records]
        if len(record_ids) != len(set(record_ids)):
            raise DuplicateRecordError("同じbatch内に重複candidateがあります")
        with self._store_lock():
            duplicates = [record_id for record_id in record_ids if self._locations(record_id)]
            if duplicates:
                raise DuplicateRecordError(
                    "同じcandidateがすでに存在します: " + ", ".join(sorted(duplicates))
                )
            for prepared in prepared_records:
                event = self._make_event(
                    action="collect",
                    record_id=prepared["id"],
                    actor=actor,
                    reason=reason,
                    old_state=None,
                    new_state="candidate",
                )
                self._commit_transaction(before=None, after=prepared, event=event)
        return prepared_records

    def _load_record_unlocked(self, record_id: str) -> dict:
        locations = self._locations(record_id)
        if not locations:
            raise StoreError(f"recordが見つかりません: {record_id}")
        if len(locations) > 1:
            raise StoreError(f"複数stateに同じrecordがあります: {record_id}")
        state, path = locations[0]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreError(f"recordを読み込めません: {path}: {exc}") from exc
        try:
            validate_corpus_record(data)
        except RecordValidationError as exc:
            raise StoreError(f"破損したrecordです: {path}: {exc}") from exc
        if data["decision"]["state"] != state:
            raise StoreError(f"directoryとdecision.stateが一致しません: {path}")
        return data

    def _require_reviewer_decision_unlocked(self, record: dict, expected_state: str) -> None:
        record_id = record["id"]
        matching = [event for event in self._audit_events() if event.get("record_id") == record_id]
        if not matching:
            raise RecordValidationError("reviewer decisionを示すaudit eventがありません")
        chain_errors = self._audit_chain_errors(record, matching)
        if chain_errors:
            raise RecordValidationError(chain_errors[0])
        event = matching[-1]
        decision = record["decision"]
        if (
            event.get("new_state") != expected_state
            or event.get("actor") != decision.get("reviewer")
            or event.get("timestamp") != decision.get("decided_at")
            or event.get("reason") != decision.get("reason")
        ):
            raise RecordValidationError("recordとreviewer decision auditが一致しません")

    def _audit_chain_errors(self, record: dict, events: list[dict]) -> list[str]:
        record_id = record["id"]
        errors: list[str] = []
        if not events:
            return [f"{record_id}: audit eventがありません"]
        first = events[0]
        if (
            first.get("old_state") is not None
            or first.get("new_state") != "candidate"
            or first.get("action") != "collect"
        ):
            errors.append(f"{record_id}: audit chainはcollectによるcandidate作成から始める必要があります")
        previous_state = first.get("new_state")
        for index, event in enumerate(events[1:], start=2):
            old_state = event.get("old_state")
            new_state = event.get("new_state")
            if not isinstance(old_state, str) or not isinstance(new_state, str):
                errors.append(f"{record_id}: audit stateが{index}件目で不正です")
                previous_state = new_state
                continue
            if old_state != previous_state:
                errors.append(f"{record_id}: audit state chainが{index}件目で不連続です")
            if old_state not in AUDIT_ALLOWED_TRANSITIONS or new_state not in AUDIT_ALLOWED_TRANSITIONS[old_state]:
                errors.append(f"{record_id}: auditに不正な遷移があります: {old_state} -> {new_state}")
            expected_action = AUDIT_ACTION_BY_TRANSITION.get((old_state, new_state))
            if expected_action is not None and event.get("action") != expected_action:
                errors.append(
                    f"{record_id}: {old_state} -> {new_state}のactionは"
                    f"{expected_action}である必要があります"
                )
            previous_state = new_state
        if previous_state != record["decision"]["state"]:
            errors.append(f"{record_id}: 最終audit stateとrecord stateが一致しません")
        if record["decision"]["state"] != "candidate":
            final = events[-1]
            decision = record["decision"]
            if (
                final.get("actor") != decision.get("reviewer")
                or final.get("timestamp") != decision.get("decided_at")
                or final.get("reason") != decision.get("reason")
            ):
                errors.append(f"{record_id}: decisionと最終audit eventが一致しません")
        return errors

    def load_record(self, record_id: str) -> dict:
        if not self.root.exists():
            raise StoreError(f"recordが見つかりません: {record_id}")
        self._assert_safe_layout()
        if self.pending_dir.exists() and any(self.pending_dir.glob("*.json")):
            raise StoreError("未回復のpending transactionがあります。write操作前にstoreを初期化してください")
        with self._read_lock():
            return self._load_record_unlocked(record_id)

    def list_records(self, states: set[str] | None = None) -> list[dict]:
        """Storeを変更せずrecord summaryを返す。"""

        if not self.root.exists():
            return []
        self._assert_safe_layout()
        selected = set(STATE_DIRECTORIES) if states is None else set(states)
        unknown = selected - STATE_DIRECTORIES.keys()
        if unknown:
            raise StoreError(f"未知のstateです: {', '.join(sorted(unknown))}")
        if self.pending_dir.exists() and any(self.pending_dir.glob("*.json")):
            raise StoreError("未回復のpending transactionがあります")
        records: list[dict] = []
        with self._read_lock():
            for state in sorted(selected):
                directory = self.root / STATE_DIRECTORIES[state]
                if not directory.exists():
                    continue
                for path in sorted(directory.glob("*.json")):
                    record = self._load_record_unlocked(path.stem)
                    records.append(
                        {
                            "id": record["id"],
                            "state": state,
                            "language": record["language"],
                            "genre": record["genre"],
                            "sample_type": record["sample_type"],
                            "quality_class": record["quality_class"],
                            "expected_behavior": record["annotations"]["expected_behavior"],
                            "local_only": record["rights"]["local_only"],
                        }
                    )
        return sorted(records, key=lambda item: item["id"])

    def validate_store(self) -> list[str]:
        """Storeを変更せずrecord、state、auditの整合を検証する。"""

        if not self.root.exists():
            return []
        errors: list[str] = []
        try:
            self._assert_safe_layout()
        except StoreError as exc:
            return [str(exc)]
        pending = sorted(self.pending_dir.glob("*.json")) if self.pending_dir.exists() else []
        if pending:
            errors.append(f"未回復のpending transactionが{len(pending)}件あります")
        records: dict[str, dict] = {}
        with self._read_lock():
            for state, directory_name in STATE_DIRECTORIES.items():
                directory = self.root / directory_name
                if not directory.exists():
                    continue
                for path in sorted(directory.glob("*.json")):
                    try:
                        record = json.loads(path.read_text(encoding="utf-8"))
                        validate_corpus_record(record)
                        if record["decision"]["state"] != state:
                            errors.append(f"{path}: directoryとdecision.stateが一致しません")
                        if record["id"] in records:
                            errors.append(f"{record['id']}: 複数stateに同じrecordがあります")
                        records[record["id"]] = record
                    except (OSError, json.JSONDecodeError, RecordValidationError) as exc:
                        errors.append(f"{path}: {exc}")
            try:
                events = self._audit_events()
            except StoreError as exc:
                errors.append(str(exc))
                events = []
        event_ids: set[str] = set()
        by_record: dict[str, list[dict]] = {}
        for event in events:
            event_id = event["event_id"]
            if event_id in event_ids:
                errors.append(f"audit event IDが重複しています: {event_id}")
            event_ids.add(event_id)
            for key in ("record_id", "actor", "reason", "timestamp", "tool_version"):
                if not isinstance(event.get(key), str) or not event[key].strip():
                    errors.append(f"audit event {event_id}: {key}がありません")
            by_record.setdefault(str(event.get("record_id")), []).append(event)
        for record_id, record in records.items():
            record_events = by_record.get(record_id, [])
            errors.extend(self._audit_chain_errors(record, record_events))
        for record_id in by_record.keys() - records.keys():
            errors.append(f"{record_id}: auditだけが存在しrecordがありません")
        return errors

    def annotate(self, record_id: str, annotations: dict, *, actor: str, reason: str) -> dict:
        """Candidateへ人間のannotationを保存し、annotatedへ遷移する。"""

        if not actor.strip() or not reason.strip():
            raise StoreError("audit用のactorとreasonが必要です")
        self.initialize()
        with self._store_lock():
            before = self._load_record_unlocked(record_id)
            if before["decision"]["state"] != "candidate":
                raise InvalidTransitionError("annotateできるのはcandidateだけです")
            record = deepcopy(before)
            record["annotations"] = deepcopy(annotations)
            record["decision"] = {
                "state": "annotated",
                "reviewer": actor,
                "decided_at": self.clock(),
                "reason": reason,
            }
            validate_corpus_record(record)
            if not record["annotations"]["rationale"].strip():
                raise RecordValidationError("annotation rationaleが必要です")
            event = self._make_event(
                action="annotate",
                record_id=record_id,
                actor=actor,
                reason=reason,
                old_state="candidate",
                new_state="annotated",
                timestamp=record["decision"]["decided_at"],
            )
            self._commit_transaction(before=before, after=record, event=event)
            return record

    def promotion_preview(self, record_id: str) -> dict:
        """Local corpus promotionの計画をread-onlyで返す。"""

        record = self.load_record(record_id)
        if record["decision"]["state"] != "accepted":
            raise InvalidTransitionError("promotionにはaccepted recordが必要です")
        if not record["annotations"]["rationale"].strip():
            raise RecordValidationError("promotionにはannotation rationaleが必要です")
        with self._read_lock():
            self._require_reviewer_decision_unlocked(record, "accepted")
        return {
            "record_id": record_id,
            "target": "local",
            "current_state": "accepted",
            "next_state": "promoted",
            "apply_required": True,
            "will_modify": [str(self._state_path("accepted", record_id)), str(self._state_path("promoted", record_id))],
            "will_not_modify": ["SKILL.md", "references/", "examples/", "evals/"],
            "changes_rule_behavior": False,
        }

    def promote_local(self, record_id: str, *, actor: str, reason: str) -> dict:
        """Gateを再確認し、accepted recordをlocal promoted corpusへ移す。"""

        if not actor.strip() or not reason.strip():
            raise StoreError("audit用のactorとreasonが必要です")
        self.initialize()
        with self._store_lock():
            before = self._load_record_unlocked(record_id)
            if before["decision"]["state"] != "accepted":
                raise InvalidTransitionError("promotionにはaccepted recordが必要です")
            if not before["annotations"]["rationale"].strip():
                raise RecordValidationError("promotionにはannotation rationaleが必要です")
            self._require_reviewer_decision_unlocked(before, "accepted")
            record = deepcopy(before)
            record["decision"] = {
                "state": "promoted",
                "reviewer": actor,
                "decided_at": self.clock(),
                "reason": reason,
            }
            validate_corpus_record(record)
            event = self._make_event(
                action="promote-local",
                record_id=record_id,
                actor=actor,
                reason=reason,
                old_state="accepted",
                new_state="promoted",
                timestamp=record["decision"]["decided_at"],
            )
            self._commit_transaction(before=before, after=record, event=event)
            return record

    def transition(self, record_id: str, target_state: str, *, actor: str, reason: str) -> dict:
        if not actor.strip() or not reason.strip():
            raise StoreError("audit用のactorとreasonが必要です")
        self.initialize()
        with self._store_lock():
            before = self._load_record_unlocked(record_id)
            record = deepcopy(before)
            old_state = record["decision"]["state"]
            if target_state not in ALLOWED_TRANSITIONS[old_state]:
                raise InvalidTransitionError(
                    f"許可されていないstate transitionです: {old_state} -> {target_state}"
                )
            if (
                old_state == "candidate"
                and target_state == "annotated"
                and not record["annotations"]["rationale"].strip()
            ):
                raise RecordValidationError("annotatedへ進むにはannotation rationaleが必要です")
            now = self.clock()
            record["decision"] = {
                "state": target_state,
                "reviewer": actor,
                "decided_at": now,
                "reason": reason,
            }
            validate_corpus_record(record)
            event = self._make_event(
                action=AUDIT_ACTION_BY_TRANSITION[(old_state, target_state)],
                record_id=record_id,
                actor=actor,
                reason=reason,
                old_state=old_state,
                new_state=target_state,
                timestamp=record["decision"]["decided_at"],
            )
            self._commit_transaction(before=before, after=record, event=event)
            return record
