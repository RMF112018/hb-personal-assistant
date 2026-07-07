# 06 — Effective-state read model proof

Effective state is COMPUTED, never written back into a source (or the review item's built columns):

    effective_state = latest disposition's to_effective_state  (if any disposition exists)
                      else the review item's built effective_state (default `candidate`)

Implemented in `ReviewRepository._effective_state_for_item` (used by `get_effective_state`,
`effective_state_for_target`, and the MCP/API surfaces).

## Disposition → (review_state, effective_state) mapping (`review_models.DISPOSITION_STATE_MAP`)
- accept → operator_accepted / accepted
- reject → operator_rejected / rejected
- defer → deferred / deferred
- mark_not_required → not_required / not_required
- mark_stale → stale / stale
- mark_superseded → superseded / superseded
- request_more_context → needs_review / candidate

## Proof (`tests/test_review_repository.py`)
- `test_disposition_maps`: each disposition_type yields the mapped review_state/effective_state, both in
  the returned result and in `get_effective_state`.
- `test_dispositions_are_append_only`: with two dispositions, the LATEST (defer) determines the effective
  state (`deferred`), `disposed=True`.
- `test_disposition_does_not_mutate_item_columns`: the review item's stored columns stay at their built
  defaults — effective state is derived, not persisted back.
- `test_effective_state_for_target`: `effective_state_for_target(target_kind, target_id)` returns the
  per-item computed states.
- API `test_fastapi_analytics_review.py::test_effective_state_reflects_disposition` and MCP
  `test_nas_mcp_review.py::test_tools_return_data` confirm the computed `accepted` state end-to-end.
