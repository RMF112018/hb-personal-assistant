# N8C-9 — Unified Review Queue, Disposition Ledger, Effective Review State — Closeout

**Status:** implemented + verified, **UNCOMMITTED** (stop-before-commit per authorization).
**Date:** 2026-07-06 (UTC stamp `20260706T220246Z`).

## Lineage
- N8C-7 commit: `b99151f1` — feat(nas): add n8c memory compiler
- N8C-8 commit: `208e7b68` — feat(nas): add n8c decision memory layer (committed locally this run; not pushed)
- N8C-9 branch: `ops/nas-second-brain-n8c-09-review-queue-20260706T220246Z`
- N8C-9 base: `208e7b68` (the N8C-8 commit)

## What N8C-9 adds
A source-backed **review overlay** over the N8C-4…N8C-8 advisory records. It answers "what needs review /
what was accepted, rejected, deferred, or marked not required / what is stale or superseded" WITHOUT
mutating any source table, executing any action, or adding a remote write tool.

- **Schema V105** (`LATEST_SCHEMA_VERSION 104 → 105`): 3 additive overlay tables
  `assistant_review_items` / `assistant_review_dispositions` / `assistant_review_events`.
- **Review builder** (`review_builder.py`): deterministic, pack-scoped, read-only discovery of review
  candidates from claims, context-pack items, enrichment review, memory compilations, and
  decision/preference/open-loop records. `build --apply` writes only `assistant_review_items`.
- **Disposition ledger** (`review_repository.record_disposition` + `review_disposition.py`): append-only
  local/operator decisions; writes only the review tables; executes nothing.
- **Effective-state read model**: effective state is COMPUTED from the review item + its latest
  disposition; never written back into a source table.
- **Exposure**: 5 read-only API GET routes, a local `hb-assistant review` CLI (preview/build/list/
  effective-state/export/disposition), and 5 read-only MCP tools with kill switch
  `HB_MCP_ASSISTANT_REVIEW=0`.

## Boundaries honored
No source-advisory-table mutation; no action execution / email / calendar / task / reminder /
notification; no vault or source/card-render mutation; no raw/import mutation; no raw prompt/response or
email-body persistence; no startup builder/scheduler/worker; no remote MCP write/disposition/action tool;
no N8D / `agent_bridge` touch; no vector store / LlamaIndex. `ai_outputs_card_upsert` remains the only
sanctioned remote write. Effective state is computed, never written back.

## Verification (see 11-tests.md)
- 5 new N8C-9 test files (migration, repository, builder, API, MCP) — green.
- Full N8C-1→N8C-9 regression — green.
- ruff (in-scope N8C-9 files) — clean.
- `scripts/test-schedule.sh -q` (migrator canary) — pass.

## Deferred (see 12-risk-and-defer-list.md)
- `assistant_review_batches` table (optional grouping) — deferred as YAGNI; the 3 core tables suffice.
- Global/`--all` (non-pack-scoped) build — deferred; pack-scoped build is the mandatory default.
