# 02 — Live DB Source Proof (read-only)

Live DB: `/Users/bobbyfetting/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`

## File-system facts (pre-copy)

| Field | Value |
|---|---|
| size | 4,151,631,872 bytes (~3.9 GiB) |
| mtime | 1783123233 (Jul 3 2026 20:00:33) |
| inode | 105921913 |
| mode | `-rw-r--r--` (bobbyfetting:staff) |
| `-wal` / `-shm` sidecars | **none** (cleanly checkpointed) |

SHA-256 recorded in `local-sensitive/live-db.sha256` (full path + hash withheld from committable evidence).

## Read-only inspection (no mutation)

Opened `file:<path>?mode=ro` (URI) + `PRAGMA query_only=ON`. No VACUUM/ANALYZE/REINDEX/migration/writes; no row contents read.

| Check | Result |
|---|---|
| `PRAGMA query_only` | `1` (read-only enforced) |
| `PRAGMA database_list` | single `main` db = live path |
| `PRAGMA page_count` × `page_size` | 1,013,582 × 4,096 = 4,151,631,872 B (== file size → no un-flushed WAL) |
| `PRAGMA journal_mode` (read) | `wal` (reported, not changed) |
| `PRAGMA quick_check` | `ok` |
| table count (`sqlite_schema`) | 506 |
| `SQLiteMigrator(live).current_version()` | **98** |
| `LATEST_SCHEMA_VERSION` (const) | 98 |

## Source-unmodified proof

Re-`stat` after the read-only open: `size=4151631872 mtime=1783123233 inode=105921913` — **identical** to pre. No `-wal`/`-shm` sidecar was created by the read-only connection. **Live DB unmodified.**
