# 07 — cloudflared Secret Handling

## The token never enters git or logs
- **Injection:** `${CLOUDFLARE_TUNNEL_TOKEN}` in `compose-cloudflared.yaml`, sourced from the **git-ignored** `deploy/nas/.env` (via `--env-file` in `cloudflared-runner`). The compose uses `:?` so it fails closed if unset.
- **`.env.example`** carries only a **commented, value-free** placeholder and a note that the real value lives only in `deploy/nas/.env`.
- **`.gitignore`** ignores `.env`, and now explicitly `deploy/nas/.env`, `deploy/**/.env`, and `**/*.cloudflared-credentials.json` / `deploy/**/cloudflared/*.json`.
- **Runner hygiene:** `cloudflared-runner status` uses `docker ps` (not `inspect`, which would show env); `logs` tails connector output (cloudflared does not log its token). The runner refuses to start if the token is absent.
- **Scan gate:** `tests/test_repo_sensitive_scan.py` (`security/sensitive_scan.py`) would flag a raw `CLOUDFLARE_TUNNEL_TOKEN=<value>` via `env_secret_assignment`. `55` attests zero N8B-added findings.

## Operator token flow (out of repo)
1. Create the tunnel in Cloudflare → copy the connector token.
2. Put it in `deploy/nas/.env` on the NAS **only**: `CLOUDFLARE_TUNNEL_TOKEN=<value>` (never committed).
3. Confirm the Access app denies unauthenticated traffic.
4. `cloudflared-launcher start`.

## What must NEVER appear (repo/evidence/logs)
Tunnel token, Cloudflare API token, Access service-token client secret, SSH keys, Text-Vault/Fernet keys, MSAL cache, decrypted content.

## Verdict
Secret handling defined and protected; no secret present in the repo (`55`).
