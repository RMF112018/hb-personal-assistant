# 25 — Usefulness Scorecard

Computed from the integrated daily-run apply proof against a `/tmp` DB copy
(`17-daily-run-integrated-copy-proof.json`, `18-status-json-proof.json`). Counts/statuses only.

## Before (production baseline — `05-table-counts-baseline.json`)

| Signal | Value |
|---|---|
| `email_calendar_projection_runs` | 3 (projection had run, but candidates never built) |
| `daily_brief_action_candidates` | **0** |
| `candidate_source_refs` | **0** |
| `construction_project_identity` | 0 |
| Procore open action signals | 5,912 |
| Brief usefulness | operator-useless (rich substrate, zero candidates) |

## After (integrated apply on copy)

| Signal | Value |
|---|---|
| Projection status | `ok` · coverage `complete` · 0 unmapped business fields |
| Daily candidates (total) | **31** |
| — calendar | 6 source-linked |
| — procore | 25 source-linked |
| Candidate source-ref coverage (overall) | **100%** |
| Executive source-ref coverage | **100%** |
| Project-key coverage (in-window calendar) | **100%** |
| Calendar events in window / needs-review | 6 / 0 |
| Procore open / promoted / suppressed / aggregate-sludge | 5,912 / 2,095 / 3,817 / 3,655 |
| Procore aggregate sludge promoted to executive rows | **0** (suppressed → diagnostics only) |
| Project identities (deterministic backfill on copy) | 0 → **6**, 0 conflicts |
| Email/follow-up readiness | `data_gap` (23,034 source rows, 0 follow-up rows) → data-gap card surfaced |
| Data gaps surfaced | email_followup (data_gap), procore (due_date_coverage_low) |
| Usefulness verdict | **useful** |
| Run status | **success** · operator_usable: true · freshness: fresh |
| Guard columns (32 checked) | all 0 |

## Contradiction guard (known-bad — `16-contradiction-known-bad-proof.json`)

Source rows present but zero candidates and no data-gap acknowledgment →
verdict **degraded**, `passed: false`, reasons:
`no_useful_deterministic_section`, `calendar_window_nonempty_but_no_candidates`,
`procore_promotable_but_no_candidates`, `email_rows_but_empty_followup_no_data_gap`.
A clean success is impossible when useful source data exists but candidates are empty.

## Verdict

The slice converts the raw/structured substrate into a source-linked, gated, operator-useful daily
brief: candidates went 0 → 31 (100% source-linked), aggregate Procore sludge is diagnostics-only,
unknown projects are review-safe, empty email/follow-up is an explicit data gap, and the misleading
"success with empty substrate" path is closed.
