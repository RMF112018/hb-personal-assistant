# 01 — Unified Design Contract and Current Code Map

## Objective

Create a concise design contract for the first slice and map it to existing repo modules before implementation.

## Required analysis

Inspect and summarize current behavior of:

- V49 email/calendar projection engine and CLI.
- Daily-run orchestration stages.
- Calendar prep candidate generation.
- Procore digest and ranking.
- Candidate writer and source-ref gate.
- Daily brief context packet/status output.
- Project alias/project identity tables and APIs.
- Existing tests around daily brief candidate projection, source-ref gates, usefulness gates, and projection coverage.

Use searches like:

```bash
rg -n "projection-reprocess|projection-coverage|projection_runs|projection_coverage|build_calendar_prep_candidates|build_procore_action_digest|persist_candidate_with_refs|gate_model_candidate_context|executive_coverage_ok|daily_brief_context_packet|daily-run|daily_run|usefulness|contradiction|data_gaps" src tests docs
```

## Design decisions to document

1. Where the projection activation stage belongs.
2. Whether projection activation is dry-run or apply in each mode.
3. How candidate projection stages are invoked and capped.
4. How source-ref coverage is checked.
5. How project-key coverage and unresolved project review states are reported.
6. How Procore suppressed backlog is surfaced as diagnostics only.
7. How the daily brief status transitions to degraded/failed on contradictions.
8. What is explicitly not being built in this slice.

## Deliverable

Create:

- `docs/evidence/phase-10-daily-brief-raw-projection-first-slice/04-unified-design-contract.md`

Use this file as the implementation guide for later prompts.

## Acceptance

- Design reuses existing modules where possible.
- Any new module has a clear purpose and no duplicate logic.
- No raw value examples are included.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
