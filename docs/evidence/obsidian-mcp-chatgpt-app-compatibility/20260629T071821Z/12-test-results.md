# Test Results

Passed:

- `tests/test_obsidian_mcp_oauth.py -q`: 33 passed
- `tests/test_obsidian_mcp_oauth.py tests/test_obsidian_mcp_backend.py -q`: 44 passed
- `tests -q -k "obsidian_mcp or oauth or chatgpt"`: passed with one skipped test
- `npm run test -- SettingsPage`: 13 tests passed across 2 files
- `npm run typecheck`: passed
- `npm run build`: passed
- `ruff check src/hb_assistant/obsidian_mcp tests/test_obsidian_mcp_oauth.py tests/test_obsidian_mcp_backend.py`: passed

Known validation caveat:

- Broad `ruff check ... api.py ...` is blocked by pre-existing unrelated lint debt in `api.py`, including schedule/forecast `HTTPException` references and existing B904/SIM105 issues.

