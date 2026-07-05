# 19 — Human vs Agent Access Model (defense-in-depth)

## Two layers (Access required but NOT sufficient)
**Cloudflare Access = edge authn** (primary). **Origin-side auth on `nas_mcp:8765` = defense-in-depth** (required before final N8B PASS).

Rationale: the exposed origin (`nas_mcp/server.py`) has **no auth of its own** — its entire prior security model was loopback-only. Fronting it with Access alone means any origin leak (tunnel misroute, Access misconfig/bypass) exposes the read+AI-Outputs-write surface unauthenticated. So Access is necessary but not sufficient.

## Access lanes
| Lane | Who | Auth |
|---|---|---|
| Human/admin | Bobby | Cloudflare Access identity login |
| Claude | MCP client | Access service token (or supported OAuth) — `mcp-claude` |
| ChatGPT | app/connector | ChatGPT-compatible path (likely DCR/OAuth — verify) — `mcp-chatgpt` |
| Grok | MCP/bridge | service token or secure bridge — `mcp-grok` |
| Local fallback | NAS/Tailnet admin | not public, not Cloudflare-dependent |

Per-client tokens (never shared, never one broad permanent token). Service tokens use `CF-Access-Client-Id` / `CF-Access-Client-Secret` headers.

## Service-token lifecycle (template, secrets out of repo)
name · owner · client · expiration · rotation date · revocation path · allowed hostname/path. Secrets stored outside the repo; never in evidence (`21` redacted, HOLD until created).

## Origin-side auth (required later sub-phase — BLOCKER for final PASS)
Port the existing `obsidian_mcp/oauth_store.py` (SHA-256 token store, PKCE, DCR) + `BearerTokenMiddleware` (`obsidian_mcp/mcp_app.py:204`) onto the `nas_mcp` Starlette app (`nas_mcp/server.py`), so the origin refuses unauthenticated requests independent of Access. Reconcile the token `resource` binding to `https://mcp.bobby-fetting.me/mcp` (currently validated against the `:8000` surface).

## Actor attribution
The AI Outputs write tool records `source_client` in the mutation receipt (`27`); broker audit records `actor` per request. Map Access identity/service-token → `source_client` at the auth sub-phase.

## Verdict
Model defined; origin-side auth explicitly a blocker before final PASS.
