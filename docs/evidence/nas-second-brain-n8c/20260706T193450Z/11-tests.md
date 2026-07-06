# 11 — Tests & verification (N8C-7)

All runs: `PYTHONPATH=src:subrepos/construction-financial-review/src .venv/bin/python -m pytest ...`
(Python 3.14 venv at `/Users/bobbyfetting/hb-personal-assistant/.venv`).

## New N8C-7 tests — 38, PASS
| File | Tests | Covers |
|---|---|---|
| `test_memory_v103_migration.py` | 4 | V103 head=103; 4 memory tables created; idempotent-twice (one v103 row); prior V100/V101/V102 rows survive |
| `test_memory_repository.py` | 7 | node_id determinism; upsert-node idempotent (no dup); upsert-mention idempotent + counts; persist-compilation reuse-on-same-input & supersede-on-changed-input; mention-requires-provenance; mark-node-stale + event; search_nodes |
| `test_memory_compiler.py` | 13 | discovery from claim subject/object; from enrichment summary + backlink + claim pack-items; every node ≥1 mention & every mention has provenance; bounded compilation; `mention_tier` rule table (trusted/stale/ambiguous/low-conf/Qwen-summary/raw-fallback/backlink); raw claim_text fallback capped + never trusted; idempotent apply (no dup); changed input → new compilation + supersede; node_id stable; preview/dry-run read-only; apply writes only memory tables; claims stay candidate/unreviewed; bounded JSON export (no `result_json`) |
| `test_fastapi_analytics_memory.py` | 7 | 5 GET routes 200 + `read_only` + `_assert_safe`; children counts; 404; all roles; GET-only introspection; no write route; limit clamped |
| `test_nas_mcp_memory.py` | 7 | 4 tools return snapshot data; clean `memory_node_not_found`; snapshot rejects UPDATE; kill-switch `assistant_memory_disabled`; reads survive safe mode / `ai_outputs_card_upsert` stays gated; no write/compile tool registered (nav 12 + pack 4 + memory 4 preserved); status advertises memory tools |

Standalone runs: `test_memory_v103_migration + test_memory_repository + test_memory_compiler` →
**24 passed**; `test_fastapi_analytics_memory + test_nas_mcp_memory` → **14 passed**. Total **38 passed**.

## N8C-1→7 regression set — 293 passed, exit 0
One command over: claims (`test_claim_extraction`, `test_claim_repository`), enrichment
(`test_enrichment_models/repository/review/worker/no_autostart`), context-packs
(`test_context_pack_builder/repository/v102_migration`), memory (the 5 new N8C-7 files), identity/nav
(`test_obsidian_source_card_identity`, `test_obsidian_source_navigation`, `test_source_index_repository`,
`test_source_identity_v99_migration`, `test_schema_version_head_consistency`), API
(`test_fastapi_analytics_assistant_nav/claims/enrichment/context_packs`), MCP
(`test_nas_mcp_assistant_nav/context_packs/readonly/remote_profile/ai_outputs/safe_mode_limits_freshness`).

Result: **exit 0**; every `-q` progress mark is a pass dot (4 full lines of 72 + 5 = **293**, no `F`/`E`).
Pytest exits 0 only when all collected tests pass — so 293 passed / 0 failed. (Pass-dot + exit-0
derivation: this environment's redirected pytest output omits the trailing `N passed` summary line, so
the count is derived from the progress dots and the exit code, per the N8C-6 convention.)

## Three existing tests updated for the (intentional, approved) V103 head bump
- `test_source_identity_v99_migration.py` — latest-head assertion `102 → 103`
  (`test_latest_schema_version_is_103`).
- `test_schema_version_head_consistency.py` — added `test_v103_migration_row_present` and
  `test_prior_assistant_tables_survive_v103` (V102 row-present test retained).
- `test_context_pack_v102_migration.py` — the standalone `test_head_is_102` (which asserted V102 was the
  head) replaced by `test_v102_present_and_head_at_least_102` (V102 remains applied; later migrations
  advance the head). The `version = 102` idempotency/row assertions are unchanged.

## Schedule canary — PASS
`scripts/test-schedule.sh -q` → **exit 0** (335 tests, all progress dots). This bundle carries the
cross-domain migrator/schema head-consistency tests — the canary for the `store/migrator.py` V103 edit.

## Ruff — PASS
`ruff check` on all new/changed in-scope source (`obsidian_mcp/memory_{models,repository,compiler}.py`,
`cli/memory.py`, `cli/main.py`, `nas_mcp/{profile,broker,tool_registration}.py`) → **All checks passed**.
`store/assistant_memory_tables.py` is under the ruff-excluded `store/`. `construction/analytics/api.py`
is outside the repo's enforced ruff scope; its committed baseline already reports 48 findings and the
N8C-7 memory-route additions add **zero** new findings (identical count before/after).

## CLI / smoke (temp migrated DB, repo-seeded)
`memory compile --help` shows `--pack-id [required]` + `--dry-run/--apply [default: dry-run]`. Smoke run:
schema head 103; dry-run left all non-memory tables unchanged; `--apply` wrote 4 nodes / 4 mentions /
4 compilations and left claims/enrichment/context-pack/source untouched; re-apply idempotent
(`new_mentions=0`, `new_compilations=0`); claims stayed candidate/unreviewed; export bounded JSON with no
`result_json` / no absolute paths; node tiers `{low_confidence, stale_source}` (cautious, none trusted).
