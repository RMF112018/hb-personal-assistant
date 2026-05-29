# Phase 05 Prompt 07 — Billing Periods, Subcontractor Invoices & Invoice Items

> **Scope:** the subcontractor billing surface — `billing-periods`,
> `subcontractor-invoices` (requisitions), and the three invoice item families
> (`-contract-items`, `-contract-detail-items`, `-change-order-items`). Adds
> **migration V9** (billing-period + invoice-header tables); invoice items reuse the
> V8 `procore_financial_invoice_items` table. **No live GETs**; all 5 endpoints stay
> `live_verified=False` (fail-closed) until operator smoke. Companions:
> [`05-…compliance.md`](./05-commitments-purchase-orders-attachments-and-compliance.md),
> [`06-…line-items.md`](./06-change-orders-and-financial-line-items.md).

## 1. Migration V9 (additive + idempotent)

`store/migrator.py` `V9_STATEMENTS` + a V9 apply block — `apply()` now returns **9**.
Two new tables (both with `raw_body_persisted CHECK(=0)` + `redaction_applied CHECK(=1)`):

- **`procore_financial_billing_periods`** — period anchors: `billing_period_key` PK,
  `billing_period_id`, `status`, `start_date`, `end_date`, `due_date`, `position`,
  `updated_at_utc`. Index `(project_key, status)`.
- **`procore_financial_subcontractor_invoices`** — requisition headers: `record_key`
  PK, `invoice_id`, `commitment_record_key`/`commitment_id`,
  `billing_period_key`/`billing_period_id`, `previous_invoice_id`, `vendor_id`,
  `vendor_entity_key`, `invoice_number`, `number`, `invoice_type`, `status`, `final`,
  `billing_date`, `period_start`/`period_end`, `percent_complete`, `payment_date`,
  `submitted_at`, `erp_status`, and the AIA summary amounts (`current_payment_due`,
  `total_claimed_amount`, `original_contract_sum`, `contract_sum_to_date`,
  `total_completed_and_stored_to_date`, `total_retainage`,
  `total_earned_less_retainage`, `balance_to_finish_including_retainage`). Index
  `(project_key, status, billing_period_id, vendor_id)`.

Invoice **items reuse the existing V8 `procore_financial_invoice_items`** table — it
already carries scheduled value, this-period work, stored materials, total-to-date,
retainage, claimed amount, status, cost code, WBS flat code — keyed by `item_type`
and `endpoint_id`. No third items table is added.

Smoke: `apply()==9`, idempotent re-apply, both V9 tables + indexes present, V1–V8
intact (tested in `tests/test_procore_financials_v9.py`).

## 2. Normalizers — `procore/normalizers/subcontractor_invoice.py`

`normalize_billing_period`, `normalize_subcontractor_invoice`, and three thin item
normalizers over a shared `_invoice_item_canonical`. Posture: amounts/quantities/rates
verbatim (decimal-safe `parse_amount`); item `description_of_work`/`comment`
hash-only; creator hashed; vendor / contract names kept (organisation labels). **The
`summary_text` AIA cover block (subcontractor street/city/state/zip/name, GC text) is
never carried** — address/contact content does not persist.

## 3. Projection — `store/procore_invoice_projection.py`

`project_invoice_family(endpoint_id, raw, ...)` + `INVOICE_ENDPOINTS`.

| Endpoint | Table | Notes |
|---|---|---|
| billing-periods | `procore_financial_billing_periods` | period anchor; signals `billing_period_open`, `billing_period_due_soon` |
| subcontractor-invoices | `procore_financial_subcontractor_invoices` | edges + amount facts + 5 header signals (below) |
| -contract-items / -contract-detail-items / -change-order-items | `procore_financial_invoice_items` | shared item projection; amount facts w/ WBS+cost; `invoice_materials_stored` |

- **Edges:** invoice → commitment (`invoice_of`), → billing period (`billed_in_period`),
  → previous invoice (`supersedes`); vendor company + creator person via
  `link_record_entities` (vendor label preserved, creator hashed).
