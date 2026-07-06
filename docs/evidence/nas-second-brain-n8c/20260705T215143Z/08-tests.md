# 08 — Tests & Verification

Run with `PYTHONPATH=src:subrepos/construction-financial-review/src <repo>/.venv/bin/python -m pytest`.

## New N8C-4 tests — 34, all pass
| File | Tests | Focus |
|---|---|---|
| `tests/test_claim_repository.py` | 12 | provenance mandatory; confidence clamp + DB CHECK; status/review enforcement; bounded evidence; idempotent upsert; event log; filters; empty-on-create |
| `tests/test_claim_extraction.py` | 16 | each claim type (date/preference/risk/assumption/commitment/decision/task); deterministic; bounded evidence; orchestrator ambiguous/deleted **block**, stale **block-then-label**, no-auto-run, source/card links, internal validated seam |
| `tests/test_fastapi_analytics_claims.py` | 6 | read-only local claim API: list/filter/by-source/by-card, all-roles, `_assert_safe`, GET-only |

## Migration guard updates
`tests/test_source_identity_v99_migration.py` → asserts `LATEST_SCHEMA_VERSION == 100`.
`tests/test_schema_version_head_consistency.py` → adds `test_v100_migration_row_present`
(`v100_assistant_claims`); fresh-DB-head and idempotency tests track the constant.

## Regression sweep — all green (171 passed, 0 failed, run in two batches)
- Batch 1 (79): the 3 new N8C-4 files + head-consistency + N8C-3 (`test_obsidian_source_navigation`,
  `test_fastapi_analytics_assistant_nav`, `test_nas_mcp_assistant_nav`).
- Batch 2 (92): N8C-2 (`test_obsidian_source_card_identity`, `test_source_index_repository`,
  `test_source_identity_v99_migration`, `test_obsidian_generated_note_retirement`,
  `test_obsidian_generated_artifact_db_reset`, `test_obsidian_source_maintenance`,
  `test_obsidian_source_self_index_guard`, `test_obsidian_source_index_eml_archive`) + N8C-1
  (`test_nas_mcp_ai_outputs`, `test_nas_mcp_remote_profile`,
  `test_obsidian_source_card_local_summary_marker`).

## Lint & invariants
- `ruff check` clean on all new modules + changed tests; `migrator.py` error count unchanged (HEAD and
  now both clean).
- Migration idempotent → `apply()==apply()==100`; both claim tables created; DB CHECKs block unsupported
  claims and out-of-range confidence.
- No extraction/writes on import (`import claim_extraction/claim_repository` performs no work).
- `source_notes.py` and `source_navigation.py` untouched; obsidian tool count 56; remote MCP
  `assistant_*` count still 12 (no claim tool remotely).
