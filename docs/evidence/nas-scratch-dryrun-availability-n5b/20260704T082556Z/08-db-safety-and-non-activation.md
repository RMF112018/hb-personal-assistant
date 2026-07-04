# 08 — DB Safety & Non-Activation

## DB posture in N5B
N5B needed **no** production DB. No DB was opened — read-only or otherwise — during this phase.

## Vault/DB reconcile (12.C) — DEFERRED for safety
`scripts/obsidian_vault_db_reconcile.py` — confirmed read-only from source:
- DB opened read-only via `file:...?mode=ro` (`_ro`); vault only stat/globbed; a `source_intelligence_state`
  fingerprint is captured before **and** after to prove no mutation (`runtime_state_unchanged`); count-only output.
- It contains **no** `SQLiteMigrator.apply()` call and uses a raw `sqlite3` read-only URI (so opening it does not
  trigger the app's auto-migrate path).

**Why deferred:** it is DB-backed, and per §13 ("if there is uncertainty, skip DB-backed checks and defer") N5B does
not open the production copied DB from this bounded phase. The production copied DB lives on the NAS
(`app-support/db/…`, not locally mounted); pointing the tool at the live Mac production DB introduces avoidable
interaction with a possibly-running backend/WAL. The conservative, faithful choice is to defer the reconcile to a
later explicitly-bounded phase that opens a **copy** read-only in isolation.

## Production DB write-safety reaffirmed (not exercised, recorded for continuity)
- `SQLiteMigrator.apply()` has no version guard → a normal app connection against the copied app-support root is a
  WRITE (WAL + statements) even at schema 98. N5B started no backend/MCP and made no connection to the copied DB.
- The scratch root uses `app-support-smoke/*`, deliberately separate from the production copied app-support, so no
  config-driven path resolution can reach the copied DB.

## Non-activation confirmation
- No production config placed/activated (drafts + scratch configs only; `enabled_roots=[]`).
- No source root registered in any DB.
- No ingestion, card generation, summary generation, or LLM workflow run.
- No backend / MCP / scheduler / watcher started.
