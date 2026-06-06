# MCP Daily Brief Handoff Tool — hb_daily_brief_packet

**Phase:** 09 Addendum — Daily Brief / MCP Handoff & Rendering · **Prompt:** 02
**Generated (UTC):** 2026-06-06T10:09:12.421412+00:00 · **repo_sha:** 8532e8268c21e481da78f36c6f914a6724c10ffd

## Purpose

Expose the approved, metadata-only `DailyBriefHandoffPacketV1` (Prompt 01) through **one** narrow MCP workflow-wrapper tool, for Claude scheduled rendering only. The tool reuses the Prompt 01 packet builder; no retrieval/DB/vector/Graph/Procore logic lives in MCP.

## Tool

- name: `hb_daily_brief_packet` (repo `hb_*` convention; maps to suggested `construction_daily_brief_packet` / `get_daily_brief_handoff`)
- wrapper: `mcp_daily_brief_packet_wrapper` · risk: low · receipt_required: True
- allowed tool count (registry): 10

## Inputs

- `date` — optional, default local today
- `project_scope` — optional, default `all`
- `include_rendering_instructions` — optional, default true

## Output

Returns `DailyBriefHandoffPacketV1` at `result.results[0]`. Does not return raw rows, raw source payloads, raw retrieved context, vector results, or direct DB query results.

## MCP policy (enforced)

- workflow_wrapper_only: True
- read_only: True
- local_first: True
- metadata_only: True
- source_linked: True
- no_raw: True
- no_writeback: True
- no_final_determination: True
- no_direct_graph_procore_db_vector: True

## Deny-first preserved

Anything not in the allowlist (memory mutation, vector search, daily-brief apply) is denied as tool_not_allowed; explicit DB/Graph/Procore/writeback actions remain denied; denied tokens in arguments are denied.

## Representative dispatch (controlled, metadata-only inputs)

- decision: allowed · output_classification: daily_brief_handoff_packet · source_count: 6
- packet_id: `dbp_2d348570c8e5cdc2398de1e1bf09902e` · packet_version: DailyBriefHandoffPacketV1 · project_scope: P1
- section counts:
  - recent_changes: 3
  - review_required_items: 1
  - aging_watchlist: 1
  - meeting_prep: 0
  - risk_watchlist: 1
  - stale_or_low_confidence_warnings: 2
  - accepted_memory_context: 1

## CLI / Proof

```bash
hb-assistant second-brain mcp daily-brief-handoff-proof --json
hb-assistant second-brain mcp audit --json
hb-assistant second-brain mcp no-raw-access --json
hb-assistant second-brain mcp no-writeback --json
```

