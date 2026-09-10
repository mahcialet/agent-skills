---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# ADR 0001: Python repository-native harness

Status: accepted for M1–M4 implementation decisions, not authorization to execute later milestones. Date: 2026-09-11.

See the [Japanese source](0001-repository-harness.md) and [EP-HARNESS-001](../exec-plans/active/EP-HARNESS-001.en.md).

| ID | Decision | Rationale / reconsideration |
|---|---|---|
| D1 | Python, `python -m tools.repoctl` | Reuse Python assets; reject mandatory Go. |
| D2 | Normal verify is deterministic and local | Exclude external LLMs, production APIs and live hosts; avoid billing/auth/model variance in normal CI. |
| D3 | Preserve validator/installer/Skill tool responsibilities | Do not mix harness introduction with Skill behavior changes. |
| D4 | Provider-neutral eval plan/ingest/report | Reuse RFE contracts; direct model runners need separate decisions. M5 is unstarted. |
| D5 | Distinguish installer smoke from live-host validation | Placement success is not client-use evidence. M6 is unstarted. |
| D6 | Versioned evidence from M2 | Record failures, targets and cleanup from the outset. |
| D7 | Validate Plan state, fields, references and evidence; manual merge | Do not transplant the full scheduler/GitHub gate. |
| D8 | Separate human-validation Plan | Implementation completion differs from real-use verification. M7 is unstarted. |
| D9 | Japanese `.md` source and `.en.md` for new/substantially updated durable docs | Preserve existing paths. Do not blanket-translate SKILL.md, identifiers, licenses or quotations. Translation is not a separate behavior definition. Source hash manifest detects staleness, not translation quality. |
| D10 | Intended negative-fixture failures are regression evidence | Repeated passing runs alone do not establish causality. |

Do not transplant agent-env's Go runtime, product dependency, scheduler, complete Plan orchestration, automatic merge or billing platform. Reconsider sharing once contracts stabilize across repositories.

The user's explicit scope permits only M1–M4. Separate M3 smoke/native-matrix acceptance from deferred M6 and available environments; record unexecuted checks as pending. No new Python parser dependency is needed.
