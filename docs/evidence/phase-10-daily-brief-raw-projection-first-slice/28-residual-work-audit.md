# 28 — Residual-Work Audit

## In-scope acceptance criteria — status

| Criterion | Status |
|---|---|
| V49 projection runs safely on a DB copy and produces structured rows when raw exists | ✅ `07` (apply on copy: email 16,603 / thread 6,823 / calendar 138 structured) |
| `email_calendar_projection_runs` + `_coverage` populated on apply | ✅ migrator + engine receipts; `07`/`08` |
| Projection coverage reports zero unmapped business fields | ✅ `08` (`total_unmapped_business_fields = 0`, complete) |
| Calendar candidates persisted source-linked when useful events exist | ✅ `10` (persisted, 100% source-ref) |
| Procore candidates persisted from promoted ranked signals | ✅ `12` (promoted 2,095; persisted capped) |
| Suppressed Procore backlog diagnostic-only | ✅ ranking suppresses 3,817; 0 in executive rows |
| `candidate_source_refs` 100% for executive sections | ✅ `14` (overall/calendar/procore = 1.0) |
| Project-key coverage improves; unresolved are review-safe | ✅ in-window 100%; `__needs_review__` sentinel; identity backfill 0→6 (`13`) |
| Daily-run/status surfaces projection/candidate/coverage/gaps/verdict | ✅ `first_slice` block (`18`) |
| Known-bad (source rows, empty candidates) cannot be clean success | ✅ `16` (degraded; 4 reasons) |
| Empty email/follow-up surfaced as data gap | ✅ data-gap card; `18` |
| Production DB hash/size/mtime unchanged by this slice | ✅ `23` (no slice write path touched production) |
| No external writeback | ✅ `22` |
| Guard columns zero | ✅ `21` (32 cols, all 0) |
| No raw leak | ✅ `20` (0 findings) |
| New/updated targeted tests pass | ✅ `24` (15 new + affected suites) |
| Changed modules pass ruff/mypy/compile | ✅ `24` |

## Residual work remaining inside the first slice

**None.** Every in-scope acceptance criterion is satisfied and proven on a DB copy.

## Items intentionally outside this slice (documented, not residual)

- Semantic email→task/commitment follow-up extraction agent (readiness + data-gap only — SCOPE_LOCK).
- Procore due-date extraction from raw payloads (reported as data-quality gap).
- Wiring `ProjectIdentityBackfill` as a live daily-run stage (deterministic backfill + proof done;
  daily calendar resolution already 100% in-window via alias resolver).

These are next-slice candidates, each blocked only by scope, not by a stop condition.
