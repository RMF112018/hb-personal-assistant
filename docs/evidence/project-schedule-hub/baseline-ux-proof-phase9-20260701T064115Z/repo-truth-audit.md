# Phase 9 Repo-Truth Audit — Baseline UX Proof

**Audit date:** 2026-07-01  
**Base commit:** `c2b4f70230990d850e521888eb7c1237dba1c345`  
**Branch:** `feature/schedule-baseline-ux-proof-phase9-20260701T064115Z`

## Phase 8 prerequisite: PRESENT

Phase 8 merged at `76dc7449` (included in current main). Resolver, named workbench GET, driver detail, controls links, read-only named preview, POST rejection, workbench `invalid_comparison_basis` all present.

## Phase 9 amendment: controls no-silent-fallback

**Pre-Phase 9 gap:** `GET /schedule/controls` used `normalize_controls_comparison_basis()` which coerced unknown values to `prior_update`.

**Phase 9 fix:** Align with workbench/driver — unknown → `400 invalid_comparison_basis`; omitted → default `prior_update`; `baseline` remains BC whitelist.

## Route map (post-Phase 9 target)

| Route | Accepted basis | Unknown | Omitted |
|---|---|---|---|
| `GET /schedule/controls` | `prior_update`, named slots, `baseline` | `400 invalid_comparison_basis` | `prior_update` |
| `GET/POST /schedule/review-items` | workbench set | `400 invalid_comparison_basis` | `prior_update` |
| `GET /schedule/drivers/.../detail` | workbench set + dual param | `400` | `prior_update` |

## baseline_context shape drift

| Field | Controls | Workbench/Driver |
|---|---|---|
| Version key | `baseline_schedule_version_key` | `schedule_version_key` |
| Display | `baseline_display_name` | `display_name` |

Frontend normalizer planned; no backend schema change.

## UX gaps (proof targets)

- Hub "Open Workbench" omits `comparison_basis`
- Workbench basis toggle does not update URL
- Driver unavailable back link drops `as_of`
- `ScheduleBaselineSelector` shows raw version key in primary line
- Driver header shows raw enum not slot label

## Out of scope

Disposition persistence, V90/named sync, parser/CPM/import/trends, broad redesign.
