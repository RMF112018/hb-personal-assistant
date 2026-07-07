# 08 — API / CLI exposure

## CLI (read-only)
`hb-assistant workflow catalog` and `hb-assistant workflow route`. No `--apply/--build/--execute/
--send/--schedule` flag (`test_no_apply_or_build_flag`). Registered in `cli/main.py` via 2 lines
mirroring the answer-draft group.

## API (read-only, GET only)
`GET /api/assistant/workflows/catalog` and `GET /api/assistant/workflows/route`, added inside
`create_app`, role-gated (`role_dep` + `del role`), wrapped by `_assistant_env` (guardrails.read_only).
`/catalog` is a literal path declared before any parameterized route. No POST/PUT/PATCH/DELETE, no
build/apply/execute route, no workflow-run persistence. Tests: `test_catalog_route_ok_and_safe`,
`test_route_endpoint_routes_and_carries_policies`, `test_routes_are_get_only`,
`test_catalog_before_param_route`.
