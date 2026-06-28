# Phase 3A — OAuth 2.1 / PKCE Adapter for Grok Remote MCP

Evidence bundle for adding Authorization-Code-with-PKCE authentication to the
UI-managed Obsidian MCP server so the Grok Custom Connector can reach the
Cloudflare-tunneled `/mcp` endpoint. Single unified FastAPI app — no second
process. Static bearer auth continues to work; OAuth scopes never bypass the
vault write policy.

## What shipped

| Area | File |
| --- | --- |
| OAuth state store (codes/tokens/events, PKCE, metadata, Grok values) | `src/hb_assistant/obsidian_mcp/oauth_store.py` |
| Config fields `oauth_enabled`, `public_base_url` (+ validator) | `src/hb_assistant/obsidian_mcp/config.py` |
| Middleware OAuth-token auth + per-tool scope authorization | `src/hb_assistant/obsidian_mcp/mcp_app.py` |
| UI OAuth status read-model | `src/hb_assistant/obsidian_mcp/service.py` (`oauth_status`) |
| Public OAuth + discovery routes, UI status route, consent HTML | `src/hb_assistant/construction/analytics/api.py` |
| Backend tests (21) | `tests/test_obsidian_mcp_oauth.py` |
| Remote Connector / OAuth UI section | `frontend/src/components/settings/ObsidianMcpPanel.tsx` |
| API client `getObsidianMcpOAuth` | `frontend/src/lib/api.ts` |
| Frontend tests (2 added) | `frontend/src/pages/SettingsPage.test.tsx` |

## Endpoints

Public (unauthenticated, tunnel-reachable; declared before the `/mcp` mount so
they take precedence over the catch-all):

- `GET /.well-known/oauth-authorization-server` (RFC 8414)
- `GET /.well-known/oauth-protected-resource` (RFC 9728)
- `GET /.well-known/openid-configuration` (alias)
- `GET /oauth/authorize` (HTML consent page) · `POST /oauth/authorize` (approve → code)
- `POST /oauth/token` (authorization_code + PKCE → access token)

Role-gated UI:

- `GET /api/settings/obsidian-mcp/oauth` (status + generated Grok setup values)
- `PATCH /api/settings/obsidian-mcp/config` (sets `oauth_enabled`, `public_base_url`)

## OAuth client model

`client_id: hb-obsidian-grok` · public client · `token_auth_method: none (PKCE)` ·
`grant_type: authorization_code` · PKCE **S256 required** · scopes
`obsidian.read` (list_directory, search_vault, read_file) and `obsidian.write`
(create_note, patch_note). Write scope is additive — it does **not** bypass the
existing `writes_enabled` / `vault_markdown_write_enabled` / path / markdown-only /
SHA-gate policy in `mutations.py`.

## Security properties (all enforced + tested)

- PKCE S256 required; verified with `secrets.compare_digest`.
- Authorization codes: 600 s TTL, single-use (burned on success/expiry).
- Access tokens: 3600 s TTL; only **SHA-256 hashes** persisted on disk under
  `~/Library/Application Support/HB Personal Assistant/analytics/obsidian_mcp/oauth/`
  (`0o600`). Raw token returned only once in the `/oauth/token` response.
- `redirect_uri` bound to the code and exact-matched at exchange (https, or
  localhost http for testing).
- Audit events record only event kind + scope + timestamp — never code/token/verifier.
- `/mcp` rejects missing / expired / invalid / insufficient-scope credentials (401
  at the middleware; `insufficient_scope` tool error for wrong scope).
- Static bearer token path unchanged; OAuth is opt-in via `oauth_enabled`.

## Verification

- `flow-transcript.txt` — redacted end-to-end run through the real FastAPI app
  (metadata → authorize validation → consent → approve → PKCE mismatch reject →
  token issue → single-use reuse reject → scope enforcement (read-only blocked
  from write) → `/mcp` 401s → UI status proves no raw token/code leak).
- `backend-test-results.txt` — `pytest tests/test_obsidian_mcp_oauth.py` (21 passed).
- Frontend: `npm run test src/pages/SettingsPage.test.tsx` (9 passed) and
  `npm run build` (tsc + vite) succeed. The Remote Connector / OAuth panel renders
  the generated Grok setup values and saves the Public MCP Base URL; no token
  values are rendered.

## Final gate — manual Grok runtime smoke (operator)

Automated tests cover everything except the live Grok handshake. To close the
final gate:

1. Run the backend on `127.0.0.1:8000`; `cloudflared tunnel --url http://127.0.0.1:8000`.
2. In Settings → Obsidian MCP → Remote Connector / OAuth, set **Public MCP Base URL**
   to the tunnel URL and enable OAuth.
3. Register the Grok connector with the copied setup values (MCP URL `…/mcp`,
   authorize `…/oauth/authorize`, token `…/oauth/token`, client id `hb-obsidian-grok`,
   token auth method none/PKCE, scopes `obsidian.read` + `obsidian.write`).
4. Approve in the browser consent page; confirm Grok lists all five tools, reads with
   `obsidian.read`, and writes only with `obsidian.write` while UI write mode is enabled.
