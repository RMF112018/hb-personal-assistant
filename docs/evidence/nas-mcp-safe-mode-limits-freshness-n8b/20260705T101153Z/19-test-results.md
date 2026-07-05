# 19 — Test Results

Runner: `/Users/bobbyfetting/hb-personal-assistant/.venv/bin/python` + `PYTHONPATH=src`
(main-repo venv; worktree has none). Profile default `remote_cloudflare`.

## Commands
```
PYTHONPATH=src python -m pytest tests/test_nas_mcp_safe_mode_limits_freshness.py -q  # 25 passed
PYTHONPATH=src python -m pytest tests/test_nas_mcp*.py -q                            # 83 passed
ruff check <changed .py>                                                            # All checks passed!
git diff --check                                                                    # clean
```

## New suite (`tests/test_nas_mcp_safe_mode_limits_freshness.py`, 25)
Safe mode: `test_safe_mode_allows_status_and_freshness`,
`test_safe_mode_denies_ai_outputs_and_mutations`, `test_safe_mode_denial_is_audited`.
Rate limits: `test_rows_capped_by_env`, `test_search_results_capped_by_env`,
`test_oversized_card_denied`, `test_write_window_blocks_repeated_writes`,
`test_write_window_fails_closed_on_unreadable_or_corrupt_state`,
`test_write_window_state_error_missing_file_is_zero`,
`test_binary_and_broad_scan_denied`, `test_concurrency_limiter_unit`.
Overrides: `test_no_mcp_tool_can_create_override`, `test_operator_cli_creates_and_revokes`,
`test_override_requires_reason_and_expiry`, `test_override_extends_only_its_scope`,
`test_expired_and_revoked_override_no_longer_apply`, `test_raise_only_override_never_lowers`,
`test_active_override_in_capability_mode`.
Freshness: `test_freshness_reports_present_and_missing_explicitly`,
`test_queue_status_returns_counts`, `test_recent_failures_redacted_no_payload`,
`test_freshness_output_has_no_local_paths`, `test_freshness_tier0_in_audit`.
Origin-auth interaction: `test_freshness_requires_origin_auth`,
`test_per_token_allowed_tools_cannot_reach_freshness`.

## Full NAS suite
`tests/test_nas_mcp*.py` → **83 passed** (58 prior + 25 new). Pre-existing Starlette/httpx
TestClient deprecation warning only. No deploy files changed → compose checks N/A. Sensitive
scan: see `18`.
