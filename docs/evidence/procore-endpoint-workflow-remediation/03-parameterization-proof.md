# 03 — Endpoint Parameterization Remediation Proof

Prompt: `03_ENDPOINT_PARAMETERIZATION_REMEDIATION.md`. Implements the package's
**preferred architecture #1**: route the daily source-refresh Procore reads
through the canonical `EndpointAdapter` registry via `run_live_sync`, instead of
adding ad-hoc logic to the legacy `sync.py` request builder.

## What changed

| File | Change |
| --- | --- |
| `src/hb_assistant/procore/daily_refresh_plan.py` (new) | Pure planning/taxonomy module: maps the daily-refresh endpoint set to canonical adapter ids, classifies scope (company vs per-project), computes a bounded daily-log date window, and translates `run_live_sync` receipts to an operator status taxonomy. No I/O/HTTP/DB. |
| `src/hb_assistant/source_refresh/orchestrator.py` | `_procore_stage` now executes the canonical plan: dry-run emits a plan only (no live read); apply runs `run_live_sync` per endpoint/project and aggregates receipts. Legacy `run_sync` import removed. Reports `persistence_path="procore_live"` + canonical tables. |
| `tests/test_sources_refresh.py` | Updated to patch `run_live_sync` (was `run_sync`); asserts dry-run performs no live read, company-level `projects` runs once, and daily-log calls carry bounded dates. |

`procore/sync.py` and `procore_endpoint_contract.seed.yaml` are **unchanged** and
remain available behind the manual `procore sync run` CLI (legacy/compat role,
documented in `05`).

## Before / after request classification (no resolved Procore IDs)

| Endpoint (legacy → canonical) | Before (legacy `sync.py`) | After (canonical `run_live_sync`) | Result |
| --- | --- | --- | --- |
| `list-projects` → `projects` | `GET /rest/v1.1/projects` per project, no company context → **400** | `GET /rest/v1.0/projects` with company header, **run once per company**; other pilots `skipped_company_level_already_handled` | fixed |
| `list-change-events` → `change-events` | `GET /rest/v1.1/change_events`, no project/company → **400** | `GET /rest/v1.1/change_events?project_id=…` (flat + project_id query) per project | fixed |
| `list-invoices` → `subcontractor-invoices` | `GET /rest/v1.1/requisitions`, no project/company → **400** | `GET /rest/v1.1/requisitions?project_id=…` per project | fixed |
| `list-daily-logs` → `daily-log-*` (11 subtypes) | `GET /…/daily_logs`, no date window → **400** | `GET /…/daily_logs/<subtype>?start_date=&end_date=` bounded window (lookback 7d, ending brief date) per project | fixed |
| `list-punch-items` → `punch-items` | `GET /rest/v1.0/projects/{id}/punch_items` → **404** | `GET /rest/v1.1/punch_items?project_id=…` per project | fixed |
| `list-prime-contracts` → `prime-contracts` | `GET /rest/v1.0/projects/{id}/prime_contracts` → **404** | `GET /rest/v1.0/prime_contracts?project_id=…` per project | fixed |
| `list-rfis` → `rfis` | `GET /rest/v1.0/projects/{id}/rfis` (worked) | `GET /rest/v1.0/projects/{project_id}/rfis` per project | unchanged-correct |
| `list-submittals` → `submittals` | worked | `GET /rest/v1.0/projects/{project_id}/submittals` per project | unchanged-correct |
| `list-commitments` → `commitment-contracts` | worked | `GET /rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts` per project | unchanged-correct |
| `list-drawings` → *(no adapter)* | `GET /rest/v1.0/projects/{id}/drawings` → **404** | **never called**; classified `skipped_tool_not_enabled` | classified |

## Scope handling (acceptance criteria)

- **Company-level not run per project**: `projects` is fetched once; remaining pilots are explicitly `skipped_company_level_already_handled` (test: `test_sources_refresh.py::test_sqlite_upsert_counts_reported_apply` asserts exactly one `projects` call).
- **Flat + project_id query**: `change-events`, `subcontractor-invoices`, `prime-contracts`, `punch-items` send `project_id` as a query param via `_project_id_query_params` (handled inside `run_live_sync`).
- **Bounded date windows**: daily-log endpoints receive `start_date`/`end_date` (`daily_log_window`, default 7-day lookback). Never unbounded.
- **Parent/child**: daily refresh runs only top-level list endpoints; N+1 child fetching stays within `run_live_sync` and is not triggered by the daily plan.
- **Alias mapping**: legacy `list-*` ids are preserved on each `PlannedEndpoint.legacy_alias` and resolved to canonical adapters via `endpoints.get()` (`_BY_LEGACY`).

## Dry-run safety

In dry-run the orchestrator emits the plan (endpoint list + scope + `planned`/`skipped_tool_not_enabled`) and performs **no** live read — `run_live_sync` is never invoked (test asserts `patched["run_live_sync"] == []`). This is honest: a dry-run cannot fetch live data, and `run_live_sync` would otherwise fail-closed (`gate_blocked`) before any HTTP call when `HB_PROCORE_LIVE` is unset.

## Validation

- `ruff check` / `ruff format --check` / `mypy` clean on both changed modules.
- `pytest tests/test_sources_refresh.py tests/test_procore_sync_multi_project.py tests/test_scheduler_degraded_surfacing.py tests/test_procore_live_apply_fix.py` → all pass.
- Canonical live-sync suite (`-k "procore_live_sync or procore_repositories or procore_live_apply"`) → all pass.
- Pre-existing/environmental failures (local `config/config.yml` enables production live reads; `test_launcher_scheduler.py` production-default tests + one fastapi surface test) are documented in `08` — they fail identically on clean `main` and pass with the shipped default config.
