# Runbook — Source-Index Migration, Backup, Recovery & Rollback (Phase C)

Operational runbook for migrating a legacy source-index SQLite database to the current schema head
(V127) with a verified backup, atomic-interruption recovery, and a restore-based rollback. Scope:
PC-WI-05 of `GOAL-SOURCE-INDEX-PHASE-C-CLOSURE-001`. This runbook describes the procedure and its
guarantees; the guarantees are proven by the Phase C test suite (`tests/source_index/`) and gated by
`scripts/ci_source_index_phase_c_gate.sh`. It performs **no** production database migration by itself.

> Guardrails: every backup/restore/rehearsal database lives under a **caller rehearsal root**; the
> configured application database is refused by default; no schema downgrade is performed in place.

## 0. Preconditions

- A validated legacy source-index database (origin V121/V124/V125/V126, or fresh) under a rehearsal root.
- The matching executable build for the origin (for a rollback probe, the **prior** executable).
- Runtime: Python 3.12+ (validated on 3.14.5), SQLite 3.53.1. Schema head = V127.

## 1. Back up before migrating (PC-WI-02, PC-AC-030/031)

1. Take a **consistent online backup** with `sqlite3.Connection.backup()` over a read-only source URI
   (`mode=ro`) — never a raw file copy while a WAL is active.
2. Persist the durable **receipt** (`generated_utc`, `schema_version`, `backup_path`, `backup_sha256`,
   `byte_size`, source/backup logical-inventory hashes, `status`). `status` is `complete` only when the
   live source still equals the snapshot; otherwise `source_advanced_during_backup`.
3. **Verify** the backup (`verify_backup`): size + SHA-256 + integrity. A partial/corrupt backup must
   never be mistaken for valid.

Keep the verified backup + receipt: it is the sole rollback source (see §5).

## 2. Migrate to head (single atomic transaction)

Run the migrator against the target: `SQLiteMigrator(db_path=...).apply()`. The entire V1→V127 body runs
in **one** `with transaction(conn)` block — there are no per-migration commits.

- **V125** adds `source_index_scan_quarantine`; **V126** adds source rename-lineage; **V127** *rebuilds*
  `source_intelligence_events` (widens the `event_type` CHECK to accept the governed `moved` type; adds
  `dest_rel_path`/`next_attempt_at`). V127 is **not** additive — see §6.

## 3. Validate after migrating (PC-WI-01, PC-AC-015..025)

- `PRAGMA quick_check` / `integrity_check` / `foreign_key_check` all clean.
- Ledger contains every version `1..127` exactly once (no gaps, no duplicates).
- Logical-inventory + semantic parity oracles pass (event/generation/lineage/card/FTS identity).

## 4. Interruption & recovery (PC-WI-03, PC-AC-036..039)

- **Atomic interruption (PC-AC-037):** if the process is killed mid-`apply()`, no migration is
  committed. On the next open, SQLite WAL/journal recovery discards the uncommitted transaction and the
  database returns to its **origin head**, logically unchanged. Verify `MAX(version)` == origin and the
  integrity checks before reusing it.
- **Recoverable rerun (PC-AC-038):** simply rerun `apply()`; it reaches V127 with the ledger intact (no
  duplicated migrations).
- **Bounded locking (PC-AC-036):** a competing writer causes `apply()` to fail with "database is
  locked" within the connection's bounded `busy_timeout` (5000 ms) rather than hanging. Retry after the
  other writer releases the lock.
- **Unrecoverable integrity failure (PC-AC-039):** if the database is corrupt, the fail-closed read-only
  inventory engine raises / reports integrity ≠ ok. Do **not** treat a corrupt database as migrated;
  restore from backup (§5).

## 5. Rollback = restore + prior executable (PC-WI-02/03/04, §8, PC-AC-041/042)

There is **no in-place schema downgrade**. To roll back:

1. Stop all use of the migrated database.
2. **Restore** the verified pre-migration backup to a **new** path (`restore_backup`).
3. **Verify** the restored backup (integrity + logical inventory; `validate_restored`).
4. Run the **matching prior executable** against the restored database.
5. Verify read-only service before resuming.

In-place schema downgrade is unsupported unless separately implemented and approved; the V127
`source_intelligence_events` rebuild cannot be losslessly reversed.

## 6. Executable / database compatibility constraints (PC-WI-04, PC-AC-040)

- A **prior** executable (e.g. head V124) against a **new V127** database is compatible **only for the
  read-only generation-table path** (`current_version()`, `SourceIndexRepository.generated_note_counts()`).
- It **must not** process the `source_intelligence_events` queue, write events, or run as a general
  application against V127: V127 introduces the `moved` event type the prior executable's vocabulary
  (`created`/`modified`/`deleted`/`reindex_requested`/`rebuild`) does not include, and it would
  misclassify or reject such rows.
- See `docs/architecture/source-index-phase-c-executable-compatibility.md` for the full matrix.

## 7. CI gate & determinism (PC-WI-05, PC-AC-046/047)

- `scripts/ci_source_index_phase_c_gate.sh` runs the Phase C suite (`tests/source_index/`) + ruff +
  strict mypy on the Phase C source modules, deterministically (venv-pinned interpreter; scratch DBs +
  temp roots + a fresh-interpreter historical `git worktree`; no NAS/production/network).
- It runs **separately** from `scripts/ci_source_index_gate.sh` (Phase A/B), which remains green.
- **Full git history** is required: the executable-compatibility proof checks out a pinned prior
  executable; a shallow clone makes those tests fail closed (INSUFFICIENT EVIDENCE), never a false pass.
