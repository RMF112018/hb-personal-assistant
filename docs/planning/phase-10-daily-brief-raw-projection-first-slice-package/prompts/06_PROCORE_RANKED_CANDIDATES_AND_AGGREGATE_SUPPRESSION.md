# 06 — Procore Ranked Candidate Projection and Aggregate Suppression

## Objective

Make Procore daily-brief input source-linked, ranked, and suppression-aware instead of broad aggregate sludge.

## Required behavior

- Reuse `build_procore_action_digest`, `rank_procore_signals`, and `persist_candidate_with_refs` where possible.
- Persist only promoted ranked signals/candidates into `daily_brief_action_candidates` with `section = 'procore'`.
- Every persisted Procore candidate must have at least one `candidate_source_refs` row.
- Suppressed aggregate backlog must appear only as diagnostics/backlog, not as executive action rows.
- Semantically closed/resolved/complete signals must not be promoted as open actions.
- Due-soon/recent/source-change/financial/high-importance reasons should drive why-today ranking.

## Handle missing due dates

If `due_at_utc` coverage is low/zero:

- Do not fabricate due dates.
- Report due-date coverage as a data quality metric.
- Use other why-today dimensions where available: recent, source-change-linked, financial materiality, high/critical importance, owner-linked.
- Add a clear recommendation for future due extraction if still blocked.

## Receipt fields

- total open signals
- promoted count
- suppressed count
- aggregate sludge count
- semantically closed count
- due-soon count
- recent count
- candidates would persist / persisted / skipped existing
- source-ref coverage
- top suppression reasons

## Tests

Add synthetic tests for:

- overdue/due-soon/high/financial/source-change signals promote
- stale aggregate backlog suppresses
- closed/resolved signal suppresses
- persisted candidates are source-linked
- raw metadata/payload/free-text is not emitted

## Acceptance

- Procore action signals can be numerous without flooding the executive daily brief.
- Candidate output is source-linked and ranked.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
