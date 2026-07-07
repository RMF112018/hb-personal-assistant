# 03 — Stage Contract

## Stage types (`STAGE_TYPE_VALUES`)
`daily_brief_actions`, `meeting_follow_ups`, `project_actions`, `open_loop_actions`, `review_follow_ups`,
`mixed_actions`, `unknown`. Resolved from the workflow_type; a stage bundles candidates — it never names an
external delivery channel.

## Action kinds (`ACTION_KIND_VALUES`) — INTERNAL-REVIEW only
`open_loop_follow_up`, `review_candidate`, `source_review`, `project_risk_review`, `information_gap_review`,
`decision_review`, `preference_review`, `human_follow_up`, `unknown`. There is NO send_email / create_task /
schedule_meeting / dispatch kind (asserted by `test_action_stage_models::test_action_kinds_are_internal_
review_only`).

## Staged states (`ITEM_STAGE_STATE_VALUES`)
`candidate` (surfaced for operator review) · `blocked` (recognized but withheld, with a bounded block_reason).
Never active/executed/sent.

## Section → candidate mapping (`_SECTION_MAP`)
| workflow_section | action_kind | state |
| --- | --- | --- |
| open_loops / active_open_loops / candidate_open_loops / blocked_or_waiting | open_loop_follow_up | candidate |
| review_needed / candidate_updates / candidate_findings / candidate_items | review_candidate | candidate |
| risks_or_caveats | project_risk_review | candidate |
| questions_to_resolve | information_gap_review | candidate |
| prior_decisions / related_decisions / decisions_preferences | decision_review | candidate |
| known_preferences | preference_review | candidate |
| source_files | source_review | candidate |
| trusted_facts / trusted_updates / trusted_items / project_scope | — (skipped, established context) | — |
| stale_or_superseded / excluded_items | (terminal) | blocked |

## Advisory-only gate
Each `advisory_next_steps` entry → `human_follow_up` candidate, UNLESS it reads like an execution instruction
(send/email/schedule/create-task/remind/call/dispatch/…) → staged `blocked`,
`block_reason='execution_like_advisory'`, never active. Verified in
`test_action_stage_builder::test_execution_like_advisory_is_blocked_never_active`.

## Feedback integration
Each N8C-18 advisory recommendation → an advisory review candidate (suggest_source_check → source_review;
suggest_more_context → information_gap_review; else → review_candidate), anchored to feedback_id/
recommendation_id. The feedback record is READ, never mutated.

## Deterministic identity
`request_digest = sha256(stage_type | workflow | policy | budget)[:24]` (lineage key).
`source_context_digest = sha256(sorted item signatures)[:24]`.
`input_digest = sha256(request_digest # source_context_digest # builder)[:24]`.
`stage_id = sha256(stage_type | workflow_type | request_digest | input_digest | builder)[:24]`.
Identical context → same stage_id → idempotent reuse; changed context → new stage supersedes the prior of the
same (stage_type, workflow_type, request_digest, policy) lineage.
