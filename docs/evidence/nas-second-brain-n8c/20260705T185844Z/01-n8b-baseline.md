# 01 — N8B Baseline (N8C-0 repo-truth, captured here)

N8C-0's repo-truth baseline is captured in this file. N8C-1 begins from actual `origin/main` state.

## Base
- `origin/main` @ `e80f3729c661a98daa04c2d393b19fce253eeb94`. Contains the live N8B
  `src/hb_assistant/nas_mcp/` package. Worktree merge-base == base (no divergence).
- Local `main` was behind at planning time and lacked `nas_mcp` — always base off `origin/main`.

## Corrected assumptions (verified against `origin/main`, not carried from stale notes)
- `LATEST_SCHEMA_VERSION = 99` (`store/migrator.py`), **not 97**. A V99 migration already recomputes
  file `source_id`s.
- `source_id_for` (`obsidian_mcp/source_index_repository.py`) **folds in `source_root_key`** for file
  sources: `key = f"{source_kind}|file|{source_root_key or ''}|{rel_path}"`.

## N8B MCP surface (unchanged by N8C-1 except AI-Outputs frontmatter)
- Server `nas_mcp/server.py` (Streamable HTTP + `/health` + OAuth routes + `OriginAuthMiddleware`).
- Profile/gates `nas_mcp/profile.py`: default `remote_cloudflare`; three independent write gates —
  `ai_outputs_write_enabled` (True), `scratch_output_write_enabled` + `legacy_vault_write_enabled`
  (hard-denied, no override).
- Tools `nas_mcp/tool_registration.py`: tier-0 status/freshness, `hb_db_select`, `hb_root_*`,
  `hb_output_*` reads; conditional `ai_outputs_card_upsert`. DB allowlist `nas_mcp/db_allowlist.py`
  default-deny (single `schema_version` entry).
- AI-Outputs writer `nas_mcp/ai_outputs.py`: client/mode allowlists, folder-lock, traversal guards,
  SHA-gated update, append size re-check, backup + receipts.
- Compose `deploy/nas/mcp/compose-mcp.yaml`: `127.0.0.1:8765` only; snapshot DB `:ro`.

## Source-intelligence substrate (reused, not extended)
`store/source_intelligence_tables.py` (`_sources/_metadata/_text/_chunks/_relationships/
_generated_notes/_events/_state` + FTS + V94 `_summaries`); sole reader/writer
`obsidian_mcp/source_index_repository.py`; card renderer `obsidian_mcp/source_notes.py`.

## Frontend/API
FastAPI `create_app()` in `construction/analytics/api.py`; React client `frontend/src/lib/api.ts`
uses relative `/api` (Vite proxy), never direct SQLite/fs. (Worktree `CLAUDE.md` "no frontend" line
is stale.)
