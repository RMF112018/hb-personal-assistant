# 55 — Redaction Scan

## Automated
`tests/test_repo_sensitive_scan.py` (`security/sensitive_scan.py`) → **16 pre-existing findings, ALL in untouched files; zero N8B-added.** A raw `CLOUDFLARE_TUNNEL_TOKEN=<value>` anywhere would trip `env_secret_assignment` — none present.

## Manual scan of the N8B tree (`src/hb_assistant/nas_mcp`, `deploy/nas/mcp`, evidence)
No NAS hostname, tailnet-IP literal, tunnel/API token, or Access client secret. The only pattern hits were benign self-references:
- `cloudflared-runner` greps for the token **key name** `^CLOUDFLARE_TUNNEL_TOKEN=` (a presence check — no value).
- `07-cloudflared-secret-handling.md` shows the placeholder `CLOUDFLARE_TUNNEL_TOKEN=<value>` as an instruction.
- `nas_mcp/redaction.py` contains the pre-existing PEM-redaction regex (unchanged, not N8B).

## Non-secret (intentionally present)
`/volume1`, `/volume2`, `127.0.0.1`, `8765`, and the public hostname `mcp.bobby-fetting.me` are non-secret structural constants.

## Verdict
No secret/hostname/tailnet-IP committed; scan gate clean for N8B. Raw live artifacts (tunnel status/logs/digests) will live only in gitignored `local-sensitive/` at activation.
