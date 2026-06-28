# 10 — Sample Data Walkthrough

End-to-end trace for the real imported schedule.

| Attribute | Value |
| --- | --- |
| Project | `tropical` |
| Imported package | `TWN.zip` (zip_package) |
| Schedule version key | `tropical\|1071\|2026-06-23 08:00` |
| Selected current schedule | `TWNU19` (file `TWNU19-wBL.xer`) |
| Source format | `primavera_xer` |
| Activities / Relationships / WBS | 1507 / 3921 / 215 |

## 1. Package import (UI)

`TWN.zip` was imported through the frontend UI; the import selected the XER current schedule and
persisted package metadata in `schedule_import_packages`. Evidence:
`manual-ui-import-log.md`, `artifacts/import-package-evidence.txt`,
`artifacts/import-package-manifest.json`, `imported-schedule-version-keys.txt`.

## 2. Migration

The copied evidence DB was migrated **82 → 89** (`artifacts/apply-evidence-db-migrations-output.txt`),
creating the CPM tables and the v89 quality-metric status widening. Schema `MAX(version)` in the
evidence DB = 89 (`artifacts/table-count.txt`).

## 3. CPM chain execution

The six-stage chain was run and persisted (`artifacts/run-cpm-chain-for-imports.py`,
`artifacts/cpm-chain-run-output.json`). Run verification
(`artifacts/cpm-run-verification.txt`) shows graph_diagnostics (`not_implemented`, diagnostics
only), forward/backward/float/criticality each computing 1507 activities, and longest_path
producing a 45-activity path. Run IDs and dependency wiring are in doc 04.

## 4. API evidence

With the backend created explicitly as `create_app(db_path="/tmp/hb-schedule-cpm-evaluation.sqlite")`,
the 4 read-only endpoints return `available: true` (doc 07;
`artifacts/api-cpm-{summary,activities,longest-path,diagnostics}-sample.json`).

## 5. DCMA evidence

`evaluate_dcma_critical_path("tropical|1071|2026-06-23 08:00")` →
`measurable: true`, basis `application_computed_cpm`, status `available_app_cpm_recalculated`,
caveat `computed_critical_outside_longest_path`, `source_critical_flags_used: false`
(`artifacts/dcma-computed-cpm-sample.json`; doc 06).

## 6. UI evidence

The Computed CPM page surfaced the chain after the explicit-DB backend restart (doc 08;
`ui-cpm-review-notes.md`). Before the explicit-DB restart it showed "No computed CPM yet" — the
`create_app`/`db_path` runtime-binding finding (docs 07, 11, 12).

## Provenance line (one sentence)

`TWN.zip` (UI import) → `schedule_import_packages` → evidence DB migrated 82→89 → six-stage CPM
chain persisted → DCMA measurable on application-computed CPM only → surfaced read-only via 4 API
endpoints and the Computed CPM page, **without using any source critical flags**.
