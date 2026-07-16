# 11 — Compatibility & Rollback Matrix

## Scope note — AC-15 (EVID-AUD-004)
The migration was rehearsed via the shared `SQLiteMigrator.apply()` **engine** against an EXPLICIT_DEVELOPMENT
target — **not** the integrated MANAGED_PRODUCTION operator route (that route is bound to the real NAS path by
exact-path equality and cannot be reproduced off-production). Therefore, for V127-AC-15: **migration-engine
rehearsal = PASS; integrated operator-route rehearsal = NOT VERIFIED** (owned by the deployment gate in a
maintenance window). The SOURCE / NOT VERIFIED cells below already reflect that off-prod boundary.

generated_utc: 2026-07-16
Legend: PASS = direct reproducible evidence; SOURCE = determined from source/policy, not run against prod; NOT VERIFIED = not empirically exercised.

| App/process state | DB V124 | DB V127 | Evidence |
|---|---|---|---|
| **Currently deployed image** (<deployed-revision>, ~V124-era MCP `--nas-readonly`) | RUNS (PASS) — live now; reads the V124 snapshot, does not open the live managed DB | INCOMPATIBLE for 'moved' rows (SOURCE) — old code cannot read/insert `'moved'` events (migrator.py:9417-9419); extra columns tolerated but `'moved'` rows unknown. Not run against V127 (NOT VERIFIED empirically) | 08 (deployed identity), 06 (source caveat) |
| **New V127-capable image** (97efbb6b candidate) | REFUSES to serve until explicit authorized migration (SOURCE) — startup policy `schema_behind_requires_operator_flag` / `_requires_backup_receipt` → fail-closed unless the startup-migration enable flag is set + valid receipt | RUNS (PASS) — head match; image code `LATEST_SCHEMA_VERSION=127`, imports/loads clean | 07 (image proof), route-map, startup_schema_policy source; new-image-on-V124 startup refusal NOT VERIFIED empirically (needs a MANAGED path) |
| **Dedicated migration/admin process** (startup or admin route) | Migrates V124 → V127 (PASS) — rehearsed end-to-end via candidate image, 5.7s, atomic, idempotent | N/A (already at head; re-run is a no-op) | 14, 16, 15b |
| **Prior rollback image** (<prior-rollback-image> / deployed <deployed-revision>) | RUNS (SOURCE — it is the pre-V124 lineage) | Requires DB RESTORE first (SOURCE) — code rollback after schema advancement is unsafe while `'moved'` rows exist; restore the V124 backup, then run the old image | 08 (image present), 13 (restore proof), 15 |

## Determinations (from evidence)
- Old application can run against V127? **NO for 'moved'-bearing data** (source-documented); tolerant of the additive V126 column but not the widened event semantics. Not empirically run (would require prod).
- New application starts normally against V124? **NO — it fail-closes and demands an explicit authorized migration** (startup policy), which is the intended safety behavior (no silent migration on restart, per VIEWER_MODE.md). SOURCE; empirical off-prod test blocked by MANAGED-path binding.
- New application refuses service until explicit migration? **YES** (startup policy decisions `schema_behind_requires_operator_flag` / `_requires_backup_receipt`).
- Old application can be restored after schema advancement? **Only via DB restoration** — a bit-for-bit V124 restore is proven (13); image-swap alone is unsafe after V127.
- Code rollback requires database restoration? **YES** after V127 (source caveat + restore proof).
- Forward recovery required after V127? Re-run the V127 image against a repaired/restored DB (documented; not a data-loss path since the migration is additive + atomic).

## Notes
- The matrix cells marked SOURCE/NOT VERIFIED cannot be empirically closed without executing against the live
  production target or a MANAGED-classified path, which is outside the authorized read-only + local-rehearsal scope.
  Independent deployment-readiness review should close them in a controlled maintenance window.
