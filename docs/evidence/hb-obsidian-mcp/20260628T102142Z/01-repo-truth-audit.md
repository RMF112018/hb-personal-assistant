# Repo Truth Audit

## Existing Surfaces

- The repo is Python-first with Typer, Pydantic, FastAPI optional extras, and a React frontend.
- Existing MCP work lives under `hb_assistant.construction.second_brain.mcp`.
- That existing MCP bridge is stdio-only, fail-closed, and no-raw by default.
- Existing file extraction includes bounded PDF and DOCX parsers.
- Existing Settings UI uses `SettingsPage` with reusable panel components.
- Existing FastAPI route patterns live in `hb_assistant.construction.analytics.api`.

## Implementation Strategy

- Add new `hb_assistant.obsidian_mcp` package for the UI-managed Obsidian MCP foundation.
- Keep the existing `second-brain mcp` bridge unchanged.
- Add Settings API routes under `/api/settings/obsidian-mcp`.
- Add React `ObsidianMcpPanel` to the existing Settings page.
- Use the official Python MCP SDK only as an optional runtime adapter; do not hand-roll user-facing MCP operation.

## Gaps Closed

- UI configuration and status surface.
- Backend health-check surface.
- Tool registry surface.
- Test list/search/read actions.
- Grok config generation with token redaction.
- Safe filesystem tool implementation.

## Deferred

Note mutation, construction-domain analysis, Obsidian REST mode, register mutation, and starter skills remain deferred.
