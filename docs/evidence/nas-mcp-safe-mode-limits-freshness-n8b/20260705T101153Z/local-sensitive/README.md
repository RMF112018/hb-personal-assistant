# local-sensitive/ (N8B safe-mode/limits/freshness) — gitignored, never committed

Ignored by `.gitignore` (`/local-sensitive/`, `docs/evidence/**/local-sensitive/`). Holds raw
runtime material that must never enter git history.

## What belongs here (only at live activation, with approval)
- Raw NAS MCP audit excerpts that contain host/tailnet identifiers.
- Any raw runtime capture with the NAS hostname, tailnet IP, or connector ids.

## What must NEVER be here or in committed evidence
- MCP bearer tokens, Cloudflare tunnel/API tokens, Access service-token secrets.
- SSH private keys, Text-Vault/Fernet keys, MSAL caches, decrypted content, raw source payloads.
- The `overrides.json` / `tokens.json` runtime stores (they live under app-support, `0600`,
  outside the repo).

## Redaction rule
Committed evidence carries no raw token/secret/key, no NAS hostname, no tailnet-IP literal, no
payloads. Overrides are referenced by id/scope only; freshness output is aggregate-only.
`/volume1`/`/volume2`, `127.0.0.1`, `8765`, and `mcp.bobby-fetting.me` are non-secret constants.

## This session
Empty — no live Cloudflare activation ran. All data in this bundle is from ephemeral pytest
tmp dirs.
