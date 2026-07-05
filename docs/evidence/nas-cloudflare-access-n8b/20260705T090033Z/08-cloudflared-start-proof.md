# 08 — cloudflared Start Proof — HOLD

**Status: HOLD** — requires the operator to (1) create the Cloudflare tunnel, (2) create + verify the Access app, (3) place the token in git-ignored `deploy/nas/.env`, then authorize `cloudflared-launcher start`. Not started in this foundation (decision 6).

When executed, this file will record (redacted): `cloudflared-runner status` output (container up), the **resolved image digest** (`docker inspect`), and the Cloudflare-side connector "healthy/registered" state — with no token printed.

Acceptance (live): connector runs on the NAS, appears healthy in Cloudflare, Mac not required.
