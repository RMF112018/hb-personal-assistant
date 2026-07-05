# local-sensitive/ (N8B) — gitignored, never committed

Ignored by `.gitignore` (`/local-sensitive/`, `docs/evidence/**/local-sensitive/`). Holds raw runtime material that must not enter git history.

## What belongs here (only at live activation, with approval)
- Raw Cloudflare tunnel/connector status output, resolved image digest, and connector logs.
- Cloudflare Access auth-log exports.
- Any capture containing the NAS hostname, tailnet IP, tunnel/account/connector ids.

## What must NEVER be here or in committed evidence
- Cloudflare tunnel token, Cloudflare API token, Access service-token client secret.
- SSH private keys, Text-Vault/Fernet keys, MSAL cache, decrypted content.

## Redaction rule
Committed evidence carries no NAS hostname, tailnet-IP literal, or any secret/key/token. `/volume1`/`/volume2` paths, `127.0.0.1`, `8765`, and the public hostname `mcp.bobby-fetting.me` are non-secret. Sensitive raw artifacts are referenced by name + SHA-256 only.

## This session
Empty — no live Cloudflare activation ran. All N8B foundation evidence references parameters by name/structure only.
