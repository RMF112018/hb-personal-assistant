# 11 — Tests

Runner (shared venv): `/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python`;
`PYTHONPATH=src:subrepos/construction-financial-review/src`.

## New N8C-9 tests (all green)
- `tests/test_review_v105_migration.py` — head=105, 3 tables created, idempotent re-apply
  (one `schema_migrations` row), V100–V104 rows survive, provenance CHECK rejects anchorless insert.
- `tests/test_review_repository.py` — id determinism, default unreviewed/candidate, provenance guard,
  idempotent upsert, lineage supersede (+ independent targets coexist), disposition→state maps,
  append-only ledger (latest wins), disposition does not mutate item columns, missing-item raises,
  read-only preview, `effective_state_for_target`.
- `tests/test_review_builder.py` — preview read-only + source snapshot unchanged; build --apply produces
  anchored + bounded items; families discovered; `--kind` scoping narrows; idempotent + nonmutating
  rebuild; claims/decisions remain candidate/unreviewed.
- `tests/test_fastapi_analytics_review.py` — 5 GET routes OK + `_assert_safe`; effective state reflects
  disposition; dispositions listed; 404 on missing; all roles; GET-only; no write/disposition route;
  bounded limit clamped.
- `tests/test_nas_mcp_review.py` — tools return data; missing denied cleanly; RO snapshot rejects writes;
  kill switch disables ONLY review (siblings stay on); reads survive safe mode while the one write stays
  gated; no write/action tool registered (`len(ASSISTANT_REVIEW_TOOLS)==5`, existing tools preserved);
  status advertises the flag + tool set.

## Full regression (N8C-1 → N8C-9)
Command: the full list from the task's verification section + the 5 new N8C-9 files, `-q --tb=line`.
**Result: 364 passed, 0 failed, exit 0.** Includes the updated head tests
(`test_decision_memory_v104_migration.py` relaxed to `>= 104` + V104-row-present;
`test_source_identity_v99_migration.py` → `== 105`; `test_schema_version_head_consistency.py` +
`test_v105_migration_row_present` / `test_prior_assistant_tables_survive_v105`).

## ruff
In-scope N8C-9 files (`obsidian_mcp/review_*.py`, `cli/review.py`, `cli/main.py`,
`nas_mcp/{broker,profile,tool_registration}.py`, the 5 new test files): **All checks passed.**
`store/*` + the `tests/test_*` glob are in `extend-exclude` (out of enforced scope); `api.py` has 1
pre-existing finding, unchanged by N8C-9 (zero delta vs base `208e7b68`).

## scripts/test-schedule.sh -q (migrator cross-domain canary)
Run because `store/migrator.py` was edited (V105). **Result: pass (SCHED_EXIT=0).**
