# 01 — N8C-10 Baseline & Carry-Forward

## N8C-10 committed cleanly (Part 1 of the plan)
`bfc1e743 feat(nas): add n8c intelligence projections` — off N8C-9 `e218746a`. Plain message, no AI trailer,
not pushed. `git merge-base --is-ancestor e218746a bfc1e743` → true.

Committed contents (33 files): V106 4-table intelligence-projection schema
(`assistant_intelligence_projection_tables.py`), builder/repository/models, CLI `intelligence` group,
6 API GET routes, 5 read-only MCP tools, migrator V106 block (LATEST_SCHEMA_VERSION 105→106), evidence bundle
`docs/evidence/nas-second-brain-n8c/20260707T063852Z/`, and head-test updates (v105 → `>= 105`, v99 head
constant, schema-version-head-consistency V106 rows).

## Carry-forward into N8C-11
- N8C-10 projection items carry **frozen** effective_state / inclusion_state / provenance anchors / digests.
  N8C-11 consumes those directly (read-only) and never re-hits review/source tables to rebuild state.
- `LATEST_SCHEMA_VERSION` baseline for N8C-11 = 106 (bumped to 107 by N8C-11).
- `agent_bridge` / N8D absent → next schema is unambiguously 107.
- N8C-10 remote assistant MCP tool total = 36; `ai_outputs_card_upsert` is the sole remote write.
