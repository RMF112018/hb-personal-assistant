# 02 — Endpoint Contract Matrix

Prompt: `02_ENDPOINT_CONTRACT_MATRIX.md`. Compares the legacy seed contract, the canonical `EndpointAdapter` registry, the active daily execution path, and live failure evidence.

## The core mismatch (made explicit)

- **Active daily path** = `source_refresh/orchestrator.py::_procore_stage` → `procore/sync.py::run_sync`, which loads `resources/config/procore_endpoint_contract.seed.yaml` and formats only `{company_id}`/`{project_id}` into the path, passing only `updated_after`. Its HTTP client does **not** supply the Procore company context the way the canonical client does, so company/flat endpoints get HTTP 400 "Missing Project or Company ID" and stale per-project routes get 404. Writes `procore_sync_*`.
- **Canonical path** = `procore/live_sync.py::run_live_sync` + `procore/endpoints.py` adapters. Correct routes, company-vs-project-vs-flat scope, `project_id` as a **query param** for flat endpoints (`_project_id_query_params`, `live_sync.py:530`), date windows (`start_date`/`end_date`, `live_sync.py:992`), pagination, normalizers, redaction, run tracking, watermarks. Writes `procore_live_*` — **the tables downstream consumers already read**.
- **DB proof**: `procore_synced_entities` holds only `list-rfis`/`list-submittals`/`list-commitments` (the 3 successes). Every failing legacy endpoint already has a healthy canonical equivalent in `procore_live_records` (`projects` 21, `change-events` 192, `subcontractor-invoices` 220, `punch-items` 4, `prime-contracts` 4, daily-log families) — except `drawings`, which has **no adapter** (0 rows).

## Matrix — the 10 daily-refresh endpoints

| legacy seed id | seed path (active daily) | live failure | canonical adapter id | canonical path | scope | required params (canonical) | persistence target | remediation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `list-projects` | `/rest/v1.1/projects` | **400** Missing Project or Company ID | `projects` | `/rest/v1.0/projects` | company-level (flat, no project_id) | company context (header) | `procore_live_records` | **fix** — route canonical; run **once per company** |
| `list-rfis` | `/rest/v1.0/projects/{project_id}/rfis` | success (603 rows) | `rfis` (`legacy=list-rfis`) | `/rest/v1.0/projects/{project_id}/rfis` | project (path) | project_id (path) | `procore_live_records` | **fix** — route canonical (already correct) |
| `list-submittals` | `/rest/v1.0/projects/{project_id}/submittals` | success (445 rows) | `submittals` (`legacy=list-submittals`) | same | project (path) | project_id (path) | `procore_live_records` | **fix** — route canonical |
| `list-commitments` | `/rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts` | success (137 rows) | `commitment-contracts` | `/rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts` | company/project (path) | company_id, project_id (path) | `procore_live_records` | **fix** — route canonical |
| `list-change-events` | `/rest/v1.1/change_events` | **400** Missing Project or Company ID | `change-events` | `/rest/v1.1/change_events` | flat + project_id query | project_id (query) | `procore_live_records` | **fix** — route canonical (project_id query) |
| `list-invoices` (**7th**) | `/rest/v1.1/requisitions` | **400** Missing Project or Company ID | `subcontractor-invoices` | `/rest/v1.1/requisitions` | flat + project_id query | project_id (query) | `procore_live_records` | **fix** — route canonical (project_id query) |
| `list-prime-contracts` | `/rest/v1.0/projects/{project_id}/prime_contracts` | **404** | `prime-contracts` | `/rest/v1.0/prime_contracts` | flat + project_id query | project_id (query) | `procore_live_records` | **fix** — route canonical flat route |
| `list-punch-items` | `/rest/v1.0/projects/{project_id}/punch_items` | **404** | `punch-items` | `/rest/v1.1/punch_items` | flat + project_id query | project_id (query) | `procore_live_records` | **fix** — route canonical flat v1.1 route |
| `list-daily-logs` | `/rest/v1.0/projects/{project_id}/daily_logs` | **400** Start/End Date required | `daily-log-*` (11 subtypes) | `/rest/v1.1/projects/{project_id}/daily_logs/<subtype>` | project (path) + **date window** | project_id (path), start_date, end_date | `procore_live_records` | **fix** — route canonical subtypes with **bounded** dates |
| `list-drawings` | `/rest/v1.0/projects/{project_id}/drawings` | **404** | *(none — no adapter; 0 live rows)* | n/a | n/a | n/a | none | **classify** `skipped_tool_not_enabled` (no generic error) |

### Canonical daily-log subtypes (replace `list-daily-logs`)
`daily-log-weather`, `daily-log-manpower`, `daily-log-notes`, `daily-log-deliveries`, `daily-log-inspections`, `daily-log-dcrs`, `daily-log-dumpster`, `daily-log-delays-review-routed`, `daily-log-accident-review-routed`, `daily-log-safety-violation-review-routed`, `daily-log-visitor` — all `live_verified=True`, path `/rest/v1.1/projects/{project_id}/daily_logs/<log>`, date-windowed.

## Required findings — confirmed

- ✅ `sync.py` uses the seed contract, formats only `{company_id}`/`{project_id}`, passes only `updated_after`.
- ✅ `live_sync.py` has richer adapter metadata, query-param handling (`_project_id_query_params`), date-window hooks, run tracking (`procore_live_sync_runs`), watermarks (`procore_live_sync_watermarks`), and projection hooks.
- ✅ Several failing endpoints (`punch-items` flat v1.1, `prime-contracts` flat, `change-events`/`subcontractor-invoices` project_id-query) have correct canonical adapters where the seed is stale/wrong.

**Conclusion:** route daily-source-refresh through the canonical adapters via `run_live_sync`; classify `list-drawings` as unsupported. This is detailed in `03`.
