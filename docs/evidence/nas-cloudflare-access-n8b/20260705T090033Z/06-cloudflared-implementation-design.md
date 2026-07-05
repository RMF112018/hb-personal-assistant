# 06 — cloudflared Implementation Design

## Choice: Docker Compose sidecar (matches the existing NAS MCP stack)
`deploy/nas/mcp/compose-cloudflared.yaml`, service `hb-personal-assistant-cloudflared`:
- **Image PINNED**: `${CLOUDFLARED_IMAGE:-cloudflare/cloudflared:2024.12.2}` — no floating `:latest`. **Operator must verify the tag exists and capture the resolved digest at deploy** (`docker inspect --format '{{index .RepoDigests 0}}' <image>`) into `10`/`local-sensitive`.
- **Command**: `tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}` (token from git-ignored `deploy/nas/.env` only).
- **Network**: joins the existing `hb-mcp-internal` bridge (`external: true`, `name: hb-mcp-internal`; the MCP compose now stamps `name: hb-mcp-internal`) so it reaches `http://hb-personal-assistant-mcp:8765`. No `network_mode: none` (would trip `check-mcp-compose.sh`).
- **No `ports:`** — outbound-only connector; nothing is published inbound.
- **restart: "no"** for this foundation branch (see `11` for the promotion gate).
- Runs as the default nonroot cloudflared user; no auth/secret volumes mounted.

## Lifecycle scripts (documented, NOT installed)
`deploy/nas/mcp/cloudflared-launcher` (start|stop|status|logs) → `cloudflared-runner` (root-owned, fixed verbs, `docker compose` on the connector compose) → granted via `sudoers.hb-pa-cloudflared.example` (exact-command NOPASSWD, mirrors `hb-mcp-runner`). The runner **fails closed** if `CLOUDFLARE_TUNNEL_TOKEN` is absent from `.env`, and never prints the token (`status` uses `docker ps`; `logs` tails connector output only).

## Required behavior vs status
| Requirement | This foundation |
|---|---|
| Runs on NAS, not Mac | ✅ (NAS Docker service) |
| Routes only to MCP origin | ✅ (internal bridge, single dashboard ingress) |
| Token not committed/printed | ✅ (`07`, `55`) |
| Starts after reboot | design only — HOLD (`11`) |
| Restarts after failure | design only — HOLD (`11`) |
| Stoppable cleanly | ✅ (`down`) |
| Connector healthy in Cloudflare | HOLD — live (`08`) |

## Verify (local, no start)
`docker compose -f compose-cloudflared.yaml config` parses (with a dummy token); `sh -n` clean on both scripts; `check-mcp-compose.sh` still PASS.

## Verdict
Connector scaffold complete and parse-verified. Live start + reboot/failure supervision = HOLD.
