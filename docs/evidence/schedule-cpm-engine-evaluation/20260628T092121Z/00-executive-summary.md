# 00 — Executive Summary

## Coordinates

- **Branch:** `docs/schedule-cpm-engine-evaluation-20260628T092114Z`
- **HEAD:** `f2916c21` (== `origin/main`; Phases 1–8 merged) — Merge PR #177 (Phase 8)
- **Evaluation package:** `docs/evidence/schedule-cpm-engine-evaluation/20260628T092121Z/`
- **Evidence DB:** `/tmp/hb-schedule-cpm-evaluation.sqlite` (schema v89)
- **Evaluated schedule:** `tropical|1071|2026-06-23 08:00` — package `TWN.zip`, current schedule
  `TWNU19` (`primavera_xer`), 1507 activities / 3921 relationships / 215 WBS.

## CPM capability (what works)

The Schedule CPM engine computes a full six-stage critical-path chain over an imported schedule —
graph diagnostics → forward pass → backward pass → float → longest path → criticality — and
persists each run with provenance. On the evaluated schedule the chain computes 1507 activities
per stage and extracts a 45-activity longest path. The **DCMA critical-path metric is measurable**
on the **application-computed CPM only** (status `available_app_cpm_recalculated`, basis
`application_computed_cpm`, `source_critical_flags_used: false`); source-only schedules remain
`not_measurable_requires_recalculation`. The computed chain + DCMA evidence + provenance are
surfaced read-only via four API endpoints and a "Computed CPM" frontend page.

## Not yet implemented (what this is not)

This package proves the **engine and its surfacing**, not PM-facing product. There is no
schedule storytelling / narrative, no version-diff narrative, and no causal / root-cause delay
analysis (that is Phase 9). The DCMA metric is **evidence-based, not a certification** — no
"certified DCMA compliant" or "true / P6 critical path" claim is made. Read paths never recompute
CPM, and source-export evidence is kept separate from application-computed CPM.

## Top validation findings

- Backend: `scripts/test-schedule.sh` **314 passed / 2 deselected**; all per-file CPM test suites
  green (only expected external-fixture skips). Frontend: typecheck clean, `ScheduleCpmPage.test.tsx`
  **7/7**, CPM files eslint-clean. (Doc 09.)
- All four API CPM samples and the embedded DCMA block show `available: true` / `measurable: true`
  (docs 06, 07).
- **Runtime finding:** `create_app()` without `db_path` leaves `app.state.db_path = None`, so a
  factory launch shows `available: false` over a populated DB; explicit
  `create_app(db_path=...)` returns `available: true`. This is an evaluation/runtime-harness
  finding, **not** a CPM computation failure (docs 07, 08).

## Remaining risks

- The `create_app`/`db_path` runtime binding (above).
- `graph_diagnostics` reports a `not_implemented` status **label** for its diagnostics-only scope —
  correct behavior, misleading label for executives.
- The `computed_critical_outside_longest_path` caveat (1312 computed-critical vs 45 on the longest
  path) must be carried into any narrative.
- The working tree carried unrelated **obsidian_mcp WIP** (doc 01); the eventual commit must stage
  only the evidence directory. Stale `CLAUDE.md` ("no frontend") flagged for separate housekeeping.

## Final readiness conclusion

```
Ready with Conditions
```

Conditions before/during Phase 9 (detail in doc 12):

1. Backend evidence/runtime API launches must use explicit `create_app(db_path=...)`, or a future
   patch must make `create_app()` honor `HB_ASSISTANT_DB_PATH`.
2. The `graph_diagnostics` `not_implemented` status label should be reviewed before
   executive-facing presentation.
3. The `computed_critical_outside_longest_path` caveat must be carried into Phase 9 language.
4. Phase 9 must not claim legal / root-cause delay causation (or DCMA certification / "true P6
   critical path").

## Document index

`01` branch & stack · `02` repo-truth inventory · `03` schema & migrations ·
`04` CPM computation chain · `05` source-vs-computed field map · `06` DCMA integration ·
`07` API contract · `08` frontend surfacing · `09` test & validation · `10` sample-data walkthrough ·
`11` known limitations & risks · `12` Phase-9 readiness · plus `manual-ui-import-log.md`,
`ui-cpm-review-notes.md`, and `artifacts/`.