- **Amount facts:** header facts (`current_payment_due`, `total_retainage`,
  `total_completed_and_stored_to_date`, `total_claimed_amount`, `contract_sum_to_date`)
  carry the requisition `period_start`/`period_end` → period + commitment aggregation;
  item facts (`scheduled_value`, `work_completed_this_period`,
  `materials_presently_stored`, `total_completed_and_stored_to_date`,
  `subcontractor_claimed_amount`, `retainage_held`) carry `wbs_code_id`+`cost_code_id`.
- **Signals:** `invoice_pending_approval` (status in draft/under-review/submitted set),
  `invoice_approved_not_paid` (approved + no payment), `invoice_final` (`final` true),
  `invoice_retainage_held` (`total_retainage > 0`), `invoice_payment_due`
  (`current_payment_due > 0`); `invoice_materials_stored` from a child item with
  `materials_presently_stored > 0` (anchored on the parent invoice record key);
  `billing_period_open` / `billing_period_due_soon` (≤ 7 days, non-closed).
- `retainage_held` ← `work_completed_retainage_retained_this_period` (documented
  mapping; provisional pending live smoke).

## 4. Read views (query support)

`read_financial_billing_periods(project_key)` and
`read_financial_subcontractor_invoices(project_key, status=?, billing_period_id=?, vendor_id=?)`
— optional filters combine with AND, matched verbatim as TEXT.

## 5. Live-sync wiring

5 normalizers registered in `_NORMALIZER_BY_ID`; a guarded `INVOICE_ENDPOINTS` block
calls `project_invoice_family` (after the commitment block). All 5 stay
`live_verified=False`, so the orchestrator fail-closes before the normalizer lookup
(no transport) until promotion.

## 6. Tests

- `tests/test_procore_financials_v9.py` (4): V9 applies/idempotent/V1–V8 intact; CHECK guards reject raw persistence.
- `tests/test_procore_subcontractor_invoice_normalizers.py` (3): billing-period fields; invoice amounts preserved + `summary_text` excluded + creator hashed + vendor label kept; item amounts/precision + description hash-only.
- `tests/test_procore_invoice_projection.py` (8): billing-period rows + signals; invoice rows + facts (w/ period) + edges (invoice_of/billed_in_period/supersedes) + the header signals; child-item rows + facts (WBS/cost) + `invoice_materials_stored`; **query filters by status / billing_period_id / vendor_id (+ combined)**; raw-body guard; idempotency.
- `tests/test_procore_endpoint_registry.py`: `_INVOICE_IMPLEMENTED` added + OR'd into `_IMPLEMENTED`; new `test_phase05_invoice_endpoints_have_normalizers`.
- Migration-version asserts bumped 8→9 in `tests/test_procore_financials_v8.py`, `test_procore_history_migration_v7.py`, `test_construction_store_repositories.py` (latest-version asserts only; the `WHERE version = 8` idempotency check is unchanged).

## 7. Verification run

- `ruff check .` clean; `ruff format` clean on edited source; `mypy src` → no issues in 112 source files.
- `pytest -m "not integration and not live and not manual"` → **1186 passed, 1 skipped, 1 deselected** (was 1171; +15 new tests).
- Migration smoke: `apply()==9`, idempotent, V9 tables + indexes present, V1–V8 intact.
- Fail-closed unchanged: `procore live endpoints list --json` → 27 verified / 32 unverified / 59 total.

## 8. Acceptance criteria status

| Criterion | Status |
|---|---|
| Billing and invoice endpoints project safely | ✅ V9 tables + 5 normalizers/projections, fail-closed, unit-tested |
| Invoice amount facts support period and commitment aggregation | ✅ header facts carry `period_start`/`period_end`; commitment via `invoice_of` edge + `commitment_id` column |
| Address/contact fields are redacted or excluded | ✅ `summary_text` excluded entirely; item free text hash-only; creator hashed |
| Query tests prove invoices can be filtered by status/period/vendor | ✅ `read_financial_subcontractor_invoices` + `test_invoice_query_filters_by_status_period_vendor` |
| Required signals emitted | ✅ all 8 (`invoice_*` + `billing_period_*`), each tested |
| No live GETs; fail-closed preserved | ✅ all 5 `live_verified=False`; 59/27/32 unchanged |
