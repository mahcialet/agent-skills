---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# Repository instructions

This translates [AGENTS.md](AGENTS.md), not a separate behavior definition.
Start with the [documentation index](docs/index.en.md), [architecture](docs/architecture.en.md), [quality policy](docs/QUALITY.en.md) and [Plans](docs/PLANS.en.md).

## Scope

These instructions apply throughout the repository.

## Skill design

- All supported hosts use the same behavior definition in `skills/<name>/SKILL.md`.
- Do not hand-maintain separate Codex and Copilot copies.
- Separate provider-specific metadata from common instructions.
- Keep every file a Skill reads at runtime within its Skill directory.
- Editing Skills must not change original text or files unless the user explicitly requests editing.

## Documentation

- Japanese is the default language for repository explanations.
- Host-discovery frontmatter, CLI/schema identifiers, license originals and required quotations may remain English.
- Do not translate identifiers or schema keys merely to follow the Japanese documentation policy.
- Distinguish planned, experimental, implemented and verified; do not advertise unimplemented features as available.
- Pair new/substantially updated durable explanations and ExecPlans with Japanese `.md` sources and English `.en.md` translations. Do not duplicate SKILL.md by host/language. Matching translation hashes do not prove matching meaning.

## Validation and Plans

- The canonical entrypoint is `python -m tools.repoctl verify`; read quality policy for preparation, evidence and limits.
- `check` is static validation, `test --list` lists suites, `test` executes. Normal checks never launch live models/hosts/production APIs.
- `docs-check`, `generated-check`, `plans list/check` are read-only. Only explicit `generate` changes generated sections.
- Record authorized scope and remaining work in ExecPlans. Do not automatically execute draft, paused or human Plans.
- Unmerged Plans are not completed. Respect separate authorization for merge and live model/host operations.

## Changes

- Preserve third-party attribution and license notices.
- Update examples and eval fixtures when behavior changes.
- Behavior-changing Skill rules require supporting, counter and boundary examples, regression confirmation with existing evals, provenance checks and explicit human review.
- Never promote local-corpus observations to core rules without human review.
- Keep the root catalog synchronized with `skills/`.
- Run `./scripts/validate-skills.sh` before committing.
- Separate commits by purpose and never force push.
