# 06 — V125 migration evidence (additive, upgrade-safe, idempotent, integrity-checked)

**Migration:** V125 `source_index_scan_quarantine` — the durable poison-file quarantine table (A4).
**`LATEST_SCHEMA_VERSION`:** 124 (origin/main `9c27839b`) → **125** (branch HEAD). Additive only; no existing
table is rewritten. Raw captures: `a4-migration-evidence.txt` (fresh / idempotent / simulated upgrade) and
`a4-migration-precise.txt` (REAL V124→V125 upgrade + DDL + FK/quick/integrity + rollback coexistence).

## What was verified precisely

| Scenario | Method | Result |
|---|---|---|
| **Fresh DB at V125** | `SQLiteMigrator(fresh).apply()` | → 125; table + both indexes present; `quick_check`/`integrity_check`/`foreign_key_check` = ok |
| **REAL V124 fixture** | built with the **origin-baseline (V124) migrator** (`scratchpad/origin-baseline/src`) | `apply()` → 124; no quarantine table (pre-upgrade shape confirmed) |
| **Actual V124 → V125 upgrade** | copy the real-V124 DB, `apply()` with the branch migrator | → 125; `schema_migrations[125] = (125, 'v125_source_index_scan_quarantine')`; quarantine table created; `quick_check`/`integrity_check`/`foreign_key_check` = ok |
| **Idempotent rerun** | second `apply()` on the upgraded DB | → 125 (no-op); still exactly one table; `quick_check` = ok |
| **Table / index / FK definitions** | `sqlite_master.sql` + `PRAGMA foreign_key_list` | see DDL below; **no foreign keys declared** (intentional) |
| **Rollback coexistence** | run the **origin-baseline (V124) migrator against a V125 DB** holding a blocking quarantine | `apply()` → 125, no error; table + the unresolved blocking row are preserved; `quick_check` = ok |

## Table / index DDL (from a fresh V125 DB)

```sql
CREATE TABLE source_index_scan_quarantine (
    quarantine_id                  TEXT PRIMARY KEY,
    source_root_key                TEXT NOT NULL,
    generation_id                  TEXT,           -- NULLABLE: nulled when the origin generation is pruned
    origin_generation_id           TEXT,           -- retained sanitized audit lineage
    source_id                      TEXT,
    rel_path                       TEXT NOT NULL,   -- root-relative; never an absolute host path
    failure_stage                  TEXT NOT NULL,
    error_code                     TEXT NOT NULL,   -- structured classification, never raw exception text
    attempt_count                  INTEGER NOT NULL DEFAULT 0,
    first_seen_at                  TEXT NOT NULL,
    last_seen_at                   TEXT NOT NULL,
    last_attempt_at                TEXT,
    status                         TEXT NOT NULL DEFAULT 'quarantined',
    resolution_state               TEXT NOT NULL DEFAULT 'unresolved',
    resolved_at                    TEXT,
    last_successful_observation_at TEXT
);
CREATE UNIQUE INDEX idx_source_index_scan_quarantine_active
    ON source_index_scan_quarantine (source_root_key, rel_path)
    WHERE resolution_state = 'unresolved';           -- ≤ 1 active unresolved record per (root, path)
CREATE INDEX idx_source_index_scan_quarantine_root_state
    ON source_index_scan_quarantine (source_root_key, resolution_state);
```

## Foreign keys — deliberately none

`PRAGMA foreign_key_list('source_index_scan_quarantine')` returns **no rows**. This is intentional and is a
correctness requirement, not an omission: the quarantine is a **root-level** blocker that must survive
generation pruning. A foreign key with `ON DELETE CASCADE` to `source_index_scan_generations` would let
generation retention silently erase an unresolved blocker. Instead, `generation_id` is a soft, nullable
reference: when the origin generation is pruned it is set to `NULL` while `origin_generation_id` is retained
for audit and the unresolved record persists (see `07`/`a4-retention-evidence.txt`). `foreign_key_check`
returns no violations precisely because there are no FKs to violate.

## Rollback assumption (explicit scope)

Rollback safety rests **only** on the additive property: an older (V124) application ignores the new table.
Demonstrated by running the origin-baseline V124 migrator against a V125 DB — it does not error, does not drop
the table, and leaves unresolved blocking rows intact. **No schema DOWNGRADE is implemented or claimed.** A
true downgrade (dropping the table and rewinding `schema_migrations`) is neither provided nor tested; if a
rollback of application code is ever performed, the V125 table simply remains as dormant, ignored state.

## Automated coverage
The same behaviors are locked in by tests in `tests/test_source_index_quarantine.py`:
`test_migration_fresh_creates_quarantine_table`, `test_migration_is_idempotent`,
`test_migration_upgrade_recreates_quarantine_table` — plus the three pre-existing schema-version tests
(`test_v122_fresh_and_incremental_migration`, `test_v119_migration_idempotent_and_additive`,
`test_v120_migration_idempotent_and_additive`), which were updated to assert against `LATEST_SCHEMA_VERSION`
rather than a hardcoded `123` (see `08`).
