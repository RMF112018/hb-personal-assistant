# 05 — Answer-Contract Compliance

The draft CONSUMES the N8C-11 packet's `answer_contract` (guidance metadata) and never re-derives review
state:
- `answer_allowed` → gates the whole draft (True required; else insufficient_support only).
- `candidate_claims_allowed` (truthy string `"with_caveat"` or `False`) → candidate items surface as
  `candidate_context` WITH a review label only in review-aware drafts and only when the budget includes
  candidates; a trusted_answer_draft always excludes them.
- `must_not_say[]` → those targets are excluded_manifest-only.
- `action_policy = "no_execution"` is preserved by construction: the draft layer has no action/execution path.

Proof: `test_answer_draft_builder.py::test_answer_allowed_false_yields_only_insufficient_support`,
`::test_trusted_draft_excludes_candidate_and_deferred`, `::test_review_aware_routing_and_labels`,
`::test_must_not_say_target_never_support`. API export carries the header's `answer_contract_digest`; the
packet export (N8C-11) still carries the full contract for a consumer that needs it.
