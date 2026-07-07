# 08 — Idempotency & Digest Determinism

## Deterministic ids (all sha256[:24], fold `RESEARCH_PACKET_BUILDER_VERSION = "research-packet-v1"`)
`compute_packet_input_digest`, `compute_packet_output_digest`, `compute_answer_contract_digest`,
`compute_packet_id`, `compute_packet_item_id`, `compute_citation_id`, `compute_packet_receipt_id`.

## Idempotency + lineage supersede
`ResearchPacketRepository.upsert_packet(...)`:
- same `packet_id` → reuse (no duplicate);
- lineage-scoped supersede of prior draft/built packets of the same
  `(packet_type, projection_id, IFNULL(scope_json,''))`, plus a `marked_superseded` event;
- a changed `input_digest` yields a new/stale packet (prior marked stale, not silently overwritten).

## Proof (test_research_packet_repository.py, 14 tests, all pass)
- id determinism incl. citation + receipt ids;
- no-dup on re-upsert of the same packet_id;
- changed input_digest → new/stale;
- upsert writes only the 5 packet tables (see 09).
