# Backend runner design

`scripts/dev_schedule_clean_db_backend.py` starts the FastAPI shell against an explicit copied DB path.

## Guards

- Requires `--db-path`, `--port`, `--confirm-clean-copy`
- Rejects live DB via `hb_assistant.config.db_path_guard.is_live_db_path`
- Rejects paths outside `local-sensitive/clean-db/` unless `--allow-custom-copy-path`
- `--print-proof-only` emits JSON without binding a port

## DB binding proof

- Calls `create_app(db_path=...)` directly (not `HB_ASSISTANT_DB_PATH` alone)
- Startup proof JSON includes `background_workers_disabled_by_env`
- `/health` exposes schedule DB resolution when `HB_EVIDENCE_DIAGNOSTICS=1` or operator role
