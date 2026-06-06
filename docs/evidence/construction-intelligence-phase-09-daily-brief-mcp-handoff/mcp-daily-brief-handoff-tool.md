# MCP Daily Brief Handoff Tool — hb_daily_brief_packet

**Phase:** 09 Addendum — Daily Brief V2 Executive Utility Hardening · **Prompt:** 03
**Generated (UTC):** 2026-06-06T14:29:57.167575+00:00 · **repo_sha:** 3965ccb05aebb83bde430651a3896ddcdff77d64

## Purpose

Expose the approved, metadata-only `DailyBriefHandoffPacketV2` through **one** narrow MCP workflow-wrapper tool, for Claude scheduled rendering only. The tool reuses the V2 packet builder; no retrieval/DB/vector/Graph/Procore logic lives in MCP. Claude renders only `render_payload`; `governance_metadata` is never rendered into the brief.

## Tool

- name: `hb_daily_brief_packet` (repo `hb_*` convention; maps to suggested `construction_daily_brief_packet` / `get_daily_brief_handoff`)
- wrapper: `mcp_daily_brief_packet_wrapper` · risk: low · receipt_required: True
- allowed tool count (registry): 10

## Inputs

- `date` — optional, default local today
- `project_scope` — optional, default `all`
- `include_rendering_instructions` — optional, default true (drops `governance_metadata.rendering_instructions` when false)

## Output

Returns `DailyBriefHandoffPacketV2` at `result.results[0]`: a user-facing `render_payload` (brief_date, portfolio_scope, yesterday, today_agenda, next_7_days, schedule, rfis, submittals, punch, procurement, needs_attention, focus_recommendations, project_signals, email_activity, calendar_activity, data_gaps) and an internal `governance_metadata` (packet id/hash, source coverage, source refs, guardrails, rendering_instructions, proof/receipt metadata). Does not return raw rows, raw source payloads, raw retrieved context, vector results, or direct DB query results.

## MCP policy (enforced)

- workflow_wrapper_only: True
- read_only: True
- local_first: True
- metadata_only: True
- source_linked: True
- no_raw / no_writeback / no_final_determination: True
- no_direct_graph_procore_db_vector: True

## Deny-first

Anything not in the allowlist (memory mutation, vector search, daily-brief apply) is denied as `tool_not_allowed`; explicit DB/Graph/Procore/writeback actions remain denied; denied tokens in arguments are denied.

## CLI

- proof: `hb-assistant second-brain mcp daily-brief-handoff-proof --json`
- audit: `hb-assistant second-brain mcp audit --json`
