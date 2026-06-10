# Repo-Truth Audit — MCP Context Packet Hardening (Prompt 08)

## Existing surfaces (mature)

| Concern | Location | State |
|---|---|---|
| Context packet builder | `…/local_ai/daily_brief_context_packet.py` `build_daily_brief_context_packet` | Bounded, source-linked, deterministic; sections + `caps`. |
| Handoff packet | `daily_brief` `build_daily_brief_packet` / `_v2` | Hashed refs, redacted titles, flags, render/governance split. CLI `daily-brief packet`. |
| MCP module | `…/mcp/` (wrappers, broker, policy, resources, prompts) | 10 allowed tools; denied tools; read-only/metadata-only policy. |
| MCP packet policy | `resources/config/phase_10_mcp_packet_policy.seed.yaml` | resources/tools/forbidden/guardrails (read_only, metadata_only, source_refs_required). |

## Gap (Prompt requirements 1 + 3)

The context packet had sections + caps but no explicit, first-class **MCP contract envelope** (purpose,
generated_at, source window, source-ref summary, candidate summaries, caps applied, omitted-raw
categories, redaction flags, freshness warnings) and no **fail-closed forbidden-content gate** over the
payload.

## Decision (surgical)

Add `mcp_packet_hardening.py` (`build_hardened_mcp_packet` + `scan_for_forbidden_content` + renderer)
that wraps the existing `build_daily_brief_context_packet` (no second contradictory path) in the MCP
contract envelope and runs a regex forbidden-content gate over the real payload — withholding the
context (fail-closed) on any match. New `daily-brief mcp-packet` CLI verb. Read-only, no writeback, no
schema change. Aligns with the existing `daily-brief packet` (same context source).
