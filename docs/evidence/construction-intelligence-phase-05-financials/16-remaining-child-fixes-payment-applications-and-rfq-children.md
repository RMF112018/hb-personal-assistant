# Phase 05 — payment-applications flat path + rfq-children contract_id; promote 3 (56 verified)

> Operator supplied the real Procore request/response shapes for the remaining held
> endpoints; two are faithfully fixable, one re-held with observed status, two unchanged.

## Root causes (from operator-supplied shapes)

- **payment-applications** — registered as a child of prime-contracts
  (`/rest/v1.0/prime_contracts/{prime_contract_id}/payment_applications`) but never in
  `_N1_CHILD_ENDPOINTS`, so the `{prime_contract_id}` token was never substituted → 404. The
  supplied request is a **flat list** `GET /rest/v1.0/payment_applications?project_id=…` whose
  records carry `g702{…}`, `contract{id,type,title}`, `period_id`, `total_amount_paid`, etc. —
  matching the existing owner normalizer/projection.
- **rfq-responses / rfq-quotes** — `GET /rest/v1.0/rfqs/{rfq_id}/responses?project_id=…&contract_id=…`:
  they require a **`contract_id`** query param (= the rfq's `commitment_contract_id`) in addition
  to project_id; the N+1 child GET wasn't sending it → 404 "Contract not found". The supplied
  shapes match the existing normalizers/projections (comment/description hashed, `cost`/
  `schedule_impact` amounts, created_by hashed, attachment URLs path-only, edges response_of/
  quote_of → rfq).

## Fixes

- `endpoints.py`: payment-applications → flat parentless endpoint
  (`path_template="/rest/v1.0/payment_applications"`, `parent_path_template=None`,
  `parent_record_id_field=None`, `required_path_params=()`); the orchestrator adds `project_id`
  as a query param (path lacks `{project_id}`).
- `live_sync.py`: `_N1_CHILD_EXTRA_PARENT_PARAMS` map adds an extra parent-sourced query param to
  the N+1 child GET — `rfq-responses`/`rfq-quotes` → `contract_id` from the parent rfq's
  `commitment_contract_id` (omitted when the rfq has no commitment id; per-parent error
  isolation already handles a residual 404).

## Re-probe (after fixes, `--max-items 5`)

| Endpoint | result |
|---|---|
| payment-applications | ✅ success, 0 records (pilot has none — valid empty; no 404; g702/contract projection unit-tested) |
| rfq-responses | ✅ success, 0 records (sampled rfqs have none; 404 gone) |
| rfq-quotes | ✅ success, 0 records (sampled rfqs have none; 404 gone) |
| purchase-order-detail-line-items | 🔒 still 404 for all sampled POs (the `/line_item_contract_details` sub-resource 404s while the `/line_items` sibling succeeds — the sampled POs have no contract-detail items; held, revisit when a PO with details exists) |

## Promotion + cadence

`endpoints.py`: **3** promoted (`live_verified=True`) — payment-applications, rfq-responses,
rfq-quotes. Registry posture **53 → 56 live-verified / 3 fail-closed / 59 total**. Full live
cadence (smoke → sync → idempotent re-run): all `success`, `projection_error_count=0`,
byte-stable (0/0 — valid empty for the pilot). No-secret probe over the 2,209 real financial
rows: zero Bearer/PEM/`sig=`/email/URL findings; guards intact (the rfq attachment signed URLs
never persist — reduced to path-only / dropped by the offline test's assertion too).

## Tests / verification

- `tests/test_procore_live_sync_n1_children.py`: `test_rfq_quote_child_get_carries_project_id_and_contract_id`
  (asserts the child GET sends `project_id` + `contract_id`=701973 from the parent rfq, emits the
  `cost` amount fact + `quote_of` edge, and never persists the `?sig=` attachment URL).
- `tests/test_procore_endpoint_registry.py`: `_PHASE05_PROMOTED` → 29; payment-applications is now
  parentless (parent/child consistency test still passes).
- `tests/test_procore_live_gate.py`: endpoints-list counts 53/6 → **56/3**.
- `ruff check .` + `mypy src` clean (115 files); `pytest -m "not integration and not live and not
  manual"` → **1244 passed, 1 skipped, 1 deselected** (+1 new test).

## Residual fail-closed (3)

- **purchase-order-detail-line-items** — `/line_item_contract_details` 404s for the sampled POs
  (no contract-detail items); held, will resolve when a PO with details is present.
- **budget-change-line-items** — **403 FORBIDDEN**: requires a Procore permission grant (not a
  code fix).
- **budget-details** — permanent non-routable sentinel (no resolved REST path).
