# 04 — Token Store & Client Model

`nas_mcp/origin_auth.py` → `OriginAuthTokenStore(path)`. JSON file, `0600`, atomic
temp-write-then-replace. Keyed by `sha256(raw_token)`; **the raw token is never persisted.**

## Record schema (per token)
| field | purpose |
|---|---|
| `token_id` | stable public id (`secrets.token_hex(8)`) for list/revoke/rotate |
| `client` | one of `claude` / `chatgpt` / `grok` / `admin` / `local` |
| `client_label` | human label (e.g. "Claude Desktop") — audit attribution |
| `actor` | actor identity written into audit events |
| `issued_at` / `expires_at` | ISO timestamps |
| `expires_ts` | float epoch (expiry comparison) |
| `revoked` (+ `revoked_at`) | revocation state |
| `tier` | informational capability tier (profile remains the authority, `07`) |
| `allowed_tools` | optional allow-list that only **narrows** access |
| `fingerprint` | first 8 hex of the hash (safe display only) |

## Operations
- `create_token(client, client_label, actor, expires_days, tier?, allowed_tools?)` → `(raw, public_record)`. Validates `client` ∈ allowed set and `expires_days > 0`. Raw returned once.
- `validate(raw)` → `(AuthContext | None, reason)` where reason ∈ `ok` / `unknown_token` / `revoked` / `expired`. Same 401 to the client for every non-`ok` (no existence leak); precise reason only in the 0600 audit.
- `revoke(token_id)` → bool (idempotent-false if already revoked/absent).
- `rotate(token_id, expires_days)` → revoke old + mint replacement carrying the same client/label/actor/tier/allowed_tools. Refuses to rotate an already-revoked id.
- `list_tokens()` → public records only (no SHA key, no raw).

## Client model (distinct clients required by the phase)
`claude`, `chatgpt`, `grok`, `admin` (Bobby/operator), `local` (test client). Each token binds one client + label + actor; audit events carry all three so activity is attributable per client.

## Storage location
Env `HB_MCP_ORIGIN_AUTH_TOKEN_STORE` > `mcp.origin_auth_store_path` > `<app_support>/origin-auth/tokens.json`. On the NAS this resolves under the configured `/volume2/personal-assistant` app-support root — **not** the obsidian macOS namespace. `0600`, outside any served root.
