# 07 — API Contract Evidence

Four **read-only** GET endpoints surface the persisted CPM chain + DCMA evidence. All are
registered in `src/hb_assistant/construction/analytics/api.py` via `create_app(*, db_path)` and
backed by `_schedule_cpm_read_service()` → `ScheduleCpmReadService`.

```
GET /api/schedules/versions/{schedule_version_key}/cpm/summary
GET /api/schedules/versions/{schedule_version_key}/cpm/activities
GET /api/schedules/versions/{schedule_version_key}/cpm/longest-path
GET /api/schedules/versions/{schedule_version_key}/cpm/diagnostics
```

## Cross-cutting guarantees

- **Read-only:** GET routes drop the write/operator role dependency; the read service performs no
  writes. (Backend test `test_schedule_cpm_api.py` includes a read-only assertion that the run
  list is unchanged across the GETs.)
- **Source/computed separation:** responses carry `evidence_class: application_computed_cpm`,
  `source_export_evidence: separate`, and `source_critical_flags_used: false`; only the app-owned
  `_ACTIVITY_WHITELIST` fields are returned (no raw source critical/driving/float fields).
- **Missing data:** when no computed CPM exists for a version, the endpoint returns **HTTP 200**
  with `available: false` (not an error).
- **Unknown version:** `_enforce_version_project_scope(...)` yields **HTTP 404** for an
  unknown/foreign schedule version key.

## Per-endpoint

| Endpoint | Response shape (top-level) | Sample artifact |
| --- | --- | --- |
| `cpm/summary` | `schedule_version_key`, `available`, `runs{6 stages}`, `dcma_critical_path{...}`, `missing_dependency_reasons`, `evidence_class`, `source_export_evidence` | `artifacts/api-cpm-summary-sample.json` |
| `cpm/activities` | `available`, computed activity rows (whitelisted fields) | `artifacts/api-cpm-activities-sample.json` |
| `cpm/longest-path` | `available`, `path_id`, ordered path activities (45) | `artifacts/api-cpm-longest-path-sample.json` |
| `cpm/diagnostics` | `available`, graph diagnostics (52), node/edge/acyclic | `artifacts/api-cpm-diagnostics-sample.json` |

All four sample files parse as valid JSON and show `available: true` for the evaluated schedule
(verified with `python -m json.tool`). A second copy keyed by version is under
`artifacts/api-samples/tropical-1071-2026-06-23-0800-*.json`.

## Runtime / configuration finding — `create_app(db_path=...)`

A real evaluation finding (not a CPM computation failure):

- **`create_app()` with no `db_path`** leaves `app.state.db_path = None`, so a normal uvicorn
  factory launch reads no DB and the CPM summary returns **`available: false`** even though the
  evidence DB contains the full CPM chain (see
  `artifacts/debug-api-cpm-summary-current-ui-version.json` and
  `artifacts/debug-create-app-db-path.txt`).
- **`create_app(db_path="/tmp/hb-schedule-cpm-evaluation.sqlite")`** (via
  `artifacts/run-evidence-api.py`) correctly binds the evidence DB and returns
  **`available: true`** (see
  `artifacts/debug-api-cpm-summary-explicit-db-runner.json` and
  `artifacts/api-cpm-summary-sample.json`).

**Condition for Phase 9 / future:** evidence/runtime API launches must use explicit
`create_app(db_path=...)`, **or** a future patch must make `create_app()` honor
`HB_ASSISTANT_DB_PATH`. This is carried as a readiness condition in docs 00 and 12.

> Note: `artifacts/run-evidence-api.py` (and the other `capture-*.py` scripts) are **evidence
> helpers inside this package**, not product/runtime code, and must not be staged as a repo
> runtime change.
