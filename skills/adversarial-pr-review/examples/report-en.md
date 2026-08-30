# A3 review report: tenant authorization boundary

## Scope and parameters

- Target: pull request adding an export endpoint
- Base / head: `main` / pull-request head
- Level / minimum / depth / mode: `A3` / `A1` / `deep` / `gate`
- Selection rationale: the endpoint accepts a tenant identifier from the request even though access must remain
  within the authenticated tenant
- Excluded scope: the identity provider's internal token-validation implementation

## Findings

### F-001: The export query trusts a tenant ID from the request body

- Priority: P1
- Adversarial level: A3
- Confidence: Confirmed
- Location: `src/export/handler.go`, where `body.TenantID` is passed to `LoadExportRows`
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

## Unexecuted validation

No production identity provider or tenant environment was accessed. The local test and repository caller path
already demonstrate the issue, so production access was unnecessary and outside this review's boundary.

## Residual risks

- Other export formats and asynchronous workers were not in the requested scope.
- A4 identity-provider, CI, or privileged-worker compromise was not reviewed.

## Gate decision

`BLOCK` because F-001 is an unresolved P1 cross-tenant disclosure. This is a report-only decision; no GitHub
review, status, label, or merge state was changed.
