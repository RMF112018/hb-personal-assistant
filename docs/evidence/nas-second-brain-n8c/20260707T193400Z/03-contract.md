# 03 — Handler Contract + Registry Change

## Registry: implemented, not deferred
The four `WorkflowSpec`s now carry `implementation_deferred_to="N8C-18"` (context is implemented in N8C-17;
only action staging / delivery remains) with trimmed, honest `deferred_capabilities`:

| workflow | implementation_deferred_to | deferred_capabilities |
|---|---|---|
| meeting_prep | N8C-18 | `stage_meeting_actions` |
| daily_brief_context | N8C-18 | `stage_brief_actions` |
| project_intelligence_context | N8C-18 | `stage_project_actions`, `external_source_sync` |
| open_loop_triage | N8C-18 | `stage_open_loop_actions` |

No spec retains a `build_*` marker (asserted in `test_workflow_registry.py` +
`test_workflow_router.py::test_*`). Catalog notes now expose
`context_workflows_implemented_in="N8C-17"` and `context_workflow_actions_deferred_to="N8C-18"`.

## Envelope: additive, backward-compatible
`_envelope(...)` gained two additive fields, emitted for ALL workflows:
- `workflow_sections: dict[str, list]` — bounded per-workflow named sections (each list capped to
  `MAX_ITEMS`; non-list values dropped by `_bound_sections`).
- `workflow_policy = "context_only"` — a more-specific marker alongside the unchanged `POLICY_BLOCK`
  (`action_policy=no_execution`, `execution_policy=route_only`, review/citation/source policies intact).

Every pre-existing envelope key is still present (asserted in
`test_workflow_router.py::test_envelope_has_fixed_policies_and_is_bounded`). Old requests (no new fields)
still route unchanged; the added request fields all default empty and are individually bounded.

## Named sections per handler
- **daily_brief_context:** trusted_updates, candidate_updates, open_loops, review_needed
- **meeting_prep:** meeting_objective, trusted_context, candidate_context, prior_decisions,
  known_preferences, open_loops, questions_to_resolve
- **project_intelligence_context:** project_scope, trusted_facts, candidate_findings, source_files,
  decisions_preferences, open_loops, review_needed
- **open_loop_triage:** active_open_loops, candidate_open_loops, blocked_or_waiting, review_needed,
  stale_or_superseded, related_decisions

Absent artifacts → `insufficient_context` (empty sections); an explicitly-supplied missing open loop →
`missing_required_artifact` (never built).

## No new surfaces
No new MCP tool, no MCP rename, no new API route, no new CLI command. The CLI (`hb-assistant workflow route`)
and API (`/api/assistant/workflow/route`) already return the full envelope, so they surface the richer
result transparently — proven green by `tests/test_cli_workflow.py` and
`tests/test_fastapi_analytics_workflows.py`.
