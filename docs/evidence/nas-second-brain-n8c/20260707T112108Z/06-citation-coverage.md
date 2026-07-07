# 06 — Citation Coverage

- Every answer-support section carries ≥1 citation (`test_every_support_section_is_cited`).
- Draft citations preserve the originating `packet_citation_id` when present
  (`test_citations_preserve_packet_lineage_and_source_carrythrough`); when absent, a citation is synthesized
  from the item's own provenance anchor and metadata is marked `citation_lineage=degraded`
  (`test_degraded_lineage_marked_when_no_packet_citation`).
- Schema-level CHECK: a draft citation must carry `packet_citation_id` OR ≥1 of the 14 anchors
  (`test_answer_draft_v108_migration.py::test_citation_check_rejects_anchorless_and_lineageless`,
  `::test_citation_packet_lineage_satisfies_check`, `::test_citation_provenance_anchor_satisfies_check`).
- Model-level: `DraftCitation.to_row()` raises `citation_without_packet_lineage_or_provenance` on the same
  condition (dual enforcement).
