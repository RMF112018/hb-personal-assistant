# 01 — Preflight from N4

## Git state
| Field | Value |
|---|---|
| branch | `ops/nas-copied-db-n3-20260704T060648Z` |
| HEAD | `39961a35` (N4 evidence commit) |
| vs origin/main | 6 ahead / 0 behind |
| working tree | clean at phase start |
| push status | not pushed; no PR |

Commit stack: `39961a35` N4 evidence · `761864ea` N3 evidence · `9e533f6a` N2C · `4fe34348` N2B · `b912b4ed` schema 97→98 · `581ad598` scaffold.

## N4 evidence package
- Present at `docs/evidence/nas-secrets-auth-text-vault-n4/20260704T065942Z/` (12 files, **committed** in `39961a35`).
- N4 closed **WARN**: source coherence proven; NAS coherence deferred; key/blob copy required before N5 full readiness.

## Deferred condition now addressed
N4A is the authorized action that resolves the N4 deferral: copy the Text Vault key + blobs to the NAS and prove
NAS-side key↔blob↔DB coherence. (MSAL/Procore re-provision remains separately deferred to N5.)

## Controlling safety facts carried from N4
- Key must move WITH blobs (plaintext unrecoverable); do not trigger a code path that could generate a new key on the NAS.
- `SQLiteMigrator.apply()` has no version guard (write + WAL even at v98); FastAPI startup auto-migrates. ⇒ NAS DB read `mode=ro` only; no backend/MCP against the copied app-support root.
