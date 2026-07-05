# 00 — N8A Live Phase — Index

Read-only live-state reconciliation + the two operator-approved remediations for N8A. Executed as `bfetting` over SSH (`hb-nas:10021`), **non-sudo**, no DB/vault/config mutation, no secrets printed. Sudo stayed password-required throughout; **no NOPASSWD grant and no privileged runner were installed** (both remediations proved to be no-ops).

## Status

| Doc | Scope | Status |
|---|---|---|
| `01-live-state-reconciliation.md` | RO reconciliation of committed `05a`/`06a` vs live | **DONE** |
| `02-config-drift-remediation.md` | `/volume1`→`/volume2` config fix | **CLOSED — already resolved** (no edit) |
| `03-sudoers-and-runner-cleanup.md` | proof-runner revocation + dead sudoers rule | **A closed (runners absent); B closed (dead rule absent, rc=1); C no new grant** |
| `04-mac-scheduler-status.md` | Mac single-writer scheduler (report only) | **DONE — loaded/idle, N8B/N9 action item** |

## Key reconciliation outcome
The two N8-open remediation items are **already resolved** on the live NAS:
- Temporary proof runners (`hb-pa-proof05/06/07`) — **revoked/absent**.
- `/volume1` app-support config drift — **corrected to `/volume2`** (both configs), `_vault_disabled` sentinel intact.

So N8A made **no live NAS mutation**. It verified at rest: the Proof-06 card and the proof05/06/07 backups are present; configs are `/volume2`-aligned with the storage guard.

## Root confirmations
1. **Dead `/volume1` sudoers rule** (`05a`): **DONE** — operator ran `sudo grep -rns "/volume1/personal-assistant/bin/hb-mcp-runner" /etc/sudoers /etc/sudoers.d/` → `rc=1` (absent). Sudo was password-required (entered interactively); no NOPASSWD grant used. (`03` §B)
2. **DB at-rest counts** (optional, confirms V99 + no duplicate rows): one read-only `sudo` pass over the `0600` svc-owned DB (immutable RO). **Not run** — not a blocker; N8A wrote nothing and the card/backups/config are confirmed at rest. See `03` and the snapshot `05`/`07`.
