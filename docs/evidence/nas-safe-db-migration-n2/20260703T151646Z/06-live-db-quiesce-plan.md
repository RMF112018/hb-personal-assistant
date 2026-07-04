# N2 · 06 — Live Mac DB Quiesce Plan (PLAN ONLY — not executed)

For a later phase. In N2, only **non-invasive path/process checks** may be run, and only with explicit
operator approval; none were run in N2.

## Objective

Guarantee the live Mac DB is fully quiesced (no writer, no open handle) before the backup-API snapshot,
with a clean rollback if migration is aborted.

## Steps (later operator phase)

1. **Detect the running backend** on loopback:
   `lsof -nP -iTCP:8000 -sTCP:LISTEN` — identify the uvicorn/launcher PID (if any).
2. **Stop it safely** via the app's own launcher (preferred over `kill`):
   `hb-assistant launcher status` → `hb-assistant launcher stop` (exact subcommand to be confirmed
   against the CLI at execution time). Disable any launchd/scheduler entry for the migration window.
3. **Prove port free:** `lsof -nP -iTCP:8000 -sTCP:LISTEN` returns nothing.
4. **Prove no DB handle:** `lsof "~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"`
   returns nothing (also check `-wal`/`-shm`).
5. **Checkpoint/snapshot:** optionally `PRAGMA wal_checkpoint(TRUNCATE)` via a read/write open **only if
   the operator explicitly authorizes touching the live DB**; otherwise snapshot as-is via backup API
   (`05`), which does not require a writer.
6. **Backup for rollback:** the source stays untouched (read-only). Record its pre-copy schema head +
   key row counts as the rollback baseline.
7. **Rollback path:** if migration aborts, simply restart the Mac backend — the live DB was never
   mutated. `hb-assistant launcher start` (or the macOS launchd entry).
8. **No schedulers/watchers** during the window: confirm no automation/orchestrator run is active.

## Guardrails

No scheduler/watcher/automation may run during quiesce. Do not `kill -9` the backend (risk of leaving a
hot WAL); prefer the graceful launcher stop. The live DB is opened **read-only** for the snapshot; any
read/write touch requires separate explicit authorization.
