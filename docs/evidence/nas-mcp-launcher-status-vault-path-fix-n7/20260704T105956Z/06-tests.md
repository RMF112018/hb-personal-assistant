# 06 — Tests

## Commands

```bash
PYTHONPATH=src python -m pytest tests/test_nas_mcp_readonly.py -q
PYTHONPATH=src python -m ruff check src/hb_assistant/nas_mcp tests/test_nas_mcp_readonly.py deploy/nas/mcp
sh deploy/nas/mcp/check-mcp-compose.sh
```

## Results

| Check | Result |
|---|---|
| pytest | **19 passed** |
| ruff | **All checks passed** |
| check-mcp-compose.sh | **PASS** |

## New/updated coverage

- Launcher `status`/`start` use `sudo -n` runner (no direct Docker)
- Runner fixed verbs `start|stop|status|health`
- Runner status bounded inspection
- Sudoers single command, no docker/sh/ALL grants
- Compose vault mount NAS path
- MCP config vault mount `/mnt/vault`
- No Mac vault path in NAS MCP sources
- Vault `path_display`, no `/volume1/` leak
- Absolute, traversal, `.enc`, token path denial
- Symlink escape denial
- Audit files on filesystem tests

mypy: not required for changed shell/tests; typed modules unchanged in signatures.
