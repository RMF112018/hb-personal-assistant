# 04 — Review-item discovery proof

`review_builder.py` performs deterministic, pack-scoped, read-only discovery. `pack_id` is REQUIRED;
`kinds` narrows families within the pack; there is no global/`--all` default.

## Sources → review items (each anchored to its target + source evidence)
- **claims** → `claim_review` (target_kind `claim`, anchor `claim_id`+`pack_item_id`+`source_id`) — a
  claim is a candidate when candidate/unreviewed, a decision/task/commitment/risk/contradiction
  candidate, low-confidence, or its source drifted.
- **context-pack items** → `context_pack_review` (target_kind `context_pack_item`, anchor
  `pack_item_id`) when `review_tier != safe_summary`.
- **enrichment review** → `enrichment_review` (target_kind `enrichment_review_item`, anchor
  `receipt_id`+`source_id`) filtered to the pack's source_ids, non-`safe_summary` tiers.
- **memory compilations** → `memory_review` (target_kind `memory_compilation`, anchor
  `compilation_id`+`memory_node_id`) for the pack's sources, needs-review/stale/truncated.
- **decision/preference/open-loop records** → `decision_review`/`preference_review`/`open_loop_review`
  (anchor the respective record id + `pack_id`) for records with `pack_id == pack` and
  `status=candidate`/`review_state=unreviewed`.

## Proof (see `tests/test_review_builder.py`)
Seed: 2 claims (`decision_candidate`, `commitment`) on source `s1` → enrichment job/receipt →
`enrichment_review` context pack → N8C-8 decision-memory apply. Then `build_review_queue(apply=True)`:
- `test_build_apply_produces_anchored_bounded_items`: ≥1 item; every item has a non-empty `target_id` AND
  at least one provenance anchor; `evidence_excerpt` ≤ `EVIDENCE_HARD_CAP` (2000).
- `test_families_discovered`: yields claim/context-pack review AND decision/open-loop review.
- `test_kind_scoping_narrows`: `kinds=("decisions",)` yields only `decision_review`.
- Bounded metadata only: builder copies bounded `title`/`summary`/`evidence_excerpt` (models hard-cap
  them); it never copies full `result_json`, pack exports, compilations, or raw bodies.
