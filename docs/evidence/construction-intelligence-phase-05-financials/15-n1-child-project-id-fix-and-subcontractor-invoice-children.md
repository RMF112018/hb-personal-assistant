# Phase 05 — N+1 child `project_id` fix + subcontractor-invoice / v1.0 child promotion (2026-05-29)

> Root-cause fix for the held v1.0 child endpoints, prompted by the operator supplying the
> real Procore request/response shapes for the subcontractor-invoice family.

## Root cause (from the operator-supplied shapes)

The v1.0 child endpoints require **`project_id` as a query param** —
`GET /rest/v1.0/requisitions/{requisition_id}/contract_items?project_id=...` — but the
generalized N+1 child fetch called `client.paginate(child_path, ...)` with **no params**, so
every v1.0 child GET 404'd (the `detail_transport_error` cluster). The main fetch loop
already adds `project_id` when the path lacks `{project_id}`; the N+1 child call was missing
the same logic. v2.0 children embed `/projects/{project_id}/` in the path and so already
worked. The operator-supplied subcontractor-invoice item shapes also confirm the existing
normalizer/projection already match the live contract (item_type, cost_code_id, line_item_id,
wbs_code, scheduled_value, work_completed_this_period, materials_presently_stored,
total_completed_and_stored_to_date, subcontractor_claimed_amount,
work_completed_retainage_retained_this_period → `retainage_held`, description_of_work/comment
hashed) — so the only fix needed was the query param.

## Fix

`live_sync.py` N+1 block: send `project_id` on the child GET when the child `path_template`
lacks `{project_id}`:
`child_params = {"project_id": ...} if "{project_id}" not in adapter.path_template else None`
→ `client.paginate(child_path, params=child_params, ...)`. One-line behavior change; token
substitution / parent-id tagging / per-parent error isolation unchanged.

Offline regression (`tests/test_procore_live_sync_n1_children.py`):
`test_v1_child_get_carries_project_id_query_param` drives `subcontractor-invoice-contract-items`
with a path-aware fake transport that asserts every child GET carries `project_id` and returns
the operator-confirmed item shape; asserts children upsert into
`procore_financial_invoice_items` with the requisition id as `parent_procore_id`,
`retainage_held` from `work_completed_retainage_retained_this_period`, and `raw_body_persisted=0`.
The v2.0 `commitment-line-items` case (no query param — path already scoped) still passes.

## Re-probe (after fix, `--max-items 5`)

| Endpoint | result |
|---|---|
| subcontractor-invoice-contract-items | ✅ success (0 records for sampled requisitions — valid empty; envelope verified, shape unit-tested) |
| subcontractor-invoice-contract-detail-items | ✅ success 5/5, 0 proj err |
| subcontractor-invoice-change-order-items | ✅ success 5/5, 0 proj err |
| purchase-order-line-items | ✅ success 5/5, 0 proj err |
| budget-detail-columns | ✅ success 5/5, 0 proj err |
| budget-detail-rows | ✅ success 5/5, 0 proj err |
| purchase-order-detail-line-items | 🔒 held — child GET still 404 (`/purchase_order_contracts/{id}/line_item_contract_details` path divergence) |
| rfq-responses, rfq-quotes | 🔒 held — child GET 404 even with `project_id` ("Contract not found" — genuinely different path) |
| payment-applications | 🔒 held — 404 (registered flat path wrong; nested under prime contracts) |

## Promotion + cadence

`endpoints.py`: **6** promoted (`live_verified=True`) — the 3 subcontractor-invoice item
endpoints, purchase-order-line-items, budget-detail-columns, budget-detail-rows. Registry
posture **47 → 53 live-verified / 6 fail-closed / 59 total**.

Full live cadence (smoke → sync → idempotent re-run, `--max-items 5`): all `success`,
`retrieved==upserted`, `projection_error_count=0`, byte-stable re-runs (contract-detail-items
5/5, change-order-items 5/5, purchase-order-line-items 5/5, budget-detail-columns 5/5,
budget-detail-rows 5/5; contract-items 0/0 valid-empty).

## No-secret probe

Scan of every `procore_financial_*` row (incl. the new invoice items + budget rows) for
Bearer/PEM/`sig=`/`token=`/`access_token`/URL/email **and** the subcontractor `summary_text`
address fields (street/zip) → **zero findings**; `raw_body_persisted=0` /
`redaction_applied=1` intact. (`summary_text` is never projected by design.)

## Tests / verification

- `tests/test_procore_endpoint_registry.py`: `_PHASE05_PROMOTED` → 26.
- `tests/test_procore_live_gate.py`: endpoints-list counts 47/12 → **53/6**.
- `ruff check .` + `mypy src` clean (115 files); `pytest -m "not integration and not live and
  not manual"` → **1243 passed, 1 skipped, 1 deselected** (+1 new test).

## Residual fail-closed (6)

purchase-order-detail-line-items, rfq-responses, rfq-quotes (child paths 404 vs live API),
payment-applications (404 nested path), budget-change-line-items (403 forbidden), budget-details
(sentinel). Held — observed status documented; correct paths/permissions require Procore
API-doc / operator verification (not guessed).
