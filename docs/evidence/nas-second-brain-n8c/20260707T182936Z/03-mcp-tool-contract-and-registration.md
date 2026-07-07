# 03 — MCP tool contract & registration

Six tools, registered via the existing `_assistant_result` broker forwarder, gated by
`if assistant_workflows_enabled():` in `tool_registration.py`, dispatched by a broker branch placed BEFORE
the generic `assistant_`-prefix catch-all:

| tool | returns | DB |
|------|---------|----|
| `assistant_list_workflows` | `{catalog}` (registry) | none |
| `assistant_route_workflow` | `{workflow}` full envelope | RO snapshot |
| `assistant_get_workflow_context` | `{workflow_context}` bounded slice | RO snapshot |
| `assistant_get_workflow_artifacts` | `{workflow_artifacts}` refs+count | RO snapshot |
| `assistant_get_workflow_policy` | `{workflow_policy}` policy+request | RO snapshot |
| `assistant_get_workflow_summary` | `{workflow_summary}` counts+decision | RO snapshot |

Every routing tool builds a `WorkflowRequest.from_inputs(...)` (all inputs clamped: text capped, ids
trimmed) and calls `WorkflowRouter(db).route(request, conn=<ro_snapshot>)`. Descriptions state each tool
retrieves bounded routing/context artifacts and does NOT generate final answers or execute actions.
Names use route/context/policy/artifacts/summary verbs — none is a forbidden finality/action substring.
