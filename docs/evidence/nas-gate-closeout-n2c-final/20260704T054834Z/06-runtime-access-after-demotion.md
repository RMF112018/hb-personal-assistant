# N2C-V · 06 — Runtime Access After Demotion (FINAL)

## Question
After removing `personal-assistant-svc` from `administrators`, can the future HB backend still
read/write everything it needs under `/volume1/personal-assistant`?

## Answer: yes — verified per folder
Runtime write-proof (operator, via `sudo -u personal-assistant-svc`) was **PASS on every runtime
folder**:

| Folder | Purpose | Write |
|--------|---------|-------|
| `auth` | MSAL token cache (re-auth on NAS in a later phase) | PASS |
| `security` | security/config material | PASS |
| `db` | SQLite DB + WAL/SHM (copied-DB dest in N3) | PASS |
| `backups` | pre-overwrite DB backups | PASS |
| `logs` | runtime logs | PASS |
| `evidence` | on-NAS evidence capture | PASS |
| `cache` | derived/cache data | PASS |
| `tmp` | scratch | PASS |
| `runtime` | pid/socket/runtime state | PASS |

## Operational access model (post-demotion)
- No direct svc login (`05`).
- Backend process runs **as** `personal-assistant-svc` (unprivileged) and owns the tree above.
- Human/admin operations go through `bfetting` (`04`); svc-context commands via
  `sudo -u personal-assistant-svc`.

## Bearing on N3
The N3 copied-DB destination (`db/`, with `backups/` for the pre-overwrite snapshot) is confirmed
writable by the runtime account under least privilege. No permission blocker remains for a later,
**separately authorized** copied-DB creation.

**Gate: PASS.**
