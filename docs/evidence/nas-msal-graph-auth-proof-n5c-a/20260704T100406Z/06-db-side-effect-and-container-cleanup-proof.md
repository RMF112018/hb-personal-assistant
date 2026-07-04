# 06 — DB Side-Effect + Container Cleanup Proof

## Production DB unchanged (no open/migrate)
```
db_pre  mtime=2026-07-04 08:55:03.807899678 UTC  size=4151631872
db_post mtime=2026-07-04 08:55:03.807899678 UTC  size=4151631872
```
- Byte-identical mtime **and** size before/after the login → the copied production DB was **not opened, written, or
  migrated**. This holds even though the app-support bind mount made the DB *visible* to the container, because
  `auth login` opens no DB (repo truth, `02`).

## Container cleanup
```
lingering=0        (no --rm leftover containers from hb-personal-assistant:nas)
running_hbpa=0     (no hb-personal-assistant backend/other container running)
```
- Login ran in a `--rm` container that exited on completion; nothing persists.

## No side effects
- No backend/uvicorn (default `CMD` overridden with `hb-assistant auth login`).
- No MCP / scheduler / watcher.
- No source ingestion / card generation.
- Only artifact created: the delegated MSAL cache under `app-support/auth` (`05`).
