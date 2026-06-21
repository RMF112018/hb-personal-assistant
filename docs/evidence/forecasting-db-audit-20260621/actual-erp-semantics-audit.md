# Actual / ERP Semantics Audit

Evidence JSON: `actual-erp-semantics-evidence.json`  
Live-copy source: `docs/evidence/forecasting-gates-live-copy-20260621T133000Z/live-copy.sqlite` (read-only, gitignored)

## Findings

### Cumulative actual bases

| Basis | Field | Population (3044 rows) | Status |
|-------|-------|--------------------------|--------|
| `budget_actual_cumulative` | `actual_cost` | 0 (100% null) | **Unresolved** — not usable as primary actual on live copy |
| `budget_job_to_date_cumulative` | `job_to_date_costs` | 1566 | **Proven** Procore rollup (Direct Costs + Subcontractor Invoices) |
| `direct_cost_rollup` | `direct_costs` | 522 | Workflow-stage component; included in JTD formula |
| `erp_actual_sidecar` | `erp_job_to_date_costs` | 956 | ERP sidecar; compare only, never substitute |
| `erp_actual_sidecar` | `erp_direct_costs` | 956 | ERP sidecar; compare only |

### Invoice and periodized actuals

| Basis | Source | Coverage |
|-------|--------|----------|
| `invoice_progress_fact` | Invoice detail items | 51,428 detail rows / 2 projects |
| `invoice_progress_fact` | Subcontractor invoices | 1,002 invoices / 4 projects |
| `monthly_periodized_actual` | `forecast_monthly_actuals_by_budget_code` | 1,081 rows / 1 project / 108 budget codes |
| `payment_cash_flow_fact` | `payment_date` on invoices | 0 populated (timing facts sparse) |

### Reconciliation posture

- **Never add:** budget cumulative + invoice detail progress; Procore JTD + ERP JTD; monthly periodized + cumulative without period join.
- **Primary cumulative actual on live copy:** `job_to_date_costs` when `actual_cost` is null.
- **ERP fields:** populated on ~31% of rows where JTD exists; material per-project variance possible — gate emits **warning**, not hard failure.
- **`actual_cost`:** Procore column mapping unresolved; zero population prevents formula proof on live copy.

### Model training / EAC-ETC guidance

| Use case | Safe source |
|----------|-------------|
| Training period axis | `forecast_monthly_actuals_by_budget_code` |
| Cumulative reconciliation | `job_to_date_costs` (not `actual_cost` on live copy) |
| Progress anomaly compare | Invoice detail `total_completed_and_stored_to_date` vs JTD |
| Cash timing | `payment_date` / `billing_date` (not earned cost) |

## Remaining gaps

1. Prove whether `actual_cost` equals JTD or a distinct Procore column in configured budget views.
2. Confirm ERP integration completeness per project before ERP sidecar warnings become actionable.
3. Expand monthly actual coverage beyond single-project `forecast_monthly_actuals_by_budget_code` population.