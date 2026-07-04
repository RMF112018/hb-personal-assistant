# 03 — SQLite Backup-API Copy Proof

## Method

Reused the repo's canonical read-only backup pattern (`src/hb_assistant/launcher/profiles.py:213-222`):

- Source connection: `sqlite3.connect("file:<live>?mode=ro", uri=True)` + `PRAGMA query_only=ON`
- Destination: new file, `src.backup(dst, pages=1000, sleep=0.05)`
- Destination `PRAGMA wal_checkpoint(PASSIVE)` then closed cleanly
- Partial destination unlinked before start if present; no retry against source on error

## Result

| Field | Value |
|---|---|
| backup API | `src.backup(dst)` |
| source opened | read-only URI + `query_only=ON` |
| destination (raw `.sqlite`, **outside repo**) | `<scratchpad>/nas-n3/hb-personal-assistant-n3-copy.sqlite` |
| destination size | 4,151,631,872 bytes |
| elapsed | 3.6 s (local SSD) |
| destination sidecars | none (checkpointed single file) |
| **source unchanged** | **True** (size/mtime-ns/inode identical pre vs post: 4,151,631,872 / same) |

The raw copied `.sqlite` is deliberately staged in the session scratchpad (outside the git repo) so it can never be committed. Only its SHA + summaries appear in evidence (`local-sensitive/local-copy.sha256`).
