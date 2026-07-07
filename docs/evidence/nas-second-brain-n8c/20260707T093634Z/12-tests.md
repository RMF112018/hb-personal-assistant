# 12 — Tests

Runner:
```
cd /Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z
PYTHONPATH=src:subrepos/construction-financial-review/src \
  /Users/bobbyfetting/hb-personal-assistant/.venv/bin/python -m pytest <targets>
```

## New N8C-12 tests — 42 total, all pass
- `test_source_connector_service.py` — 18 (root-aware search rows; root+ext filters; bounded snippets; keyset
  cursor determinism + equal-rank rows; cursor/query mismatch; list root/prefix keyset; metadata
  original-vs-card; metadata by source_ref; unknown→source_not_found; live bounded read + max_chars; indexed
  fallback; sensitive-root never live; unsupported-binary denied; path-escape contained; no directory
  traversal spy; reads do not mutate; status/roots no abs paths)
- `test_fastapi_analytics_source_connector.py` — 10 (GET-only + `_assert_safe` + 404 + 400 bad cursor + all
  roles + clamp + cursor round-trip + no write/scan route)
- `test_nas_mcp_source_connector.py` — 8 (RO snapshot + `query_only`; kill-switch scoped; tool sets preserved
  BY NAME; 6-tool count; `hb_root_*` not broadened; status reports flag/tools; raw obsidian source tools stay
  blocked; `ai_outputs_card_upsert` only write)
- `test_source_connector_eval.py` — 6 (deterministic LLM-client routing-intent fixtures)

## Regression
N8C-1→N8C-11 (51 files) + the 4 N8C-12 files: **479 passed** (0 failures).

## Ruff
Clean on all in-scope N8C-12 files (`obsidian_mcp/source_connector_models.py`,
`source_content_provider.py`, `source_connector_service.py`, `source_index_repository.py`,
`cli/source_connector.py`, `cli/main.py`, `nas_mcp/{profile,broker,tool_registration}.py`). `store/` excluded
(unchanged this phase); api.py legacy debt unchanged (48 pre-existing, 0 in the new source-connector block);
new test files also ruff-clean.

## Schedule canary
`scripts/test-schedule.sh` — **343 passed**, exit 0 (migrator NOT edited this phase; run as the cross-domain
canary).

## Not run (out of scope)
`tests/test_review_router.py` — unrelated `construction/email` wall-clock date flake; not run or modified.
No live Ollama/Qwen — the connector is deterministic; bounded reads reuse the existing indexed extractor.
