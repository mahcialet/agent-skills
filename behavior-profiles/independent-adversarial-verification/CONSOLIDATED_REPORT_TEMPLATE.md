# Consolidated Review and Remediation Report

## Metadata

| Field | Value |
|---|---|
| Report ID | `{{REPORT_ID}}` |
| Operation mode | `review-and-remediate` |
| Report type | `consolidated` |
| Output destination | `{{console_OR_file}}` |
| Requested output path | `{{null_OR_EXPLICIT_PATH}}` |
| Actual output path | `{{null_OR_EXPLICIT_PATH}}` |
| Target repository | `{{TARGET_REPOSITORY}}` |
| Target fingerprint before review | `{{INITIAL_FINGERPRINT}}` |
| Target fingerprint after remediation | `{{FINAL_FINGERPRINT}}` |
| Review timestamp | `{{ISO_8601_TIMESTAMP}}` |
| Reviewer mechanism | `{{REVIEWER_MECHANISM}}` |
| Independence level | `{{independent_OR_degraded}}` |
| Review capability | `{{CAPABILITY_OR_generic}}` |
| Review scope | `{{IN_SCOPE}}` |
| Excluded scope | `{{OUT_OF_SCOPE}}` |
| Remediation authorization source | `GRANTED BY INVOCATION MODE: {{EXPLICIT_REQUEST}}` |
| Code changes by reviewer | `NONE` |
| Final decision | `{{PASS_OR_FAIL_OR_INCONCLUSIVE}}` |

## Review phase

- Reconstructed acceptance criteria: {{CRITERIA}}
- Falsification hypotheses: {{HYPOTHESES}}
- Validation executed: {{VALIDATION_OR_NONE}}
- Validation not executed: {{UNEXECUTED_AND_REASONS_OR_NONE}}

Review phase: COMPLETE

Code changes by reviewer: NONE

Remediation authorization: GRANTED BY INVOCATION MODE

Next action: hand findings to implementer for adjudication

## Finding traceability summary

| Finding ID | Review finding | Disposition | Action required | Action taken | Verification | Final status |
|---|---|---|---|---|---|---|
| `{{FINDING_ID}}` | {{FINDING_SUMMARY}} | `{{confirmed_OR_rejected_OR_inconclusive}}` | `{{yes_OR_no_OR_undetermined}}` | {{ACTION_OR_NONE}} | {{VERIFICATION}} | `{{fixed_OR_not-fixed_OR_not-authorized_OR_not-required_OR_deferred}}` |

findingが0件の場合は `Actionable findings: 0` とし、summary tableへ架空のfindingを作らない。

## Finding details and adjudication

### `{{FINDING_ID}}` — `{{TITLE}}`

- Priority / severity: `{{NATIVE_PRIORITY_OR_SEVERITY}}`
- Confidence: `{{NATIVE_CONFIDENCE}}`
- Target: `{{FILE_LINE_OR_SYMBOL}}`
- Trigger / precondition: {{TRIGGER_AND_PRECONDITION}}
- Actual impact: {{ACTUAL_IMPACT}}
- Evidence: {{REVIEW_EVIDENCE}}
- False-positive condition: {{FALSE_POSITIVE_CONDITION}}
- Authorization status: `authorized-by-invocation-mode`
- Disposition: `{{confirmed_OR_rejected_OR_inconclusive}}`
- Adjudication evidence: {{IMPLEMENTER_EVIDENCE}}
- `action_required`: `{{yes_OR_no_OR_undetermined}}`
- `action_status`: `{{fixed_OR_not-fixed_OR_not-authorized_OR_not-required_OR_deferred}}`
- Action summary / non-action reason: {{ACTION_OR_REASON}}
- Verification: {{VERIFICATION}}

すべてのreview findingについてこのsectionを繰り返し、rejected / inconclusive / not-requiredも
欠落させない。

## Implementer changes

- Files changed: {{FILES_AND_PURPOSE_OR_NONE}}
- Adjacent cleanup performed: `NO`
- Deferred scope expansion: {{DEFERRED_ITEMS_OR_NONE}}

## Regression tests and verification

- Regression tests: {{TESTS_OR_NONE_AND_REASON}}
- Verification: {{COMMAND_ENVIRONMENT_RESULT}}
- Verification not executed: {{UNEXECUTED_AND_REASON_OR_NONE}}

## Read-only re-review

| Field | Value |
|---|---|
| Re-review report ID / result | `{{REREVIEW_ID_OR_RESULT}}` |
| Re-reviewer mechanism | `{{REREVIEWER_MECHANISM}}` |
| Independence level | `{{independent_OR_degraded}}` |
| Code changes by re-reviewer | `NONE` |
| Original finding status | `{{RESOLVED_OR_RESIDUAL}}` |
| New findings | `{{NEW_FINDING_IDS_OR_NONE}}` |
| New findings automatically remediated | `NO` |

新規findingの詳細とevidence: {{NEW_FINDING_DETAILS_OR_NONE}}

## Residual risks

{{RESIDUAL_RISKS}}

## Final decision

`{{PASS_OR_FAIL_OR_INCONCLUSIVE}}` — {{BOUNDED_RATIONALE}}

Code changes by reviewer: NONE

One authorization remediation cycles completed: `1`

Next action: {{STOP_OR_EXPLICIT_NEW_AUTHORIZATION_REQUIRED}}
