# 03 — Feedback Contract

## Feedback target kinds (`FEEDBACK_TARGET_KIND_VALUES`)
`workflow_result`, `workflow_section`, `workflow_artifact`, `answer_draft`, `answer_draft_section`,
`research_packet`, `research_packet_item`, `citation`, `source_ref`, `source_file_metadata`, `context_pack`,
`intelligence_projection`, `projection_item`, `review_item`, `claim`, `memory_node`, `memory_mention`,
`decision`, `preference`, `open_loop`, `advisory_next_step`, `unknown`.

## Feedback types (`FEEDBACK_TYPE_VALUES`) — all advisory signals, none applies a change
`useful`, `not_useful`, `incorrect`, `incomplete`, `needs_review`, `needs_more_context`, `wrong_source`,
`missing_source`, `wrong_review_label`, `candidate_should_be_trusted`, `trusted_should_be_candidate`,
`should_be_excluded`, `duplicate`, `stale`, `operator_note`, `unknown`.

## Feedback-record lifecycle status (NOT a review disposition)
`open`, `acknowledged`, `resolved`, `superseded`.

## Advisory recommendation types (`RECOMMENDATION_TYPE_VALUES`) — suggestions only
`suggest_review`, `suggest_more_context`, `suggest_source_check`, `suggest_relabel_candidate`,
`suggest_relabel_trusted`, `suggest_exclude`, `suggest_deduplicate`, `operator_note`, `unknown`.
There is NO accept/reject/defer/dispose value.

## Deterministic derivation map (`_RECOMMENDATION_MAP`)
| feedback_type | recommendation_type |
| --- | --- |
| not_useful / incomplete / needs_more_context | suggest_more_context |
| incorrect / needs_review / wrong_review_label / stale | suggest_review |
| wrong_source / missing_source | suggest_source_check |
| candidate_should_be_trusted | suggest_relabel_trusted |
| trusted_should_be_candidate | suggest_relabel_candidate |
| should_be_excluded | suggest_exclude |
| duplicate | suggest_deduplicate |
| operator_note / unknown | operator_note |
| **useful** | **(no recommendation)** |

Every derived recommendation is anchored to the primary (first) target and carries
`review_policy=advisory_review_loop` + `requires_operator_review=1`.

## Deterministic identity
`feedback_id = sha256(feedback_type | input_digest | FEEDBACK_BUILDER_VERSION)[:24]` where `input_digest`
folds the feedback type + sorted target signatures + bounded note digest + author. Identical
`(type, targets, note, author)` → same `feedback_id` → idempotent reuse (verified in
`test_feedback_models.py` + `test_feedback_repository.py`).
