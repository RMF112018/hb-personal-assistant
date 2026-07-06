# N8C-6 — Enrichment Review, Context Pack Builder, and Source-Linked Intelligence Packets

**Status:** implemented + tested + evidence. **NOT committed** (commit not authorized by the task).
**Push:** none. **PR:** none.

## Baseline & branch
- N8C-5 base commit: `fc56b48654022e8e3600c62831b37bcb3d2b81dc` (`feat(nas): add n8c qwen enrichment queue`).
- N8C-6 branch: `ops/nas-second-brain-n8c-06-context-packs-20260706T182550Z` (branched from `fc56b486`).
- Preflight (verified before any change): HEAD `fc56b486`, working tree clean, `LATEST_SCHEMA_VERSION = 101`, no `src/hb_assistant/agent_bridge/` (no N8D in this worktree).
- Worktree: `/Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z` (operator-local path; recorded as context only).

## Schema / migration status
- New head: **`LATEST_SCHEMA_VERSION = 102`**. Migration `v102_assistant_context_packs`.
- Four additive tables (context-pack-owned only): `assistant_context_packs`, `assistant_context_pack_items`, `assistant_context_pack_receipts`, `assistant_context_pack_events`.
- Additive + idempotent: applying twice leaves exactly one v102 row; V100 (`assistant_claims`/`_events`) and V101 (`assistant_enrichment_jobs`/`_receipts`) tables and migration rows survive (proof: `03-schema-and-contract.md`, `test_context_pack_v102_migration.py`, `test_schema_version_head_consistency.py::test_v102_migration_row_present`).
- The enrichment-review layer adds **no** table (pure derived read model).

## Changed / new files
New source (all `obsidian_mcp/` unless noted; ~1,565 LOC):
- `store/assistant_context_pack_tables.py` — V102 DDL (4 tables), enum tuples (single source of truth for the CHECKs).
- `obsidian_mcp/context_pack_models.py` — enums, `Budget`, `compute_pack_id` (idempotent), `estimate_tokens` (conservative 4 chars/token, documented), validators, size caps, bounded-excerpt helper.
- `obsidian_mcp/enrichment_review.py` — DERIVED review read model over receipts + candidate claims + identity state; `classify_review_tier`.
- `obsidian_mcp/context_pack_repository.py` — sole reader/writer of the 4 tables; atomic `persist_pack`; no-overwrite; explicit `mark_pack_stale`.
- `obsidian_mcp/context_pack_builder.py` — `preview` / `build(apply=)` / `export` / `mark_context_pack_stale_if_needed`.
- `cli/context_pack.py` — `hb-assistant context-pack preview|build|export|list` (read-only default; `build --apply` is the only writer).
New tests: `test_context_pack_v102_migration.py`, `test_enrichment_review.py`, `test_context_pack_repository.py`, `test_context_pack_builder.py`, `test_fastapi_analytics_context_packs.py`, `test_nas_mcp_context_packs.py`.
Modified: `store/migrator.py` (V102 wiring + head bump), `construction/analytics/api.py` (6 GET routes), `cli/main.py` (typer registration), `nas_mcp/profile.py` (`assistant_context_packs_enabled()` gate), `nas_mcp/broker.py` (allowlist + read-only-snapshot dispatch + status), `nas_mcp/tool_registration.py` (gated read-only tool block), plus two existing tests updated for the enlarged (but nav-preserving) `assistant_*` surface.

**Not touched:** N8D / `agent_bridge/`, source/card rendering, `construction/second_brain/`. (Proof: `13-git-status.md`.)

## Review model (N8C-6 §8)
A review item is DERIVED (never stored) from an enrichment receipt: stable `review_item_id`, carries `receipt_id/job_id/job_type/source_id/note_rel_path/claim_id`, `review_item_type` (source_summary | claim_candidate | backlink_suggestion | unknown), the claim's `review_state` (else `unreviewed`), an advisory `review_tier`, bounded `summary`/`evidence_excerpt`, `result_digest`, and DB-derived `source_state`. Tier classification is integrity-first: ambiguous card link → `needs_operator_review`; deleted/missing/stale source → `source_stale`; low confidence (<0.4) → `low_confidence`; then by type (`claim_candidate` / `link_candidate` / `safe_summary`). `review_tier` is advisory and **distinct** from `review_state` — nothing accepts a claim.

## Context-pack builder (N8C-6 §9–§11)
- Pack types implemented: `enrichment_review`, `source_review`, `implementation_context`.
- `pack_id = sha256(pack_type | normalized scope_json | normalized budget_json | input_digest | builder_version)[:24]` — identical inputs → identical id; a changed `input_digest` → a new id; `build --apply` never overwrites an existing pack (reports `reused`).
- Deterministic assembly: order by (tier severity, −confidence, source_id, item_type, anchor); per-item cap → total-char cap → max_items; over-budget items are retained as rows with `included=0` + `exclusion_reason` (never silently dropped); `truncated`/`stale_count` recorded.
- Items store **bounded selected excerpts only**; the full enrichment `result_json` is never copied — linked via `receipt_id` + `result_digest`.
- Stale lifecycle: no automatic scan; an explicit live check (`mark_context_pack_stale_if_needed`) re-derives the input digest and, on drift, marks the pack stale + logs a lifecycle event.

## Exposure summary
- **API:** 6 read-only GET routes under `/api/assistant/enrichment/review` + `/api/assistant/context-packs` (bounded, `_assistant_env` guardrails, relative-path only, coded 404s). No POST/PUT/PATCH/DELETE. (`09-api-cli-mcp-exposure-proof.md`.)
- **CLI:** `hb-assistant context-pack` — `preview`/`build --dry-run`/`export`/`list` read-only; `build --apply` the only writer, into context-pack tables only.
- **MCP:** 4 read-only remote tools (`assistant_list_context_packs`, `assistant_get_context_pack`, `assistant_get_context_pack_items`, `assistant_list_enrichment_review_items`) gated by default-ON `assistant_context_packs_enabled()` (kill-switch `HB_MCP_ASSISTANT_CONTEXT_PACKS=0`), served from the read-only DB snapshot (`mode=ro&immutable=1` + `PRAGMA query_only=ON`). The 12 N8C-3 nav tools are preserved; `ai_outputs_card_upsert` remains the ONLY sanctioned remote write. No build/apply/write MCP tool.

## Boundary proofs (see numbered files)
No vault mutation · no raw/import/source/claim/enrichment table mutation on preview/dry-run (row-count before==after) · no raw prompt/response persisted (only sha256 digests exist) · no raw email bodies · no startup builder/worker · no remote MCP write tool · no N8D duplication · candidate claims remain candidate/unreviewed.

## Verification (results: `11-tests.md`)
- New N8C-6 tests + updated schema-head & nav tests: PASS (58 tests).
- N8C-1→5 regression set (§21) + new N8C-6 tests together: **254 passed, 0 failed** (exit 0, 4 runs).
- `ruff check` on changed source files: PASS.
- `scripts/test-schedule.sh -q` (migrator/schema canary): PASS (exit 0).
