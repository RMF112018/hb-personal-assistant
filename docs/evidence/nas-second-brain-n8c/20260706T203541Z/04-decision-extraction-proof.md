# N8C-8 — decision extraction proof

## Path (deterministic, no LLM)
`decision_memory_extractor.discover_decision_memory(pack_id)` reads the pack's `claim_candidate` items,
loads each claim (`ClaimRepository.get_claim`), and maps a `claim_type == "decision_candidate"` claim to
a `DecisionRecord(decision_type="decision_candidate")`:
- `normalized_subject` ← claim `normalized_subject`; `normalized_decision` ← claim `normalized_object`
  (then `normalized_predicate`), with a bounded `claim_text` fallback (flagged `needs_review`);
- `decided_at` ← claim `observed_at`; `confidence` ← claim confidence;
- provenance = `source_id / note_rel_path / claim_id / pack_id / pack_item_id`; `evidence_excerpt`
  (bounded) + `evidence_location` + `source_digest` (via `source_repo.get_source_detail`).

## Proof (`test_decision_memory_extractor.py`, smoke run)
- A `decision_candidate` claim "We decided to keep MCP read-only" →
  `decisions=[decision_type=decision_candidate, normalized_decision="keep read-only"]`
  (`test_decision_extracted_from_decision_candidate_claim`).
- The record is advisory: `status=candidate`, `review_state=unreviewed`
  (`test_default_status_is_candidate_unreviewed`). It NEVER accepts the underlying claim — the claim
  stays `candidate`/`unreviewed` (`test_claims_stay_candidate_unreviewed`).
- Provenance present + bounded evidence (`test_every_record_has_provenance_and_bounded_evidence`).
- Architecture/policy decision types remain available in the enum for a future slice; N8C-8 emits
  `decision_candidate` from claims (no LLM inference of decision sub-type).
