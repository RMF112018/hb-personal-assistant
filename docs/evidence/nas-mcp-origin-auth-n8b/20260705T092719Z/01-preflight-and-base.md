# 01 — Preflight & Base

## Base
- `git fetch origin --prune` — clean.
- Started from the **N8B foundation tip** `cdd29ed0` ("docs: add N8B foundation evidence"), which sits on the foundation stack off `origin/main` @ `7f22fa9d`.
- Foundation commits present in ancestry:
  - `cdd29ed0` docs: add N8B foundation evidence
  - `39d16a4b` deploy: add token-free cloudflared scaffold for NAS MCP
  - `34831f97` nas-mcp: add remote cloudflare profile and AI Outputs write gate
- New branch: `ops/nas-mcp-origin-auth-n8b-20260705T092719Z` (created off `cdd29ed0`).
- Working tree at start: clean (3 foundation commits ahead of `origin/main`).

## Preconditions inherited from the foundation
- `remote_cloudflare` MCP profile is the default; broad vault mutation + scratch output writes are hard-blocked remotely; connected-LLM write is limited to `ai_outputs_card_upsert`.
- cloudflared scaffold exists but no live tunnel started.
- Foundation left origin-side auth on `nas_mcp:8765` as an explicit blocker — **this phase closes that blocker at the origin** (edge/live proofs remain later sub-phases).

## Scope guardrails honored
No live Cloudflare tunnel started; no public route; no push; no secrets printed or committed; no broad vault writes enabled; no ingestion / queue drain / watcher / scheduler started; `remote_cloudflare` capability profile not weakened (origin auth only *adds* a gate).
