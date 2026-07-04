# 09 — Tests

```bash
PYTHONPATH=src python -m pytest tests/test_nas_mcp_readonly.py tests/test_nas_mcp_files_rw.py -q
PYTHONPATH=src python -m ruff check src/hb_assistant/nas_mcp tests deploy/nas/mcp
sh deploy/nas/mcp/check-mcp-compose.sh
```

| Check | Result |
|---|---|
| pytest | **29 passed** |
| ruff | **pass** |
| check-mcp-compose.sh | **PASS** |
