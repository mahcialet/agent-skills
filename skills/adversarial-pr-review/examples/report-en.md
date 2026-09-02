# A3 review report: tenant authorization boundary

## Scope and parameters

- Target: pull request adding an export endpoint
- Repository label: `export-service`
- Base / head: `main` / pull-request head
- Level / minimum / depth / mode: `A3` / `A1` / `deep` / `gate`
- Selection rationale: the endpoint accepts a tenant identifier from the request even though access must remain
  within the authenticated tenant
- Excluded scope: the identity provider's internal token-validation implementation
- Identifier scope: new report

## Review contract

- Specification status: sufficient
- Purpose / actors: authenticated tenant users export only data authorized for their verified tenant context
- Criteria sources:
  - Repository contract: `docs/permission-matrix.md` and the existing download handler
  - PR-declared criterion: the export endpoint follows the existing tenant authorization boundary
- Expected outcomes: the export query derives tenant scope from verified authorization context
- Forbidden outcomes: a tenant user retrieves another tenant's export rows by supplying a body parameter
- Declared scope / non-scope: export HTTP endpoint / identity-provider token internals
- Declared impact: export API and export response
- Unresolved decisions: none for the repository-local authorization path
- Stop / recovery / handoff: disable the endpoint if cross-tenant access is observed; no verified runbook owner was found
- Final decision owner: unresolved

## Requirement traceability

| Source reference | Kind | Requirement / forbidden outcome | Implementation path | Test / evidence | Status |
|---|---|---|---|---|---|
| `docs/permission-matrix.md` / export permission | repository contract | export data remains within the authorized tenant | middleware → handler → query | E-01〜E-05 and focused local test | Violated |
| PR description / authorization compatibility | PR-declared criterion | new export matches the existing download boundary | export handler compared with download handler | symmetric handler rejects mismatch | Violated |

## Impact comparison

- Declared impact: export API and response serialization
- Discovered impact: shared export query and its tenant predicate
- Undeclared impact requiring follow-up: asynchronous export formats outside the reviewed path

## Coverage gap audit

- Inspection separation: an independent read-only reviewer performed the blind pass.
- Initial findings were not used as the completion criterion: the pass started from the changed tenant-scope contract.

### Change-obligation coverage

| Changed concept | Route inspected | Status | Evidence | Linked finding / hypothesis |
|---|---|---|---|---|
| tenant scope | request producer → body parser → middleware context → query consumer → response side effect | Inspected | E-01〜E-05 | F-001 |
| asynchronous export formats | alternate producer and worker consumer | Unverified | route is outside the retrieved source set | Residual risk |

### Relational-invariant coverage

| Field / state group | Relationship checked | Status | Evidence |
|---|---|---|---|
| body tenant ID and verified context tenant ID | paired presence, equality requirement, mode compatibility | Inspected | E-01〜E-04 |

### Repository-rule obligations

| Base instruction | Triggering change | Required companion | Status | Evidence |
|---|---|---|---|---|
| repository test policy | authorization behavior change | focused cross-tenant test | Inspected | E-05 |

### Blind-spot result

The blind pass confirmed F-001 through a route not limited to the changed handler. It did not create an additional
finding for the unavailable asynchronous route; that route remains an explicit residual risk.

## Findings

### F-001: The export query trusts a tenant ID from the request body

- Priority: P1
- Adversarial level: A3
- Confidence: Confirmed
- Location: `export-service/src/export/handler.go:64`
- Contract / invariant reference: `docs/permission-matrix.md` / export permission and
  `Repository contract: data access is scoped to ctx.TenantID`
- Actor / trigger: an authenticated user submits another tenant's identifier in the JSON body
- Precondition: the user has export permission for their own tenant but can discover or guess another tenant ID
- Code path: HTTP handler → body parser → `LoadExportRows(body.TenantID)` → unscoped export response
- Broken invariant: data access must be scoped to the tenant in the verified authorization context
- Impact: a user can retrieve another tenant's export data
- Evidence: middleware stores the authorized tenant in `ctx.TenantID`; the changed handler never reads it;
  the repository's existing download handler rejects a mismatch; the query filters only on its argument
- Reproduction or verification: the local handler test passes tenant B in the body while authenticating as tenant A
  and receives tenant B's fixture row
- Fix direction: derive tenant scope from the verified context, or compare the body value before any query
- False-positive condition: an upstream component, not present in the reviewed path, cryptographically binds and
  rewrites the body tenant to the authorized context before this handler runs

Priority P1 describes the impact and merge urgency. A3 describes the attacker's ability to cross a tenant boundary;
it does not make the priority automatically P1.

## Hypotheses

None. The local test and caller path in the repository show that the handler returns data for the tenant named in
the request body. This finding does not depend on the unavailable identity-provider implementation.

## Evidence ledger

| ID | Source | Checked | Result / limitation |
|---|---|---|---|
| E-01 | changed file | source of tenant scope | request body is trusted |
| E-02 | middleware | authorized tenant context | `ctx.TenantID` is available but unused |
| E-03 | symmetric handler | download authorization | mismatch is explicitly rejected there |
| E-04 | query | tenant predicate | filters solely on the caller argument |
| E-05 | local test | cross-tenant body value | returned tenant B's fixture row |

## Test evidence

| Test / check | Provenance | Source / command | Result | Limitation |
|---|---|---|---|---|
| CI unit checks | observed | check run for `<HEAD_SHA>` | success | integration and production identity provider are outside the check |
| focused tenant-scope test | executed | `go test ./src/export -run TestTenantScope`; Go 1.24 with local fixture DB | reproduced cross-tenant row return | local handler and fixture DB only |

## Unexecuted validation

No production identity provider or tenant environment was accessed. The local test and repository caller path
already demonstrate the issue, so production access was unnecessary and outside this review's boundary.

## Residual risks

- Other export formats and asynchronous workers were not in the requested scope.
- A4 identity-provider, CI, or privileged-worker compromise was not reviewed.

## Gate decision

- Gate recommendation: BLOCK
- Approval status: NOT GRANTED
- Human approval required: yes
- Decision owner: unresolved
- Rationale: F-001 is an unresolved P1 cross-tenant disclosure.

This is a report-only recommendation. No GitHub review, status, label, approval, or merge state was changed.
