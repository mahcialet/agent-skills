# Remediation Report

## Metadata

| Field | Value |
|---|---|
| Remediation report ID | `{{REMEDIATION_REPORT_ID}}` |
| Operation mode | `review-then-remediate` |
| Report type | `remediation` |
| Source review report ID | `{{SOURCE_REPORT_ID}}` |
| Source review report path | `{{null_OR_EXPLICIT_PATH}}` |
| Source target fingerprint | `{{SOURCE_FINGERPRINT}}` |
| Current target fingerprint | `{{CURRENT_FINGERPRINT}}` |
| Stale status | `{{current_OR_stale}}` |
| Authorization source | `{{EXPLICIT_USER_INSTRUCTION}}` |
| Authorized finding scope | `{{FINDING_IDS_OR_all-findings}}` |
| Additional scope | `{{SCOPE_OR_NONE}}` |
| No-touch boundary | `{{BOUNDARY_OR_NONE}}` |
| Implementer | `{{IMPLEMENTER_MECHANISM}}` |
| Output destination | `{{console_OR_file}}` |
| Output path | `{{null_OR_EXPLICIT_PATH}}` |
| Final decision | `{{PASS_OR_FAIL_OR_INCONCLUSIVE}}` |

reportが `stale` の場合はfindingを修正せず、再reviewまたは新しい明示指示が必要な状態で停止する。

## Authorized findings

{{AUTHORIZED_FINDING_IDS_AND_EXCLUDED_FINDINGS}}

## Finding adjudication and actions

### `{{FINDING_ID}}` — `{{TITLE}}`

- Authorization status: `{{authorized_OR_not-authorized}}`
- Adjudication: `{{confirmed_OR_rejected_OR_inconclusive}}`
- Adjudication evidence: {{INDEPENDENT_REPRODUCTION_OR_REFUTATION}}
- `action_required`: `{{yes_OR_no_OR_undetermined}}`
- `action_status`: `{{fixed_OR_not-fixed_OR_not-authorized_OR_not-required_OR_deferred}}`
- Action summary: {{ACTION_OR_NON_ACTION_REASON}}
- Files changed: {{FILES_OR_NONE}}
- Regression test: {{TEST_OR_NONE_AND_REASON}}
- Verification: {{VERIFICATION_OR_NOT_EXECUTED_REASON}}

すべてのauthorized findingについてこのsectionを繰り返す。unauthorized findingは変更せず、
`action_status=not-authorized` とする。

## Files changed by implementer

{{FILES_AND_PURPOSE_OR_NONE}}

## Regression tests

{{REGRESSION_TESTS_OR_NONE_AND_REASON}}

## Verification

{{COMMAND_ENVIRONMENT_RESULT_AND_LIMITATIONS}}

## Read-only re-review

- Re-review report ID / result: `{{REREVIEW_ID_OR_RESULT}}`
- Reviewer mechanism: `{{REREVIEWER_MECHANISM}}`
- Independence level: `{{independent_OR_degraded}}`
- Code changes by re-reviewer: `NONE`
- Original findings resolved: {{RESOLUTION_STATUS}}
- Residual findings: {{RESIDUAL_FINDINGS_OR_NONE}}
- New findings: {{NEW_FINDINGS_OR_NONE}}
- New findings automatically remediated: `NO`

## Residual risks and next action

{{RESIDUAL_RISKS}}

次の明示指示が必要: `{{yes_OR_no}}`

## Final decision

`{{PASS_OR_FAIL_OR_INCONCLUSIVE}}` — {{BOUNDED_RATIONALE}}

Code changes by reviewer: NONE
