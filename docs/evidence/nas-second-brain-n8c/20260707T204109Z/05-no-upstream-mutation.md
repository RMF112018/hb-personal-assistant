# 05 — No Upstream Mutation / No Review-Disposition Write

## Repository writes only feedback-owned tables
`FeedbackRepository.upsert_feedback` inserts into exactly `assistant_feedback_records` / `_targets` /
`_recommendations` / `_receipts` / `_events`. Guards:
- `test_feedback_repository.py::test_upsert_writes_only_feedback_tables` — snapshots every non-feedback
  table's rowcount before and after an apply; asserts they are unchanged.
- `test_feedback_service.py::test_apply_mutates_no_upstream_table` — same, through the service `apply=True`
  path with a `wrong_review_label` feedback.
- `test_feedback_service.py::test_repository_only_writes_feedback_tables` — static scan: every
  INSERT/UPDATE/DELETE literal in the repository targets an `assistant_feedback*` table (or the parametrized
  `{table}` in `_insert`, whose only call sites are feedback tables).

## No disposition verbs
- `test_feedback_service.py::test_service_never_writes_review_disposition_words` — the service source
  contains no accept/reject/defer/dispose.
- `test_feedback_cli.py::test_no_disposition_or_execution_commands` — the CLI exposes exactly
  `{add, list, show, recommendations, export}` and none of accept/reject/defer/dispose/execute/send/schedule/
  stage/remind/apply.
- `test_nas_mcp_feedback.py::test_no_write_build_or_disposition_tool_registered` — no registered assistant
  tool name contains any disposition/execution/write verb.

## review_state / effective_state are copied, never written back
The feedback target may carry `review_state` / `effective_state` (bounded metadata copied from the review
overlay the operator is giving feedback on). These are stored on the feedback target row only; the feedback
layer never writes them back to `assistant_review_*` or any projection.
