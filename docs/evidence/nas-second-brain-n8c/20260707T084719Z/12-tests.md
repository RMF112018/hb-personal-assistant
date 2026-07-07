# 12 — Tests

Runner:
```
cd /Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z
PYTHONPATH=src:subrepos/construction-financial-review/src \
  /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest <targets>
```

## New N8C-11 tests — 50 total, all pass
- `test_research_packet_v107_migration.py` — 7 (head 107, 5 tables, idempotent, V100–V106 survive,
  provenance CHECK)
- `test_research_packet_repository.py` — 14 (id determinism incl. citation + receipt; no-dup; changed
  input_digest → new/stale; upsert writes only packet tables; projection/review/source unmutated; citation
  anchor-entropy no-collision)
- `test_research_packet_builder.py` — 15 (answer-role per inclusion_state; policy per packet_type; every
  included item cited unless open_question/excluded_context; citations provenance-linked + bounded; answer
  contract citation_required / action_policy=no_execution / review_labels_required / unresolved_questions /
  bounded must_not_say; budget caps; excluded minimized; no full-payload copy; preview/dry-run read-only;
  no final-answer field)
- `test_fastapi_analytics_research_packets.py` — 7 (GET-only + `_assert_safe` + 404 + bounded + all roles)
- `test_nas_mcp_research_packets.py` — 7 (RO snapshot; kill switch scoped; no write/build/answer/action tool;
  6-tool count; existing tool sets preserved BY NAME; `ai_outputs_card_upsert` only write)

## Head-tracking updates (106 → 107)
- `test_source_identity_v99_migration.py` — head constant/name updated to 107.
- `test_schema_version_head_consistency.py` — V107 row-present + prior-tables-survive asserts added
  (constant-driven, auto-track).
- `test_intelligence_projection_v106_migration.py` — head assertion relaxed `== 106` → `>= 106` and renamed
  `test_v106_present_and_head_at_least_106` (mirrors the N8C-10 treatment of the v105 test). This was the one
  failure surfaced by the first regression run; fixed and re-run green.

## Regression
N8C-4→N8C-11 chain (44 files, incl. claim / enrichment / context-pack / memory / decision / review /
intelligence / research-packet / identity / schema-head / MCP): **401 passed** (after the v106 fix).

## Ruff
Clean on all in-scope N8C-11 files. `store/` is `extend-exclude`d; api.py has pre-existing legacy
B904/I001/B008/F821 (lines 4018–6321) unrelated to N8C-11 — none in the research-packets block (3061–3145).
Fixed in this session: 3 I001 (import sort) + 1 C408 (`dict()` → literal) in new test files.

## Schedule canary
`scripts/test-schedule.sh` — exit 0 (migrator.py edited; cross-domain migrator canary green). The `-q`
summary line is not captured (documented `-q` gotcha); all-dots output + exit 0 confirm green.

## Not run (out of scope)
`tests/test_review_router.py` — unrelated wall-clock date flake in `construction/email`; per plan, not run or
modified.
No live Ollama/Qwen — the builder is deterministic; no test requires a model.
