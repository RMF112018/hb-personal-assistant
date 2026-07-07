# 08 — Idempotency & Digests

Deterministic ids `sha256_hex(...)[:24]`, all folding `ANSWER_DRAFT_BUILDER_VERSION = "answer-draft-v1"`:
`compute_draft_input_digest` (per-item packet_item_id + effective_state + target_digest#citation-lineage-sig,
sorted, + policy + budget + answer_contract_digest), `compute_draft_id`, `compute_draft_section_id`,
`compute_draft_citation_id`, `compute_draft_output_digest`, `compute_draft_receipt_id`.

- Same inputs → same `draft_id` → repository reuses (no duplicate row), no supersede
  (`test_answer_draft_repository.py::test_deterministic_ids_and_idempotent_reuse`).
- A changed input (e.g. a new objective, or a changed packet/effective-state/citation lineage) → new
  `input_digest` → new `draft_id` → the prior draft of the same `(draft_type, packet_id, draft_policy_json)`
  lineage is marked `superseded` + a `marked_superseded` event
  (`::test_changed_packet_supersedes_prior_draft`).
- Explicit drift → `mark_answer_draft_stale_if_needed` marks `stale` + event (`::test_stale_on_input_drift`).
No background scan exists.
