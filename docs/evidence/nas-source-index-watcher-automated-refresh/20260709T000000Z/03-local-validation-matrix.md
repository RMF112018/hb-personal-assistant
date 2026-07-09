# 03 — Local validation matrix

**16/16 scenarios passed** · schema head 117 · tool count 87 (unchanged).

| # | Scenario | Result |
|---|---|---|
| 1 | empty temp DB migrated to head | ✅ PASS |
| 2 | bootstrap dry-run plans, writes nothing | ✅ PASS |
| 3 | bootstrap apply indexes file layer | ✅ PASS |
| 4 | bootstrap apply builds structure layer | ✅ PASS |
| 5 | watcher_ready true after both layers | ✅ PASS |
| 6 | file index rows exist | ✅ PASS |
| 7 | health reports bootstrap complete + watcher ready | ✅ PASS |
| 8 | health has all V117 sections | ✅ PASS |
| 9 | health path-safe (no abs path) | ✅ PASS |
| 10 | idempotent second bootstrap (0 re-indexed) | ✅ PASS |
| 11 | reconcile detects new+modified files | ✅ PASS |
| 12 | reconcile detects folder drift | ✅ PASS |
| 13 | drain updates file/content index (c.md indexed) | ✅ PASS |
| 14 | deleted file no longer active search hit | ✅ PASS |
| 15 | run-state enum distinguishes 4 states | ✅ PASS |
| 16 | health surfaces drift with dirty_bridge_enabled false | ✅ PASS |

Full per-step detail (counts, keys, paths-checked) in `03-local-validation-matrix.json`.
All runs use throwaway temp DBs + temp source roots; no live/production DB touched.
