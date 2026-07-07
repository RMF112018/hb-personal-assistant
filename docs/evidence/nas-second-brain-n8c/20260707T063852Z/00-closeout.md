# N8C-10 — Review-Aware Intelligence Projection & Trusted Context Surfaces — Closeout

**Phase:** NAS Second-Brain N8C-10
**Status:** IMPLEMENTED — UNCOMMITTED (stop-before-commit per authorization)
**Worktree:** `/Users/bobbyfetting/hb-pa-n8c02-20260705T200705Z`
**Branch:** `ops/nas-second-brain-n8c-10-review-aware-intelligence-20260707T063852Z`
**Base:** `e218746a` (N8C-9 `feat(nas): add n8c review queue`) — verified ancestor of HEAD
**Prior lineage:** N8C-8 `208e7b68` → N8C-9 `e218746a` → N8C-10 (this, uncommitted)
**Schema:** `LATEST_SCHEMA_VERSION = 106` (V106, additive; V100–V105 preserved)

## What this phase adds

N8C-10 makes downstream surfaces **review-aware**. It materializes bounded, effective-state-filtered
**intelligence projections** (trusted / candidate / review-aware / implementation context) by REUSING the
N8C-9 review overlay (queue + append-only disposition ledger + computed effective state) and the upstream
advisory records — so ChatGPT / the frontend / a future N8D bridge can consume a clean "trusted context
packet" without rehydrating every source table.

A projection is a **materialized read product**:
- Effective review state is **READ** from the N8C-9 review tables and classified into an `inclusion_state`
  per the projection type's policy. It **never converts a candidate into accepted truth.**
- The builder **writes only** the four `assistant_intelligence_projection*` tables (and only on `--apply`).
- It executes nothing (no email/calendar/task/reminder/notification/N8D), mutates no source or review
  table, persists no raw prompt/response/email-body/full-payload, copies no full upstream payload.

## Deliverables

| Layer | Artifact |
|---|---|
| Schema V106 | `store/assistant_intelligence_projection_tables.py` (4 tables) + `store/migrator.py` guarded block |
| Models | `obsidian_mcp/intelligence_projection_models.py` (enums, caps, deterministic ids, budget, classify) |
| Repository | `obsidian_mcp/intelligence_projection_repository.py` (idempotent upsert, lineage supersede, RO reads) |
| Builder | `obsidian_mcp/intelligence_projection_builder.py` (preview / build / export — deterministic, no LLM) |
| CLI | `cli/intelligence.py` (`preview` / `build --dry-run/--apply` / `list` / `export`) + `cli/main.py` |
| API | `construction/analytics/api.py` — 5 read-only GET routes |
| MCP | `nas_mcp/{profile,broker,tool_registration}.py` — 5 read-only tools, independent default-ON kill switch |
| Tests | 5 new N8C-10 test files + 3 updated head-consistency tests |

## Boundaries honored (hard)

No source-advisory OR review-table mutation; no action execution; no vault/source/card-render mutation;
no raw prompt/response/email-body persistence; no full upstream payload copy (only bounded
title/summary/excerpt + ids/digests/state); no startup builder/scheduler/watcher/worker; no remote MCP
build/apply/action tool; no N8D import / `agent_bridge` touch; no vector store / graph schema. Effective
state is READ from the review tables; projections are never written back into source/review tables.

**Authorization:** implement N8C-10, **stop before committing.** No push, no PR, no merge. No AI trailer.

See the numbered files in this bundle for per-claim proof.
