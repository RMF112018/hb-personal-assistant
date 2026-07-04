# N2 · 05 — Safe SQLite Backup-API Migration Plan (PLAN ONLY — not executed)

This is a **plan for a later phase (N3)**. Nothing here runs in N2. No DB is copied/opened/migrated.
The copy MUST use the SQLite **backup API**, never a raw file copy of a hot WAL DB.

## Why backup API, not `cp`

The live DB runs in WAL mode; a raw copy of `*.sqlite` without the matching `-wal`/`-shm` (or mid-write)
yields a torn/corrupt DB. The SQLite Online Backup API produces a transactionally consistent snapshot
from a read-only source connection and never touches the source's WAL/shm as separate files.

## 1. Preflight (all must pass before any copy)

- Live Mac backend **stopped/quiesced** — see `06-live-db-quiesce-plan.md`.
- No process holds the live DB open: `lsof "<live db path>"` returns nothing.
- Live DB path confirmed: `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`.
- WAL/shm state observed (`-wal`/`-shm` present? checkpointed?); a clean checkpoint preferred before snapshot.
- Current source schema head confirmed (expected **98** after the N2 fix).
- Text-Vault references inventoried (does the DB carry `encrypted_full_text_ref` rows?) — informs `08`.
- Source app-support size measured (capacity check on NAS-local volume).

## 2. Backup method

1. Open **source** read-only via URI: `sqlite3.connect("file:<src>?mode=ro", uri=True)`.
2. Open **destination** NAS-local DB (created fresh in a temp name).
3. `src.backup(dest)` (Python `sqlite3` backup API) — full-page snapshot.
4. Verify destination:
   - `PRAGMA integrity_check;` → `ok`.
   - Schema head: `MAX(version) FROM schema_migrations` == source head (98).
   - Row counts for key tables match source (± only explained deltas).
   - Confirm **no** raw `-wal`/`-shm` were copied alongside (backup API produces a single consistent file).
5. Atomic promote: `rename` temp → final only after all checks pass.

## 3. Destination (NAS-local ONLY)

`/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite`. **Never** a `/Volumes/*`
(SMB) path — SQLite over SMB risks lock/corruption. A stop condition (below) refuses `/Volumes`.

## 4. Backups / rollback

- Before any overwrite of an existing destination, copy it to a timestamped `*.bak-<ts>`.
- Preserve the source untouched (read-only open guarantees this) as the rollback of record.
- Write a copy receipt (counts, integrity result, schema head, sizes) into the N3 evidence dir — no raw row content.

## 5. Stop conditions (refuse the copy)

Live backend still running · DB still hot (open handle / uncheckpointed under active writer) · schema
drift unresolved · destination resolves to SMB/`/Volumes` · `integrity_check` != ok · unexplained
row-count deltas · auth/security not hardened when secrets/Text-Vault are in scope · public exposure
unresolved when the DB will be network-reachable.

## 6 & 7. No workers, no vault/source writes

Any later smoke that opens the copy runs with `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` and no
scheduler/watcher/automation/source-ingestion/vault writes.

## Draft script (NOT implemented in N2)

Per operator instruction the copy script is **not** implemented in this phase. When authorized, a
`scripts/nas_copy_db_with_sqlite_backup.py` should: default to **dry-run/report-only**; require
explicit flags to write; refuse live/`/Volumes`/non-NAS-local destinations; open source `mode=ro`;
run the verifications above; and emit a redacted receipt. It must never open the live DB read-write.
