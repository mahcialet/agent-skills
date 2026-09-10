---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# Architecture

[Japanese source](architecture.md) / [Index](index.en.md)

## Repository harness

`tools/repoctl` is a repository development entrypoint, never a Skill runtime dependency. It connects existing validators, installer and Skill tests while separating structural validation from test execution. See [ADR 0001](adr/0001-repository-harness.en.md), the [harness contract](testing/harness-contract.en.md) and [ExecPlan](exec-plans/active/EP-HARNESS-001.en.md) for decisions, reachability/contracts and implementation status.

## Skill layout

Each Skill starts at `skills/<skill-name>/SKILL.md`. Runtime instructions, references, examples, scripts and `NOTICE.md` reside together so supported hosts can share them. A copied Skill operates independently of other Skills and parent paths.

The repository root contains shared validation, installation support, catalog, CI, license index and contribution policy. Skill-specific behavior instructions and processing belong inside each Skill.

Repository `SKILL.md` files are the shared editable source. When `install-local.sh` copies a Skill, it leaves the source unchanged and appends only to the installed description a short source Git commit ID, differences from the commit tree, or the reason no commit ID could be determined. Codex and GitHub Copilot share the same `.agents/skills/<name>` in the same scope. `--link` references source directly and therefore does not append a commit ID.

Active Skills reside in `.agents/skills`; replaced backups reside outside discovery in `.agents/backups` so old versions are not shown as separate candidates. Copy backups retain old files; link backups retain the link itself, not a snapshot of its target.

## Shared use across hosts

Codex and GitHub Copilot use the same `SKILL.md`. Optional host metadata such as `agents/openai.yaml` must not be the sole location of behavior instructions. Consider a provider adapter only when a confirmed incompatibility cannot be handled in the common format.

## Progressive disclosure

`SKILL.md` defines triggers and procedure. Split detailed rules into small references with explicit reading conditions, loading only relevant ones. Examples and eval fixtures record behavior but are distinct from material required on every invocation.

## Reader-First Editor development infrastructure (partially implemented)

Normal review currently uses only bundled references and evals. Explicit local-corpus use from normal review is not implemented.

Implemented infrastructure:

- Schema v1, local data-directory resolution, state transitions and audit logs.
- Manual corpus CLI and reference-only collection from public GitHub PRs.
- Adversarial investigation bundles and proposal drafts.
- Provider-neutral regression plans, result ingestion and reports.
- Human approval artifacts and scoped rule application.

Separate distributed Core from user-specific Local data:

```text
Core
├── Common principles and language-specific techniques
├── bundled examples
└── bundled evals

Local
├── candidates
├── accepted / rejected records
├── promoted corpus
├── investigations
├── rule proposals
├── regression plans / runs / reports
└── rule approvals
```

Local data cannot be stored in an installed Skill's source directory. User scope is the default; project scope requires explicit selection. Collection or corpus promotion never automatically changes Core `SKILL.md`, references or evals. Normal review does not implicitly read Local data.

Separate deterministic processing from Agent judgment:

| Actor | Responsibility |
|---|---|
| Bundled tools | Collection, normalization, provenance, state transitions, schema validation, diff/audit records, bundles/regression plans, aggregation, apply gates |
| Agent | Pattern hypotheses, counterexample search, boundary analysis, semantic risk, conservative proposals, provider-side eval execution |
| Human | Rights decisions, annotation, corpus promotion, regression review and final behavior-changing rule approval |

Tools never directly invoke a particular provider's API or CLI. Codex and Copilot share bundle/regression formats. Approval does not modify proposals; a separate artifact fixes the report and exact diff hash. `rules apply` changes only permitted paths and rolls back failed validation. It never commits or pushes automatically. See [corpus workflow](../skills/reader-first-editor/docs/corpus-workflow.md) and [Agent investigation](../skills/reader-first-editor/docs/agent-investigation.md).

## Optional Japanese syntax sensor

The GiNZA adapter is optional, loaded only by explicit invocation, not a Core dependency. Package installation, model downloads and fixture parsing are outside normal review paths. Missing dependencies/models or load/parse failure produce nonfatal availability results, allowing LLM-only processing to continue.

The sensor returns structural observations, backend/model versions and text hashes. It does not decide readability, RR labels, ambiguity or whether rewriting is needed. A/B aggregation also never invokes providers directly: it compares paired observations executed externally with Codex and GitHub Copilot using a common schema. Even observed improvements without automatic blockers require human review and do not enable default use.
