# Suite comparison (offline-safe module batch)

Scope: tests matching `test_prompt*`, `test_tool*`, `test_n8c*`, `test_nas*`, `test_source*`, `test_canonical*` with 120s per-module timeout.

Full monolithic suite hangs on unauthenticated HTTPS (Azure login) even with `-m "not live"`; network unavailable for pip install of pytest-timeout.

- Feature branch: `tests/test_source_structure_cli.py rc=1 /Users/bobbyfetting/hb-personal-assistant-worktrees/fix-prompt-preflight-routing-consistency/tests/test_source_structure_cli.py:106: assert 80 == 78 | =========================== short test summary info ============================ | FAILED tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots`
- Baseline `05765b65`: `tests/test_source_structure_cli.py rc=1 /Users/bobbyfetting/hb-personal-assistant-worktrees/baseline-05765b65/tests/test_source_structure_cli.py:106: assert 80 == 78 | =========================== short test summary info ============================ | FAILED tests/test_source_structure_cli.py::test_export_evidence_emits_gate_off_and_on_snapshots`

## Fail module sets
- Feature fails: ['tests/test_n8c23_mcp_surface_safety.py', 'tests/test_n8c_final_validation.py', 'tests/test_nas_mcp_oauth.py', 'tests/test_nas_mcp_origin_auth.py', 'tests/test_nas_mcp_safe_mode_limits_freshness.py', 'tests/test_nas_mcp_tool_annotations.py', 'tests/test_source_connector_eval.py', 'tests/test_source_structure_cli.py']
- Baseline fails: ['tests/test_n8c23_mcp_surface_safety.py', 'tests/test_n8c23_org_neutral_scan.py', 'tests/test_n8c_final_validation.py', 'tests/test_nas_mcp_tool_annotations.py', 'tests/test_source_connector_eval.py', 'tests/test_source_structure_cli.py']
- New regressions (feature - baseline): ['tests/test_nas_mcp_oauth.py', 'tests/test_nas_mcp_origin_auth.py', 'tests/test_nas_mcp_safe_mode_limits_freshness.py']
- Pre-existing (intersection): ['tests/test_n8c23_mcp_surface_safety.py', 'tests/test_n8c_final_validation.py', 'tests/test_nas_mcp_tool_annotations.py', 'tests/test_source_connector_eval.py', 'tests/test_source_structure_cli.py']
- Fixed on feature (baseline - feature): ['tests/test_n8c23_org_neutral_scan.py']

## Classification after remediation commits
- `test_nas_mcp_oauth/origin_auth/safe_mode` were **new** due to over-eager `token` redaction; **fixed** in ea1f32e2.
- `test_n8c_final_validation` hardcoded `== 116`; **fixed** to use `LATEST_SCHEMA_VERSION` (V118).
- Remaining pre-existing: annotations destructive set, source_structure 80==78, source_connector_eval, n8c23 surface 97==78.

## Remote main
`git ls-remote origin refs/heads/main` → `05765b6512593d7383cfc6a2c1f6603ac3bbd215` (matches audited SHA).
