# 02 — Intelligence Projection: Current-State Audit

Before implementing, confirmed there was no prior projection layer and that the four projection tables did
not exist at V105, so V106 is purely additive.

## Pre-existing state (at N8C-9 / V105)

- No `assistant_intelligence_projection*` table existed; no `intelligence_projection_*` module existed;
  no `intelligence` CLI group; no `/api/assistant/intelligence/*` route; no `assistant_*_intelligence_*`
  MCP tool.
- Highest schema version was 105 (`v105_assistant_review`).

## Reusable pieces confirmed (consumed, not duplicated)

- `obsidian_mcp/review_builder.py`: `discover_review_candidates`, `ReviewProviders`, `ALL_KINDS` — the
  pack-scoped, read-only candidate enumerator with deterministic `review_item_id`, provenance anchors,
  `target_digest`, and bounded title/summary/evidence.
- `obsidian_mcp/review_repository.py`: `get_effective_state(review_item_id, conn=)` — latest disposition
  else built default; `conn=`-threaded for the MCP read-only snapshot.
- `obsidian_mcp/context_pack_models.py`: `estimate_tokens`.
- `obsidian_mcp/memory_models.py`: `bound_text`, `clamp_confidence`, `sha256_hex`.
- V100–V105 migrator pattern (guarded per-version block + `_vN_statements()` importing `VN_STATEMENTS`).
- `analytics/api.py` `_assistant_env` + `role_dep` GET block convention; `nas_mcp` `_ro_uri` +
  `PRAGMA query_only=ON` read-only snapshot + default-ON independent kill switch.

## Design decision

Mirror the N8C-9 review stack exactly (schema module → models → repository → builder → CLI → API → MCP →
tests). Projections are **derived read products** materialized from the review overlay; they own only their
four tables and are the single new schema surface in this phase.
