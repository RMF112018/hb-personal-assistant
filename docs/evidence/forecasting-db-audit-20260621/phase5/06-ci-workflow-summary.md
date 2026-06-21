# CI Workflow Summary (Phase 5)

## GitHub Actions

Created: `.github/workflows/forecasting-semantic-gates.yml`

- Triggers: `pull_request`, `push` to `main`
- Python 3.12, `pip install -e ".[dev]"`
- Runs `scripts/ci_forecasting_semantic_gates.sh`

## Local CI script

`scripts/ci_forecasting_semantic_gates.sh` — same checks, no live DB or Procore required.

Sets `HB_FORECASTING_EVIDENCE_SKIP_NO_RAW=1` for evidence integration test.

## CI-safe vs operator-only

| Check | CI | Operator live-copy |
|-------|----|--------------------|
| Synthetic gate tests | Yes | — |
| Semantic YAML parse | Yes | — |
| Ruff forecasting scope | Yes | — |
| Live-copy gate evidence | No | `scripts/run_forecasting_gates_live_copy_evidence.sh` |
| Actual/ERP audit scripts | No | `scripts/audit_actual_erp_semantics.py` |
| Budget dynamic column audit | No | `scripts/audit_budget_dynamic_columns.py` |

## Result

Local script: **pass** (see `01-test-results.txt`).