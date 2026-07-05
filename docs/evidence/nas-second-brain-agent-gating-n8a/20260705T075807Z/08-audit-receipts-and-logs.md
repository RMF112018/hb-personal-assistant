# 08 — Audit Receipts + Logs

## Test receipts (non-live, clean base)

| Suite | Result |
|---|---|
| `test_nas_default_off_gating.py` | 6 passed |
| `test_obsidian_source_watch_ownership.py` | 11 passed |
| `test_source_identity_v99_migration.py` | 6 passed |
| **Total** | **23 passed** |

`LATEST_SCHEMA_VERSION = 99` (`store/migrator.py:17`) on the base `origin/main` @ `704f59c8`.

## Live read-only receipts (non-sudo, as `bfetting` @ `hb-nas:10021`)

| Check | Command (structure) | Result |
|---|---|---|
| Proof runners present? | `ls /usr/local/sbin \| grep hb-pa-proof0` | none (absent) |
| Config drift? | `grep application_support_root/obsidian_vault` on both configs; `grep -l /volume1` | `/volume2` on both; no `/volume1` token |
| Sentinel preserved? | vault key in `hb-pa-config.yml` | `…/app-support/_vault_disabled` |
| Card at rest? | `find …/vault/obsidian -name 'note-a.txt__*.md'` | 1 hit: `Source Notes/Shared/note-a.txt__482f41ec8a37.md` |
| Backups present? | `ls …/db/backups/` | proof05, proof06 (×2), proof07 |
| DB perms | `stat` | `personal-assistant-svc:users` `600` (no bfetting read) |
| Vault perms | `stat` | `personal-assistant-svc:users` `777` (flagged, pre-existing) |

**Operator root check DONE (sudo, password-required):** dead `/volume1` sudoers rule → `sudo grep … /etc/sudoers /etc/sudoers.d/` returned `rc=1` (absent). **Optional, not run:** DB at-rest V99 + per-table counts (`0600` svc DB). See `../live-20260705T075807Z/00-live-index.md`.

## Mutation receipts
**None.** N8A made zero live NAS mutations (no config edit, no runner install/revoke, no DB/vault write, no card). Both approved remediations were already-resolved no-ops.

## Ownership / lock receipts
Not exercised live (no watcher/ingestion run). Gating verified via the temp-DB ownership suite (11 passed): host-stamped lease refuses a second writer, fails closed on lease error. Owner tokens are redacted from `status()` by design (`source_watch.py:284`).

## Redaction / secret-scan proof
- `tests/test_repo_sensitive_scan.py` reports **16 findings, ALL pre-existing** in untouched files (`tests/test_procore_full_raw_payload_ingestion.py`, `tests/test_obsidian_mcp_oauth.py`, `subrepos/construction-financial-review/tests/test_safety_scan.py`, `frontend/src/**/*.test.tsx`, …). **Zero are in N8A files** — identical to the N8 base ("16 findings all pre-existing, zero in N8 files"). This is the known allowlist drift, not an N8A regression.
- Manual scan of the N8A evidence tree for **NAS hostname / tailnet-IP literal / tokens / keys / secrets / decrypted bodies / MSAL / Cloudflare** → none. The only regex hits were this document's own *do-not-include* word lists and the non-secret loopback constant `127.0.0.1` (committed per N8 convention). `/volume1` and `/volume2` appear as required to document the drift/dead-rule findings (non-secret).
- All SSH command output was filtered through a tailnet-IP redactor; no hostname or IP literal was printed or committed. No `local-sensitive/` raw artifact was needed (all live checks were non-secret path/existence reads).
- 0 attribution trailers; no Claude/Anthropic/Cursor lines in the evidence.
