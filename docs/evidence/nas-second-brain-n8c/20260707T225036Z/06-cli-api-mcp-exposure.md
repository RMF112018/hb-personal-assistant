# N8C-20 — CLI / API / MCP exposure

## CLI — `hb-assistant quality` (6 commands)

| command | posture | writes? |
|---------|---------|---------|
| `preview --target-kind --target-id` | read-only plan | no |
| `build --target-kind --target-id --dry-run/--apply` | default dry-run | only `--apply`, quality tables only |
| `list` | read-only | no |
| `show --quality-run-id` | read-only | no |
| `summary` | read-only | no |
| `export --quality-run-id` | read-only bounded JSON | no |

`test_no_execution_or_disposition_commands` asserts the command set is exactly
`{preview, build, list, show, summary, export}` and contains none of: execute, repair, send, schedule,
dispatch, remind, task, apply, accept, reject, defer, dispose, run. The `--apply` writer is CLI-only and never
exposed remotely.

## API — `/api/assistant/quality*` (6 GET-only routes)

```
GET /api/assistant/quality
GET /api/assistant/quality/summary              (declared BEFORE /{quality_run_id})
GET /api/assistant/quality/{quality_run_id}
GET /api/assistant/quality/{quality_run_id}/findings
GET /api/assistant/quality/{quality_run_id}/targets
GET /api/assistant/quality/{quality_run_id}/export
```

All wrapped in `_assistant_env` (`guardrails.read_only=true`), all-roles via `role_dep`+`del role`.
`test_routes_are_get_only` asserts every route's methods ⊆ {GET, HEAD}; `test_no_write_or_build_route` asserts
POST/DELETE return 401/404/405; `test_missing_returns_404` covers absent runs; `test_routes_ok_and_safe`
asserts no forbidden token (tokens, PEM, absolute paths, claim/evidence/email bodies) leaks.

## MCP — read-only inspection ONLY (clarification #4)

Group `quality` (13th assistant group), gated by `assistant_quality_enabled()` (default-ON kill-switch
`HB_MCP_ASSISTANT_QUALITY`). Six tools, each served from a READ-ONLY DB snapshot
(`mode=ro&immutable=1` + `PRAGMA query_only=ON`) via `_invoke_assistant_quality`:

```
assistant_list_quality  assistant_get_quality  assistant_get_quality_findings
assistant_get_quality_targets  assistant_get_quality_summary  assistant_get_quality_export
```

There is NO quality build/apply/evaluate/run/repair MCP tool. `hb_mcp_status` advertises
`assistant_quality_enabled` + `assistant_quality_tools`. The kill-switch is scoped to the quality tools only —
disabling it leaves the feedback and action-stage groups (and all others) enabled
(`test_kill_switch_disables_only_quality`).
