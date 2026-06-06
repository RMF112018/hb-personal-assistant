# 174 — FastAPI Sync Governance (Prompt 06)

**Objective:** complete the admin-only first-live-sync approval and per-project schedule (cadence/priority/rate) flow, add low-friction user "request refresh" surfaces, and provide automatic freshness status derived from local sync state. This fulfills the explicit Prompt 06 requirement and the high-level contract in `07_AUTOMATED_SYNC_AND_FRESHNESS.md` (admin-only first sync to protect rate limits; users request refresh; admin sets cadence/priority; UI shows "refreshed X minutes ago", "next scheduled", pending markers).

## Route Inventory (added/extended in Prompt 06)

Existing foundation from Prompt 04 (still present):
- `POST /admin/connections/{connection_id}/approve-first-sync` (admin) — flips pending → approved_first_sync_not_started on local source sync state.
- `POST /admin/projects/{project_key}/sync-schedule` (admin) — records schedule intent; now enhanced to persist cadence into location.sync_frequency_minutes and richer status marker including priority/rate_limit.

New in Prompt 06:
- `POST /projects/{project_key}/refresh-request` (operator+) — low-friction CM-user action that marks the project's sources with sync_status="user_refresh_requested". Does not start sync; admin can observe/fulfil via schedule or approval flows.
- `GET /projects/{project_key}/sync-freshness` (viewer+) — automatic, local-only freshness surface. Returns per-source last_successful/last_attempted, computed minutes_ago, coarse label (fresh/stale/never), and current sync_status marker. Overall project freshness aggregated.
- `GET /admin/sync/pending-approvals` (admin) — lists sources/connections carrying pending_admin_approval, schedule_pending_admin, or user_refresh_requested markers (with project and last timestamps). Purely local scan.

All surfaces reuse the ConnectionSetupService (extended for 06) and existing store tables (construction_source_locations + construction_source_sync_state and siblings for email/calendar). No new schema migration.

## Approval & Schedule Flow (admin-only)

- New connection sources start with first_sync_status = "pending_admin_approval" (or "excluded").
- Admin calls approve-first-sync → local state becomes "approved_first_sync_not_started". first_sync_triggered remains false (never starts a crawler from the UI shell).
- Admin calls sync-schedule with cadence_minutes/priority/rate_limit/scope → 
  - sync_state.sync_status updated to "schedule_pending_admin:cadence=XX;priority=YY;rate=..." (or similar) for the project's sources.
  - source_location.sync_frequency_minutes updated from cadence (the table already supports the field; used by future automation).
- User (operator+) can call refresh-request on an approved project → sets "user_refresh_requested" marker. This is observable by admin in pending-approvals or via freshness.

No non-admin can trigger first live sync or heavy historical pulls. Guardrails continue to assert "first_sync_triggered": false.

## Freshness & User Refresh (low-friction + automatic)

- Freshness is computed in-process from last_successful_sync_utc / last_attempted_sync_utc in the local *_sync_state rows (plus the governance status marker).
- Labels: "fresh" (<60m), "stale" (>=60m or never after first approval), "never".
- "Data refreshed N minutes ago" and schedule intent are carried in the response for UI badges (Today, Projects, Admin/Data Confidence).
- User refresh request is intentionally a request, not a trigger — it surfaces the user's intent for admin scheduling or for future local orchestrator to pick up under admin policy.

## Local Persistence (reuse, no additive migration for Prompt 06)

- All writes are to pre-existing V5/V6-era tables: construction_source_*_locations and *_sync_state (plus email/calendar variants for Microsoft scopes).
- Status strings are used as the governance bus for pending/approved/requested/schedule markers (simple, no new columns needed for MVP governance).
- sync_frequency_minutes on locations is populated from admin cadence for downstream (automation) use.
- No raw content, tokens, or source payloads; only timestamps, counts, and redacted error strings (pre-existing guard columns on the tables remain 0).

The service continues to fail-closed: missing sources → "requires_read_model"; bad roles → 403; never calls live Graph/Procore or the CLI.

## Guardrails

Every response carries the (extended) guardrails from ConnectionSetupService:
- local_setup_only, no_cli_shellout, no_live_endpoint_calls, no_external_writeback, tokens/secrets never returned, first_sync_triggered=false,
- plus new: user_refresh_requests_supported, freshness_computed_from_local_sync_state.

Role model (from roles_permissions.json + 03 doc):
- CM user / operator: can_request_refresh (the refresh-request POST), can view freshness.
- Admin: all of the above + approve, schedule cadence/priority, list pending approvals.
- Viewer: read-only (freshness, list keywords etc.); cannot request or mutate governance state.

## Validation

- New dedicated test: `tests/test_fastapi_analytics_sync_governance.py` (FastAPI-gated, mirrors connection/keywords test style: (client, db) helper, FORBIDDEN + _assert_safe, operator can request (marks state), viewer can read freshness, admin-only for pending list, 403 on wrong role, store inspection of status flips, safe payloads).
- `tests/test_fastapi_analytics_app_shell.py` updated with the three new paths in the exact OpenAPI set equality.
- Existing analytics tests (service boundary, connection setup, keywords, auth) continue to pass (additive methods only; no behavior change to prior routes).
- Post-edit verification (see run log in session): targeted pytest, safe subset, ruff, mypy (analytics + store), no lints, schema smoke (V40 from Prompt 05 still applies cleanly; no new V for 06).

## Cross-References

- Prompt: `docs/planning/fastapi-analytics-dashboard-implementation-package/prompts/Prompt_06_SYNC_GOVERNANCE.md`
- Spec: `.../07_AUTOMATED_SYNC_AND_FRESHNESS.md`
- Implementation sequence: `.../17_IMPLEMENTATION_SEQUENCE.md` (Phase UI-06)
- Backend design: `.../09_FASTAPI_BACKEND_DESIGN.md` (admin sync/health surfaces)
- Roles: `.../resources/json/roles_permissions.json` (can_request_refresh vs admin-only first-sync)
- Predecessor notes: 172 (connection setup), 173 (keywords), this note records the governance completion.

This change is additive to the optional analytics-ui surface, strictly local-first and metadata-only, and preserves all prior guardrails and the "no first-sync trigger for non-admins" contract. No frontend, no live data, no schema impact beyond what Prompt 05 already applied.