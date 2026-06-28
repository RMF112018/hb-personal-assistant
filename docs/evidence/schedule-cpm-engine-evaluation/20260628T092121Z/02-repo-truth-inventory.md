# 02 — Repo Truth Inventory

Inventory of the files that make up the Schedule CPM engine, with each file's role
(**computes** / **persists** / **reads** / **renders** / **tests**). All paths verified present
on `HEAD` (`f2916c21`, == `origin/main`). Symbol references confirmed by `grep` against the live
files (see `artifacts/cpm-table-ddl.txt`).

## Backend — computation (`src/hb_assistant/construction/analytics/`)

| File | Role | Notes |
| --- | --- | --- |
| `schedule_cpm_graph.py` | computes | Graph diagnostics (nodes/edges/cycles); `graph_diagnostics` run |
| `schedule_cpm_forward_pass.py` | computes | Early start/finish forward pass; `forward_pass` run |
| `schedule_cpm_backward_pass.py` | computes | Late start/finish backward pass; `backward_pass` run |
| `schedule_cpm_float.py` | computes | Total/free float; `float` run |
| `schedule_cpm_longest_path.py` | computes | Longest path extraction; `longest_path` run |
| `schedule_cpm_criticality.py` | computes | Critical / near-critical classification; `criticality` run |
| `schedule_cpm_dcma_integration.py` | computes (pure) | `DcmaCriticalPathEvaluation` dataclass + `evaluate_dcma_critical_path_eligibility(...)`; no SQL, no source-field reads |
| `schedule_cpm_service.py` | orchestrates / reads | `ScheduleCpmGraphService` — chain run methods + read-only `evaluate_dcma_critical_path(svk)` |

## Backend — DCMA quality integration (`construction/analytics/`)

| File | Role | Notes |
| --- | --- | --- |
| `schedule_quality_engine.py` | computes / reads | `METRIC_STATUS_AVAILABLE_APP_CPM = "available_app_cpm_recalculated"`; `EvaluationContext.computed_cpm_critical_path`; loader `_load_computed_cpm_eligibility`; critical-path metric branch |
| `schedule_quality_posture.py` | computes | Additive readiness branch for the app-CPM-recalculated status |

## Backend — read / API (`construction/analytics/`)

| File | Role | Notes |
| --- | --- | --- |
| `schedule_cpm_read_service.py` | reads | `ScheduleCpmReadService` with `cpm_summary` / `cpm_activities` / `cpm_longest_path` / `cpm_diagnostics`; explicit app-owned `_ACTIVITY_WHITELIST`; no source fields |
| `api.py` | reads (HTTP) | 4 GET CPM routes under `/api/schedules/versions/{schedule_version_key}/cpm/*` + `_schedule_cpm_read_service()` factory; `_enforce_version_project_scope(...)` for 404 scoping |

## Backend — persistence (`src/hb_assistant/store/`)

| File | Role | Notes |
| --- | --- | --- |
| `schedule_cpm_tables.py` | persists (DDL) | CPM table definitions (370 lines) — `schedule_cpm_runs`, `schedule_cpm_activity_results`, `schedule_cpm_relationship_results`, `schedule_cpm_diagnostics`, `schedule_cpm_paths`, `schedule_cpm_path_activities` |
| `schedule_cpm_repository.py` | persists / reads | CPM run + result repositories; `get_criticality_run` helper; `ScheduleCpmDiagnosticsRepository` (reused by the read service) |
| `schedule_float_tables.py` | persists (DDL) | `METRIC_STATUS_CHECK_VALUES` includes `available_app_cpm_recalculated` (the v89-widened CHECK) |
| `migrator.py` | persists (schema) | `LATEST_SCHEMA_VERSION = 89`; `_reconcile_v89_metric_status_app_cpm(conn)` row-preserving rebuild of `schedule_quality_metric_results.status` CHECK |

## Frontend (`frontend/src/`)

| File | Role | Notes |
| --- | --- | --- |
| `pages/ScheduleCpmPage.tsx` | renders | "Computed CPM" tab — run-chain card, DCMA evidence card, longest-path panel, computed activity table; `?project=&version=` selection |
| `lib/api.ts` | reads (client) | 4 typed CPM client fns + types (CPM portion is merged Phase 8; file also carries unrelated obsidian_mcp WIP — see doc 01) |
| `app/routes.tsx` | renders | Route `schedules/cpm` → `<ScheduleCpmPage />`, title "Computed CPM" |
| `components/schedule/SchedulePageChrome.tsx` | renders | Nav entry `{ to: '/schedules/cpm', label: 'Computed CPM', icon: Workflow }` |

## Tests (`tests/` + `frontend/src/pages/`)

| File | Role |
| --- | --- |
| `tests/test_schedule_cpm_graph.py` | tests graph diagnostics |
| `tests/test_schedule_cpm_forward_pass.py` | tests forward pass |
| `tests/test_schedule_cpm_backward_pass.py` | tests backward pass |
| `tests/test_schedule_cpm_float.py` | tests float |
| `tests/test_schedule_cpm_longest_path.py` | tests longest path |
| `tests/test_schedule_cpm_criticality.py` | tests criticality |
| `tests/test_schedule_cpm_dcma_integration.py` | tests DCMA eligibility evaluator (pure) |
| `tests/test_schedule_cpm_api.py` | tests the 4 read-only CPM endpoints |
| `tests/test_schedule_critical_path_quality.py` | tests the computed-CPM quality metric branch |
| `frontend/src/pages/ScheduleCpmPage.test.tsx` | tests the Computed CPM page (7 tests) |

## CLAUDE.md drift (flagged, not changed)

Root `CLAUDE.md` states "No web service, frontend, or JS workspaces." This is **stale** — a
React 19 + Vite frontend exists at `frontend/`. Left unchanged (out of scope for this evidence
task); flagged here and in doc 11 as a housekeeping item for Bobby.
