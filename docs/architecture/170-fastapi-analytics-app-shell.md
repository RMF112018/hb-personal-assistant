# 170 — FastAPI Analytics App Shell (Prompt 02)

**Objective:** add an optional FastAPI application shell for the future analytics
dashboard while keeping the base package FastAPI-free and preserving the
read-only service boundary from Prompt 01.

## Optional Dependency

`pyproject.toml` adds the `analytics-ui` optional dependency group with FastAPI,
Uvicorn, and HTTPX. The app module lazy-imports FastAPI inside `create_app()` and
`role_dependency()`, so migrations, CLI use, service-boundary tests, and base
installs do not require UI dependencies.

## Routes

`hb_assistant.construction.analytics.create_app()` exposes only:

- `GET /health` — app, schema, role, chat-disabled, and read-only guardrail
  metadata.
- `GET /chat/status` — explicit disabled-chat status.
- `GET /openapi.json` — FastAPI-generated OpenAPI for the shell routes.

No active chat route is implemented. There is no `POST /chat`,
`POST /chat/send`, `POST /chat/completions`, websocket chat, analytics endpoint,
frontend asset route, live endpoint call, or Typer CLI shell-out.

## Role Dependency

The exported `role_dependency()` reads `X-HB-UI-Role` and defaults to `viewer`.
Allowed roles are `viewer`, `operator`, and `admin`; invalid roles return 403.
All roles are read-only in Prompt 02. The dependency is exported for future
route adapters but does not grant write permission.

## Guardrails

The shell is local-first and metadata-only. It does not write to source systems,
persist operator DB rows, call live endpoints, run CLI commands, expose raw
bodies/prompts/responses/auth material/signed links, or make operational
determinations. Active chat remains disabled and inaccessible.

## Validation

`tests/test_fastapi_analytics_app_shell.py` is optional-dependency gated with
`pytest.importorskip("fastapi")`. In base environments without FastAPI the file
skips; with `analytics-ui` installed it verifies health, OpenAPI route inventory,
role handling, disabled chat status, inaccessible active-chat routes, and
metadata-only output.
See Prompt 25 runbook and INDEX for the packaged local smoke (FPR-018 final) and final evidence summary. Cite prompt-25-documentation-runbook-packaging-closeout.md.
