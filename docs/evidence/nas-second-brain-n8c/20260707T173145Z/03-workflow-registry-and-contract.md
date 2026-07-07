# 03 — Workflow registry & contract

## Canonical workflow types (11)
ask_second_brain · research_answer · source_file_lookup · meeting_prep · daily_brief_context ·
project_intelligence_context · open_loop_triage · decision_preference_lookup · draft_review ·
action_draft_preparation · unknown

## Routing targets (11)
source_connector · research_packets · answer_drafts · intelligence_projections · review_queue ·
decision_memory · memory · context_packs · claims · open_loops · unknown

## Result envelope (always present)
workflow_id (ephemeral) · workflow_type · request · routing_decision · selected_artifacts ·
trusted_items · candidate_items · excluded_items · citations · source_refs · review_labels ·
open_questions · risks_or_caveats · deferred_capabilities · **advisory_next_steps** ·
requires_operator_review · status · warnings · metadata + fixed policy block.

## Fixed policy block (never overridable)
action_policy=no_execution · execution_policy=route_only · review_policy=preserve_review_state ·
citation_policy=preserve_citations · source_policy=use_existing_artifacts_only

## Advisory-only naming (clarification #5)
The next-steps field is named **`advisory_next_steps`** (not `suggested_next_steps`). It carries only
advisory review/navigation strings — never executable instructions, scheduled actions, outbound
communications, N8D job commands, reminders, task creations, or workflow execution steps. Proven by
`test_no_suggested_next_steps_field_uses_advisory`.
