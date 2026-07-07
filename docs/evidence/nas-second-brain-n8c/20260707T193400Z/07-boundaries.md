# 07 — No-Execution / No-Persistence / No-Action-Staging Boundary

## Fixed policy block intact + additive context-only marker
Every envelope carries the unchanged `POLICY_BLOCK` AND the additive `workflow_policy="context_only"`:

    action_policy    = no_execution
    execution_policy = route_only
    review_policy    = preserve_review_state
    citation_policy  = preserve_citations
    source_policy    = use_existing_artifacts_only
    workflow_policy  = context_only          # N8C-17 additive

Proven for all four workflows by `test_workflow_handlers.py::test_policies_intact_and_context_only[*]` and at
the MCP layer by `test_nas_mcp_workflows.py`.

## No execution / staging / delivery
Nothing is executed, staged, scheduled, sent, or created. No task, reminder, email, calendar item, agenda,
invite, or disposition is produced; no open loop is closed/reopened/deferred/accepted/rejected; no action
object is staged. Action staging/delivery is honestly deferred to N8C-18 (`stage_*` capabilities).

## advisory_next_steps is advisory-only (clarification #9)
`advisory_next_steps` contains navigation/review guidance only. It is proven free of EVERY execution verb
(send, schedule, create task, remind, email, notify, assign, close, reopen, accept, reject, defer, dispose,
launch, run, execute, build, apply, scan, reindex, create N8D) by
`test_workflow_handlers.py::test_advisory_next_steps_are_advisory_only[*]`. The strings were deliberately
rewritten to avoid even NEGATED uses of those verbs.

## No persistence
Routing/assembly writes nothing — no workflow run/event/receipt/history, no raw request. `workflow_id` stays
an ephemeral deterministic response id. Proven: `test_nas_mcp_workflows.py::
test_no_workflow_persistence_tables_written` (table set unchanged after several routes) and
`test_no_workflow_persistence_table_in_migrator`.

## Finality guard NOT weakened
The N8C-12/N8C-16 finality guard is unchanged and still green: no MCP tool name contains a forbidden verb,
and no envelope/summary carries a final-answer/executed-action field
(`test_nas_mcp_workflows.py::test_existing_finality_guard_still_passes`,
`test_no_forbidden_substring_in_workflow_names`, `test_summary_is_nonfinal_route_metadata`).
