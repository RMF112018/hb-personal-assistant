# Phase 5 Completion Report — Forecasting Production Hardening

## 1. Executive summary

Phase 5 resolves all four remaining open items from Phase 4:

- **Actual/ERP semantics** documented with live-copy evidence; actuals gate now distinguishes seven explicit bases.
- **Custom/dynamic budget columns** cataloged, classified, and gated — unknown numerics cannot silently enter the model.
- **Projection parity** expanded to prime contracts, change events, and subcontractor invoices; RFQ pair documented as unsupported scope subset.
- **GitHub Actions** workflow and local CI script added for forecasting semantic gates.

All CI-safe tests pass. Ruff clean on forecasting scope. Phase 5 evidence bundle is no-raw safe.

## 2. Branch / HEAD / dirty status

| Field | Value |
|-------|-------|
| Branch | `feature/forecasting-db-audit-20260621` |
| HEAD | `86f31c6206ecac54f941534c517dbb2b6a18c47c` (+ Phase 5 uncommitted changes) |
| Phase 4 | Committed and merged to main (`c313e904`) |
| Dirty | Phase 5 files only for commit; exclude 08c side-effects and tgz archives |

## 3. Files changed

**Code**

- `src/hb_assistant/forecasting/gates.py` — actuals basis gate, dynamic columns gate, parity expansion
- `src/hb_assistant/forecasting/budget_column_roles.py` — label mapping, dynamic catalog loader
- `src/hb_assistant/forecasting/__init__.py` — export dynamic columns gate

**Scripts**

- `scripts/audit_actual_erp_semantics.py`
- `scripts/audit_budget_dynamic_columns.py`
- `scripts/ci_forecasting_semantic_gates.sh`

**CI**

- `.github/workflows/forecasting-semantic-gates.yml`

**Semantic catalog**

- `actuals_precedence_model.yml` (v2)
- `budget_dynamic_columns.yml` (new)
- `procore_budget_semantics.yml`, `procore_invoice_semantics.yml`
- `validation_queries/actuals_reconciliation.sql`, `projection_parity.sql`, `budget_dynamic_columns.sql`
- `README.md`, `forecast-gates-ci-readiness.md`

**Tests**

- `tests/test_forecasting_gates.py` — actuals, dynamic columns, parity expansion tests
- `tests/test_forecasting_readiness.py`, `tests/test_forecasting_semantic_catalog.py`

**Evidence**

- `docs/evidence/forecasting-db-audit-20260621/phase5/` (full bundle)
- Audit markdown + JSON artifacts

## 4. Actual/ERP semantics findings

- `actual_cost`: 0% populated on live copy — **unresolved** Procore mapping; use `job_to_date_costs` as primary cumulative actual.
- `job_to_date_costs`: 1566 populated — proven Procore rollup (Direct Costs + Subcontractor Invoices).
- ERP sidecar (`erp_job_to_date_costs`): 956 populated — compare only; gate warns on material aggregate variance, never hard-fails on null ERP.
- Invoice detail (51k rows) and monthly actuals (1k rows) reconciled separately from cumulative rollups.
- `payment_date`: unpopulated on live copy — cash-flow basis documented but sparse.

## 5. Custom/dynamic budget column findings

- Six budget views profiled; standard Procore labels map to `budget_column_roles.yml`.
- Unmapped `source` columns (Change Events, Commitments, Prime, Requisitions) classified `review_required`.
- `forecast_budget_dynamic_columns` gate warns on unmapped numeric cells.

## 6. Projection parity expansion results

| Family | Live-copy parity |
|--------|------------------|
| prime | 7/7 match |
| change_event | 1059/1059 match |
| subcontractor_invoice | 1002/1002 match |
| rfq | 12 vs 291 — **unsupported_ep_scope_subset** (info) |

## 7. CI workflow result

- `.github/workflows/forecasting-semantic-gates.yml` created
- `scripts/ci_forecasting_semantic_gates.sh` passes locally
- No live DB, Procore, or SchemaCrawler required

## 8. Tests and lint

| Check | Result |
|-------|--------|
| CI test suite | 88 passed |
| Ruff (forecasting scope) | All checks passed |

## 9. No-raw scan

`phase5/98-no-raw-leak-scan.json`: **ok=true**, unsafe_finding_count=0

## 10. Remaining unresolved issues

1. `actual_cost` Procore formula / column mapping (zero population blocks proof)
2. RFQ EP vs financial scope alignment (291 financial vs 12 EP)
3. `payment_date` population sparse — cash-flow modeling limited
4. Monthly actuals cover one project only on live copy
5. Prime change-order line item parity (no enriched pair confirmed yet)

## 11. PR readiness assessment

**Ready for PR** with Phase 5 files staged selectively:

- Include: code, tests, semantic catalog, Phase 5 evidence, CI workflow, audit scripts
- Exclude: 08c modified JSON, untracked tgz bundles, live-copy.sqlite

## 12. Recommended next phase

Phase 6 candidates:

1. RFQ projection scope investigation and parity enablement
2. `actual_cost` population proof when budget view config exposes column
3. Prime change-order / line-item parity pairs
4. Wire `forecast_budget_dynamic_columns` into readiness gate #9 summary in 08c proof JSON
5. Operator live-copy re-run with expanded parity families