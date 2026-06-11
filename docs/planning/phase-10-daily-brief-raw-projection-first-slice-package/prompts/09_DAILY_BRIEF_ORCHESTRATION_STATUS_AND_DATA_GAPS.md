# 09 — Daily Brief Orchestration, Status, and Data-Gap Cards

## Objective

Wire projection, candidate projection, gates, and data-gap summaries into the daily brief run/status surfaces.

## Required daily-run stages

Add or harden stage receipts for:

1. V49 projection.
2. Calendar candidate projection.
3. Procore candidate projection.
4. Project identity resolution summary.
5. Source-ref gate.
6. Usefulness/contradiction gate.
7. Data-gap card generation.

## Status JSON must include

- `projection.email_calendar`
- `candidates.total`
- `candidates.by_section`
- `candidate_source_ref_coverage`
- `project_key_coverage`
- `calendar.events_in_window`
- `calendar.candidates_persisted`
- `calendar.needs_review_count`
- `procore.total_open_signals`
- `procore.promoted_count`
- `procore.suppressed_count`
- `procore.aggregate_sludge_count`
- `email_followup.raw_available`
- `email_followup.watch_items`
- `data_gaps`
- `usefulness_verdict`
- `degraded_reasons`

All values must be counts/status/reason codes only. Do not emit raw titles, bodies, URLs, attendees, recipient arrays, or payload values.

## Browser/Obsidian/private brief

If the repo has private local brief surfaces that intentionally show useful meeting titles, keep those surfaces within existing policy. Evidence/status files for this package must still be raw-free.

## Acceptance

- Operator can tell whether the brief is useful, degraded, or blocked and why.
- Empty sections are explained by data gaps or explicit exclusions.


## Safety constraints for this prompt

- Use DB copies for validation.
- Do not print raw private values.
- Do not mutate external systems.
- Do not mutate production DB during validation.
- Commit only code/docs/tests/evidence that are raw-free.
- Stop if any stop condition is triggered.
