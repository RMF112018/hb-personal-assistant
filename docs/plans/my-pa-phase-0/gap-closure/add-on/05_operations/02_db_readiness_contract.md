# DB Readiness Contract

## Required DB Path

```text
~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite
```

## Before SQLite Connect

The application must verify:

- parent directory exists;
- parent directory is writable;
- path is not a directory;
- SQLite file can be created/opened;
- WAL sidecar files can be created if journal mode is WAL.

## Failure Output

Commands must return structured JSON similar to:

```json
{
  "status": "blocked_db_unavailable",
  "path": "~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite",
  "parent_exists": true,
  "parent_writable": false,
  "error": "DB parent is not writable",
  "repair_hint": "Run hb-assistant diagnostics paths --repair-dry-run --json"
}
```

## Do Not

- Do not emit raw tracebacks in normal `--json` mode.
- Do not silently fall back to an in-repo SQLite DB.
- Do not create DB files inside the git repository.
