# Forecasting Semantic Catalog

Repo-owned semantic layer design artifacts for forecasting DB evidence and future model implementation.

## Authority

- **Primary evidence:** `docs/evidence/forecasting-db-complete-evidence-*/`
- **Code truth:** `src/hb_assistant/procore/`, `src/hb_assistant/store/`, `src/hb_assistant/construction/analytics/`
- **Field classifiers:** `src/hb_assistant/forecasting/field_classifiers.py`

## Relationship confidence levels

| Level | Meaning |
|-------|---------|
| `high` | Schema + row-profile + repo-code alignment |
| `medium` | Row-profile supported; business semantics partially proven |
| `low` | Schema or naming only; needs validation |
| `unresolved` | Conflicting or insufficient evidence |

## Evidence basis tags

`schema-supported`, `row-profile-supported`, `repo-code-supported`, `Procore-doc-supported`, `inferred`, `unresolved`

## Catalog files

| File | Domain |
|------|--------|
| `semantic_catalog.yml` | Top-level entity index |
| `procore_budget_semantics.yml` | Budget detail, cells, changes |
| `procore_commitment_semantics.yml` | Commitments, CCOs |
| `procore_purchase_order_semantics.yml` | PO contracts, polymorphic holders |
| `procore_prime_contract_semantics.yml` | Prime contracts, PCOs |
| `procore_change_event_semantics.yml` | Change events, RFQs |
| `procore_invoice_semantics.yml` | Subcontractor invoices, billing periods |
| `forecast_internal_semantics.yml` | Internal/external forecast tables |
| `normalization_rules.yml` | Amount/date/boolean/status rules |
| `double_count_prevention_model.yml` | Exposure lifecycle precedence |
| `actuals_precedence_model.yml` | Actuals source hierarchy |

## Runnable gates

Read-only SQLite gates (JSON output):

```bash
hb-assistant construction-agent forecast double-count-gate --db-path /path/to/db.sqlite --json
hb-assistant construction-agent forecast actuals-reconciliation-gate --db-path /path/to/db.sqlite --json
hb-assistant construction-agent forecast gates --db-path /path/to/db.sqlite --json
```

### Double-count gate (`forecast_double_count_prevention`)

**Checks:** change-event + RFQ overlap; change-event + approved CCO coexistence; budget actual + invoice detail coexistence; budget modification + change-event coexistence.

**Does not yet check:** prime change-order vs budget rollup column inclusion; per-line-item amount equality proofs.

**Severity:** `info` = coexistence only; `warning` = likely double-count if summed; `error` = only in `--mode strict` for warnings.

### Actuals reconciliation gate (`forecast_actuals_reconciliation`)

**Checks:** cumulative budget actual vs monthly actuals; Procore vs ERP job-to-date; invoice detail exceeding budget cumulative.

**Thresholds:** `--absolute-threshold` (default `100.00`), `--percent-threshold` (default `0.005`).

**Does not:** add all actual fields together; treat ERP as interchangeable with Procore without explicit sidecar tagging.

## Validation SQL

Run SQL under `validation_queries/` against the local SQLite DB (read-only). Never export raw payload bodies.

| Query | Purpose |
|-------|---------|
| `double_count_prevention.sql` | Workflow-stage overlap |
| `actuals_reconciliation.sql` | Cumulative vs periodized vs ERP |
| `purchase_order_relationships.sql` | PO polymorphic holder classification |
| `projection_parity.sql` | `procore_ep_*` vs `procore_financial_*` counts |
| `cost_type_mapping_guard.sql` | Cost-type null rate; category ≠ cost_type |