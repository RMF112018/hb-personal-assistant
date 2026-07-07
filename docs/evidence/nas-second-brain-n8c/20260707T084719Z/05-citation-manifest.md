# 05 — Citation Manifest

Every answerable packet item is backed by ≥1 citation drawn from that item's **frozen** provenance anchors
(no re-hit of source/review tables). Citations are bounded (id/label/excerpt/location + anchors + digests),
ordered, and stored in `assistant_research_packet_citations`.

## Anchor-specific entropy (no collision)
`compute_citation_id` folds `anchor_kind`, `anchor_id`, and `citation_order` (plus target_kind/target_id/
digests and `RESEARCH_PACKET_BUILDER_VERSION`) → sha256[:24]. Multiple citations for the same target/digest
but different anchor or order produce **distinct** citation ids.
Proof: `test_research_packet_repository.py::test_citation_id_anchor_entropy_no_collision`.

## Provenance enforced in BOTH model validation AND schema CHECK
- Schema: `assistant_research_packet_citations` carries the shared `_PROVENANCE_CHECK` (≥1 anchor among
  source_id / claim_id / review_item_id / projection_item_id / memory_node_id / decision_id / preference_id /
  open_loop_id / …). An anchorless citation row is rejected by SQLite.
- Model: `Citation.to_row(...)` raises `ResearchPacketValidationError` if no anchor is present.

## Coverage rule
Every **included** item gets ≥1 citation **unless** `answer_role ∈ {open_question, excluded_context}`.
Proof: `test_research_packet_builder.py` (every-included-item-cited assertion; citations
provenance-linked + bounded).
