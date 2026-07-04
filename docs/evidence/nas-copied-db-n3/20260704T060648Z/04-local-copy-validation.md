# 04 — Local Copied-DB Validation

Target: `<scratchpad>/nas-n3/hb-personal-assistant-n3-copy.sqlite` (opened `mode=ro`).

| Check | Result |
|---|---|
| `PRAGMA quick_check` | `ok` |
| `PRAGMA integrity_check` (full) | `ok` |
| `PRAGMA page_count` × `page_size` | 1,013,582 × 4,096 = 4,151,631,872 B |
| table count (`sqlite_schema`) | 506 (matches source) |
| `SELECT MAX(version) FROM schema_migrations` | 98 |
| `SQLiteMigrator(copy).current_version()` | **98** |

SHA-256 of the copy in `local-sensitive/local-copy.sha256`. (Note: the copy's SHA differs from the live DB's SHA by design — the backup API rewrites the file; byte-equality with source is not expected. The relevant equivalence is copy ↔ NAS-placed file, pending Step 7.)

**Local validation: PASS.**
