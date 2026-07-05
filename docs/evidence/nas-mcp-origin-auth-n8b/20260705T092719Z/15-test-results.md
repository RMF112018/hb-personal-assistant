# 15 — Test Results

Runner: `/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python` with `PYTHONPATH=src`
(main-repo venv; the worktree has no `.venv`). Profile default `remote_cloudflare`.

## Commands
```
PYTHONPATH=src python -m pytest tests/test_nas_mcp_origin_auth.py -q   # 19 passed
PYTHONPATH=src python -m pytest tests/test_nas_mcp*.py -q              # 58 passed
ruff check <changed .py>                                              # All checks passed!
git diff --check                                                      # clean
```

## New suite (`tests/test_nas_mcp_origin_auth.py`, 19)
Store: `test_token_hashed_never_persisted_and_0600`, `test_validate_roundtrip_and_unknown`,
`test_expired_token_denied`, `test_revoked_token_denied`, `test_rotate_revokes_old_mints_new`,
`test_list_tokens_has_no_secrets`, `test_create_rejects_unknown_client`.
Middleware / e2e: `test_mcp_denied_without_auth`, `test_mcp_denied_bad_and_malformed_bearer`,
`test_mcp_denied_revoked_and_expired`, `test_valid_token_allowed_and_audit_attribution`.
Capability: `test_valid_token_cannot_call_blocked_or_scratch_writes`,
`test_valid_token_can_call_ai_outputs_but_not_outside_folder`, `test_allowed_tools_narrowing`.
Health: `test_health_minimal_public_hides_detail`, `test_health_protected_requires_auth`.
Signals / CLI: `test_gate_status_surfaces_origin_auth_signals`,
`test_remote_profile_origin_auth_is_hard_on`, `test_cli_create_lists_and_revokes`.

## Full NAS suite
`tests/test_nas_mcp*.py` → **58 passed, 1 warning** (39 foundation + 19 new; existing
`test_build_asgi_health_endpoint` updated to the minimal-public health contract). Warning is
a pre-existing Starlette/httpx TestClient deprecation, unrelated.

## Scope
No deploy files changed → `check-mcp-compose.sh` / cloudflared `config` not applicable this
phase (unchanged from foundation). Sensitive scan: see `14`.
