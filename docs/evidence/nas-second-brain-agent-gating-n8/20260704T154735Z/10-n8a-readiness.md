# 10 — N8A (Cloudflare / Public Exposure) Readiness Assessment

N8A is **out of scope** for N8 (assessed only, not implemented). This records whether the pieces N8A
would depend on are ready.

## Ready

- **Default-off posture (3a):** `HB_NAS_RUNTIME=1` forces workers/watcher/poll-loop off and refuses
  on-demand watcher starts — a public-facing surface would not silently spin background work.
- **Storage locality guard:** `HB_NAS_RUNTIME=1` restricts the DB to NAS-local `/volume2/personal-assistant/`
  (rejects `/Volumes`, SMB/NFS, UNC, permissive override) — fail-closed.
- **Single-writer within the canonical DB:** watcher lease + run lock (now host-stamped) serialize and
  fail-closed on contention.
- **Source identity:** cross-root collision ruled out (3c) — multi-root ingestion is safe before any
  broader exposure.
- **Loopback-only default:** compose publishes to `127.0.0.1`; tailnet IP is opt-in and redacted in repo.
- **MCP broker (N7):** read-only DB allowlist + path-safe FS tools + audit + redaction already exist.

## Blocking / required before N8A

1. **AuthZ/AuthN for a public edge.** Current backend role handling (`X-HB-UI-Role`) is a trusted-header
   model suited to loopback/tailnet. A Cloudflare edge needs real authentication (the OAuth 2.1/PKCE MCP
   path exists, but the FastAPI operator surface would need equivalent enforcement) before exposure.
2. **NAS firewall / router / Tailscale posture reconfirmation** — carried unconfirmed from N2C; must be
   verified on the NAS.
3. **Mac↔NAS single-writer cutover** — unload `com.hb.personal-assistant.scheduler.production` on the Mac
   (preflight action item) so only the NAS owns the canonical DB/scheduler.
4. **Live bounded proofs (Phases 04–07)** — must pass on the NAS (ingestion, card write, duplicate
   prevention, live-DB V99 backfill) before trusting the pipeline behind any edge.
5. **Secret-management review** — `auth/security` folder hardening (0777 blocker from N1A/N2C) before any
   credentials land on the NAS; no tokens/keys committed.

## Verdict

**N8A NOT READY.** Foundations (default-off, storage guard, single-writer, source identity, MCP broker)
are in place, but public exposure is gated on real edge authn/authz, NAS network reconfirmation, the
single-writer cutover, the live bounded proofs, and secret-folder hardening.
