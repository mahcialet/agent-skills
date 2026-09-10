---
status: active
owner: maintainers
last_verified: 2026-09-11
plan_id: EP-HARNESS-001
plan_type: implementation
base_branch: master
branch: feat/ep-harness-001
priority: 20
workstreams:
  - repository-harness
  - developer-documentation
conflicts:
  - installer-contract
  - validation-entrypoints
  - eval-contract
  - repository-documentation-policy
depends_on: []
merge_policy: manual
promotion_criteria:
  - The maintainer explicitly authorizes implementation of this plan.
  - The implementer rechecks repository instructions, current base, plan ID availability, and working-tree ownership.
  - The initial execution scope and the requirement to finish M1 before behavior-changing edits are recorded.
---

# Introduce a repository-native harness to agent-skills

**Target:** `mahcialet/agent-skills`

**Reference:** the repository-native harness in `mahcialet/agent-env`

**Artifact status:** M1–M4 implementation is authorized. Base and work area were rechecked; work is on a dedicated branch. M5 onward, live model/host execution and merge are not authorized by this request.

This is a self-contained ExecPlan for Codex. It provides purpose, scope, validation and remaining work without rereading conversation history. ChatGPT does not write to the repository; instructed Codex creates the branch and places this Plan in the repository.

`last_verified` originally records the date reference information was checked, not harness execution verification. Unless explicitly identified as implemented, `python -m tools.repoctl ...` below describes a planned interface, not an existing command. This is the translation of [the Japanese Plan](EP-HARNESS-001.md).

## Purpose / Big Picture

Make agent-skills understandable, changeable, verifiable and transferable to a new Agent session without conversation history. Connect concise root instructions, design navigation, canonical validation, a living ExecPlan, execution evidence and decisions reserved for humans. This is more than a test runner but not a wholesale port of agent-env's Go implementation, product runtime or complete Plan orchestration.

The intended basic workflow is:

```text
Use AGENTS.md to identify the Skill and change location
  → Check scope and acceptance conditions in the ExecPlan
  → Make changes
  → Run deterministic repoctl verify
  → Evaluate Skills/live hosts only when needed and authorized
  → Record results, evidence, limits and human decisions
```

### Deliverables

1. Portable Python repoctl with tasks reaching every existing check.
2. Skill, catalog, documentation and Plan validation plus negative tests.
3. Provider-neutral contracts connecting existing Skill evaluation, isolated installer smoke and explicit live-host verification.
4. Human checklists, evidence interpretation and a separate human-validation ExecPlan.

### Non-goals

- Improving Skill editing/review/ticket rules or automatically promoting corpus observations.
- New model/billing infrastructure, persistent Agent schedulers or automatic merge systems.
- Adding agent-env product dependencies, rewriting in Go or extracting a shared harness repository.
- Production Backlog/Redmine writes, real-user Skill deployment or authentication changes.
- Mass translation of existing documents or separate Skill instructions per host/language.
- Wholesale installer/test refactoring merely because files are large.

## Progress

Check only observed completion. At each milestone record revision, commands, results and unverified scope.

- [x] 2026-09-11: Read references and existing validation routes to prepare the initial Plan; this was not implementation verification.
- [x] 2026-09-11: Explicitly authorized M1–M4 only; `origin/master` = `d423d1f483e48cfa955b02114c17611c6f2993cd`; work area `/home/mahcialet/work/git_work/marmite/agent-skills`. Initially only the supplied untracked Plan existed. Created `feat/ep-harness-001`; preserve the supplied original and create an active translation pair.
- [x] 2026-09-11 M1: Recorded all routes in `docs/testing/harness-contract.md` and D1–D10 in ADR 0001. Linux/Python 3.13.5 baseline: Ruff, root validator (3 Skills), catalog and 33 root installer tests PASS. No existing failures.
- [ ] M2: Portable runner, evidence foundation and canonical Python installer entrypoint.
- [ ] M3: Separate check/test/verify and connect native CI.
- [x] 2026-09-11 M4: Implemented Skill/artifact/document/Plan checks and locally verified on Linux/Python 3.13.5. Retain M2/M3 native constraints and acceptance limits in the ledger below; this is not entire-Plan completion.
- [ ] M5: Skill eval planning, result ingestion and aggregation.
- [ ] M6: Isolated installer smoke and explicit live-host verification.
- [ ] M7: Human-validation handoff and complete acceptance.
- [ ] Resolve independent review findings with adopted/rejected/deferred rationale.
- [ ] Confirm actual merge evidence and archive both translations.

## Surprises & Discoveries

The following initial observations came from code/doc reading, not test execution. Sources are in Artifacts and Notes.

| ID | Observation | Consequence |
|---|---|---|
| F1 | validate_skills.py runs structure, content validators, Skill unittest and README catalog checks. [S2] | Split responsibilities instead of invoking it from both check and test. |
| F2 | Root installer tests are directly started by validate-skills.sh, also used in CI; Python validator alone does not run root tests. [S2–S4] | CI is connected; preserve coverage when consolidating distributed entrypoints. |
| F3 | catalog.json is metadata input; generate-catalog.py generates README catalog sections. [S5] | Separately validate input-set equality and generated README drift. |
| F4 | Installer wrapper removes Git environment variables and validates root/HEAD. [S6] | Direct low-level helper invocation cannot replace these defenses. |
| F5 | RFE has provider-neutral regression plan/ingest/report and tools do not start providers. [S7–S8] | Connect existing processing through adapters, not replacement infrastructure. |
| F6 | Current AGENTS uses Japanese; agent-env uses English sources/Japanese translations. [S1,S10] | Preserve Japanese paths and pair new durable docs with English rather than mechanically copying naming policy. |
| F7 | Reference agent-env base includes fixture-completion and evidence-class improvements. [S10–S11] | Distinguish cancel from join and repetition from causal regression evidence. |

The initial F2 hypothesis that root tests were unconnected was withdrawn after reading the shell wrapper. A standalone validator is not the entire CI system. Record new hypotheses, reproduction conditions, effects and disposition during implementation; distinguish pre-existing fixes from the harness port.

## Decision Log

Changing these decisions requires date, reason, alternatives and affected criteria. Agents must not invent human approvers.

| ID | Decision | Reason / reconsideration |
|---|---|---|
| D1 | Python, canonical `python -m tools.repoctl` | Reuse Python; no mandatory Go. |
| D2 | Normal verify never starts external LLMs, production APIs or live host CLIs | Keep auth, billing and model variance outside normal CI. |
| D3 | Reuse existing validators/installers/bundled tools while preserving responsibilities | Avoid simultaneous Skill behavior changes. |
| D4 | Common eval plan/ingest/report, external model execution | Preserve RFE design; direct provider runner needs another decision. |
| D5 | Installer smoke differs from host discovery/loading | Correct placement does not prove client use. |
| D6 | Introduce versioned evidence in M2, not M7 | Capture failures, targets and cleanup from the outset. |
| D7 | Start Plan support with state/required-field/reference/evidence validation; manual merge | Avoid transplanting the full scheduler/GitHub gate. |
| D8 | Separate human-validation Plan for real environments and human decisions | Implementation completion is not verified real use. |
| D9 | Keep Japanese `.md`; pair new/substantially updated durable docs with `.en.md` | Preserve navigation; record in M1 ADR. |
| D10 | Do not use success counts as primary bug-fix evidence | Demonstrate that a violating fixture actually fails. |

