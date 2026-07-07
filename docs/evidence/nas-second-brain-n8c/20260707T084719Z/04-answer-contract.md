# 04 — Answer-Context Contract (guidance metadata only)

`build_answer_contract(packet_type, budget, unresolved_questions, must_not_say)` in
`research_packet_models.py` returns guidance metadata — **never** answer content. Fields:

- `answer_allowed` — **COMPUTED** from included support + policy, never defaulted true. A packet whose only
  support is excluded/stale/superseded/not_required (zero trusted+candidate included) → `answer_allowed=false`.
- `citation_required: True` (models.py:238)
- `review_labels_required: True` (models.py:239)
- `trusted_claims_allowed`, `candidate_claims_allowed` ("with_caveat")
- `excluded_claims_policy: "omit"`
- `open_loops_policy: "advisory_only"`
- `action_policy: "no_execution"` (models.py:244)
- `confidence_policy`
- `must_not_say[]` — bounded + content-minimized: IDs, labels, exclusion reasons, short bounded summaries
  only; never full rejected/excluded content.
- `unresolved_questions[]` — bounded open questions.

## Not an answer
There is **NO** `final_answer` / `answer_text` / `generated_answer` / `response` field anywhere in the models
or builder (grep confirms the only occurrences are docstring lines asserting their absence,
models.py:9,12). The contract is consumed as *guidance*, never treated as answer text.

## Proof
`test_research_packet_builder.py` asserts citation_required / action_policy=no_execution /
review_labels_required / unresolved_questions / bounded must_not_say, and the no-final-answer-field
invariant. All pass.
