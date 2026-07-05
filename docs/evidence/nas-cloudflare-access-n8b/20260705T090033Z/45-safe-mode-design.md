# 45 — Remote Safe Mode — design/gap

## Goal
An incident toggle that preserves remote **visibility** while blocking all writes/mutations.

## EXISTS (partial equivalents)
- The `remote_cloudflare` profile already denies tiers 4-5 + scratch writes (`26`).
- Per-config write kill-switches (`writes_enabled`, `vault_markdown_write_enabled`).
- Startup env guards (`HB_MCP_NAS_READONLY`, `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS`).

## GAP: a single `HB_MCP_SAFE_MODE`
Add a global flag that, when on, forces the surface to **read-only tiers 0-2 + diagnostics** and additionally denies the AI Outputs write:
- **Allowed:** health/status, data freshness, recent failures, read-only second-brain search, approved note fetch (redacted), Access/tunnel diagnostics.
- **Denied:** `ai_outputs_card_upsert`, scratch/vault writes, ingestion, drains, watcher, admin/destructive.
- **Visible:** `hb_mcp_status` / `/health` report `safe_mode: true`; safe-mode denials are audited.

Cleanest implementation: extend `nas_mcp/profile.py` so `HB_MCP_SAFE_MODE=1` forces `ai_outputs_write_enabled()` (and all write gates) to False and stamps `safe_mode` into `gate_status()`. Small, localized change — deferred to a later sub-phase so the foundation stays scoped.

## Verdict
Profile gives most of the effect already; the one-flag `HB_MCP_SAFE_MODE` that also cuts the AI Outputs write = GAP for a later sub-phase.
