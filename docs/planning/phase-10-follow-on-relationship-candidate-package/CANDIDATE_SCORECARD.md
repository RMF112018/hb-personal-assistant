# Candidate Scorecard — Follow-On After Daily Pipeline

Scores use 1–10 where 10 is best except complexity/safety risk, where lower is better. Daily pipeline/scheduler/browser/Obsidian delivery candidates are treated as in-progress and therefore not selected.

| Candidate | ROI | Repo readiness | Data readiness | Schema readiness | Model readiness | Complexity | Safety risk | Validation fit | Time to value | Notes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Relationship candidate engine | 9 | 8 | 8 | 8 | 8 | 5 | 4 | 8 | 9 | Selected. Completes loop by connecting existing sources. |
| Calendar deeper meeting prep | 8 | 7 | 8 | 7 | 7 | 6 | 4 | 8 | 8 | Next best, but should consume relationship context. |
| Inbox classification/prioritization | 8 | 6 | 7 | 6 | 7 | 6 | 5 | 7 | 7 | Useful after brief exists; less source-linked. |
| Procore deeper summarization | 7 | 7 | 9 | 7 | 7 | 6 | 4 | 7 | 7 | High data readiness, but siloed. |
| Email follow-up/raw enrichment | 7 | 7 | 8 | 7 | 7 | 5 | 6 | 7 | 8 | Good, but raw boundary risk is higher. |
| Local model evaluation/routing | 7 | 6 | 7 | 6 | 8 | 6 | 3 | 7 | 6 | Improves reliability but does not add user-facing intelligence immediately. |
| Entity normalization/deduplication | 7 | 5 | 6 | 5 | 5 | 7 | 4 | 6 | 5 | Foundational, but review/merge risk makes it slower to value. |
| Pipeline health / run status | 6 | 8 | 8 | 8 | 8 | 4 | 3 | 7 | 8 | Likely part of daily pipeline pilot; not follow-on. |
| Review/API/dashboard surfacing | 6 | 5 | 6 | 5 | 5 | 8 | 5 | 8 | 6 | Premature until candidates are richer. |
| MCP context packet builder | 5 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 5 | Policy-sensitive; local-only no-raw constraints make it later. |
| Obsidian indexing/organization | 5 | 5 | 4 | 5 | 4 | 6 | 5 | 5 | 5 | Mutation-sensitive and lower direct brief ROI. |
| File/document parsing | 5 | 4 | 2 | 5 | 5 | 8 | 5 | 6 | 4 | Data-blocked by current evidence; revisit after file ingestion. |
| Production/main integration planning | 5 | 6 | 6 | 5 | 5 | 7 | 3 | 7 | 5 | Planning family, not the next local-agent implementation. |


## Recommendation

Select **Relationship candidate engine + cross-source context enrichment**.

## Why It Beats Alternatives

- It uses existing substrate instead of starting a new subsystem.
- It improves the daily brief directly after the daily pipeline lands.
- It unlocks later calendar deeper meeting prep, inbox prioritization, and context packet workflows.
- It is deterministic-first and can remain local-only/no-writeback.
- It can be validated with DB-copy dry-run/apply/idempotency/guardrail proofs.

## Primary Risk

The current deterministic scorer is email-calendar focused. Procore relation support must be treated as conditional. Do not invent Procore relationship linkage if repo/DB truth lacks stable source refs and safe read models.

