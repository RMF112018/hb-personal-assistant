# 244 — Scheduled Refresh Graph Email/Calendar Integration

Status: Active · Manifest: Scheduled Refresh Graph Email/Calendar Integration v1

## Context

The production 20:00 `daily-source-refresh` job already runs through the repo scheduler:
`hb-assistant scheduler run daily-source-refresh --environment production --if-due`. This change keeps
that launchd command shape unchanged and wires Graph email/calendar raw refresh into the same
in-process source-refresh orchestrator that runs Procore sync and projection.

Production local config now enables the Graph live-read gate alongside Procore:
`enable_live_reads=true`, `enable_procore_live_reads=true`, and `enable_graph_live_reads=true`.
The tracked example config remains conservative by default.

## Behavior

The orchestrator stage order is:

`preflight -> procore_sync -> procore_projection -> graph_email_calendar_raw_ingestion -> email_calendar_projection -> aggregate/rebuild`

Graph raw ingestion reuses the existing read-only indexers:

- `EmailMessageIndexer.index(..., include_raw_content=True)`
- `CalendarEventIndexer.index(..., include_raw_content=True)`

The V49 projection stage reuses `run_email_calendar_projection_stage(db_path=..., apply=...)` and is
invoked only after the Graph stage has returned. `procore_only` skips both Graph and V49 email/calendar
projection with explicit reason `procore_only`; `graph_only` skips Procore sync and Procore projection
with explicit reason `graph_only`.

Graph failures are isolated. A Graph auth/refresh/projection degradation marks the overall run
`degraded` while preserving any successful Procore sync/projection status in the same receipt.

## Receipts

Scheduled receipts now include raw-free:

- `graph_sync_summary`
- `email_calendar_projection_summary`
- counts by raw/structured table family
- freshness timestamps
- Graph auth classification
- per-stage skipped/degraded reason codes

Receipts and evidence are counts/statuses only. They must not include raw bodies, HTML, join URLs, full
recipient lists, tokens, prompts, model responses, or raw Procore payloads.

## Safety

Graph remains read-only. The scheduler uses read-only Graph clients and tests fail if send, draft,
update, delete, calendar mutation, or external writeback paths are invoked.

Dry-run performs no DB writes and suppresses full raw-body/full-event fetches. Apply writes only to the
resolved local SQLite DB path supplied by the active profile/config, so validation can point
`HB_PA_CONFIG` at a `/tmp` Application Support copy.
