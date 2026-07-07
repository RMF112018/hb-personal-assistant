# 05 — Read-Only + Bounded Proof

## Read-only
The handlers call ONLY repository READ methods, reached through the router's guarded accessors. There is no
writer/build/apply, no `record_disposition`, no `mark_*_stale`, no worker, no persistence. Proven by AST
guards over the actual call/import graph (docstring prose ignored):
- `tests/test_workflow_router.py::test_handlers_call_no_writer_or_worker`
- `tests/test_workflow_handlers.py::test_handlers_source_has_no_writer_or_source_read`
- `tests/test_nas_mcp_workflows.py::test_handler_calls_no_writer_or_source_read` (broker handler + views)

Unmigrated / partially-provisioned DBs degrade to empty (not a crash): every accessor wraps its call in
`_guard_many`, which swallows `sqlite3.OperationalError: no such table`. Proven by
`test_workflow_handlers.py::test_unmigrated_db_degrades_not_crashes` (all four workflows over a schema-less
DB → routed/insufficient_context/missing_required_artifact, never an exception).

## Bounded before AND after (clarification #6)
Two-sided bounding, no whole-table load:

- **Input clamp.** Every list accessor takes `limit` → `_bounded_limit(limit)` → `[1, MAX_ITEMS]` before it
  ever reaches the repository (which itself also clamps). `req.limit` is clamped in
  `WorkflowRequest.from_inputs` via `_clean_limit` → `[1, MAX_ITEMS]`, default 25. Proven by
  `test_workflow_handlers.py::test_limit_is_clamped`.
- **Output cap.** Each named section is capped to `MAX_SECTION_ITEMS` (`_cap`); the envelope re-caps every
  section to `MAX_ITEMS` (`_bound_sections`) and every generic slot to its existing cap
  (`MAX_SELECTED_ARTIFACTS/MAX_CITATIONS/MAX_SOURCE_REFS/MAX_REVIEW_LABELS/MAX_ITEMS`).
- **Citation reads are bounded.** Explicit draft/packet citation reads (meeting_prep) are capped by
  `MAX_CITATIONS`; only explicitly-supplied artifact ids trigger a per-artifact citation read — listed
  items contribute only cheap source-refs collected off their already-bounded metadata (no extra reads).

## Deterministic
No LLM, no network, no clock/random. Classification is pure token-set logic; ids are deterministic
(`compute_workflow_id` folds the bounded request). Same inputs → same envelope.
