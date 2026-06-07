# Settings endpoint response bodies (admin role, direct `:8000`)

Captured 2026-06-07. All return **HTTP 200** with valid, well-formed JSON — yet several corresponding
Settings panels render "could not be loaded / could not be saved" error states in the running (WIP) UI.
This is the core evidence for the **response-shape / frontend contract-handling** classification.

## `GET /api/settings/preferences` → 200
```json
{"theme":"dark","default_landing_page":"Today","show_daily_brief_on_today":true,
 "followed_projects":[],"note":"Preferences are local-first; persisted under Application Support (Prompt 20).",
 "guardrails":{"read_only":true,"local_first":true,"no_cli_shellout":true,"no_live_endpoint_calls":true,
 "no_external_writeback":true,"active_chat_routes":false,"chat_enabled":false}}
```
UI render: **red error** "Preferences could not be saved. The rest of the page remains advisory."
(no PATCH was issued; no failed network request recorded).

## `GET /api/settings/daily-brief` → 200
```json
{"surface":"analytics.daily_brief.status","state":"not_configured","label":"Not configured",
 "config":{"enabled":false,"platform":"other","output_folder":null,"file_pattern":"HB-Daily-Brief-*.md",
 "stale_threshold_minutes":1440,"show_on_today":true},
 "last_file":{"path":null,"mtime_utc":null,"size_bytes":null},"is_stale":false,"parse_warnings":[], …}
```
UI render (captured page text): "Daily Brief settings could not be loaded. The rest of the page remains advisory."

## `GET /api/settings/data-quality/summary` → 200
```json
{"status":"unknown","label":"Data Quality","last_updated_at":null,
 "message":"No approved source data has been collected yet.","admin_detail_available":true}
```

## `GET /api/settings/data-quality/detail` → 200
```json
{"surface":"analytics.settings.data_quality.detail","summary":{"status":"unknown","source_count":0},
 "sources":[],"attention_items":[],"advisory_notes":[…], "guardrails":{…}}
```
UI render: "Data Health could not be loaded. … Data Health details are not available for this role."
(role was `admin`; detail endpoint returns 200 for admin — see 07-backend-logs.md).

## `GET /api/settings/keywords` → 200
```json
{"note":"Manage via /projects/{project_key}/keywords (add/edit/disable/delete/explain). …",
 "guardrails":{…}}
```
UI render: "Project keywords could not be loaded. The rest of the page remains advisory."

## Network-level summary (Playwright, admin session, all 6 surfaces)
- 501 total responses captured; **0** with status ≥ 400; **0** request failures; **0** page errors.
- Console: only React Router v7 `future flag` warnings (benign).
- ⇒ The error states above are rendered **without any failed HTTP request** → client-side
  contract-handling, not a network/endpoint failure.
