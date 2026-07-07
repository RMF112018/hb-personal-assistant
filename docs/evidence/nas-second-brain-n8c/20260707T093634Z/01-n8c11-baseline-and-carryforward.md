# 01 — N8C-11 Baseline & Carry-Forward

## N8C-11 committed cleanly (Part 1)
`0e2876c7 feat(nas): add n8c research packets` — off N8C-10 `bfc1e743`. Plain message, no AI trailer, not
pushed. `git merge-base --is-ancestor bfc1e743 0e2876c7` → true. Contents: V107 5-table research-packet
schema + models/repository/builder, CLI `research-packet` group, 6 GET routes, 6 read-only MCP tools, migrator
V107 block, evidence bundle `docs/evidence/nas-second-brain-n8c/20260707T084719Z/`, and head-test updates.

## Carry-forward into N8C-12
- `LATEST_SCHEMA_VERSION = 107` is the baseline; N8C-12 does **not** bump it.
- `agent_bridge` / N8D absent → no schema-head ambiguity.
- N8C-11 remote assistant MCP tool total = 42; `ai_outputs_card_upsert` sole remote write. N8C-12 takes this
  to 48 and keeps `ai_outputs_card_upsert` the only write.
- The N8C-11 five-layer wiring pattern (profile gate + broker tuple/dispatch/`_invoke_*` RO snapshot +
  tool_registration `if _enabled():` block + api read block + CLI group) is the template N8C-12 mirrors for a
  read/connector layer (no new tables, no builder).
