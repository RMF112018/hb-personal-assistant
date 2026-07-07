# 06 — Packet Builder

`research_packet_builder.py`. `PacketProviders` = N8C-10 intelligence-projection repository (read-only).

## Flow (projection-scoped)
1. `get_projection(projection_id)` + `list_projection_items(projection_id, conn=)` — read-only.
2. Per item → `classify_answer_role(inclusion_state, packet_type, budget) -> (answer_role, included)`,
   consuming the item's **frozen** effective_state / inclusion_state / anchors / digests (no re-hit of review
   tables).
3. Build citations from the item's provenance anchors (one per present anchor kind, bounded, ordered).
4. `input_digest` over sorted (projection_item_id, effective_state, target_digest, citation-digests) + policy
   + budget + answer_contract.
5. Apply budget (deterministic order: answer-role rank → confidence desc → target).
6. Derive bounded `must_not_say` from rejected/not_required/superseded/excluded items.
7. `build_answer_contract(...)` → `output_digest` over included item ids.

## Answer-role classification (per inclusion_state)
`classify_answer_role` maps inclusion_state → (answer_role, default-included-when-policy-allows). Policy:
- trusted-answer-context packets **exclude** candidates;
- review-aware packets **include** candidates **and label** them;
- `implementation_research_context` keeps open loops advisory (answer_role `implementation_note`/
  `open_question`, never executable).
No packet converts candidate → accepted truth.

## Read-only surfaces
`preview_research_packet` (read-only), `build_research_packet(apply=)` (CLI `--apply` is the sole writer),
`export_research_packet` (bounded JSON: header + answer contract + bounded items + bounded citations).

Proof: `test_research_packet_builder.py` (15 tests) — role classification per inclusion_state; policy per
packet_type; every-included-item-cited; preview/dry-run read-only; no full-payload copy; no final-answer field.
