# N8C-8 — preference extraction proof

## Path (deterministic, no LLM)
- **Primary (claims):** a `claim_type == "preference"` claim → `PreferenceRecord(preference_type=
  "user_preference")`; `normalized_preference` ← claim `normalized_object`/`predicate`; `strength`
  derived from confidence (≥0.8 strong / ≥0.6 medium / else weak). Provenance from the claim.
- **Secondary (memory compilations, WEAK advisory):** each entry in a built compilation's
  `preferences_json` → `PreferenceRecord(preference_type="workflow_preference")` with `strength="weak"`,
  `confidence ≤ COMPILATION_CONFIDENCE_CAP (0.4)`, `review_state="needs_review"`, and
  `metadata_json.compilation_derived=true`. Provenance = `compilation_id` + `memory_node_id` + a
  representative source anchor from the node's mentions.

## Proof (`test_decision_memory_extractor.py`, smoke run)
- A `preference` claim "Bobby prefers no AI trailer in commits" →
  `preferences=[user_preference, normalized_preference="no ai trailer"]`
  (`test_preference_extracted_from_preference_claim`).
- A built compilation with `preferences_json=["prefer weekly cadence"]` →
  `workflow_preference` record with `confidence ≤ 0.4`, `review_state=needs_review`, `compilation_id`
  set, `compilation_derived=true` (`test_compilation_produces_weak_candidates`).
- Model-inferred (compilation-derived) preferences are never treated as binding — they are the WEAKEST
  tier, always `needs_review`.
- Default `status=candidate` / `review_state ∈ {unreviewed, needs_review}`
  (`test_default_status_is_candidate_unreviewed`); provenance + bounded evidence enforced.
