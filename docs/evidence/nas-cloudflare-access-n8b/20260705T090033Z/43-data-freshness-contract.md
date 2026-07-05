# 43 — Data Freshness Contract — design/gap

## Goal
Every client can query freshness so stale second-brain data is visible, not hidden.

## EXISTS
`source_index_status` (`obsidian_mcp`) already computes rich freshness — index/watcher status, `sources_total`, `queued_count`, `error_count`, `stale_note_count`, `last_indexed_at`, generation state, `_freshness()` on search results — **but it is currently blocked on the NAS surface** (`NAS_OBSIDIAN_BLOCKED`). `hb_mcp_status` exposes profile/roots/allowlist. `run-registry-status` / `write_readiness` exist but are CLI/HTTP, not MCP tools.

## GAP (later sub-phase)
A unified, read-only NAS freshness tool set:
- `hb_status`, `hb_data_freshness`, `hb_queue_status`, `hb_recent_failures`, `hb_last_successful_runs`, `hb_capability_mode`.
Fields: last successful source ingestion / watcher run / queue drain / vault scan / daily brief / Graph-email sync / Procore sync; DB schema version; active source roots; queue depth; failed jobs since last success; safe mode status; capability tier mode; last AI Outputs mutation (from `mutations.jsonl`).

Implementation path: **unblock a read-only projection of `source_index_status`** on the NAS surface (it is a read tool; safe to expose) + a thin `hb_data_freshness` wrapper. No new data source needed.

## Verdict
Data + a rich (currently-blocked) status tool EXIST; exposing a bounded read-only freshness tool set on the NAS surface = GAP for a later sub-phase.
