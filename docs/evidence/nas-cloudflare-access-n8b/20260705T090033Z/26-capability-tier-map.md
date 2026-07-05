# 26 — Capability-Tier Map + `remote_cloudflare` Profile Matrix

The `remote_cloudflare` MCP profile (`nas_mcp/profile.py`, default; pinned in `compose-mcp.yaml` `HB_MCP_PROFILE`) enforces:

| Tier | Capability | remote_cloudflare | Enforced by |
|---|---|---|---|
| 0 | Health/status/schema | **allowed** | `hb_mcp_status`, `/health` |
| 1 | Read-only second-brain (search, summaries, graph, metadata, allowlisted DB read) | **allowed** | obsidian read tools + `hb_db_select` allowlist |
| 2 | Bounded file/source reads (approved roots, size caps, redaction) | **allowed** | `hb_root_*`, `read_file`, size caps |
| 3 | Output writes | **AI Outputs card create/update only** | `ai_outputs_card_upsert` (folder-locked); scratch writers denied |
| 4 | Vault mutation / ingestion / queue drains / watcher starts | **blocked** | profile `legacy_broad_vault` gate + existing `NAS_OBSIDIAN_BLOCKED` |
| 5 | Admin/destructive (raw SQL, shell, arbitrary FS, secret/cache reads, DB migration) | **never exposed** | `DENIED_TOOL_NAMES`, denied name/dir patterns, no such tools registered |

## Hard rules (profile invariants)
- The scratch + legacy write gates are **False in remote_cloudflare regardless of env overrides** — broad vault mutation and generic output writes can never be re-enabled on the internet-facing surface.
- Source ingestion, index rebuild, summarize, queue drains, watcher start, LLM-chat memory, semantic search, and all `*_apply` tools are in `NAS_OBSIDIAN_BLOCKED` (already, pre-N8B) — denied.
- Arbitrary SQL / shell / exec / absolute-path reads are in `DENIED_TOOL_NAMES` — denied first.

## `local_trusted` profile
For the loopback/Mac-tunnel trusted path only: all three write gates default on (restores pre-N8B behavior). Selected via `HB_MCP_PROFILE=local_trusted`; never used by the Cloudflare-fronted deploy.

## Verdict
Tier model is enforced in code and proven by `29-tier-denial-proof.md`.
