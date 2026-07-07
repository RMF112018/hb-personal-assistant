# 11 — Tests, Ruff, Canary

Runner (shared venv):
```
PYTHONPATH=src:subrepos/construction-financial-review/src \
  /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest ...
```

## New N8C-10 tests (all green)

| file | count | covers |
|---|---|---|
| `test_intelligence_projection_v106_migration.py` | 5 | head 106, 4 tables, idempotent re-apply, V100–V105 rows survive, provenance CHECK rejects anchorless item |
| `test_intelligence_projection_repository.py` | 11 | deterministic ids (incl. receipt), inclusion classification, policy defaults, provenance/enum validation, idempotent upsert, lineage supersede (projection-owned only), independent-scope coexist, stale, summary shape |
| `test_intelligence_projection_builder.py` | 11 | review-aware include+label, trusted-excludes-until-accepted, provenance+bounded, budget max_items/max_chars/max_trusted, excluded-minimized, impl-context advisory, preview/dry-run/apply non-mutation, dispositions+events unchanged, idempotent apply |
| `test_fastapi_analytics_intelligence.py` | 6 | GET-only + `_assert_safe`, 404s, all-roles, no write/build route, bounded limit |
| `test_nas_mcp_intelligence.py` | 7 | tools return data, clean 404, RO snapshot rejects UPDATE, kill switch scoped, safe-mode reads OK, tool sets preserved BY NAME + no write/action tool, status advertises 5 |

**Focused N8C-10 + head consistency run: 68 passed, 0 failed** (the five new files + the three updated
head tests below).

## Updated head-consistency tests (green)

- `test_source_identity_v99_migration.py` — `test_latest_schema_version_is_106` (was 105).
- `test_review_v105_migration.py` — head equality relaxed to `>= 105` + explicit V105-row-present check
  (mirrors the memory/decision relaxations; keeps V105 proof while allowing later heads).
- `test_schema_version_head_consistency.py` — added `test_v106_migration_row_present` +
  `test_prior_assistant_tables_survive_v106`.

## Full N8C-1 → N8C-10 regression

Ran the N8C assistant/second-brain suite (claims, context packs, decision memory, memory compiler,
enrichment, review overlay, intelligence projection, migrations, FastAPI analytics assistant surfaces, and
NAS MCP assistant surfaces) — 47 test files.

**Result (excluding the unrelated date-flake `test_review_router.py`): 382 passed, 0 failed, 1 warning in
397.73s.** With `test_review_router.py` included the run adds exactly 5 failures, all in that one file
(the wall-clock flake disclosed below); no other failure anywhere.

### Pre-existing, unrelated failure — DISCLOSED (not caused by N8C-10)

`tests/test_review_router.py` (5 tests) fails today as a **wall-clock date time-bomb**, NOT from this phase:
- It exercises `hb_assistant.construction.email.review_router` — the **email correspondence** router (a
  Phase-10 email-intelligence feature), NOT the N8C-9 assistant review overlay (`obsidian_mcp/review_*`).
- The router computes `received_after = datetime.now(timezone.utc) - timedelta(days=lookback)`
  (`review_router.py:159`) with `lookback_days=30`; the test fixture hardcodes
  `received_datetime="2026-05-20T10:00:00Z"` (`test_review_router.py:46`). As of today (2026-07-07) the
  window start is 2026-06-07, so the 2026-05-20 fixture falls outside it → `messages_considered == 0` →
  the `== 1`/`== 2` assertions fail. The report literally shows `received_after='2026-06-07T…'`.
- Non-causation proof: nothing under `src/hb_assistant/construction/email/` imports the projection code
  (`grep -rl intelligence_projection src/hb_assistant/construction/email/` → none); the test file was last
  touched by a Phase-09 commit; V106 is additive and touches no `email_*` table. The failure is a count
  assertion driven purely by real time, independent of any N8C-10 change.
- This flake fires for any run > 30 days after 2026-05-20 regardless of this branch. **Left untouched**
  (out of scope; a fixture-date fix belongs to the email subsystem, not this phase).

Excluding that unrelated file, the N8C-1 → N8C-10 regression is **GREEN** (count below).

## Ruff (in-scope N8C-10 files)

`ruff check` on all new/edited N8C-10 modules + tests → **All checks passed!** The additions to the large
`construction/analytics/api.py` are ruff-clean; its 13 pre-existing `I001` (and other pre-existing)
findings were left untouched to avoid out-of-scope churn.

## Schedule migrator canary (required — migrator.py edited)

`scripts/test-schedule.sh -q` → **0 failed** (migrator/schema cross-domain canary green after the V106
addition).

## Bottom line

- New N8C-10 tests + head consistency: **68 passed, 0 failed.**
- Full N8C-1 → N8C-10 regression (clean list, 47 files): **382 passed, 0 failed** in 397.73s.
- Only failures anywhere: 5 in `test_review_router.py` — a pre-existing wall-clock date flake in the email
  correspondence subsystem, unrelated to and uncaused by N8C-10 (disclosed above).
- Ruff on in-scope N8C-10 files: **All checks passed!**
- `scripts/test-schedule.sh -q` migrator canary: **green, 0 failed.**
