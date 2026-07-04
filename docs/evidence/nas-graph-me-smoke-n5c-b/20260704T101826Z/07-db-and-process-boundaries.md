# 07 — DB & Process Boundaries

## Copied DB — untouched
| Item | Pre | Post |
|---|---|---|
| size | `4151631872` | `4151631872` |
| mtime | `1783155303` | `1783155303` |
| owner/mode | `personal-assistant-svc:users 600` | same |

The `/me` smoke exercises only the auth path (`config.loader` → `path_policy` → `auth.providers`), which imports **no**
store/migrator/sqlite module that opens the DB. `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` was set. The DB is
byte-for-byte unchanged — no writable open, no `apply()`, no projection, no ingestion.

## Process / port boundaries
| Item | Pre | Post |
|---|---|---|
| hb containers | `0` | `0` (`lingering=0`) |
| port 8000 | `not_listening` | `not_listening` |

The container ran `--rm` and exited; no lingering `hb-personal-assistant` containers, no backend/uvicorn process, and
port 8000 was never bound (the CLI/snippet binds no ports). Temp snippet: `written=yes` → `removed=yes`.
