---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# Repository harness contract

Translation of the [Japanese source](harness-contract.md). This contract was established in M1 of EP-HARNESS-001; see the [active ExecPlan](../exec-plans/active/EP-HARNESS-001.en.md) for verification status.

## Existing validation reachability (base d423d1f)

| Asset / input | Output, effects, dependencies | Discovery / route | Base CI |
|---|---|---|---|
| `scripts/validate_skills.py`, all `SKILL.md`, catalog | Structural diagnostics; Python/PyYAML; invokes content, Skill tests and catalog below | Root Python validator → each Skill validator and `unittest discover -s skills/<name>/tests` | Through shell wrapper |
| RFE `scripts/validate_content.py`, Skill docs/evals | Content, fixture and reference checks; Python/PyYAML; five bundled tool `--version` probes, no model | Root → content validator, no nested unittest | Yes |
| adversarial-pr-review `scripts/validate_content.py`, docs/evals | Content, fixture and reference checks; Python/PyYAML, no external writes | Root → content validator | Yes |
| ticket-state `scripts/validate_content.py`, docs/schemas/evals | Content, fixture and schema checks; Python/PyYAML/jsonschema, no live API | Root → content validator | Yes |
| `skills/reader-first-editor/tests/test_*.py` (9 files) | unittest results; temporary assets/local tools, Python development dependencies | Per-Skill discovery from root validator | Yes |
| `skills/adversarial-pr-review/tests/test_*.py` (1 file) | unittest results; temporary assets, Python development dependencies | Same | Yes |
| `skills/ticket-state/tests/test_*.py` (10 files) | unittest results; temporary assets/mock transports, no live API writes | Same | Yes |
| `tests/test_install_local.py` (1 file) | 33 installer tests; temporary Git repositories/destinations, Python/Git/Bash | Shell wrapper → root unittest discovery; not reached by Python validator alone | Yes |
| `scripts/generate-catalog.py --check`, catalog/metadata | README managed-section drift diagnostics; Python/PyYAML; no writes with `--check` | Root validator → generator | Yes |
| `scripts/validate-skills.sh` | Python validator and root unittest results; Bash | Developer/CI compatibility entrypoint | Yes |
| `ruff check .`, all Python | Lint diagnostics, development Ruff dependency | Separate CI step | Yes |
| `gh skill validate`, metadata | Host-format validation when GitHub CLI and capability are available | Conditional CI step | Optional / conditional |
| RFE eval 8 files, adversarial eval 6 files, ticket eval 4 files | Static YAML case validation, not successful model evaluation | Content validators | Static only |
| RFE regression plan/ingest/report | Provider-neutral JSON, result validation and aggregation; explicit output writes; models run externally | Explicit bundled tool invocation | Dynamic evaluation unconnected / optional |
| `scripts/install-local.sh` and `scripts/install_local.py` | Skill placement, selected symlink/copy, Git environment removal and root/HEAD validation; Python/Git/Bash | Explicit user invocation, installer tests above | Isolated tests, not real deployment |

`catalog.json` is an input, not a generated artifact. README managed sections are generated. Base CI uses Ubuntu/Python 3.12. Repository development dependencies are not Skill runtime dependencies.

## Canonical entrypoints and separation

- `python -m tools.repoctl check`: static structure, all content validators, catalog, documents, Plans, lint; no unittest. Deterministic bundled version probes are permitted.
- `python -m tools.repoctl test`: discovers root, each Skill and repoctl unittest suites exactly once each.
- `python -m tools.repoctl verify`: aggregates check/test. M6 smoke is `NOT_REQUESTED` in this scope, never silently successful.
- `python -m tools.repoctl doctor`: read-only Python/Git/development dependency inspection; no installation, login, billing or live hosts.
- The Python installer becomes canonical; shell remains a compatibility wrapper. Preserve root/HEAD checks, removal of Git-related environment, destination restrictions and overwrite semantics.

Python 3.12 is the initial native baseline. Configuring Linux/macOS/Windows CI is not native verification without execution evidence. Local Linux/Python 3.13.5 results are recorded separately. Reuse PyYAML instead of adding a parser dependency.

## Execution and evidence

Use `sys.executable` for Python children and validated executables with argv arrays otherwise. No shell in canonical paths. Specify cwd, allowed environment, timeout, exit code, stdout/stderr, join and cleanup. Cancellation requests are not completion evidence.

Diagnostics include stable `ASKILLS-*` code, task ID, target, reason and repair direction. Negative fixtures assert the intended code and stage. Place broken fixtures in temporary repositories; do not weaken actual Skill discovery.

Evidence defaults to console. Persist versioned run records only with explicit `--out <new-directory>`. Never overwrite old output; record target, result and cleanup, redacting secrets. Processing success and subject acceptance are separate fields. Distinguish repeated success, causal regression and real-use evidence.

## Authorized boundary

Only M1–M4 are authorized. M5 eval adapters, M6 standalone smoke/live hosts, M7 human validation, live models, live API writes and merge remain unstarted. No Skill behavior changes. M3's original smoke wording does not authorize M6; complete AC09 remains pending.

The existing installer transaction depends on `fcntl`, `dir_fd`, `flock` and `pthread_sigmask`. Moving its public entrypoint to Python must not weaken safety: native Windows installation reports `ASKILLS-INSTALL-PLATFORM`, exit 3 (BLOCKED). This is not successful portable copy-mode acceptance; AC05/AC09 remain open.

Document checks cover root/docs/skills Markdown, excluding tests, `.venv`, `.agents`, `.codex` and `.tokensave`. The supplied root intake `execplan_agent_skills_repository_harness.md` is excluded to preserve the original. Link validation covers Markdown inline links and ATX/HTML anchors, not arbitrary HTML or dynamically generated links.
