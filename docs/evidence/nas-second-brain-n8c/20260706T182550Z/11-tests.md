# 11 — Tests & verification (N8C-6)

All runs: `PYTHONPATH=src:subrepos/construction-financial-review/src .venv/bin/python -m pytest ...`
(Python 3.14.5 venv at `/Users/bobbyfetting/hb-personal-assistant/.venv`).

## New N8C-6 tests + updated schema/nav tests — PASS
`test_context_pack_v102_migration.py`, `test_enrichment_review.py`, `test_context_pack_repository.py`,
`test_context_pack_builder.py`, `test_fastapi_analytics_context_packs.py`,
`test_nas_mcp_context_packs.py`, `test_schema_version_head_consistency.py`,
`test_nas_mcp_assistant_nav.py` → **58 passed**.

Coverage maps to the task's 27 points, incl.: V102 migration + idempotency + prior-rows-survive;
review items derived from source_summary / claim_extraction / backlink_suggestions receipts; candidate
claims stay candidate/unreviewed; tier classification (low-confidence, stale, ambiguous); budget
max_items / max_chars / max_chars_per_item; provenance retained; deterministic ordering;
`truncated=true` when capped; bounded export; no full `result_json` persisted; preview/dry-run read-only
(row-count before==after); apply writes only context-pack tables; GET-only API; relative-path/redacted
outputs; MCP read-only + kill-switch + snapshot read-only + nav tools preserved + no write tool.

## Two existing tests updated for the (intentional, approved) surface change
- `test_source_identity_v99_migration.py` — head assertion `101 → 102` (renamed
  `test_latest_schema_version_is_102`).
- `test_enrichment_no_autostart.py::test_remote_mcp_has_no_enrichment_write_tool` — was "no
  `EnrichmentRepository` reference anywhere in `nas_mcp/`"; tightened to the real invariant: the remote
  surface exposes ONE read-only enrichment-review tool but calls **no** enrichment WRITE method
  (queue/claim/complete/fail/heartbeat/release) — the queue lifecycle stays CLI/service-only, and
  `ai_outputs_card_upsert` remains the only sanctioned remote write.
- Also updated: `test_nas_mcp_assistant_nav.py` registration assertions now assert the 12 nav tools are
  preserved (⊆) alongside the 4 additive read-only context-pack tools; the nav kill-switch still
  removes the nav tools.

## N8C-1→5 regression set (task §21) — PASS
Full command (with the fixes above) run over: enrichment (`test_enrichment_repository`,
`test_enrichment_worker`, `test_fastapi_analytics_enrichment`, `test_enrichment_models`,
`test_enrichment_no_autostart`), claims (`test_claim_extraction`, `test_claim_repository`,
`test_fastapi_analytics_claims`), nav (`test_obsidian_source_navigation`,
`test_fastapi_analytics_assistant_nav`, `test_nas_mcp_assistant_nav`), identity/maintenance
(`test_obsidian_source_card_identity`, `test_source_index_repository`,
`test_source_identity_v99_migration`, `test_obsidian_generated_note_retirement`,
`test_obsidian_generated_artifact_db_reset`, `test_obsidian_source_maintenance`,
`test_obsidian_source_self_index_guard`, `test_obsidian_source_index_eml_archive`), N8C-1
(`test_nas_mcp_ai_outputs`, `test_nas_mcp_remote_profile`,
`test_obsidian_source_card_local_summary_marker`).

Result: **254 passed, 0 failed** (exit 0, confirmed across 4 independent runs). Every `-q` progress
mark is a pass dot (no `F`/`E`); pytest exits 0 only when all collected tests pass.

## Schedule canary — PASS
`scripts/test-schedule.sh -q` → **exit 0** (green). This bundle carries the cross-domain
migrator/schema head-consistency tests (the canary for `store/migrator.py` edits).

## Ruff — PASS
`ruff check` on all changed source files (new `obsidian_mcp/*`, `cli/context_pack.py`, `cli/main.py`,
`nas_mcp/{profile,broker,tool_registration}.py`) → All checks passed. (`store/*` and the large
`construction/analytics/api.py` are outside the repo's configured ruff scope; the api.py additions
mirror sibling route closures and add no new findings.)
