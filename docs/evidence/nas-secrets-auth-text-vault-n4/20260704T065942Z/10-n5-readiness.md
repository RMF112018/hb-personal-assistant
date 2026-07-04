# 10 — N5 Readiness

## N4 verdict: WARN (evidence-only)
- ✔ Source Text Vault coherence **proven** (7,198/7,198 refs backed; key present).
- ⧗ NAS Text Vault coherence **deferred** (no key/blobs on NAS).
- ⛔ N5 full readiness **BLOCKED** pending explicit authorization of the Text Vault key/blob copy + NAS coherence re-proof.

## Gate to unblock N5
1. **Authorize the Text Vault key+blob copy** (spec in 08): non-privileged stage → operator sudo placement into
   `security/text-vault` (0700, files 0600, `svc:users`, key 0600) → NAS-side coherence re-proof as svc read-only
   (blob count vs 7,198 distinct refs; existence only, no decrypt/print). Target: 0 refs missing.

## N5 scope (after the gate, each separately authorized)
- **MSAL re-provision**: device-code `hb-assistant auth login` on NAS → fresh `msal-token-cache.bin` (0600 svc). (06)
- **Procore re-provision**: provide client secret via env/protected file, mint fresh `procore_token.json` (0600 svc). (07)
- **Optional bounded decrypt smoke**: prove key↔blob↔DB works end-to-end on NAS by decrypting a *tiny* sample as svc
  — **counts/success-boolean only, never print decrypted text** — against the `app-support-smoke` scratch root,
  never the copied DB.
- **Text Vault fail-closed hardening** (05): make incoherence a fail-closed/reported condition rather than silent
  new-key generation / `None`.

## Still prohibited until separately authorized
Production backend start · scheduler/watcher enablement · vault/source-root migration · MCP expansion · Cloudflare ·
direct svc SSH · broad passwordless sudo · push/PR · basing on origin/main.
