# Review Report

## Metadata

| Field | Value |
|---|---|
| Report ID | `{{REPORT_ID}}` |
| Operation mode | `{{review-only_OR_review-then-remediate}}` |
| Report type | `review` |
| Output destination | `{{console_OR_file}}` |
| Requested output path | `{{null_OR_EXPLICIT_PATH}}` |
| Actual output path | `{{null_OR_EXPLICIT_PATH}}` |
| File output status | `{{not-requested_OR_written_OR_refused}}` |
| File output note | `{{NONE_OR_REASON}}` |
| Target repository | `{{TARGET_REPOSITORY}}` |
| Target base/head/commit | `{{TARGET_REVISIONS}}` |
| Target fingerprint | `{{COMMIT_SHA_OR_BASE_CHANGED_FILES_DIFF_HASH}}` |
| Review timestamp | `{{ISO_8601_TIMESTAMP}}` |
| Reviewer mechanism | `{{SUBAGENT_SESSION_HUMAN_OR_TOOLCHAIN}}` |
| Independence level | `{{independent_OR_degraded}}` |
| Review capability | `{{CAPABILITY_OR_generic}}` |
| Specification status | `{{sufficient_OR_partial_OR_missing}}` |
| Review scope | `{{IN_SCOPE}}` |
| Excluded scope | `{{OUT_OF_SCOPE}}` |
| Validation executed | `{{COMMANDS_OR_NONE}}` |
| Validation not executed | `{{COMMANDS_AND_REASONS_OR_NONE}}` |
| Decision | `{{PASS_OR_FAIL_OR_INCONCLUSIVE}}` |
| Code changes by reviewer | `NONE` |

## Review contract

- 元の要求: {{REQUIREMENT_SOURCE}}
- Acceptance criteria: {{RECONSTRUCTED_CRITERIA}}
- External contract: {{EXTERNAL_CONTRACT_OR_NONE}}
- 反証仮説: {{FALSIFICATION_HYPOTHESES}}

## Findings

findingが0件の場合は `Actionable findings: 0` と明記し、空のfindingを作らない。

### `{{FINDING_ID}}` — `{{TITLE}}`

- Priority / severity: `{{NATIVE_PRIORITY_OR_SEVERITY}}`
- Confidence: `{{NATIVE_CONFIDENCE}}`
- Target: `{{FILE_LINE_OR_SYMBOL}}`
- Trigger / precondition: {{TRIGGER_AND_PRECONDITION}}
- Actual impact: {{ACTUAL_IMPACT}}
- Evidence: {{EVIDENCE}}
- Reproduction / failing test proposal: {{REPRODUCTION_OR_TEST_PROPOSAL}}
- False-positive condition: {{FALSE_POSITIVE_CONDITION}}
- Reviewer assessment: {{ASSESSMENT}}
- Initial remediation recommendation: {{RECOMMENDATION}}
- Authorization status: `not-authorized`

## Hypotheses and unverified risks

{{HYPOTHESES_OR_NONE}}

## Validation

### Executed

{{EXECUTED_VALIDATION_WITH_RESULTS}}

### Not executed

{{UNEXECUTED_VALIDATION_WITH_REASONS}}

## Residual risks

{{RESIDUAL_RISKS}}

## Decision

`{{PASS_OR_FAIL_OR_INCONCLUSIVE}}` — {{BOUNDED_RATIONALE}}

Review phase: COMPLETE

Code changes by reviewer: NONE

Remediation authorization: NOT GRANTED

Next action: stop
