---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# Quality and validation

[Japanese source](QUALITY.md) / [Contract](testing/harness-contract.en.md) / [Index](index.en.md)

The normal canonical entrypoint is `python -m tools.repoctl verify`. Explicitly prepare the project venv using `requirements-dev.txt`; verify never installs dependencies. `check` performs static checks, `test` discovers/runs suites, and `test --list` shows selection. Keep shell compatibility entrypoints.

Normal verification never reaches external LLMs, Backlog/Redmine, live host CLIs or real-user installation destinations. In M1–M4, standalone installer smoke and live-host evaluation are `NOT_REQUESTED`. Installer unit/integration tests are not live-host discovery evidence.

| Evidence class | Establishes | Does not establish |
|---|---|---|
| Forced invariant | A fixture catches the intended violation at the expected stage/code | All OSes/interleavings |
| Direct native / integration | Execution on the recorded revision/OS/version | Other OSes/hosts/production |
| Structural / tooling | Schema, structure, lint, drift | Meaning preservation, prose quality, host discovery |
| Model observation | Output from specified attempts | All future outputs, human approval |
| Human observation | Observation/judgment for specified cases | Merge approval, unexamined cases |
| Repetition / stability | Stability over specified repetitions | Causal reproduction or stronger evidence |

New validators need broken-fixture negative controls asserting stable `ASKILLS-*` codes and failure stages, not exit codes alone. Static runtime closure cannot prove arbitrary Python/dynamic imports; distinguish its limits from isolated copy fixtures and real-use validation.

Checks are read-only; only `generate` updates generated sections. Translation source hashes detect staleness, not semantic equality. Never update hashes without reading the translation.

Evidence defaults to console; only explicit `--out <new-directory>` persists it. Never overwrite failures; use secret sentinels to test redaction. Timeout/cancel completion requires owned child termination and cleanup confirmation. Record missing output or unfinished resources as limitations.

The required native matrix is Linux/macOS/Windows × Python 3.12. A workflow file alone is not verified execution. Local runs using other Python versions are separate evidence. The active ExecPlan records actual AC results and unexecuted scope.

Review in a separate implementation context; record findings as adopted/rejected/deferred with reasons. Revalidate affected scope after changes. Passing checks are distinct from human approval.
