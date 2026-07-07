# 05 — Projection Builder Proof

`obsidian_mcp/intelligence_projection_builder.py` — deterministic, source-backed, **pack-scoped**, NO LLM.

## Flow (all read-only until `apply=True`)

1. `RB.discover_review_candidates(review_providers, pack_id, kinds, limit, conn=)` — read-only, pack-scoped
   enumeration of anchored review drafts (claims, context-pack items, enrichment review, memory
   compilations, decision/preference/open-loop records).
2. Dedup by `review_item_id`; for each, `review_repo.get_effective_state(rid, conn=)` (latest disposition
   else built default `candidate`).
3. `classify_inclusion_state(effective_state, budget)` → `(inclusion_state, policy_included)`.
4. Deterministic sort: inclusion rank (trusted first) → confidence desc → `(target_kind, target_id)` for
   stable ties.
5. `_build_items` applies the budget, produces `ProjectionItem`s (bounded), computes `input_digest` /
   `output_digest`.

## Entry points

- `preview_intelligence_projection(...)` — fully read-only; returns header + items + receipt + counts.
  Writes nothing.
- `build_intelligence_projection(..., apply=False)` — same as preview (writes nothing).
- `build_intelligence_projection(..., apply=True)` — calls `repo.upsert_projection(...)`, writing ONLY the
  four projection tables.
- `export_intelligence_projection(...)` — bounded JSON of a persisted projection (header + bounded items).

## Policy per projection type (`ProjectionBudget.for_type`)

- `trusted_context`: `include_candidates=False`, `include_deferred=False`, `include_stale=False` — only
  operator-accepted records are included.
- `candidate_context` / `review_aware_context`: `include_candidates=True` — candidates included and labeled.
- `implementation_context`: `include_candidates=True`, `include_stale=False`, `include_open_loops=True` but
  **advisory only** — each open-loop item gets `metadata={"advisory": true}` and only bounded descriptive
  text is copied; NO executable instruction / shell command / task dispatch / reminder / schedule / ticket
  / N8D job command is ever emitted (see 10). Proven by
  `test_implementation_context_open_loops_advisory`.

## Determinism / provenance / bounding

- `test_review_aware_includes_and_labels_candidates`, `test_trusted_excludes_candidates_until_accepted`
  (see 04).
- `test_items_preserve_provenance_and_bounded` — every item has `target_id` AND ≥1 provenance anchor
  (`source_id`/`note_rel_path`/`claim_id`/`receipt_id`/`pack_id`/`pack_item_id`/`memory_node_id`/
  `memory_mention_id`/`compilation_id`/`decision_id`/`preference_id`/`open_loop_id`); any
  `evidence_excerpt` is `<= EVIDENCE_HARD_CAP` (2000) — never a full payload.
- No LLM/Ollama/Qwen is invoked anywhere in the builder — the whole path is deterministic (tests run with
  no live model).
