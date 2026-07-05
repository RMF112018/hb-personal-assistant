# 10 — N8B Readiness Assessment

N8B (the successor phase — public/edge exposure, e.g. Cloudflare/Tailscale-fronted access, per the N8 `10-n8a-readiness.md` roadmap) is **assessed only, not implemented** here. This records whether the pieces it depends on are ready after N8A.

## Ready (foundations in place)

- **Default-off posture** — `HB_NAS_RUNTIME=1` forces workers/watcher/poll off and refuses on-demand watcher starts (`03`, `23 passed`).
- **Storage locality guard** — DB restricted to `/volume2/personal-assistant/`; fail-closed. **N8A closed the `/volume1` config drift** that previously defeated the guard on the first app-support write (`../live-20260705T075807Z/02`).
- **Single-writer** — host-stamped watcher lease + run lock serialize within the canonical DB; fail-closed on contention.
- **Source identity** — V99 root-scoped ids rule out cross-root collision; confirmed at rest.
- **Live pipeline proven** — N8 bounded proofs 04–07 PASS; N8A re-confirmed at rest with no duplicates.
- **Privileged-access hygiene** — temporary proof runners + `/volume1` dead sudoers rule reconciled/cleaned (`../live-20260705T075807Z/03`); `sudo -l` shows no residual broad grant.

## Blocking / required before N8B

1. **Edge authn/authz.** The FastAPI operator surface uses a trusted-header role model (`X-HB-UI-Role`) suited to loopback/tailnet. A public edge needs real authentication (the OAuth 2.1/PKCE MCP path exists; the operator surface would need equivalent enforcement) before exposure.
2. **NAS firewall / router / Tailscale posture reconfirmation** — carried unconfirmed from N2C; must be verified on the NAS.
3. **Mac↔NAS single-writer cutover** — unload `com.hb.personal-assistant.scheduler.production` on the Mac (loaded-but-idle, targets the Mac DB) before the NAS owns a scheduler. **N8A reports only; the unload is the N8B/N9 action.**
4. **Secret-management review** — `auth/security` folder hardening (the `0777` blocker carried from N1A/N2C) before any credentials land on the NAS; no tokens/keys committed.

## Verdict

**N8B NOT READY (foundations strengthened).** N8A closed the live-proof residue (config drift, dead sudoers rule, runner reconciliation) and re-confirmed the gated pipeline, but public exposure remains gated on edge authn/authz, NAS network reconfirmation, the single-writer cutover, and secret-folder hardening.
