# ADR 286: Schedule Quality Evaluation (DCMA / GAO / AACE)

## Status

Accepted — implemented in V64 (`schedule_quality_evaluation_runs`, `schedule_quality_metric_results`, `schedule_quality_scorecards`).

## Context

Schedule Intelligence V62 committed schedules to canonical SQLite tables but ran only four inline quality checks at import time. Operators need reputable CPM assessment metrics without forensic delay claims.

## Decision

- Enqueue background evaluation on import commit, Procore version creation, and manual rerun.
- Default profile: `dcma_14_point_plus_gao`.
- Persist runs, per-metric results, findings, and scorecards keyed by `schedule_version_key` and `schedule_table_id`.
- Mark metrics `not_measurable_missing_data` when baseline/CPLI/BEI/authoritative critical-path data is absent.
- Gate cost weighting on a completed latest scorecard.

## Guardrails

- Not forensic delay analysis; no entitlement, liability, or compensability determinations.
- Read canonical DB tables only after commit.
- Redacted error codes on failure; no stack traces in API/UI.

## Profiles

| ID | Methods |
|---|---|
| `dcma_14_point` | DCMA 14-point metric families |
| `gao_schedule_best_practices` | GAO category checks |
| `aace_cpm_source_validation` | AACE source/update integrity |
| `dcma_14_point_plus_gao` | Composite default |