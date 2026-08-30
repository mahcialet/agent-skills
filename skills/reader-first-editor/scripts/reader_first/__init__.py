"""reader-first-editorのローカルcorpus支援機能。"""

from .github import (
    GitHubCollectionError,
    GitHubRestClient,
    build_reference_only_candidates,
    fetch_pull_request_snapshot,
    load_recorded_snapshot,
)
from .investigation import (
    InvestigationError,
    build_investigation_bundle,
    build_rule_proposal,
    validate_bundle_against_store,
    validate_investigation_result,
)
from .state import (
    DuplicateRecordError,
    InvalidTransitionError,
    LocalCorpusStore,
    RecordValidationError,
    StoreError,
    deterministic_candidate_id,
    prepare_candidate_record,
    resolve_data_dir,
    validate_corpus_record,
)

__all__ = [
    "DuplicateRecordError",
    "GitHubCollectionError",
    "GitHubRestClient",
    "InvalidTransitionError",
    "InvestigationError",
    "LocalCorpusStore",
    "RecordValidationError",
    "StoreError",
    "build_investigation_bundle",
    "build_reference_only_candidates",
    "build_rule_proposal",
    "deterministic_candidate_id",
    "fetch_pull_request_snapshot",
    "load_recorded_snapshot",
    "prepare_candidate_record",
    "resolve_data_dir",
    "validate_bundle_against_store",
    "validate_corpus_record",
    "validate_investigation_result",
]
