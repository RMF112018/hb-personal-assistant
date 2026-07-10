### SUPERSEDED — do not use for PR review. See SUPERSEDED.md and suite-comparison-current.md

# Suite comparison at closeout HEAD

## Scope
Offline-safe module batch: `test_prompt*`, `test_tool*`, `test_n8c*`, `test_nas*`, `test_source*`, `test_canonical*`
(120s per-module timeout). Full monolithic suite hangs on HTTPS (Azure) without pytest-timeout.

## Feature HEAD
Branch `fix/prompt-preflight-routing-consistency` after closeout commit `ee06db39` (workspace code during run).

```
SUMMARY feature pass=73 fail=4 timeout=0 total=77 duration_s=654.1
FAILURES:
tests/test_n8c23_mcp_surface_safety.py
tests/test_nas_mcp_tool_annotations.py
tests/test_source_connector_eval.py
tests/test_source_structure_cli.py
```

## Baseline `05765b65`
```
SUMMARY baseline fails include:
tests/test_n8c23_mcp_surface_safety.py
tests/test_n8c23_org_neutral_scan.py
tests/test_n8c_final_validation.py
tests/test_nas_mcp_tool_annotations.py
tests/test_source_connector_eval.py
tests/test_source_structure_cli.py
```

## Classification
| Category | Modules |
| --- | --- |
| **New regressions** | **none** |
| Pre-existing (both) | n8c23 surface safety, tool annotations, source_connector_eval, source_structure_cli |
| Fixed on feature | n8c23_org_neutral_scan, n8c_final_validation (schema head) |

## Proof matrix
`scripts/generate-route-proof-matrix.py` → **20/20 pass** (fail-closed oracle).

## Remote main
Previously confirmed via `git ls-remote origin refs/heads/main` = `05765b65…`.
