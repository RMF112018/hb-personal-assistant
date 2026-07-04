# 09 — N5 Readiness After N4A

## N4A verdict: PASS
NAS Text Vault is now coherent with the copied DB (7,198/7,198 refs backed, 0 missing, correct least-privilege perms).

## N5-readiness checklist (state now)
| Requirement | State |
|---|---|
| NAS DB still valid | ✔ `quick_check/integrity=ok`, schema 98, unchanged since N3 |
| Text Vault key present on NAS | ✔ `security/text-vault.key` 600 svc |
| Text Vault blobs present on NAS | ✔ 7,202 blobs 600 svc |
| 0 missing refs | ✔ COHERENT=YES |
| Permissions least-privilege | ✔ 700 dirs / 600 files / svc:users |
| MSAL / Procore | ⧗ still planned for **re-provision** in N5 (not copied) |
| Backend not started | ✔ |
| Vault / source roots not migrated | ✔ |

## N5 scope (each separately authorized)
1. **MSAL re-provision** — device-code `hb-assistant auth login` on NAS → fresh `auth/msal-token-cache.bin` (600 svc).
2. **Procore re-provision** — supply client secret via env `PROCORE_CLIENT_SECRET` / protected file; mint fresh `auth/procore_token.json` (600 svc). Keychain does not migrate.
3. **Optional bounded decrypt smoke** — prove key↔blob↔DB end-to-end by decrypting a *tiny* sample as svc, **printing only success + plaintext length** (no plaintext), on the `app-support-smoke` scratch root — never the copied DB / production root.
4. **Text Vault fail-closed hardening** (see 07) — code change, reviewed separately.

## Still prohibited until separately authorized
Production backend start · scheduler/watcher enablement · vault/source-root migration · MCP expansion · Cloudflare ·
direct svc SSH · broad passwordless sudo · push/PR · basing on origin/main.

**N5 not authorized. Stop after N4A closeout.**
