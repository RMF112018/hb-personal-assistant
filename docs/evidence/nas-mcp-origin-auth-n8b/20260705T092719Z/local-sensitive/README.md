# local-sensitive/ (N8B origin-auth) — gitignored, never committed

Ignored by `.gitignore` (`/local-sensitive/`, `docs/evidence/**/local-sensitive/`). Holds
raw runtime material that must never enter git history.

## What belongs here (only at live activation / token bootstrap, with approval)
- Raw origin-auth bearer tokens minted by `hb-mcp-auth create-token` (the value printed once
  to stdout) — or store them in a password manager instead.
- Raw Cloudflare tunnel/connector status, image digest, connector logs, Access auth-log
  exports (from later live sub-phases).
- Any capture containing the NAS hostname, tailnet IP, tunnel/account/connector ids.

## What must NEVER be here or in committed evidence
- Cloudflare tunnel token, API token, Access service-token client secret.
- SSH private keys, Text-Vault/Fernet keys, MSAL cache, decrypted content.
- The `origin-auth/tokens.json` store is not a secret file (it holds only `sha256(token)` +
  metadata), but treat it as sensitive: it lives under app-support, `0600`, outside the repo.

## Redaction rule
Committed evidence carries no raw token, no secret/key, no NAS hostname, no tailnet-IP
literal. Tokens are referenced by **label + fingerprint (first 8 hex of the hash)** only.
`/volume1`/`/volume2`, `127.0.0.1`, `8765`, and the public hostname `mcp.bobby-fetting.me`
are non-secret structural constants.

## This session
Empty — no live Cloudflare activation and no real token bootstrap ran. All tokens referenced
in this bundle are ephemeral test fixtures created and destroyed inside pytest tmp dirs.