D9 covers explanatory documents and ExecPlans, not blanket translation of SKILL.md, identifiers, licenses or quotations. Root AGENTS contains shared host rules and English navigation, not separate behavior definitions.

## Outcomes & Retrospective

M1 inventory and baseline are complete; M2–M4 are in progress. Update the following after validation and review:

- Implemented scope and natively executed OS/Python versions:
- Checks added to normal CI and duplicate execution removed:
- Live-host observations and unverified host scope:
- Skill quality evaluated and not evaluated:
- Remaining human decisions with Plan/case IDs:
- Independent review, declined findings and rationale:
- Remaining limits and triggers for reconsidering shared infrastructure:
- Delivery merge commit and archive changes:

## Context and Orientation

### Reference snapshots

| Repository | Branch | Examined commit |
|---|---|---|
| mahcialet/agent-skills | master | d423d1f483e48cfa955b02114c17611c6f2993cd |
| mahcialet/agent-env | master | 4e5fec663f493e4546c4d5e93e64dccfe909981f |

These are 2026-09-11 planning snapshots. Recheck origin/master and actual files at implementation start. Never roll a newer base back to the snapshot; record differences and impact.

### Current responsibilities

- `skills/<name>/SKILL.md`: shared host behavior; runtime references/tools stay within each Skill. [S1,S7]
- `scripts/`: common validation, README catalog generation and installer/support.
- `tests/`: root installer tests; Skill tests also live in each Skill.
- `docs/architecture.md`: existing architecture entrypoint; do not create a duplicate root ARCHITECTURE.md.
- `.github/workflows/validate-skills.yml`: Ubuntu/Python 3.12 lint/validation at the examined base. [S3]
- `requirements-dev.txt`: development dependencies, not mandatory Skill runtime dependencies. [S9]

The catalog contains reader-first-editor, adversarial-pr-review and ticket-state. Catalog host-support labels are not successful live-host verification in this work. [S5]

### Intended layout

Finalize paths in M1 without duplication:

```text
AGENTS.md / AGENTS.en.md
docs/
  index.md / index.en.md
  architecture.md / architecture.en.md
  QUALITY.md / QUALITY.en.md
  PLANS.md / PLANS.en.md
  adr/
  testing/
    harness-contract.md / harness-contract.en.md
    eval-contract.md / eval-contract.en.md
    host-verification.md / host-verification.en.md
  exec-plans/draft/ active/ paused/ completed/ abandoned/
tools/repoctl/
  __main__.py   # argparse / dispatch
  runner.py    # argv / timeout / join / diagnostics
  tasks.py     # task definition / composition
  evidence.py  # records / redaction
  docs.py / plans.py
  evals.py / hosts.py
  schemas/     # repository-only; never a Skill runtime dependency
scripts/       # retain compatibility entrypoints
skills/<name>/ # self-contained runtime
tests/         # preserve root tests
tests/repoctl/ # new harness tests
```

Generate negative fixtures in temporary repositories first. Do not add broken SKILL.md files inside the checkout then conceal them with broad exclusions.

## Plan of Work

### M1 — Inventory and contract

Inventory every root/Skill validator, suite, eval fixture, installer and CI task: inputs, outputs, effects, dependencies, invocation routes, discovery and present CI reachability. Coverage means reachable checks, not line coverage.

Capture the current-base baseline, separating PASS/FAIL/NOT_RUN and explicitly executing root installer tests. Preserve existing failures and decide whether this work or a separate review Plan owns them. Never hide failures by skips or changed expectations.

Write harness-contract and minimal PLANS policy. Python 3.12 is the initial baseline; record rationale/environments for other versions. Add no mandatory dependency beyond ordinary Python/Git and existing development dependencies without justification; compare any parser addition with existing PyYAML.

Record D1–D10, bilingual policy and unported agent-env features in an ADR. Check Plan ID uniqueness; if occupied, consistently change the ID, references and branch.

- AC01: Every existing suite/content validator has a route; unconnected, duplicate and optional execution is identified.
- AC02: Record baseline/failure disposition and fix the boundary between normal CI and external evaluation.

Stop only changes whose scope/behavior expands after inventory; independent foundations may continue. Never silently include major Skill behavior changes.

### M2 — Portable runner and evidence foundation

Use the standard library for help, doctor, dispatch and structured diagnostics. Lazily import optional modules so help survives missing dependencies. Doctor does not install, log in or initiate billing.

Run Python children with sys.executable and other validated executables using argv arrays; no Bash/Make/PowerShell or assembled shell strings in canonical paths. Standardize cwd, environment, timeout, exit code, stdout/stderr and cleanup.

Diagnostics include stable ASKILLS-* codes, task ID, path, reason and repair direction. Negative tests assert the intended diagnostic and failure stage, not exit code alone.

Introduce schema-versioned run results in M2. Default to console; persist only with explicit `--out <new-directory>`. Processing success and subject acceptance are separate fields.

Move public installer parsing, Git source validation and environment isolation to the common Python path; merely forwarding unchecked values to low-level helpers is insufficient. Keep install-local.sh as a thin delegate. Preserve source classification, copy/link, force, backup and rejection contracts.

- AC03: Help/doctor/core runner work without a shell; unknown commands/invalid arguments fail clearly.
- AC04: Test spaces/Japanese paths, success/failure/timeout/interruption; never succeed while owned work remains unfinished.
- AC05: Python and legacy shell agree on arguments, source classification and rejection; prevent source mutation, external backup deletion and contaminated Git environment regressions.
- AC06: Preserve failure evidence and prevent secret-sentinel leaks in output, diagnostics and stored records; never test with real secrets.

### M3 — Canonical verification and native CI

Separate static checks from test execution:

```text
check = lint + Skill/content/fixture structure + docs-check + generated-check
        + checkout-only Plan structure
test = root tests + every Skill's tests + repoctl tests
verify = check + test + deterministic isolated installer smoke
```

Do not execute tasks twice within an aggregate. Do not initially cache across separate explicit invocations. Split nested test execution from content validators if discovered.

New Skills must automatically join discovery without fixed-name list edits, and existing suites must not remain unregistered. Run each Skill suite in its own subprocess to avoid module/sys.path collisions. Initially execute sequentially; parallelism needs separate isolation/need assessment. Inspect consumers of public validate_skills.py functions and keep compatibility adapters. Never silently narrow the old shell wrapper's coverage.

Core installer tests use Python; Bash compatibility lives in a separate suite mandatory on Unix. Missing Bash on Windows must not skip all core tests.

Configure native Linux/macOS/Windows Python 3.12 verification. OS-specific commands belong only in CI bootstrap. Dependency installation is explicit preparation, never verify behavior. Check required-check implications before renaming jobs and do not change repository settings without permission. Use fresh artifact output every run and preserve redacted failure results. Never publish raw secrets; keep read-only permissions and avoid credential paths for untrusted PR code.

Keep conditional gh skill validation separately identified by execution conditions/results. Nonexecution is neither portable verification nor live-host success.

