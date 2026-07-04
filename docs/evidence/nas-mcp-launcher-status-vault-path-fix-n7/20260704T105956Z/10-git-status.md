# 10 — Git status

| Item | Value |
|---|---|
| Branch | `feat/nas-mcp-ssh-launcher-n7-20260704T102041Z` |
| Preflight HEAD | `f936f0ad` |
| N7 implementation | `5dd638ff` |
| N7 apply hotfix (`server.py`) | `a9ff717e` (committed; untouched) |
| N7-FIX | uncommitted (awaiting Bobby review) |
| Ahead of `origin/main` | 19 |
| Push | Not authorized |

## Modified (N7-FIX)

- `deploy/nas/mcp/hb-mcp-launcher`
- `deploy/nas/mcp/hb-mcp-runner`
- `deploy/nas/mcp/check-mcp-compose.sh`
- `src/hb_assistant/nas_mcp/path_safe.py`
- `src/hb_assistant/nas_mcp/fs_tools.py`
- `tests/test_nas_mcp_readonly.py`
- `docs/evidence/nas-mcp-launcher-status-vault-path-fix-n7/20260704T105956Z/` (this package)

Suggested commit message when authorized:

`fix(nas): harden MCP launcher status and vault root`
