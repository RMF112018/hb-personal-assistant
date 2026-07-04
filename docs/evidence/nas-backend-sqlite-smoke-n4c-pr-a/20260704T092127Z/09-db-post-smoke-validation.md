# 09 — DB post-smoke validation

Read-only check as `personal-assistant-svc` after compose down.

| Check | Result |
|---|---|
| `PRAGMA quick_check` | **ok** |
| Schema head | **98** |
| `table_count` (application tables) | **505** |
| `view_count` | **2** |
| `schema_object_count` | **507** |
| Schema migrations advanced | **No** — consistent with `startup_migration_performed=false` |
| File owner | `personal-assistant-svc:users` |
| File mode | **600** |

No DB drift detected relative to pre-smoke production posture.
