# N2C-V · 07 — N3 Readiness Verdict

## Verdict
**PASS — READY FOR EXPLICIT N3 AUTHORIZATION.** All N2 security/technical gates are closed. The
only remaining precondition is the operator's explicit authorization to begin N3.

## Preconditions for N3 — status
| Precondition | Status |
|--------------|--------|
| Schema head-version drift fixed (expected == applied == 98) | ✅ PASS (N2) |
| Public WAN exposure removed + UPnP mechanism disabled | ✅ PASS |
| DSM firewall default-deny with LAN + Tailnet allows | ✅ PASS |
| Independent admin control path (bfetting) proven | ✅ PASS |
| Runtime account least-privilege (svc demoted) | ✅ PASS |
| Runtime tree writable under least privilege (db/backups/…) | ✅ PASS |
| Port 8000 not publicly reachable | ✅ PASS-with-note (keep loopback/LAN bind) |
| **Explicit operator authorization to start N3** | ⛔ **NOT GRANTED** |

## What N3 is (for reference only — NOT executed here)
Bounded creation of a **copied** DB on the NAS via the SQLite **backup API**, per the plan docs in
`docs/evidence/nas-safe-db-migration-n2/…` (`05-sqlite-backup-api-plan.md`):
- Source opened `mode=ro`; destination **NAS-local only** (never `/Volumes`).
- `integrity_check` + `schema_version` (expect 98) + row-count verification post-copy.
- Timestamped pre-overwrite backup; explicit stop conditions; default dry-run/report-only.
- Live Mac backend quiesced first (`06-live-db-quiesce-plan.md`); copied-DB `/health` smoke with
  workers off and loopback/tailnet bind (`07-nas-copied-db-smoke-plan.md`).

## Hard stop
**This phase does not proceed to N3.** N3 may be authorized **separately** by the operator. Until
that explicit authorization is given in chat, no DB is copied, opened, or migrated, and no backend
is started.
