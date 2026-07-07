# 05 — No Upstream Mutation / Feedback Read-Only

## Reads N8C-17 + N8C-18, mutates neither
The builder consumes `WorkflowRouter.route(request, conn=conn)` (the N8C-17 envelope) and
`FeedbackRepository.list_recommendations(...)` (the N8C-18 advisory recs) READ-ONLY. It writes only the five
V110 stage tables via `ActionStageRepository.upsert_stage`. It never:
- writes a review disposition (review_policy pinned `preserve_review_state`),
- mutates a workflow / feedback / review / source / draft / packet / projection / context-pack / decision /
  preference / open-loop record,
- marks a feedback record acknowledged/resolved,
- reads or writes a source file.

## review_state / effective_state are copied, never written back
A staged item may carry a copied `review_state` / `effective_state` (bounded metadata from the workflow
context) — filtered to the valid N8C-9 enum values before storage. These live on the stage item row only; the
stage layer never writes them back to the review overlay or any projection.

## Lineage supersede is stage-owned
`upsert_stage` supersedes ONLY prior `draft`/`staged` stages of the SAME `(stage_type, workflow_type,
request_digest, stage_policy_json)` lineage — a stage-owned status change. It never marks a workflow/feedback/
review/source record stale. Verified in `test_action_stage_repository::test_lineage_supersede` +
`test_different_lineage_not_superseded`.