- AC07: Task lists match results; no missing root/Skill/harness suite or aggregate duplication.
- AC08: Empty mandatory suites, missing paths, failures and missing mandatory dependencies cannot yield successful verify.
- AC09: Obtain actual native CI results on all three required OSes; workflow text or syntax inspection is insufficient.
- AC10: Sentinel/fake boundaries prove checks do not reach external LLMs, Backlog/Redmine or real host CLIs; source remains unchanged except evidence/cache outputs.

### M4 — Mechanical Skill/artifact/document/Plan validation

Validate Skill names, frontmatter, required notices, runtime reference closure, duplicates and external references. If strengthening provider metadata checks, distinguish syntax/repository constraints from unverified full provider-spec compliance.

Reproduce README catalog from skills/*/SKILL.md and catalog.json. Generated-check is read-only; generate alone writes. If handling bilingual READMEs, explicitly store per-language metadata and never require runtime LLM translation.

Validate navigation, relative links, anchors, required metadata, Plan sections and lifecycle placement. State scan boundaries/exceptions; distinguish .venv, installed Skills, local results and deliberately broken test documents from sources. Exceptions must be narrow paths or explicit classes.

AGENTS.md has an initial hard limit of 150 lines, not a guideline. Move details to architecture/quality docs. Pair new/substantially updated durable documents in Japanese and English; track the complete LF-normalized source hash without claiming semantic equality. Never automatically refresh hashes to conceal stale translations.

Implement plans list/check. Translation pairs sharing an ID count as one logical Plan; unrelated duplicate IDs fail. Do not automatically complete, execute or merge Plans.

- AC11: Injecting catalog omissions/extras, README drift, broken references or invalid frontmatter fails with corresponding diagnostics.
- AC12: Detect missing/orphan/stale translations, broken indexes/anchors, missing Plan sections, lifecycle mismatch and duplicate IDs.
- AC13: Repeated generation after generate creates no diff; check commands do not change sources or translation hashes.
- AC14: Skills copied outside checkout retain self-contained runtime references without repo tools or other Skills; document limits such as dynamic imports missed by static inspection.

### M5 — Common Skill evaluation contract

Implement eval plan/ingest/report without embedded model execution. Preserve existing eval fixtures through adapters rather than forcing wholesale schema rewrites.

RFE proposal-bound regression and general Skill evaluation are distinct. Never fabricate rule proposals to evaluate without one. Do not invoke existing approval/apply flows; reuse schemas/pure aggregation only as supported by M1 inventory.

Plans fix target Skill, source fingerprint, fixture/rubric digests, case IDs, purpose, required host/model conditions, planned attempts and allowed operations. Separate execution input from expected results/rubrics; never rewrite expectations from model output during scoring.

Results record origin, host version, model ID, attempt/case IDs, observations, failure type and evidence references. Undisclosed model versions are unknown with a reason, never guessed. Label fabricated schema/aggregation fixtures synthetic.

Inventory every fixture across all three Skills as executable, descriptive-needing-design or out-of-scope. Test plan-to-report with a small representative positive/counter/boundary set. Never omit unconverted cases then report all-pass.

Representative invariants include RFE meaning preservation/unnecessary-edit avoidance, evidence-backed adversarial findings and review-only nonmutation, and ticket-state Read Only rejection/dry-run nonmutation. Confirm actual judgeability and existing specifications. Do not replace prose-quality judgment with simple keyword matching.

- AC15: Model-free plan generation, ingestion and aggregation work without breaking RFE regression contracts.
- AC16: Detect wrong revision/fixture hash, unknown cases, duplicate attempts and missing required cases; do not remove missing cases from the pass denominator.
- AC17: Preserve all failed attempts, nonexecution, timeout and exclusion reasons; reports cannot select only successes.
- AC18: Distinguish synthetic, model observations and human judgments; plan generation alone never means Skill evaluation PASS.

Real-model execution requires separate explicit authorization. Humans decide cost, maximum attempts, models and permitted data. Authentication availability alone is not permission.

### M6 — Isolated installer smoke and live hosts

Implement install-smoke as deterministic local validation using temporary repositories/homes and actual Skills. Check source immutability, structure, bundled assets, scope, backups outside discovery, collision/force/link contracts. Never target the real root .agents/skills. Reuse existing tests without meaningless triple duplication.

Separate host-verify requires explicit --kick, host, executable, verification profile and fresh output. Initially verify actual client discovery/loading, not prose quality. Build adapters from current CLI help/official docs, never invented list APIs/options. [S12–S13]

Without mechanical discovery, report incomplete live-host observation and hand off human steps. A model merely saying it loaded the Skill is not discovery evidence. Paths requiring model execution need separate permission/evaluation from nonbilling discovery.

Isolation contract:

- Temporary areas are outside checkout, arranged not to inherit parent Skills/instructions.
- Inventory user profile, XDG, host settings, extra Skill paths, Git settings, auth, hooks/MCP/plugins as well as HOME.
- Pass only required environment. If system/admin settings cannot be isolated, record limits and BLOCKED or use explicitly identified isolation.
- Changing HOME is not a security sandbox and does not authorize scenarios requiring arbitrary-code containment.
- No credentials in normal smoke. Authorized live auth uses only minimal human-selected test paths, never wholesale config copies.
- Verify selected external canary files before/after; never scan/store an entire real home to gather secrets.
- Clean only owned assets after child termination. Preserve assets of uncertain ownership and record failure.

- AC19: Native install-smoke on all three OSes verifies each scope and no unauthorized external mutation.
- AC20: Fake hosts cover profile checks, absence of auth, config contamination, failure, interruption, child join and outer-file preservation.
- AC21: Missing/unsupported hosts, auth or isolation yield BLOCKED; smoke cannot become live-host success.

Copy mode is the mandatory portable baseline. Report capability-dependent modes such as symlinks separately; unavailable selected modes are BLOCKED, never an excuse to skip required copy mode.

### M7 — Human handoff and final integration

Package each human case with prerequisites, mechanical preflight, expected observations, evidence destination and recovery. Create a separate human-validation Plan in docs/exec-plans/draft, tentatively EP-HARNESS-002 after uniqueness checking.

Set execution_mode: human-kick, merge_policy: manual and a merged dependency on this implementation. Preparing procedures/records is implementation responsibility; agents cannot complete human actions/judgments. Dates or credentials never cause automatic execution.

| Case | Human check | Mechanical evidence |
|---|---|---|
| HV01 | Can a new session find the Skill and correct validation from AGENTS alone? | Read paths, argv, results, nonexecution reasons; no internal reasoning required. |
| HV02 | Does actual Codex CLI discover/load the intended scope? | Version, isolation profile, placement hashes, host observations. |
| HV03 | Does actual Copilot CLI meet the same contract? | Same evidence independently; do not reuse Codex success. |
| HV04 | Does RFE preserve meaning and limit edits? | Source/output/rubric/diff and eval plan/attempt references. |
| HV05 | Does review-only avoid mutation and ground findings? | Before/after hashes, finding/evidence mapping, disposition. |
| HV06 | Are ticket-state Read Only/dry-run upheld in real procedures? | Fake/dedicated-test requests, diffs and unapplied items; no production connection by default. |
| HV07 | Do blocked/failure/cancel displays support next actions and recovery scope? | Injected-failure runs, unfinished assets, recovery procedures and history. |

Record PASS/FINDING/BLOCKED/NOT_RUN, observer, revision, evidence, explanation and next action per case. Observer names are not authenticated approval. Link findings to review Plans/issues; do not silently fix or dismiss them.

Finally traverse discovery, normal verify, eval protocol, installer smoke, unexecuted hosts and human remaining work. Independent review requires a separate implementation context, not self-approval of one report. Record adopted/rejected/deferred findings and rationale.

- AC22: Checklists, logs/result formats and human Plan allow starting without conversation history.
- AC23: Missing prerequisites and human decisions remain visible; machines never autoexecute/autocomplete human Plans.
- AC24: Reconcile AC01–AC23, bilingual document review, independent review and native CI evidence.

Completion boundary: this Plan implements tooling, not approval of every model/host's Skill quality. Tool-only acceptance can be considered while a separate human Plan remains explicitly incomplete. Do not claim live-host or Skill-quality verification without direct case evidence.

## Concrete Steps

### 1. Before implementation

Before changing files, inspect git status --short, git branch --show-current, git rev-parse --show-toplevel; explicitly fetch origin and inspect git rev-parse origin/master. Read AGENTS, CONTRIBUTING, architecture, installation and compatibility docs. Never overwrite/stash/reset/clean user or other-agent work; use and record a separate worktree if needed.

Create `git switch --create feat/ep-harness-001 origin/master` only after confirming branch absence and safe ownership. Resuming a branch requires base/ID/content checks; never forcibly recreate it. Record exact base SHA and snapshot differences.

Record explicit promotion, status active and the M1 gate before behavior changes. Place the paired Plan at `docs/exec-plans/active/EP-HARNESS-001.md` and `EP-HARNESS-001.en.md`, keeping ID/status/branch/dependencies/criteria equal and counting one logical Plan.

### 2. Current-base baseline

Explicitly prepare a project venv from existing requirements. Resolve python to that environment, accounting for Debian/Windows paths. These are existing checks, not the new harness:

```text
python -m ruff check .
python scripts/validate_skills.py .
python scripts/generate-catalog.py --check
python -m unittest discover -s tests -p "test_*.py"
git diff --check
```

Existing root installer tests need Bash. Before M2, unavailable Windows execution is a baseline limit, not portable native success. The shell wrapper runs both Python validator and root installer tests; decomposition exposes responsibilities. Record baseline duplication of Skill tests/catalog reached through the root validator, then eliminate it in M3.

### 3. Implementation checkpoints

M1→M2→M3→M4 is the first reviewable unit. Confirm a new Agent can reach every Skill through canonical entrypoints. M5→M6→M7 requires another explicit instruction; do not start it under this limited authorization.

At each checkpoint record position, invariants changed, evidence, remaining work and scope deviations. Use purpose-specific commits and permitted push operations; harness commands never push/merge. Never force-rewrite public history.

If choosing partial merge, split child implementation Plans/branches while preserving parent remaining work. M4 delivery does not complete M5–M7 or this entire Plan.

### 4. Intended canonical commands

Document only commands implemented in their corresponding milestones as available:

```text
python -m tools.repoctl doctor
python -m tools.repoctl check
python -m tools.repoctl test --list
python -m tools.repoctl test
python -m tools.repoctl verify
python -m tools.repoctl docs-check
python -m tools.repoctl generated-check
python -m tools.repoctl plans list
python -m tools.repoctl plans check
```

Replace every new-directory with a distinct unused directory; never overwrite a failed run:

```text
python -m tools.repoctl verify --out <new-directory>
python -m tools.repoctl eval plan --skill reader-first-editor --out <new-directory>
python -m tools.repoctl eval ingest --plan <plan.json> --input <result.json> --out <new-directory>
python -m tools.repoctl eval report --plan <plan.json> --runs <runs-directory> --out <new-directory>
python -m tools.repoctl install-smoke --host codex --out <new-directory>
python -m tools.repoctl install-smoke --host github-copilot --out <new-directory>
```

Live hosts are independently authorized operations:

```text
python -m tools.repoctl host-verify --host codex --executable <absolute-path> --profile <profile.json> --kick --out <new-directory>
python -m tools.repoctl host-verify --host github-copilot --executable <absolute-path> --profile <profile.json> --kick --out <new-directory>
```

--kick expresses an explicit action, not authenticated human approval. Agents use it only within actual human instructions.

### 5. Merge and archive

Reconcile exact-revision native CI, acceptance records, independent review, docs and remaining work; obtain human merge authorization. Until merged, even finished implementation remains active.

After merge confirm the actual delivery merge commit is an ancestor of origin/master. Never predict a future SHA. If necessary, use a small separate archive change to update merge_commit, retrospective and state, move both translations to completed and update links/indexes.

## Validation and Acceptance

### Evidence classes

These are not interchangeable. [S11]

| Class | Establishes | Not a substitute for |
|---|---|---|
| Forced invariant | Known violations trigger the expected oracle | All OSes/interleavings |
| Direct native / integration | Execution on recorded OS/version/assets | Other OSes, absent hosts, production |
| Structural / tooling | Schema, structure, lint, drift | Meaning, prose quality, host discovery |
| Model observation | Outputs in specified conditions/attempts | Other models, future outputs, human approval |
| Human observation | Human observation/judgment for specified cases | Authenticated merge approval, unseen cases |
| Repetition / stability | Specified repeated observations | Causal reproduction or stronger evidence |

Every new validator needs invalid-fixture tests failing at the intended stage/code. Prefer fail-before/pass-after contrasts for bug fixes; explain exceptions and alternate evidence limits. Synchronize concurrency/cleanup tests with barriers/events/pipes rather than sleeps or repetition. Cancellation requests, client completion and child/server termination are distinct facts.

### Required fault injection

| Target | Minimum negative controls |
|---|---|
| Task discovery | Disconnect root suite, empty mandatory suite, duplicate task registration. |
| Runner | Nonzero child, timeout, owned work continuing after cancellation, failed result persistence. |
| Docs/catalog | One-sided translation update, broken anchor, catalog extra/missing entry, edited generated region. |
| Installer | Git contamination, external paths, collision, source mutation, missing permissions, failed rollback. |
| Eval | Stale digest, wrong Skill, missing cases, duplicate attempt, synthetic misrepresented as live. |
| Host | Fake executable, config/auth contamination, unsupported discovery, outer-canary mutation. |
| Lifecycle | Automatic draft selection/human execution, completed before merge, missing references, translation mismatch. |

Detecting synthetic-as-live claims is limited to trusted runner metadata comparison; caller self-report cannot authenticate real execution. Record evidence producer and validation scope.

### Acceptance record format

Record at least one row per AC01–AC24; run counts alone are insufficient:

```text
criterion_id:
invariant:
revision / dirty_fingerprint:
command / cwd:
environment:
evidence_class:
expected_failure_stage:
result: PASS | FAIL | BLOCKED | NOT_RUN
artifact_reference:
limits:
finding_disposition:
```

Required initial matrix: Linux/macOS/Windows × Python 3.12. Other versions, WSL and architectures get separate rows. Missing required OS execution prevents implementation completion; remain active or paused with rationale. Never reuse CI for an older revision as acceptance of later fixes.

## Idempotence and Recovery

- doctor, check, test --list, docs-check, generated-check and plans list/check never mutate source/Plan state; caches/temp follow contracts.
- Explicitly identify generate, actual installer, eval persistence and host verification as side-effecting. Checks never auto-repair.
- Require fresh run paths; retries get new IDs and preserve failed runs.
- Prefer atomic persistent writes; write failure, disk exhaustion and interruption never become success; also diagnose on console.
- Mark temporary ownership/run ID; do not delete before confirmed termination or broadly kill/delete uncertain resources.
- Preserve installer backup/rollback. Retain recovery information/assets after cleanup/rollback failure.
- Never wholesale recreate .venv, personal global instructions, credentials or real installed Skills.
- After interruption recheck Plan, Git, last run and remaining resources; recorded progress is not execution proof.
- Safe rollback only of unpublished owned work; use purpose-specific reverts for shared history, never force push.

## Artifacts and Notes

### Implementation artifacts

Deliver commands/tests, harness/eval/host contracts, quality/minimal Plan policies, ADR, bilingual navigation, CI and separate human Plan. Raw evidence is not committed by default. Tracked Plans contain concise redacted results, artifact IDs, revisions and limits.

Local artifact paths are not guaranteed cross-environment documentation links. Distinguish CI artifact retention from local portability. Do not mirror runtime GitHub responses, complete comments or review bodies into the repo; retain only minimal decision references.

### Minimal run evidence contract

```text
schema_version
run_id / parent_run_id / attempt_id
command_id / redacted_argv / cwd
source_commit / source_fingerprint / dirty_state
selected_tasks / task_results / omitted_tasks_with_reasons
environment: os / architecture / python / relevant_tool_versions
operation_result
subject_result                           # NOT_RUN if not evaluated
started_at / ended_at / duration
exit_code / failure_kind / diagnostics
evidence_class / provenance_kind
stdout_stderr_artifact_references
owned_resources / cleanup_result
limitations
```

Never save the whole environment. Redact sensitive argv, endpoints, paths and streams without recording secret values used for redaction. Explicitly mark truncation; missing decision material prevents treating evidence as complete.

### References

Recheck mutable information during implementation. Fixed GitHub references use recorded commits; inspect current base separately.

agent-skills at d423d1f483e48cfa955b02114c17611c6f2993cd:

- S1 AGENTS.md: shared behavior, self-contained runtime, Japanese policy, change rules.
- S2 scripts/validate_skills.py and scripts/validate-skills.sh: composition; shell additionally runs root installer tests.
- S3 .github/workflows/validate-skills.yml: current CI.
- S4 tests/test_install_local.py: root installer suite and Bash dependency.
- S5 scripts/generate-catalog.py and catalog.json: inputs/generated regions.
- S6 scripts/install-local.sh: arguments, Git isolation/source classification, helper delegation.
- S7 docs/architecture.md: boundaries and existing RFE infrastructure.
- S8 skills/reader-first-editor/docs/agent-investigation.md: provider-neutral protocol/human boundary.
- S9 requirements-dev.txt: development dependencies.

```text
https://github.com/mahcialet/agent-skills/blob/d423d1f483e48cfa955b02114c17611c6f2993cd/<path>
```

agent-env at 4e5fec663f493e4546c4d5e93e64dccfe909981f:

- S10 docs/PLANS.md: 12 sections, branch, lifecycle, merge/archive, human-kick.
- S11 docs/QUALITY.md: entrypoints, native evidence, classes, fixture completion.
- Supplement: docs/adr/0004-repository-native-harness.md, rationale connecting short instructions/navigation/durable docs/mechanical validation.

```text
https://github.com/mahcialet/agent-env/blob/4e5fec663f493e4546c4d5e93e64dccfe909981f/<path>
```

Official host docs checked for planning on 2026-09-11; recheck CLI options/auth when implementing:

- S12 OpenAI Build skills / Where Codex loads local skills.
- S13 GitHub About agent skills / Copilot project/personal placement.

```text
https://learn.chatgpt.com/docs/build-skills
https://docs.github.com/en/copilot/concepts/agents/about-agent-skills
```

These establish discovery paths, not live-host evidence for this repo. Availability of dedicated nonbilling discovery APIs for every host has not been established.

## Interfaces and Dependencies

### Command contracts

| Command | Responsibility | Effects / prerequisites |
|---|---|---|
| doctor | Required tools/dependencies/environment | Read-only; no installation/auth/models. |
| check | Lint, structure, docs, generated drift | Source unchanged; no implicit tests/models. |
| test | Root/Skill/harness tests | Temporary fixtures; --list does not execute. |
| verify | Aggregate required deterministic checks | CI; no models/production APIs/live hosts. |
| docs-check | Docs/translations/links/Plan structure | No network/source writes. |
| generated-check / generate | Inspect/update README generated content | Only explicit generate writes. |
| install | Portable public installer interface | Explicit scope changes; preserve arguments/defenses. |
| install-smoke | Installer/bundled asset checks | Temporary only; no live host CLI. |
| eval plan/ingest/report | Plan/result validation/aggregation | Explicit outputs only; no models. |
| host-verify | Actual host discovery/loading | kick/profile/executable/evidence required. |
| plans list/check | Navigation/state/reference checks | No state/Agent/Git writes. |

Public host IDs remain codex/github-copilot as in the installer. Display names/internal aliases differ; adding a copilot alias requires explicit compatibility tests.

### Exit results

Initial canonical proposal: 0 processing success, 1 validation failure, 2 invalid usage/input contract, 3 blocked due to missing prerequisites/incompletion. Normalize user interruption to 130. Inspect legacy code compatibility and preserve with adapters or document changes.

Generation/ingestion exit 0 does not mean Skill acceptance: subject_result is NOT_RUN or follows ingested observations. Verify exits 0 only if all required tasks pass. Unselected external evaluation is NOT_REQUESTED, excluded from PASS counts. Explicit but unavailable checks are BLOCKED, never silent successful skips.

### Dependency direction

```text
repoctl → shared root processing / Skill validators, tests, eval adapters
Skill runtime → its own bundled processing and references
Skill runtime ↛ repoctl / other Skills / repository-only docs
```

Normal harness requires Python/Git/existing development dependencies, not Docker, Go, Node, Codex, Copilot or LLM authentication. CI bootstrap dependency downloads differ from network access inside verification.

### Minimal Plan lifecycle

Use draft/active/paused/completed/abandoned matching directories. Fixed IDs, plan_type, base, branch, owner, date and merge policy are explicit. Paused needs a reason/resumption condition, abandoned a reason, completed a reachable delivery merge commit.

Validate parent/dependency existence, self-reference and cycles; parentage is not execution dependency. Never automatically execute draft, paused or human-validation. This Plan adds no scheduler, automatic stacked-branch selection or GitHub merge gate.

Docs-check validates checkout structure; plans check additionally validates required local Git reachability. Provide enough CI history; structural success cannot replace missing history. Explicitly fetch before decisions requiring remote freshness.

## Execution Checkpoint — M1–M4 scope

- 2026-09-11: Reread current AGENTS, CONTRIBUTING, architecture, installation, compatibility, CI, validators and installer. No conflicting Plan ID. Base equals planning snapshot; no rollback.
- Work area/branch: `/home/mahcialet/work/git_work/marmite/agent-skills`, `feat/ep-harness-001`. Preserve supplied root Plan. Active filenames use Plan ID without changing placement responsibilities.
- Baseline revision d423d1f483e48cfa955b02114c17611c6f2993cd, .venv Python 3.13.5/Linux. Ruff PASS; python scripts/validate_skills.py . PASS (3 Skills/suites); python scripts/generate-catalog.py --check PASS; root unittest discover PASS (33 tests, 5.315 seconds). Preimplementation native/integration and structural evidence; no failures hidden by skips.
- Python 3.12 is currently absent from PATH; exact-revision native three-OS CI evidence is unavailable. Workflow creation alone cannot pass AC09.
- Original M3 verify smoke depends on M6. Honor limited authorization: standalone smoke remains unimplemented/NOT_REQUESTED; implement check/test. Full M3 and AC09 remain incomplete until required evidence exists.
- Read-only master required-status API returned 404 (unprotected); preserve existing validate name through an aggregate job. No repository settings changed.
- M5–M7, live models/hosts, production APIs and merge are unstarted; do not infer expanded authority.
- Independent review, final commands, dirty fingerprint, detailed AC03–AC14 results and remaining work will be appended at M4. Never mark unverified acceptance PASS.
- M2 STOP POINT: Existing installer transactions depend on fcntl, dir_fd, flock and pthread_sigmask; safe native Windows support requires separate design. Preserve defenses; the Python public entrypoint reports ASKILLS-INSTALL-PLATFORM/exit 3 BLOCKED for Windows installation. Do not blanket-skip core suites. Portable AC05 and AC09 remain unmet, so M2/M3 stay unchecked; independent runner, validation and POSIX compatibility work continues.

### M4 execution evidence and acceptance ledger (2026-09-11)

Shared target: uncommitted work atop d423d1f483e48cfa955b02114c17611c6f2993cd, cwd `/home/mahcialet/work/git_work/marmite/agent-skills`, Linux 6.12.107+deb13-amd64/Python 3.13.5. Final code-validation dirty fingerprint: `69ea0e0104fe7825bbfa033a65f3b8861dd02dff4ef93a84c62f622be8fc47ae`. This ledger is a subsequent documentation change, not falsely claimed covered by that fingerprint. Review both languages, explicitly refresh their hash and rerun document checks.

- E1: `.venv/bin/python -m tools.repoctl verify --out .repoctl/m1-m4-final`; run `20260910T201108Z-b4b58230be19`, 13 tasks PASS, exit 0, operation/subject/cleanup PASS, 14.69 seconds. Root 44, adversarial 30, RFE 186, ticket-state 124, repoctl 17: 401 tests total. Eight static tasks and five suites, no aggregate duplication. Local explicitly persisted, untracked evidence: `.repoctl/m1-m4-final/summary.json`. Classes: direct local integration and structural/tooling, not live-model/host evidence.
- E2: `.venv/bin/python -m tools.repoctl doctor --out .repoctl/m1-m4-doctor` PASS, operation PASS/subject NOT_RUN. Prerequisite inspection is not subject-quality acceptance.
- E3: `.venv/bin/python -m tools.repoctl plans check --out .repoctl/m1-m4-plans` PASS, using local Git reachability. This does not prove CI remote freshness/native execution.
- E4: Forced fixtures in tests/repoctl/test_validation.py and test_runner.py (17 tests PASS within E1): dynamic discovery, empty suites, duplicate/missing tasks, broken documents, Plan state/sections/references/cycles, shallow history, generated drift/idempotence, external-checkout Skill copies and rejected external runtime references. Mechanical fixtures are not model observations.
- E5: Public Python installer, shell compatibility and existing transaction tests (E1 root 44 PASS): contaminated Git environment, unavailable Git/non-Git/unborn/HEAD, rejection, copy/collision/force/backup. Native Windows is BLOCKED; weakening existing defenses is deferred, not implemented.
- E6: Revalidated post-E1 review fixes with `python -m unittest discover -s tests/repoctl`: 17 tests PASS (0.625 seconds, console). Replaced the timeout fixture with child-ready/parent-ready handshakes, inject timeout only after readiness and assert owned-group SIGKILL/parent reap. This postdates the E1 fingerprint. Final technical review independently retested known blocker fixes.
- E7: Preserved mandatory compatibility-wrapper precommit history. `.repoctl/m1-m4-precommit` (run `20260910T201431Z-4c57cadfd62b`, fingerprint `50e024ae8f31176ad9140f6c9fbbf748b8b008359acb88f3400ea576f2df8f94`) was BLOCKED/exit 3 because system Python lacked Ruff. Retrying with venv first in PATH at `.repoctl/m1-m4-precommit-venv` (run `20260910T201513Z-5f6a25e3d7b8`, fingerprint `05acb869fabd1d933ab1bc2c9dbec38252fc0a78ac2a04f1d8aed42328d470c1`) correctly caught source/translation-hash mismatch during document edits: FAIL/exit 1. After both languages and manifest settled, docs-check `.repoctl/m1-m4-docs-recorded` (run `20260910T201603Z-9a92185df022`) PASS. `env PATH=<repo>/.venv/bin:$PATH ./scripts/validate-skills.sh --out .repoctl/m1-m4-precommit-final` (run `20260910T201625Z-38a1714297c7`) passed 13 tasks/401 tests, exit 0, 13.41 seconds. The latter two share fingerprint `4077e5a1d48d0f6511020cd2e424af55b438a5d880d80d8d5f660d53e226f7bc`; all four ran on base d423d1f483e48cfa955b02114c17611c6f2993cd plus dirty work. Failures remain in separate directories, never overwritten. This E7 addition postdates that evidence and requires another document check. Installer local commit `38321ef` was subsequently created. No push/native CI/merge performed.

| AC | Invariant, evidence / failure stage | Result | Limits / disposition |
|---|---|---|---|
| AC01 | M1 route table; E1 task/suite comparison | PASS | Base optional gh check unexecuted because live hosts are prohibited here. |
| AC02 | Separate baseline/E1 and external-evaluation boundary | PASS | Baseline only Linux/Python 3.13.5. |
| AC03 | Help/doctor/argv dispatch; E2 and runner tests | PASS (local) | Shell-free canonical path, not three-OS proof. |
| AC04 | E4/E6 timeout/nonzero/cancel/leftover-owned-child detection | PASS (POSIX scope) | Windows child cleanup UNVERIFIED; ready-handshake timeout injection is a forced invariant, not all-OS proof. |
| AC05 | E5 common Python entrypoint and shell comparison | BLOCKED (full portability) | POSIX44 tests PASS; Windows transaction unported; safe backend design remains. |
| AC06 | E4 durable failures, argv/JSON/token redaction and operation/subject separation | PASS (local fixtures) | No real secrets; not complete detection of unknown secret formats. |
| AC07 | E1 13 tasks; E4 new-Skill discovery/duplicates/missing root | PASS | Sequential isolated subprocesses; no cross-command cache. |
| AC08 | E4 empty/missing/duplicate/dependency oracles | PASS | Nonexecution is BLOCKED/ERROR, not successful skip. |
| AC09 | Three native OSes × Python 3.12 CI | NOT_RUN | Workflow only; push/native-CI permission unanswered, no execution results; M3 incomplete. |
| AC10 | E1 local argv/mock API boundary; no external launch | NOT_RUN (complete sentinel acceptance) | Full-verify external-execution sentinels and source before/after contrast unconfirmed; structural boundaries are not complete runtime isolation. |
| AC11 | E4 README drift/external-reference/frontmatter faults | PASS (recorded fixtures) | Separate catalog missing/extra oracles still need confirmation. |
| AC12 | E4 missing/orphan/stale, index/anchor, Plan sections/state/IDs | PASS | Static Markdown inline-link and ATX/HTML-anchor scope. |
| AC13 | E4 repeated generation byte equality and read-only drift check | PASS (fixture scope) | Refresh final Plan hash explicitly after bilingual review. |
| AC14 | E4 outside-checkout Skill copy/external-reference rejection | PASS (static scope) | Not complete dynamic-import/arbitrary-runtime analysis. |
| AC15 | Model-free eval plan/ingest/report | NOT_RUN | M5 outside authorization, unstarted. |
| AC16 | Eval digest/case/attempt validation | NOT_RUN | M5 unstarted. |
| AC17 | Eval failures/nonexecution/aggregation history | NOT_RUN | M5 unstarted. |
| AC18 | Synthetic/model/human evaluation distinction | NOT_RUN | M5 unstarted; M2 operation/subject fields are not evaluation functionality. |
| AC19 | Three-OS standalone installer smoke | NOT_RUN | M6 unstarted; do not promote installer tests. |
| AC20 | Fake-host profile/config/auth/cleanup | NOT_RUN | M6 unstarted. |
| AC21 | Live-host BLOCKED distinct from smoke | NOT_RUN | No live hosts launched; M6 unstarted. |
| AC22 | Human cases/forms/separate Plan | NOT_RUN | M7 unstarted; EP-HARNESS-002 not created. |
| AC23 | Human decisions/no-autoexecution handoff | NOT_RUN | M7 unstarted; validator prohibitions are partial evidence only. |
| AC24 | All AC/bilingual/independent review/native CI reconciliation | NOT_RUN | Limited checkpoint; native matrix and M5–M7 incomplete. |

### Independent review and remaining work

- Separate-context runner/evidence review identified default persistence, token/JSON/argv leaks, timeout/normal-parent-exit owned children, and processing/subject conflation. Adopted and fixed; E1 regression tests and versioned records confirm changes.
- Separate-context validator review identified malformed frontmatter terminators, manifest paths, children cycles and shallow-Git misclassification. Adopted with targeted E4 fixtures; missing history is BLOCKED.
- Final separate-context technical review independently retested known blocker fixes. E6 removed sleep-dependent timeout orchestration. Windows/native remaining work was not promoted to review acceptance.
- Separate-context bilingual review compared AGENTS/QUALITY/PLANS/ADR/harness contract/architecture; no main invariant/scope meaning differences found. Corrected the installer helper typo to scripts/install_local.py in both languages. Hash equality was not the sole translation-quality evidence. This acceptance-ledger addition postdates that review and needs separate checking.
- Defer a safe Windows installer backend and native Windows process-tree cleanup evidence; do not remove POSIX defenses or claim full M2/M3 completion.
- Remaining: native three-OS CI, complete AC10 sentinel coverage and separate AC11 missing/extra catalog fault confirmation. M5–M7, live models/hosts and merge are unstarted. Local commits `38321ef` and `f9cb904` were created after this ledger was written. No push or merge.

### Windows backend design addendum (2026-09-11, design only)

The user's instruction to proceed authorizes the immediately preceding proposal for safe port DESIGN. Inspection HEAD is
`f9cb904` on `feat/ep-harness-001`. Do not expand this into implementation, native execution, push or M5+ authorization.
These are implementation candidates and verification gates, not native Windows evidence. AC05 remains BLOCKED; AC09 remains NOT_RUN.

#### Recommended structure and rejected alternatives

Keep the POSIX transaction unchanged initially and introduce a Windows-specific backend below the public Python entry.
Share arguments, source identity, stamp format and test contracts, rather than forcing POSIX syscalls into a common abstraction.
Concentrate handle-relative operations in a small boundary. The initial candidate is explicit Windows API bindings through
stdlib `ctypes`, but do not connect it to the installer before native proof of ABI, flag combinations and error translation.
If bindings become excessively risky or complex, return the dependency/compiled-helper decision to a human.

Reject `shutil` operations after `Path.resolve()`, repeated path checks as an anchoring substitute, PID-file-only locks,
automatic Developer Mode, elevation and silent junction fallback. Do not mix broad POSIX refactoring or weaker existing tests into this port.

#### Invariants and Windows candidates

| Boundary | Candidate and required proof | If not established |
|---|---|---|
| Root/ancestor anchoring | Bootstrap a real directory handle, then open each component from its held parent handle. Use NtCreateFile RootDirectory with single-component names, no-reparse opens, and volume + file ID comparison. Check source ancestry using handles too | BLOCKED before writes; no path-based fallback |
| Rename/deletion | Hold the source entry handle with DELETE access and destination parent handle. Verify SetFileInformationByHandle FileRenameInfo/RootDirectory with ReplaceIfExists=FALSE for no-replace. Candidate deletion uses handle disposition, including every child during recursive cleanup | Stop without overwriting or recursively deleting unrelated entries |
| Identity/snapshot | Retain FileIdInfo volume serial + file ID, entry type, size/content hashes and enumeration sets; recheck around copy, after stamping and before activation. IDs are meaningful while handles remain held, not permanent identifiers after closure/reuse | Preserve existing dirty classification or stop; no unsupported clean stamp |
| Lock | Keep a persistent registry guard outside Skill discovery under .agents, verify regular-file identity and use LockFileEx. Serialize opening/acquiring and cleaning per-skill locks under the guard. Do not wait indefinitely for a per-skill lock while holding the guard; release the guard on immediate acquisition failure | Stop on delayed-opener or identity mismatch; do not delete another owner's lock based on a PID |
| Permissions/sharing | Check ACLs when creating staging/control directories; do not change existing root ACLs. Minimize rights/share modes and treat sharing violations as conflicts. Prove compatibility between rename-enabling share modes and prevention of reparse modification | Do not bypass ACL/antivirus conflicts; BLOCKED if before mutation |
| Child processes | Candidate: assign required stamp/check children to a Job Object before execution, forbid breakaway, use kill-on-close and verify termination. Test nesting under the existing CI Job | Do not start an uncontained child; do not promote taskkill into strict ownership proof |

A persistent registry guard with its kernel lock released is not a surviving owner. Do not indiscriminately replace the POSIX
empty-lock-directory fixture: test the Windows guard outside discovery, released per-skill ownership and closed handles separately.
Do not delete the guard during ordinary cleanup and split the lock namespace. Share/ACL properties preventing guard/lock replacement
while open are mandatory W1 proof as well.
Reject reparse entries and multiple hardlinks for guard/lock files; preserve the existing `nlink=1` check. Fix the same LockFileEx
byte range for all writers and inject hardlink/alias bypass attempts.

The parent owns the Job; do not inherit or duplicate its handle into children. Fix the sequence as
`CREATE_SUSPENDED → AssignProcessToJobObject → ResumeThread`; on assignment failure terminate/reap the unexecuted child before stopping.
Kill-on-close depends on the last Job handle closing: test parent death, unintended extra handles and child breakaway attempts,
and verify termination rather than relying only on notifications.

The current POSIX implementation anchors parent fds but does not establish saved rollback entry IDs or atomic no-replace against third
parties. Require these as **strengthened Windows acceptance conditions**, not existing proven guarantees. POSIX changes remain a separate decision.

#### Transaction and interruption

Use `VALIDATED → STAGED → BACKED_UP → ACTIVATED → COMMITTED`, recording owned entry IDs and phase immediately after each rename.
Deliver catchable Windows cancellation as a flag, without reentering rollback between a single API mutation and its phase update.
Even with `--force`, active-to-unique-backup and stage-to-active are separate no-replace operations, not an atomic whole-operation swap.
Keep backup and stage on the target volume.
Before rename, save private intent containing old/new identities and source/destination; record the result after success.
Forced termination between successful rename and result recording is mandatory fault injection. Uncertain, missing or invalid records
must never trigger automatic restore/delete. Limit ordinary cleanup to the created entry ownership set and matching identities;
retain entries added/replaced by another actor and stop safely.

Rollback only before commit, with matching saved identities and an empty restore destination. Do not delete an active entry occupied by
another actor or a modified backup. On mismatch/sharing violation, retain evidence and backup and report incomplete recovery as failure.
Separate successful installation from incomplete post-commit cleanup; do not silently restore the previous active installation.

Do not guarantee automatic rollback after forced termination or power loss. A local phase/identity/hash record is recovery evidence;
flushing it does not prove whole-filesystem transaction durability. Detect incomplete state on the next attempt and BLOCK; destructive
recovery is a separately explicit operation. Do not equate ACLs, modes, Windows read-only attributes and Git executable bits: pin Windows
representation differences in dedicated clean/dirty stamp tests.

#### Proposed initial proof scope and open questions

Propose Windows x64, local NTFS, Python 3.12+ and ordinary copy for the first native prototype; this does not already decide public support.
Do not claim UNC/SMB, FAT/exFAT/ReFS, cloud placeholders, cross-volume operations, ARM64 or other cases without separate evidence.
Unknown capabilities must BLOCK before active mutation.

Reject junctions, mount points and other reparse entries in root/control directories. Preserve current semantics for ordinary symlinks
inside copies and `--link`; missing privileges stop the whole operation before mutation. Do not change symlink privileges or Developer Mode.
Do not treat unknown reparse tags as ordinary symlinks, or silently dereference/copy/substitute junctions. Preflight case collisions, ADS,
reserved names, trailing dots/spaces and long Unicode paths without silently rewriting names. Do not describe these protections as isolation
against administrators or process injection.

#### Next implementation gates (not started)

1. **W1 primitive proof**: use only temporary NTFS trees to verify handle-relative open/rename/delete, reparse refusal, IDs, share/ACL,
   LockFileEx and Jobs. Force races with separate-process ready/release barriers. If ABI, directory flags or root bootstrap cannot be
   established, retain BLOCKED and revisit the design. Review dependency/helper choice, initial OS/FS scope and persistent-guard contract here.
2. **W2 transaction implementation**: after W1, implement the backend reusing CLI/source classification; add native rollback, stamp and
   owned-cleanup tests. Ordinary copy and `--force` must succeed before removing the Windows gate.
3. **W3 adversarial/compatibility proof**: inject delayed openers, lock/registry swaps, 30 same-Skill writers, concurrent different Skills,
   source truncate/rename, stage changes, backup/active name conflicts, per-phase cancel/forced termination and missing symlink privileges.
   Observe source/unrelated-entry preservation, backup counts/content, single Skill discovery and handle/Job termination; sleep alone is not an oracle.
4. **W4 integration decision**: after independent review and native evidence, remove the Windows gate and run Linux/macOS regression and
   three-OS CI. Do not replace mandatory Windows copy with a skip or mock. Push/CI authority and results remain separately required;
   design approval alone does not make AC05/AC09 PASS.

W1–W4 address M2/M3 residuals, not authorization for M5–M7. This turn changes documents only; no prototype, live host or live model is launched.

#### Sources and design evidence

The following official Microsoft Learn documentation was inspected read-only on 2026-09-11. Documented API functionality is distinct
from native evidence that the combination meets installer guarantees. Ordinary copy success alone is not acceptance.

- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew): directory handles, share modes and reparse opens.
- [NtCreateFile](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile): RootDirectory-relative names, create disposition and reparse behavior. W1 must prove ABI/directory flag combinations.
- [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info): destination RootDirectory and ReplaceIfExists.
- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle): handle-based rename/disposition.
- [GetFileInformationByHandleEx](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfileinformationbyhandleex): FileIdInfo.
- [LockFileEx](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-lockfileex): OS locking and release after closure/termination; do not assume immediate release.
- [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects): nesting, breakaway and kill-on-close. Missing notifications alone do not prove termination.
- [CreateSymbolicLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createsymboliclinkw): unprivileged flag and Developer Mode conditions.

Separate-context read-only analysis compared existing fd anchoring, the lock registry, snapshots, cancellation and rollback with fixtures.
Adopted the finding that atomic no-replace and entry-ID rechecks are not established POSIX guarantees, separating them as stronger conditions.
Independent review of both languages found no major meaning differences. Adopted all three clarifications: pre-rename intent,
last-Job-handle lifetime and hardlink refusal/fixed lock byte range. Initial document validation correctly FAILED on the not-yet-updated
translation hash; `plans check` and `git diff --check` PASSED. After rechecking the additions and translation and refreshing the manifest,
reruns of `python -m tools.repoctl docs-check`, `python -m tools.repoctl plans check` and `git diff --check` all PASSED.
No native primitive/transaction tests have run; implementation feasibility remains a W1 decision.
Independent re-review confirmed all three fixes in both languages, with no unresolved known findings. This is a design-review result, not native acceptance.

### W1 execution checkpoint (2026-09-11)

This checkpoint updates the authorization state recorded at design time above. The user explicitly authorized committing the design,
implementing/testing W1, pushing the work branch and Windows verification through GitHub Actions. W2 onward, live model/host launches
and merge remain out of scope. Continue on `feat/ep-harness-001`; after fetch, `origin/master` remains
`d423d1f483e48cfa955b02114c17611c6f2993cd`. Do not modify or commit the supplied untracked original.

- Design commit: `aed77c6`. Before committing, ran
  `env PATH=<repo>/.venv/bin:$PATH ./scripts/validate-skills.sh --out .repoctl/w1-design-precommit` at repository root:
  Linux/Python 3.13.5, 13 tasks/401 tests PASS. Run `20260910T220324Z-b7db02006b56`, execution HEAD
  `f9cb90486ea25d35ef3eacc70d8874d0950fd126` plus dirty state. `git diff --check` also PASS.
  This aggregate verify summary lacks a source fingerprint; commit-bound native evidence will be obtained separately through Actions.
- W1 is experimental code in `tools/windows_probe/` and `tests/windows_probe/`, without installer/runner integration.
  Dedicated workflow `Windows W1 primitives` runs `python -m tools.windows_probe --out .repoctl/w1-native`.
  This is Python 3.12/native Windows x64 testing; non-Windows is BLOCKED. Even dedicated-suite skips cannot produce CI success.
  Evidence goes only to console and the explicit output directory; Actions artifacts expire after seven days.
  No real-user deployment locations, credentials or settings are touched.
- Existing `Validate skills` mandatory Windows suite remains BLOCKED. W1 success cannot promote AC05/AC09 or M2/M3 to complete.
  Append native results, independent review and residuals here after execution.
