# 08 — Static security scan

Scanned: `docs/evidence/nas-mcp-ssh-launcher-n7/20260704T102041Z`, `deploy/nas/mcp`, `src/hb_assistant/nas_mcp`, `tests/test_nas_mcp_readonly.py`

**Result:** PASS (documentation of deny patterns only; no real secrets/tokens/IPs)

Matches in deny-list config and redaction regexes are expected.

Compose static guard: PASS (`check-mcp-compose.sh`)
