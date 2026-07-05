# 01 — Live-State Reconciliation (read-only, non-sudo)

All checks below ran read-only as `bfetting` over SSH (`hb-nas:10021`), **without sudo** and without any DB/vault/config mutation. They reconcile the committed N8 findings (`05a`, `06a`) against actual live state. No secrets/hostname/tailnet-IP were printed.

## Result summary

| Item | Committed N8 state | Live state (this session) | Verdict |
|---|---|---|---|
| Temp proof runners `hb-pa-proof05/06/07` (+ drivers, configs) | `05a`: installed, "revocation due at closeout" | **Absent** from `/usr/local/sbin` (`ls` shows no `hb-pa-proof0*`) | **Already revoked** — `05a` stale |
| `/volume1` app-support config drift | `06a`: both configs point at `/volume1` | **Resolved** — see below | **Already remediated** — `06a` stale |
| Proof-06 bounded card | `06`: `Source Notes/Shared/note-a.txt__482f41ec8a37.md` written | **Present** at rest | **Confirmed** |
| N8 rollback backups | `05`/`06`/`07`: proof05/06/07 backups | **Present** | **Confirmed** |
| Dead `/volume1` sudoers rule | `05a`: present (dead) | **Absent** — operator `sudo grep` → `rc=1` (`03` §B) | **Closed — already removed** |
| DB at-rest counts (V99, no-dup) | `05`/`07`: V99, 3 nas_test rows, no dup | Not read (DB is `0600` svc-owned) | **Optional — not a blocker** |

## Evidence detail

**1. Proof runners.** `ls -l /usr/local/sbin/ | grep -iE "hb-pa-proof0|hb-pa-n8a|hb-mcp"` → no matches. The three temporary root-owned proof runners from N8 (and their drivers / `/volume2` configs) are gone. This confirms the closeout revocation the committed `05a` had only listed as "due."

**2. Config drift (RESOLVED).** Path keys read directly (both configs are `bfetting`-readable; `hb-pa-config.yml` is `bfetting:users` `700`, `hb-pa-config.mcp.yml` is `root:users` `640`):
```
hb-pa-config.yml:20:  application_support_root: /volume2/personal-assistant/app-support
hb-pa-config.yml:24:  obsidian_vault: /volume2/personal-assistant/app-support/_vault_disabled
hb-pa-config.mcp.yml:3:  application_support_root: /volume2/personal-assistant/app-support
```
`grep -lE "/volume1/personal-assistant"` on both configs → no match. The migration-era `/volume1` drift (`06a`) is **already corrected to `/volume2`**, and the `_vault_disabled` sentinel is intact (vault writes not enabled). This matches the prior-session "config drift resolved, verify on next boot" note; N8A verifies it at rest.

**3. Proof-06 card present.** `find …/vault/obsidian -name "note-a.txt__*.md"` → `Source Notes/Shared/note-a.txt__482f41ec8a37.md`. The N8 bounded card is at rest, unchanged.

**4. Backups present.** `…/app-support/db/backups/` lists `proof05-20260704T211230Z`, `proof06-20260704T214326Z`, `proof06-20260705T063848Z`, `proof07-20260705T070028Z` — the N8 rollback points remain available.

## Observations (pre-existing, flagged, not N8A scope)

- **Vault directory mode `777`** (`personal-assistant-svc:users`) on `…/vault/obsidian` — world-writable; consistent with the `auth/security 0777` hygiene items carried from N1A/N2C. Recommend tightening in the secret-folder-hardening track (N8B readiness item #4), not here.
- **DB** is `personal-assistant-svc:users` `mode=600` — `bfetting` has no direct read (as designed). At-rest DB counts require a root read-only pass (see `03` / pending commands).

## Verdict

**Reconciled — the N8-open remediation items are already resolved** (runners revoked; `/volume1`→`/volume2` config drift corrected, sentinel preserved; dead `/volume1` sudoers rule confirmed absent via operator `sudo grep` → `rc=1`). N8A therefore performs **no config edit and no runner revocation** (all no-ops). The DB at-rest count read-out (`0600` svc-owned) remains an optional, non-blocking confirmation — see `03`.
