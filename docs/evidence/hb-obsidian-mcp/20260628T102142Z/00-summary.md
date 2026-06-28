# HB Obsidian MCP Phase 1 Evidence Summary

- Branch: `codex/hb-obsidian-mcp-ui-foundation`
- Base commit: `f2916c21b323e4edb60c8532da85447720dd9ed6`
- Operator surface: frontend Settings panel only
- User-facing CLI added: no
- MCP tools implemented: `list_directory`, `search_vault`, `read_file`
- Existing `second-brain mcp` bridge changed: no

## Result

Implemented the UI-managed Phase 1 foundation under `hb_assistant.obsidian_mcp`, with FastAPI routes under `/api/settings/obsidian-mcp` and a React Settings panel.

The optional `mcp` SDK is installed in the validation venv. Runtime validation shows `/mcp` mounted, the Streamable HTTP app initialized without blockers, and the MCP `tools/list` response exposing `list_directory`, `search_vault`, and `read_file`.

## Validation

- `.venv/bin/pytest tests/test_obsidian_mcp_backend.py -q`: passed, 8 tests
- `.venv/bin/pytest tests/test_fastapi_analytics_app_shell.py -q`: passed
- runtime `/mcp` initialize and `tools/list` smoke: passed
- `npm run test -- SettingsPage`: passed
- `npm run typecheck`: passed
- `npx eslint src/components/settings/ObsidianMcpPanel.tsx src/pages/SettingsPage.tsx src/pages/SettingsPage.test.tsx src/lib/api.ts`: passed
- `.venv/bin/ruff check src/hb_assistant/obsidian_mcp tests/test_obsidian_mcp_backend.py tests/test_fastapi_analytics_app_shell.py`: passed

## Notes

Full frontend lint and full API lint were not used as completion gates because they include unrelated existing debt outside this change. A broad `npm run lint -- ...` still invoked `eslint .` and reported unrelated schedule component errors.
