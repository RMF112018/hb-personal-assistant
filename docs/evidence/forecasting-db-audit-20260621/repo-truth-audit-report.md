# Forecasting DB Repo-Truth Audit Report

**Worktree:** `feature/forecasting-db-audit-20260621` (from `origin/main`)  
**Date:** 2026-06-21

## Files inspected (representative)

### Procore projection
- `src/hb_assistant/procore/projection_registry.json`
- `src/hb_assistant/procore/projection_engine.py`
- `src/hb_assistant/procore/structured_analytics.py`
- `src/hb_assistant/procore/budget_detail_read_model.py`
- `src/hb_assistant/procore/live_sync.py`

### Financial enrichment (V8/V9)
- `src/hb_assistant/store/procore_commitment_projection.py`
- `src/hb_assistant/store/procore_owner_projection.py`
- `src/hb_assistant/store/procore_invoice_projection.py`
- `src/hb_assistant/store/procore_rfq_change_event_projection.py`
- `src/hb_assistant/store/procore_budget_projection.py`

### Forecast / external eval
- `src/hb_assistant/construction/analytics/forecast_external_ingest.py`
- `src/hb_assistant/construction/analytics/forecast_external_eval_service.py`
- `src/hb_assistant/construction/analytics/forecast_external_compare.py`
- `src/hb_assistant/construction/forecast/source_domain_engine.py`

### Schema / gates
- `src/hb_assistant/store/migrator.py` (V47/V55/V58/V61)
- `src/hb_assistant/construction/second_brain/financial_completeness.py`
- `src/hb_assistant/procore/normalizers/financial.py`

### Evidence (DB)
- Full `docs/evidence/forecasting-db-complete-evidence/20260621T114232Z/` bundle (26 files)

## Table projection ownership

| Family | `procore_ep_*` owner | V8/V9 enrichment owner |
|--------|---------------------|------------------------|
| Budget detail | `budget_detail_read_model.py` | `procore_budget_projection.py` |
| Commitments | `projection_engine.py` | `procore_commitment_projection.py` |
| Purchase orders | `projection_engine.py` | `procore_commitment_projection.py` (PO compat) |
| Prime contracts | `projection_engine.py` | `procore_owner_projection.py` |
| Change events / RFQs | `projection_engine.py` | `procore_rfq_change_event_projection.py` |
| Invoices / billing | `projection_engine.py` | `procore_invoice_projection.py` |
| External forecasts | `migrator.py` V61 DDL | `forecast_external_eval_service.py` (eval.sqlite only) |

## Evidence generation ownership

| Artifact | Owner |
|----------|-------|
| Forecasting DB complete evidence | `scripts/generate_forecasting_db_complete_evidence.sh` (promoted from `tmp/`) |
| No-raw-leak scan | `structured_analytics.no_raw_leak_scan()` via CLI |
| External eval packages | `ForecastExternalEvalService._write_package()` |
| Comprehensive forecast packages | CFR `generate_comprehensive_forecast_package.py` |

## Current semantic assumptions in code

1. Dual-layer projection (`procore_ep_*` + `procore_financial_*`)
2. Amounts as decimal-safe TEXT; `classify_amount()` with 7 parse statuses
3. PO dedup when same `contract_id` exists in commitments
4. External eval V61 tables intentionally empty on live DB
5. Budget detail uses custom read model, not generic V47 engine

## Unresolved semantic gaps

1. No centralized `classify_date()` (addressed by new `field_classifiers.py`)
2. `category` / `category_id` ≠ `cost_type` / `cost_type_id` (preserved uncertainty)
3. Dual projection drift between `procore_ep_*` and `procore_financial_*`
4. External eval hardcoded to `tropical` project
5. Budget calculated columns vs workflow-stage amounts double-count risk (documented, not fully gated)