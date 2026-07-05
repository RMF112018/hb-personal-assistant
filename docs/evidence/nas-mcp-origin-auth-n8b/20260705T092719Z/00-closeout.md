# 00 — N8B Origin-Auth Closeout

**Phase:** N8B-Origin-Auth — Add origin-side authentication to the NAS MCP surface (`nas_mcp:8765`)
**Stamp:** `20260705T092719Z` · **Branch:** `ops/nas-mcp-origin-auth-n8b-20260705T092719Z`
**Base:** foundation tip `cdd29ed0` (N8B foundation, off `origin/main` @ `7f22fa9d`)
**Verdict: HOLD** — origin bearer auth is implemented, enforced, and tested at the origin; full N8B remains gated on live Cloudflare Access proof, restart/reboot proof, client-compat proof, and rollback proof (all pre-declared later sub-phases).

## What this phase delivered (defense-in-depth origin auth)
1. **Origin bearer auth on `nas_mcp:8765`.** A pure-ASGI `OriginAuthMiddleware` (adapted from the obsidian `BearerTokenMiddleware` pattern) wraps the whole NAS app. In the internet-facing `remote_cloudflare` profile it is **hard-on regardless of env override**. Missing / malformed / unknown / revoked / expired credentials are denied with a uniform `401 {"detail":"unauthorized"}` (token existence never leaked); valid credentials pass through to the MCP initialize/list/call flow. (`03`, `05`, `13`)
2. **Dedicated NAS token store** (`nas_mcp/origin_auth.py`) — SHA-256-hashed, `secrets.token_urlsafe(32)`, one-time raw return, 0600 atomic JSON. Records carry client / actor / issued / expires / revoked / tier / optional allowed-tools. Reuses the obsidian store's *security design* but adds revoke / list / rotate and identity fields it lacks. (`02`, `04`)
3. **Audit attribution.** The authenticated actor / client label / token-id / auth-method thread through a contextvar into every broker audit event — **proven end-to-end** (real MCP `tools/call` → audit line carries `client_label`, `actor`, `authenticated=true`, no token value). (`12`)
4. **Profile still governs capability.** A valid token cannot call blocked broad-vault-write / scratch-write / tier-4/5 tools, cannot write outside `AI Outputs`, and an optional per-token allow-list can only *narrow* further. (`07`, `08`, `09`)
5. **Health hardened.** `/health` now returns **minimal liveness only** unauthenticated (no DB path, no root mounts, no allowlisted table keys) — a real info-leak fix. Detailed health is the authenticated `hb_mcp_status` tool, or `/health` under `HB_MCP_ORIGIN_AUTH_HEALTH_MODE=protected`. (`06`)
6. **Operator token workflow.** `python -m hb_assistant.nas_mcp.origin_auth_cli` create / list / revoke / rotate — raw token printed **once** to stdout, never persisted, never in `list`. (`11`)

## Tests / gates
`tests/test_nas_mcp_origin_auth.py` (19) + updated `test_nas_mcp_readonly.py` health test → **NAS suite 58 passed**, ruff clean on all changed files, `git diff --check` clean. Sensitive scan: **zero N8B-added unallowed findings** (see `14`). No deploy files changed → compose checks not applicable.

## Explicit blockers before full N8B PASS (carried forward)
- Live Cloudflare tunnel + Access app created by operator; prove Access denies unauthenticated at the edge (origin auth is the second layer, now in place). — `10`
- MCP + cloudflared start-after-reboot + restart-after-failure (`unless-stopped` promotion + boot task). — foundation `11`
- Client-compat proven (Claude / ChatGPT / Grok) incl. the dual-header question for service-token clients + Grok bridge. — `10`, foundation `22`
- Rollback / disable proof.

## Commit posture
Uncommitted, unpushed. Commit locally only after Bobby reviews the diff and authorizes. No push.
