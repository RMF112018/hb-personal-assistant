# Phase 9A.3 — Computed CPM Intelligence frontend surfacing

Branch: `feat/schedule-health-computed-cpm-9a3` (off `feat/schedule-health-cockpit-9a2`).
Frontend-only. No backend/API/route/schema change. Read-only render of the 9A.1
`computed_cpm_health` envelope.

## What changed (5 files)
- `components/schedule/health/ScheduleHealthCpmPanel.tsx` — shell → rich render: run-chain
  badges (kept) + computed activity counts (total/critical/near-critical/noncritical/longest-path
  members), computed longest-path summary (start→end activity IDs, member count, duration, path
  total float), DCMA critical-path metric availability/measurability, and a non-suppressed caveats
  block (notably `computed_critical_outside_longest_path`). Null-safe; falls back to "—".
- `components/schedule/health/healthShared.tsx` — adds `computedCpmAvailable` to `HealthModel`
  (`health.computed_cpm_health?.available === true`); `criticalPathDetail` now reads
  "Application-computed CPM available…" when computed CPM is available.
- `components/schedule/health/ScheduleHealthOverview.tsx` — the global info-strip banner shows
  "CPM: Application-computed CPM available" instead of `CPM_RECALCULATION_BANNER`
  ("CPM recalculation: not implemented") when computed CPM is available.
- `components/schedule/health/ScheduleHealthDeferredPanel.tsx` — the "CPM recalculation:" line
  shows "Application-computed CPM available" instead of "Deferred" when computed CPM is available.
- `pages/ScheduleQualityPage.test.tsx` — +5 tests (rich render; global copy override; source-export
  stays separate; caveats not suppressed; legacy deferred copy retained when unavailable).

## Before → after (PM-facing CPM copy)
| Location | available=false (unchanged) | available=true (9A.3) |
|---|---|---|
| Overview info strip | "CPM recalculation: not implemented" | "CPM: Application-computed CPM available" |
| Critical path confidence card | "CPM recalculation is deferred; …source-export…" | "Application-computed CPM available. Source critical-path evidence is reported separately below." |
| Unavailable/Deferred list | "CPM recalculation: Deferred" | "CPM recalculation: Application-computed CPM available" |
| Computed CPM Intelligence section | shell: "No application-computed CPM is available" | rich: counts + longest path + DCMA metric + caveats + "View Computed CPM" link |

## Source-export separation (acceptance)
The source-export "Critical Path and Float Evidence" section (EvidencePanel) is untouched and
still renders independently. The computed section carries the `Application-computed CPM` provenance
badge; the source section carries `Source-export`. Verified by the
"keeps source-export critical-path evidence separate from computed CPM" test.

## Run-chain agreement (acceptance)
Both Schedule Health (this section) and the Computed CPM tab read the same `computed_cpm_health` /
CPM read services; the section links to `/schedules/cpm?version=…` using the backend-provided
`links.computed_cpm`.

## DOM evidence
`ui-test-output.txt` — `ScheduleQualityPage.test.tsx` 11/11 pass (the rendered DOM is asserted in
each test). Full suite: 345 passed, 3 failed — the 3 are pre-existing, unrelated
`TodayPage`/`MyItemsPage` reds documented in the 9A.2 commit (340→345 = +5 new 9A.3 tests; same 3
reds). typecheck (`tsc -b`) clean; eslint clean on changed files.

## API sample (available: true)
`api-sample-computed-cpm-health.json` — real read-only output of `ScheduleHealthCpmService` against
the live DB for `tropical|1071|2026-06-23 08:00` and `tropical|24836|2026-06-23 08:00`. Both
`available: true`. For 1071: 1507 computed activities, 1312 computed-critical, 45 longest-path
members (start `DELAY-MSTPERMIT-10` → end `FM-FINCOMP`, duration 429 d, path total float −296 d),
DCMA metric available+measurable, caveat `computed_critical_outside_longest_path` present (1312
critical ≫ 45 on longest path → parallel critical chains). Every field name read by the panel is
confirmed against this live sample.
