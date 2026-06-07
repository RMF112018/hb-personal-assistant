# Phase 10A Prompt 02 — Raw Content Schema Migration

**Date:** 2026-06-07  
**Prompt:** 02 (Phase 10A Addendum — Raw Content Enabled Local Intelligence)  
**Status:** Implemented (surgical, additive)

## Objective

Implement the additive V42 migration for raw email/calendar content storage tables (and supporting raw context, model packets, access events, policy state) per the Phase 10A package SQL draft. 

- Tables + indexes exactly as specified.
- Purely additive (CREATE TABLE IF NOT EXISTS / CREATE INDEX IF NOT EXISTS only).
- No changes, drops, or column modifications to any pre-existing metadata-only tables (email_messages, calendar_event_index, task_candidates, local_model_*, all V1–V41 tables remain untouched).
- LATEST_SCHEMA_VERSION bumped to 42.
- Row-count / status helpers added for the new raw tables.
- Tests updated/extended for idempotency and presence.
- Existing phase-10 schema tests continue to pass.

Acceptance: migration applies cleanly (idempotent), existing tests pass, raw tables exist (with row_count=0 on fresh apply).

## Changes

- `src/hb_assistant/store/migrator.py`:
  - `LATEST_SCHEMA_VERSION = 42`
  - Added `V42_STATEMENTS` class attr containing the 6 raw tables + 3 indexes verbatim from `resources/sql/phase_10a_raw_content_schema_additions.sql` (policy_state, email_message_raw_content + 2 indexes, email_thread_raw_context, calendar_event_raw_content + 1 index, model_context_packets, access_events). No `_P10_GUARDS` (these tables are the exception that may hold raw bodies under policy).
  - In `apply()`, after v41 block and before return-latest, added the v42 execution + schema_migrations row insert (`'v42_phase_10a_raw_content_storage'`). Idempotent record-once pattern identical to prior versions.

- `src/hb_assistant/construction/second_brain/local_ai/schema.py`:
  - Added `PHASE_10A_RAW_TABLES` tuple (the 6 names).
  - Added `get_raw_content_table_row_counts(db_path=None) -> dict[str, int|None]` (read-only helper, COUNT(*) or None if absent).
  - Augmented `build_phase_10_schema_status_report`: when `schema_version >= 42`, computes and includes `"raw_content_tables": [...]` (each with table_name/present/row_count) and `"raw_content_table_count"`. No guard column checks or sums for these tables (documented in result/note).
  - Updated module docstring to cover the 10A addendum.
  - (The core V41 table list + 13 guards + _PHASE_10_TARGET_SCHEMA=41 left unchanged; raw is additive extension.)

- `src/hb_assistant/construction/second_brain/local_ai/__init__.py`:
  - Re-exported `PHASE_10A_RAW_TABLES` and `get_raw_content_table_row_counts` from .schema (and added to `__all__`).

- `tests/test_phase_10_schema.py`:
  - Updated module docstring and hard-coded expectations (LATEST==42, v42.db names, n42==1 in idempotency, raw table presence + row==0 assertions).
  - Extended `test_migration_applies_v41_with_all_tables` (now also validates the 6 raw tables exist post-apply and have 0 rows).
  - Strengthened `test_migration_idempotent_and_preserves_prior_versions` (asserts single v42 row, prior v41 row, pre-10A tables like source_records + V38 tables still present, raw tables present).
  - Extended `test_schema_status_ready` to assert raw_content_tables section (count=6, all present, rows=0).
  - Imports updated for the new const. All V41 guard/table tests untouched (they target only PHASE_10_V41_TABLES).
  - No changes that would cause drops or mutations of old tables.

- `docs/architecture/209-phase-10a-prompt-02-raw-content-schema-migration.md` (this file) + one-line append in `docs/architecture/00-README.md` after the Prompt 01 entry.

## Verification (executed)

- In-memory sqlite executescript of the exact draft SQL (from package): APPLY_CLEAN, exactly the 6 raw tables present (incl. email_thread_raw_context), IDEMPOTENT on re-apply, all row counts 0. (Captured via shell before code change.)
- `ruff check` + `ruff format --check` on migrator.py + local_ai/schema.py + __init__.py + test_phase_10_schema.py : clean (auto-format applied where needed).
- `mypy` scoped on the same: baseline (pre-existing notes only; no new type errors introduced).
- `pytest tests/test_phase_10_schema.py -q --tb=line -m "not integration and not live and not manual"`: all tests pass (12+).
- Manual post-apply verification (temp DB via SQLiteMigrator().apply()):
  - `SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%raw%'` → exactly the 6 new tables.
  - Prior metadata tables (e.g. email_messages or source_records, task_candidates, local_model_profiles, construction_* , phase09 tables, etc.) all still present with original columns.
  - `schema_migrations` has exactly one row for version 42; v41 and earlier counts unchanged.
  - `build_phase_10_schema_status_report` on v42 db returns "ready" for phase10 core + raw_content_tables with 6 entries, present=true, row_count=0.
  - Double apply on same DB: no error, row counts for v42 migration record stay 1.
- Status report + helper do not mutate the DB (existing test_schema_status_does_not_mutate_db still holds; raw counts are SELECT only).
- No raw leakage into non-raw tables (the new tables are the designated containers; guards remain on V41 tables and are enforced by CHECKs).
- Stop conditions (per CLAUDE.md + 10A package): additive only, no deletion/rewrite of prior tables, no writeback, no external calls, tests cover the surface.

## Rationale / Trade-offs

- Followed the exact SQL draft from the package (including email_thread_raw_context and the policy_state table) rather than a minimal 2-table subset, to keep the implementation faithful to the plan and later prompts (03/04 ingestion, 06 packets, etc.).
- No guard columns on the raw_* tables: they exist precisely to store the raw bodies (under the policy surface added in Prompt 01 and future ingestion controls). Adding guards would be contradictory.
- Kept _PHASE_10_TARGET_SCHEMA at 41 and V41 table list unchanged: Prompt 02 is an addendum; core phase-10 status remains focused on the 21 guarded tables. Raw info is additive in the report payload.
- Idempotency and "prior tables untouched" explicitly asserted in tests (defense in depth + acceptance).

## Follow-ups (per package)

Prompt 03 (email raw ingestion) and 04 (calendar) will INSERT/SELECT into the new tables (email_message_raw_content, calendar_event_raw_content) using the policy (Prompt 01) and the row counts/status helpers for receipts/diagnostics. Later prompts add context packets and access events.

## References

- Phase 10A: `00_PACKAGE_MANIFEST.md`, `04_SCHEMA_PLAN.md`, `Prompt_02_Schema_Additive_Migration.md`, `resources/sql/phase_10a_raw_content_schema_additions.sql`, `runbooks/raw-content-dev-validation-runbook.md`.
- Prior substrate: V41 in migrator + local_ai/schema.py (Prompt 01/02 of main Phase 10).
- Guard philosophy: no raw in non-raw tables (enforced on V41+); raw tables are the exception with policy gating.

This record is intentionally short (surgical per Prompt 02 scope). Later prompts extend behavior on top of the schema.
