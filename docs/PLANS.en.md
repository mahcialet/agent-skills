---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# ExecPlan policy

[Japanese source](PLANS.md) / [Documentation index](index.en.md)

Keep living, self-contained plans in `docs/exec-plans/<status>/` so another session can understand purpose, scope, validation and remaining work without conversation history. States are `draft`, `active`, `paused`, `completed`, `abandoned`. Japanese/English pairs with one ID represent one logical Plan.

Required frontmatter: `status`, `owner`, `last_verified`, `plan_id`, `plan_type`, `base_branch`, `branch`, `merge_policy`; normally `merge_policy: manual`. Validate dependency/parent existence, self-reference and cycles; parentage is not an execution dependency. IDs, status, branch, dependencies and acceptance criteria must agree across translations.

Required sections retain these English identifiers:

1. Purpose / Big Picture
2. Progress
3. Surprises & Discoveries
4. Decision Log
5. Outcomes & Retrospective
6. Context and Orientation
7. Plan of Work
8. Concrete Steps
9. Validation and Acceptance
10. Idempotence and Recovery
11. Artifacts and Notes
12. Interfaces and Dependencies

`python -m tools.repoctl plans list` lists Plans; `plans check` validates structure and required Git reachability. Neither changes state, starts agents, fetches or merges. `docs-check` checks checkout structure only. Insufficient history is not success.

Paused Plans need a reason and resumption condition; abandoned Plans need a reason. Move both translations to completed only after confirming the actual delivery merge commit is reachable from base. Do not predict SHAs; unmerged implementations remain active. Explicit fetch by the operator establishes required remote freshness.

Use `pause_reason`, `resume_criteria` and `abandon_reason` as the machine-validated fields.

Never automatically start draft, paused or human-validation Plans. Human Plans specify `execution_mode: human-kick` and merged dependencies. Observer names are not authenticated approvals; scheduled dates or available credentials do not authorize execution.

At each checkpoint record exact revision/dirty fingerprint, argv/cwd, environment, result, evidence class, failure stage, artifact reference, limitations and review disposition. Repetition alone is not evidence. Redact secrets and do not mirror raw logs.

[EP-HARNESS-001](exec-plans/active/EP-HARNESS-001.en.md) currently authorizes only M1–M4. M5 onward, live models, live hosts and merge require separate instructions. Unexecuted M3 native matrix prevents complete acceptance.
