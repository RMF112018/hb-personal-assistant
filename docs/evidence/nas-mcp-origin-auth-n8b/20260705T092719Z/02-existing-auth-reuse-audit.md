# 02 — Existing Auth Reuse Audit (reuse vs adapt decision)

The prompt asked to reuse `obsidian_mcp/oauth_store.py` if it already provides SHA-256
hashing / revocation / expiration, rather than inventing a parallel **insecure** store.
A source audit was performed before writing any code.

## What `obsidian_mcp/oauth_store.py` actually provides
- **SHA-256 hex hashing** of tokens (`_sha256`), raw returned once via `secrets.token_urlsafe(32)`, records stored as JSON with `0600` perms outside the repo. **Good — reused as the security model.**
- `validate_access_token(raw, resource=...)` honoring `revoked` + `expires_ts`. **Good.**
- Full **OAuth 2.1 / PKCE** authorize→code→token flow + Dynamic Client Registration.

## What it does NOT provide (and this phase requires)
- **No revoke function** — records carry a `revoked` bool but nothing sets it. This phase requires a revocation path.
- **No list function** and **no rotate** — required for the operator workflow.
- **No client-label / actor / capability-tier fields** on token records (only `client_id`, `scope`, `resource`). This phase requires client + actor attribution for audit.
- **Resource-bound** to `{public_base_url}/mcp` (the obsidian `:8000` surface) and stored under an **obsidian-namespaced macOS app-support path** — neither fits `nas_mcp:8765`.
- The **FastAPI backend that issues these tokens is a forbidden import** in the NAS process (`assert_no_backend_modules_loaded` blocks `construction.analytics.api`), so the NAS server cannot run the issuance routes.

## Decision: **adapt the security design, not the module**
Directly reusing `oauth_store` would ship origin auth **without revocation, listing, rotation, or client/actor attribution** — a weaker posture than the phase demands. So a **dedicated NAS store** (`nas_mcp/origin_auth.py`) was built that **copies the proven-secure primitives verbatim** (SHA-256 hex hashing, `secrets.token_urlsafe(32)`, one-time raw return, 0600 atomic JSON, expiry + revoked enforcement, uniform-401 no-existence-leak) and **adds** revoke / list / rotate + client-label / actor / tier / optional allowed-tools. This is *not* a parallel *insecure* store — it is the same security model with the required lifecycle + attribution.

The **middleware pattern** (pure-ASGI wrapper around `streamable_http_app()`, latin1 header decode, manual `401` ASGI send) **was reused** structurally from obsidian `BearerTokenMiddleware`.

## Future convergence note
If OAuth 2.1/PKCE is later wanted on the NAS surface, `oauth_store`'s validation can be layered in behind the same middleware with `resource=None` (or a NAS resource string). Bearer-token origin auth is the correct minimal first layer; full OAuth flow remains deferred (a documented HOLD, acceptable per the phase's HOLD criteria).
