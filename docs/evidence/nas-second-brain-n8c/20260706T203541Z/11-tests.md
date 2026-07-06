# 11 — Tests & verification (N8C-8)

All runs: `PYTHONPATH=src:subrepos/construction-financial-review/src .venv/bin/python -m pytest ...`
(Python 3.14 venv at `/Users/bobbyfetting/hb-personal-assistant/.venv`).

## New N8C-8 tests — 44, PASS
| File | Tests | Covers |
|---|---|---|
| `test_decision_memory_v104_migration.py` | 5 | V104 head=104; 4 tables created; idempotent-twice (one v104 row); prior V100/V101/V102/V103 rows survive; provenance CHECK enforced |
| `test_decision_memory_repository.py` | 10 | decision/preference/open-loop id determinism; upsert idempotent (no dup); changed-evidence supersede within SAME lineage; independent sources COEXIST (no cross-supersede); provenance required; anchor_key fallback when source_id absent; default candidate/unreviewed; mark_open_loop_stale + event; created event logged |
| `test_decision_memory_extractor.py` | 15 | decision from decision_candidate claim; preference from preference claim; commitment/task/risk/question → open-loops; context-pack items produce candidates (path 1); memory compilations produce weak candidates (path 2, compilation_derived + needs_review + capped conf); conservative question heuristic; unsupported rejected; every record has provenance + bounded evidence; default candidate/unreviewed; preview/dry-run read-only; apply writes only N8C-8 tables; idempotent apply; claims stay candidate/unreviewed; memory node status unchanged; bounded JSON export (no raw) |
| `test_fastapi_analytics_decision_memory.py` | 7 | 6 GET routes 200 + `read_only` + `_assert_safe`; list counts; 404s; all roles; GET-only introspection; no write route; limit clamped |
| `test_nas_mcp_decision_memory.py` | 7 | 6 tools return snapshot data; clean `*_not_found`; snapshot rejects UPDATE; kill-switch `assistant_decision_memory_disabled`; reads survive safe mode / `ai_outputs_card_upsert` gated; no write/action tool (nav 12 + pack 4 + memory 4 + decision 6 preserved); status advertises decision tools |

Standalone runs: migration+repository+extractor → **30 passed**; API+MCP → **14 passed**. Total **44**.

## N8C-1→8 regression set — 324 passed, exit 0
One command over the task's §-listed files (decision-memory ×5, memory ×5, context-pack ×6,
enrichment ×3, claims ×3, nav ×3, identity/maintenance ×8, N8C-1 ×3, schema-head consistency).
Result: **324 passed / 0 failed, exit 0** (authoritative all-pass re-run; every `-q` progress mark a
pass dot, no `F`/`E`).

## Existing tests updated for the (intentional) V104 head bump
- `test_source_identity_v99_migration.py` — latest-head assertion `103 → 104`
  (`test_latest_schema_version_is_104`).
- `test_schema_version_head_consistency.py` — added `test_v104_migration_row_present` and
  `test_prior_assistant_tables_survive_v104`.
- `test_memory_v103_migration.py` — the standalone `test_head_is_103` (which asserted V103 was the head)
  replaced by `test_v103_present_and_head_at_least_103` (V103 remains applied; later migrations advance
  the head). The `version = 103` idempotency/row assertions are unchanged. (This was the single failure
  surfaced by the first regression run — a stale head-equality assertion — fixed and re-verified.)

## Schedule canary — PASS
`scripts/test-schedule.sh -q` → **exit 0** (green). This bundle carries the cross-domain
migrator/schema head-consistency tests — the canary for the `store/migrator.py` V104 edit.

## Ruff — PASS
`ruff check` on all new/changed in-scope source (`obsidian_mcp/decision_memory_{models,repository,
extractor}.py`, `obsidian_mcp/memory_repository.py`, `cli/decision_memory.py`, `cli/main.py`,
`nas_mcp/{profile,broker,tool_registration}.py`) → **All checks passed**.
`store/assistant_decision_memory_tables.py` is under the ruff-excluded `store/`.
`construction/analytics/api.py` is outside the enforced scope; its committed baseline reports 48
findings and the N8C-8 route additions add **zero** new findings (identical count before/after).

## CLI / smoke (temp migrated DB, repo-seeded)
`decision-memory extract --help` shows `--pack-id [required]` + `--dry-run/--apply [default: dry-run]`.
Smoke run: schema head 104; `preview` + `extract --dry-run` left all non-N8C-8 tables unchanged;
`extract --apply` wrote records and left claim/enrichment/context-pack/memory/source tables unchanged;
re-apply idempotent; `list`/`export` read-only, no absolute-path leak.
