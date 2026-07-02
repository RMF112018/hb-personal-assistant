# Background worker audit

## Env gate

`HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1` (opt-in only):

- Skips schedule quality poll loop
- Skips Obsidian source root registration
- Skips source watcher startup

Any other env value is treated as unset with a warning.

## Diagnostics

`/health` reports:

- `background_worker_mode`
- `background_workers_disabled_by_env`
- `background_workers.{quality_poll_started,source_watcher_initialized,source_watcher_started}`

Evidence runs must record `background_workers_disabled_by_env` to avoid misreading disabled workers as product failure.
