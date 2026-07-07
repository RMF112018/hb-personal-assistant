# 12 — Tests

Runner:
```
cd /Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z
PYTHONPATH=src:subrepos/construction-financial-review/src \
  /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest <targets>
```

## New N8C-14 tests — 41 total, all pass
- `test_answer_draft_v108_migration.py` — 9 (head 108 + LATEST; 5 tables; idempotent row; V100–V107 survive;
  V107 packet tables survive; citation CHECK rejects anchorless+lineageless; packet-lineage satisfies;
  provenance anchor satisfies; no finality columns).
- `test_answer_draft_repository.py` — 4 (deterministic ids + idempotent reuse; changed input supersedes prior;
  stale-on-drift; upsert writes ONLY draft tables — packet/source snapshot unchanged).
- `test_answer_draft_builder.py` — 13 (review-aware routing + labels; trusted excludes candidate/deferred;
  every support section cited; answer_allowed=false → insufficient_support only; must_not_say never support;
  packet-lineage + source carry-through; degraded lineage marked; **no live source_file_read** (spy); budget
  caps + truncated; no-finality-field + dry-run read-only; open loops advisory not tasks; unknown draft_type
  rejected).
- `test_fastapi_analytics_answer_drafts.py` — 8 (GET-only + `_assert_safe` incl. finality needles; summary
  before {id}; sections carry review labels + no finality keys; 404s; all roles; clamp; no write/build route).
- `test_nas_mcp_answer_drafts.py` — 7 (RO snapshot + `query_only`; kill switch scoped; **no
  write/build/answer verb in ANY tool name incl. substring `answer`**; 6-tool count; existing tool sets incl.
  N8C-12 source connector preserved BY NAME; status advertises; `ai_outputs_card_upsert` only write).

## Head-tracking updates
- `test_source_identity_v99_migration.py` — `_is_107`→`_is_108`, `== 107`→`== 108` + comment.
- `test_schema_version_head_consistency.py` — ADDED `test_v108_migration_row_present` +
  `test_prior_assistant_tables_survive_v108` (auto-track via `LATEST_SCHEMA_VERSION`).
- `test_research_packet_v107_migration.py` — the previous-head migration test was rewritten (per the V106
  precedent) to assert `>= 107` + row present + `apply() == LATEST_SCHEMA_VERSION` instead of a hard-coded
  head (2 functions).

## Regression (N8C-1 → N8C-12 + V108)
Assistant-domain set (migration/head + all `nas_mcp_*` + N8C builders/repos/APIs + source connector +
answer-draft): **582 passed, 0 failed** (2 previous-head asserts fixed to track LATEST per the V106
precedent, then green).

## Ruff
Clean on all in-scope N8C-14 files (`obsidian_mcp/answer_draft_{models,repository,builder}.py`,
`cli/answer_draft.py`, `cli/main.py`, `nas_mcp/{profile,broker,tool_registration}.py`). `store/` excluded
(unchanged policy); `api.py` legacy debt unchanged (48; 0 in the new answer-draft block); new test files
also ruff-clean.

## Schedule canary
`scripts/test-schedule.sh` — **345 passed**, exit 0 (up from 343: the 2 new head-consistency tests; the
schedule bundle's migrator/head test is the cross-domain canary and auto-tracks the 108 bump).

## CLI end-to-end (temp DB)
`answer-draft preview` (read-only) → `build --dry-run` (persists nothing) → `build --apply` (draft_id) →
`list` → `export` (real direct_answer section w/ review_label `trusted`, 1 citation, finality-clean).

## Not run (out of scope)
`tests/test_review_router.py` — unrelated `construction/email` wall-clock date flake; not run or modified.
No live Ollama/Qwen (deterministic builder).
