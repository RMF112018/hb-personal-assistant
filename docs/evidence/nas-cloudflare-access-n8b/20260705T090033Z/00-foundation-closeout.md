# 00 — N8B Foundation Closeout

**Phase:** N8B — Always-On NAS MCP via Cloudflare Tunnel (foundation)
**Stamp:** `20260705T090033Z` · **Branch:** `ops/nas-cloudflare-access-n8b-foundation-20260705T090033Z` · **Base:** `origin/main` @ `7f22fa9d`
**Verdict: HOLD (foundation PASS; full N8B intentionally gated on live Cloudflare + the required later sub-phases).**

## Done (foundation)
1. **Profile-driven capability lockdown (code).** `nas_mcp/profile.py` — the `remote_cloudflare` exposure profile (default; pinned in `compose-mcp.yaml`) + three **independent** write gates (`ai_outputs`, `local_scratch_output`, `legacy_broad_vault`). In the remote profile the scratch + legacy gates are **hard-denied regardless of env overrides**; the internet-facing surface is provably read (tiers 0-2) + the single AI Outputs write (tier 3). Broker denies+audits blocked writes; `hb_mcp_status` + `/health` report the profile. (`03`, `26`, `29`)
2. **AI Outputs write tool (code).** `nas_mcp/ai_outputs.py` `ai_outputs_card_upsert` — folder-locked to `AI Outputs`, Markdown-only, SHA-gated update, backup-before-overwrite, mutation-receipted with client attribution; reuses the gated `mutations` engine. (`27`, `28`)
3. **Tests.** `tests/test_nas_mcp_remote_profile.py` (6) + updated existing suites → **39 passed**, ruff clean. Denial proofs: broad writes blocked+audited, overrides ignored, AI Outputs folder-locked, local_trusted re-enables. (`28`, `29`)
4. **cloudflared token-free scaffold (code, NOT started).** `compose-cloudflared.yaml` (pinned image, outbound-only, internal-bridge to the MCP origin, token via git-ignored `.env`) + launcher/runner/sudoers example (documented, not installed) + `.env.example` placeholder + `.gitignore` hardening. Parse-verified; `check-mcp-compose.sh` still PASS. (`06`, `07`)
5. **Design/gap docs** for exposure surface, route target, supervision, transport (already Streamable HTTP), human-vs-agent access (defense-in-depth), client matrix, monitoring, rate-limit, freshness, safe mode, forbidden-surface, logging/audit. (`04`,`05`,`11`,`16`,`19`,`22`,`35`,`39`,`43`,`45`,`48`,`51`)
6. **Redaction.** Zero N8B-added sensitive-scan findings; no hostname/tailnet-IP/token committed. (`55`)

## Access-before-route status
Not live. No tunnel, no Access app, no token, no public route. The connector is scaffolded but **not started**. Access-before-route is documented as a hard operator gate.

## Explicit blockers before full N8B PASS
- Origin-side auth ported onto `nas_mcp:8765` (defense-in-depth) — `19`.
- MCP + cloudflared start-after-reboot + restart-after-failure (promote `restart: unless-stopped` + boot task) — `11`.
- Cloudflare Access denies unauthenticated (verified) — `48`/`49`.
- Client-compat proven (Claude/ChatGPT/Grok) or a secure Grok bridge — `22`.
- Rollback/disable proven — `56`.
Later gaps (not blockers to start, but required for the full surface): `HB_MCP_SAFE_MODE`, request rate-limit + operator override, unified NAS freshness tool.

## Acceptance (this prompt) — met
Foundation evidence exists; MCP state audited; persistent MCP + cloudflared plans exist; secret handling documented + protected; public route not usable without Access; client matrix exists; capability-tier model + AI Outputs contract exist and are **implemented + tested**; rate-limit/override/safe-mode/freshness/monitoring/transport/forbidden-surface plans exist; no secrets printed/committed; git status captured; **no push**.

## Next prompt recommendation
N8B.next: (a) port origin-side OAuth/bearer onto `nas_mcp:8765`; then (b) operator creates the Cloudflare tunnel + Access app, provides the token out-of-repo; (c) with per-step approval, start cloudflared, prove Access denies unauthenticated, run client-compat + forbidden-surface + rollback proofs; (d) promote restart policy + boot task and prove reboot/failure restart.

## Commit posture
Uncommitted, unpushed. Commit locally only after Bobby reviews the diff and authorizes.
