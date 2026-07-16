# 06 — Schema & Migration Chain (V124 → V127)

- generated_utc: 2026-07-16
- command_class: LOCAL_REPOSITORY_READ_ONLY
- source: origin/main `97efbb6b`, `src/hb_assistant/store/migrator.py` (evidence worktree checkout)
- head: `LATEST_SCHEMA_VERSION = 127` (migrator.py:21)
- live target (verified Stage 1, 09b): schema_migrations MAX = **124** → pending chain = V125, V126, V127.

## Migration engine & transaction boundary (authoritative)
`SQLiteMigrator.apply(*, conn=None, authorization=None, require_backup_receipt=False)` (migrator.py:7657):
- Opens/owns its own connection when `conn` is None and closes it deterministically in `finally` (avoids GC-time WAL checkpoint perturbing byte-compare readers) — migrator.py:7676-7685.
- `_apply_on_connection` (7687) → `describe_opened_database(conn, db_path)` establishes the opened-target identity **and retains a read-only guard FD** (NF-ENV-001 surface), closed on every path (7701-7708).
- `_run_guarded_migration` (7710): `validate_authorization(authorization, opened, require_backup_receipt=...)` runs **before any DDL** (7739); a borrowed connection already `in_transaction` is refused (RC-3, 7754); `assert_origin_version` enforces the authorized origin (replay defense, 7768); emits `migration_started/rejected/completed` audit events.
- **The ENTIRE V1…V127 sequence runs inside ONE `with transaction(conn):`** (7781). A crash rolls back the whole migration — no partial schema, no lost queued rows.
- `revalidate_opened_identity(opened)` immediately before the transaction commits (9442, NF-AUD-005): a path→inode swap mid-migration raises and rolls everything back.

## V124 — `v124_index_metadata_fts_rowid` (migrator.py:9339-9355)
- DDL: `CREATE INDEX IF NOT EXISTS idx_si_metadata_fts_rowid ON source_intelligence_metadata(fts_rowid)`.
- Purpose: index the hot FTS-search join key (`m.fts_rowid = f.rowid`) to remove a transient full-table automatic index over the ~883k-row metadata table.
- Shape: additive, index-only, no data touched. **This is the version the live DB already sits at** (applied 2026-07-12 per live ledger).

## V125 — `v125_source_index_scan_quarantine` (migrator.py:9357-9370; statements `_v125_statements()` @7147, sourced from `store/source_index_scan_quarantine_tables.py`)
- DDL: `CREATE TABLE IF NOT EXISTS source_index_scan_quarantine (…)` + partial UNIQUE index `idx_source_index_scan_quarantine_active (source_root_key, rel_path)` + `idx_source_index_scan_quarantine_root_state (source_root_key, resolution_state)`.
- Purpose: durable poison-file quarantine (root-level blocker for files that repeatedly fail per-file observation/upsert).
- Shape: additive, ships EMPTY, parity-guarded (`IF NOT EXISTS`). No backfill.

## V126 — `v126_source_rename_lineage` (migrator.py:9372-9401)
- DDL: guarded `ALTER TABLE source_intelligence_sources ADD COLUMN renamed_from_source_id TEXT` (PRAGMA table_info check first) + partial index `idx_si_sources_renamed_from … WHERE renamed_from_source_id IS NOT NULL`.
- Purpose: same-root rename/move lineage (Phase B/B4).
- Shape: additive nullable column, **no row-wide backfill** (legacy rows stay NULL). Idempotent re-run.

## V127 — `v127_events_moved_dest_backoff` (migrator.py:9403-9437; `_events_schema_current` @9463, `_rebuild_v127_events` @9557)
- Purpose: durable-queue support for governed `'moved'` events — (a) widen the `event_type` CHECK to accept `'moved'`, (b) add nullable columns `dest_rel_path` and `next_attempt_at`.
- Mechanism: SQLite cannot ALTER a CHECK, so `source_intelligence_events` is **rebuilt** (CREATE new / INSERT…SELECT all rows / DROP / RENAME) **inside the single apply() transaction** → atomic; a crash rolls back and cannot lose queued rows.
- Uses version-pinned `EVENT_TYPE_VALUES_V127 = (*EVENT_TYPE_VALUES, "moved")` (`store/source_intelligence_tables.py`).
- **ALWAYS-REVALIDATE (PLAN-C2R2-003):** `_events_schema_current` checks the EXACT structural contract (column types/nullability/defaults, index composition, FK/trigger absence, a live CHECK probe via SAVEPOINT `v127_probe`) on EVERY apply — a v127-recorded-but-malformed table is detected and rebuilt fail-closed, not trusted on the version record. Rebuild parity failure → `v127_events_rebuild_parity_failed`; an invalid existing row (bad event_type/status or NULL event_id) → `v127_events_invalid_existing_rows`; either rolls the whole migration back.
- **Rollback caveat (from source comment, migrator.py:9417-9419):** after V127, OLD application code cannot read/insert `'moved'` rows. The comment explicitly directs: *"do NOT deploy or migrate production in Phase B (Phase C owns the prod schema-copy + backup/restore proof)."* → This engagement is that Phase C prod-copy + backup/restore proof. Feeds the compatibility matrix (11): code rollback after V127 requires DB restore, not image-swap alone.

## Covering tests (repo)
- V124: `tests/test_source_index_search_latency_index.py`, `tests/test_migrator_v123_relpath_index.py`
- V125: `tests/test_source_index_quarantine.py`
- V126: `tests/test_migrator_v126_rename_lineage.py`, `tests/test_source_index_rename_lineage.py`
- V127: `tests/test_migrator_v127_moved_event.py`, `tests/test_source_index_moved_drain.py`
- Authorization/opened-identity: `tests/test_nf_f_001_migration_authorization_guard.py`, `tests/test_nf_f_001_storage_class.py`, `tests/test_nf_f_001_reachability.py`, `tests/test_startup_schema_policy.py`, `tests/test_db_storage_guard.py`
(Behavior verified from source above, not test names alone; rehearsal in Stage 3 exercises the chain end-to-end on a V124 copy.)
