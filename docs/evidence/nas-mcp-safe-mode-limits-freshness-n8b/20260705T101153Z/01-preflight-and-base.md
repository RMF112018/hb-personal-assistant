# 01 — Preflight & Base

- `git fetch origin --prune` — clean.
- Started from the **N8B-Origin-Auth tip** `0633514d` ("docs: add N8B origin auth evidence").
- Foundation + origin-auth commits present in ancestry (6 total ahead of `origin/main` @ `7f22fa9d`):
  `0633514d` docs: add N8B origin auth evidence · `bb84ca95` test: add NAS MCP origin auth coverage ·
  `955b2a66` nas-mcp: add origin auth middleware and token store integration ·
  `cdd29ed0` docs: add N8B foundation evidence · `39d16a4b` deploy: cloudflared scaffold ·
  `34831f97` nas-mcp: remote cloudflare profile + AI Outputs write gate.
- New branch: `ops/nas-mcp-safe-mode-limits-freshness-n8b-20260705T101153Z` off `0633514d`.

## Inherited preconditions
remote_cloudflare profile default; broad vault + scratch writes blocked remotely; AI Outputs is
the only remote write; origin bearer auth hard-on for remote_cloudflare; cloudflared scaffold
present but not started.

## Guardrails honored
No live Cloudflare / no public route / no push; no secrets printed or committed; no DSM/SSH/SMB/
raw-vault/raw-SQLite exposure; no broad vault writes; no ingestion/drain/watcher/scheduler starts;
remote_cloudflare not weakened (this phase only ADDS gates); overrides never remotely creatable.
