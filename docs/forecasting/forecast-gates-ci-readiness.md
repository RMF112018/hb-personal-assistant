# Forecast Gates CI and Readiness Posture

## CI policy (safe default)

CI **must run**:

```bash
pytest tests/test_forecasting_field_classifiers.py \
       tests/test_forecasting_db_evidence_package.py \
       tests/test_forecasting_gates.py \
       tests/test_forecasting_runtime_normalization.py \
       tests/test_forecasting_semantic_catalog.py \
       tests/test_forecasting_external_fixture.py \
       tests/test_forecasting_evidence_script_integration.py \
       tests/test_forecasting_readiness.py \
       tests/test_forecasting_projection_parity_keys.py \
       tests/test_forecasting_project_eligibility.py -q

pytest tests/test_procore_normalizers_financial_amounts.py -q

ruff check src/hb_assistant/forecasting/ tests/test_forecasting_*.py
```

Evidence script integration test uses `HB_FORECASTING_EVIDENCE_SKIP_NO_RAW=1` and minimal synthetic DB — no live DB.

CI **must not require**:

- Live production SQLite
- Procore HTTP (`HB_PROCORE_LIVE`)
- SchemaCrawler (skipped in integration test)
- Copied live DB

## Readiness chain

Phase 08C `evaluate_forecast_readiness_gates()` invokes `evaluate_forecast_semantic_gates()` as gate #9 (`forecast_semantic_gates`).

Combined CLI:

```bash
hb-assistant construction-agent forecast gates --db-path /path/to/db.sqlite --json
```

## Warn vs strict

| Mode | Use |
|------|-----|
| `warn` | Readiness reports, CI fixtures, operator dashboards |
| `strict` | Local triage — promotes warnings to errors; not CI default |

Proven budget-column coexistence reports **info** in warn mode. Unresolved formulas stay **warning**, never sole hard-fail.

## Live-copy validation (operator only)

```bash
scripts/run_forecasting_gates_live_copy_evidence.sh
# Uses VACUUM INTO copy; does not commit live-copy.sqlite
```

PO drift audit:

```bash
python3 scripts/audit_po_projection_drift.py --db-path $COPY --json-out docs/evidence/.../purchase-order-projection-drift-evidence.json
```

## GitHub Actions

No `.github/workflows` present in repo. CI commands documented here for local/launchd verification. Add workflow only when repo adopts shared CI pattern.