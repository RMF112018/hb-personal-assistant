# 07 — Tests

```bash
PYTHONPATH=src python -m pytest tests/test_nas_mcp_readonly.py -q
PYTHONPATH=src python -m ruff check src/hb_assistant/nas_mcp src/hb_assistant/cli/mcp_nas.py tests/test_nas_mcp_readonly.py
sh deploy/nas/mcp/check-mcp-compose.sh
```

**Result:** 10 passed (pytest); ruff clean after fixes; compose static guard PASS.

Coverage includes: compose bridge+loopback publish, no network_mode:none+ports, runner fixed command, sudoers single entry, client tunnel URL, no create_app import on dry-run, DB allowlist/deny/limit, FS traversal/.enc deny, /health endpoint.
