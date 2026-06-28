# Frontend Surfacing — Phase 9A.2 (Schedule Health Cockpit Layout)

Branch `feat/schedule-health-cockpit-9a2`, stacked on 9A.1 (`8a62c3c8`). **Frontend-only**; no
backend/API/route/schema change (`git diff --stat` touches only `frontend/`).

## What changed
`frontend/src/pages/ScheduleQualityPage.tsx` was reorganized from a flat 915-line scorecard page
into a **thin composer (189 lines)** that renders extracted cockpit panels in tiered order. The
~40 derived values are computed once via `buildHealthModel()` and passed to thin panels (no
duplicated derivation, behavior identical).

## New directory `frontend/src/components/schedule/health/`
| File | Lines | Role |
| --- | --- | --- |
| `healthShared.tsx` | 429 | 18 pure helpers + `QualitySummary` type + `buildHealthModel()` (derived-model builder) |
| `healthCards.tsx` | 48 | `HealthCard`, `CapabilityList` primitives (split out so react-refresh stays happy) |
| `ScheduleHealthProvenanceBadge.tsx` | 50 | evidence-basis pill (source_export / application_computed_cpm / quality_metric / baseline_crosswalk / identity_safe_version_diff / derived_read_model / deferred / …) |
| `ScheduleHealthOverview.tsx` | 143 | version-identity strip + limited-health banner + 7 top cards |
| `ScheduleHealthCpmPanel.tsx` | 73 | **CPM Intelligence shell** (availability + run-chain pills + link) |
| `ScheduleHealthEvidencePanel.tsx` | 87 | Available Schedule Evidence + Critical Path and Float Evidence |
| `ScheduleHealthQualityPanel.tsx` | 127 | DCMA 14-Point + Supplemental Source Checks + GAO/AACE |
| `ScheduleHealthBaselinePanel.tsx` | 67 | Baseline Health |
| `ScheduleHealthVersionComparisonPanel.tsx` | 75 | What Changed Since the Prior Schedule? |
| `ScheduleHealthActionQueue.tsx` | 44 | Findings (prioritized review list) |
| `ScheduleHealthDeferredPanel.tsx` | 31 | Unavailable / Deferred Analysis |

## Cockpit section order (tiered: executive → PM → scheduler)
1. Provenance legend (one line)
2. **Overview** (identity strip, limited-health banner, 7 cards)
3. **Computed CPM Intelligence** (shell — new)
4. Available Schedule Evidence + Critical Path/Float (source-export)
5. DCMA / Supplemental / GAO-AACE (quality)
6. Baseline Health
7. What Changed (version-comparison readiness)
8. Findings (action queue)
9. Unavailable / Deferred Analysis

## Provenance badges
Each cockpit section header carries a `ScheduleHealthProvenanceBadge` so Source-export and
Application-computed CPM evidence are never conflated. Application-computed CPM is the only
`application_computed_cpm` basis; everything else is source/quality/baseline/diff/derived. A
one-line legend above the cockpit explains the badges.

## CPM Intelligence shell (rich render deferred to 9A.3)
Reads `health.computed_cpm_health` (9A.1 envelope). Shows: an Application-computed-CPM badge; an
available/unavailable state; a compact 6-kind run-chain availability row; and a link to
`computed_cpm_health.links.computed_cpm` (`/schedules/cpm?version=…`). It does NOT render the
stepper/longest-path table/criticality-float cards — that is Phase 9A.3.

## Behavior preservation
All existing routes (`/schedules/quality`, `/schedules/health`), the two `useQuery` calls, the
rerun `useMutation`, the pickers, and the `?project=&version=&compare=` params are unchanged. Every
test-asserted heading/text string is preserved verbatim.

## Validation
`npm run typecheck` clean; `ScheduleQualityPage.test.tsx` 6/6 (4 original assertions intact + 2 new
CPM-shell/provenance); `eslint` on the page + all new `health/*` files clean; full frontend suite
340 passed / 3 failed (the 3 are pre-existing `TodayPage`/`MyItemsPage` reds, unrelated — they
import no Schedule Health files). See `test-output.txt`.
