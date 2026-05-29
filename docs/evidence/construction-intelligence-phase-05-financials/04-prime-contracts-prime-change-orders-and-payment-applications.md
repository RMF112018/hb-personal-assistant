# Phase 05 Prompt 04 — Prime Contracts, Prime Change Orders & Payment Applications

> **Scope:** owner-side family — normalizers + financial projections + amount facts + edges +
> signals for the 6 owner endpoints, wired into live_sync. **No live GETs**; the endpoints stay
> `live_verified=False` (fail-closed) until an operator runs a bounded smoke. Companion:
> [`03-shared-financial-normalizers-and-redaction-utilities.md`](./03-shared-financial-normalizers-and-redaction-utilities.md).

## 1. New modules

### `src/hb_assistant/procore/normalizers/owner_contract.py` (ruff-checked)
`NORMALIZATION_SCHEMA_VERSION = 1`. Six normalizers (standard canonical-dict shape) reusing the
Prompt 03 toolkit: `normalize_prime_contract`, `normalize_prime_contract_line_item`,
`normalize_prime_contract_attachment`, `normalize_prime_change_order`,
`normalize_prime_change_order_line_item`, `normalize_payment_application`.
- Amounts/quantities/rates kept verbatim (`parse_amount`, decimal-safe).
- Free text (title/description/inclusions/exclusions/review_notes) → **hash-only** summary via
  `hash_summary` (no excerpt — high-sensitivity financial text).
- Parties → `person_hash_summary` (`*_ref` = `{hash_prefix, id}`); attachment URLs → path-only.
- Payment-application financial amounts read from the nested `g702` AIA-form object.

### `src/hb_assistant/store/procore_owner_projection.py` (store layer)
`project_owner_contract_family(endpoint_id, raw, *, project_key, sync_run_id=None, now_utc,
db_path=None, parent_procore_id=None)` dispatches each endpoint to the Prompt 02 repo upserts +
`emit_amount_facts` + `link_record_entities` + `emit_action_signal` + `extract_attachment_refs`.
Financial-table rows carry **structured facts only** (amounts/codes/status/dates) — no free text.

Shared store-layer helpers added to `procore_financial_projection.py` for reuse by later
families: `record_key`, `coerce_amount` (decimal-safe; never lossy float), `is_positive_amount`
(Decimal compare for `>0` signal gates — comparison only), `bool_to_int`.

## 2. Projection mapping

| Endpoint | Table | Amount facts | Edges | Signals |
|---|---|---|---|---|
| prime-contracts | `procore_financial_contracts` (family `owner`) | grand_total, original/revised sum, approved COs, retainage_percent | architect/created_by (people), contractor/vendor (companies), attachments | `prime_contract_unexecuted`, `prime_contract_private` |
| prime-contract-line-items | `procore_financial_line_items` (kind `prime_contract`) | amount | parent = contract record_key | — |
| prime-contract-attachments | `procore_attachment_refs` (path-only) | — | contract→attachment | — |
| prime-change-orders | `procore_financial_change_orders` (family `prime`) | grand_total, schedule_impact | created_by/received_from/reviewers, `change_order_of`→contract | `prime_change_order_unexecuted`/`_unpaid`/`_schedule_impact` |
| prime-change-order-line-items | `procore_financial_change_order_line_items` | amount | parent = CO record_key | — |
| payment-applications | `procore_financial_payment_applications` (amounts from `g702`) | current_payment_due, total_retainage, balance_to_finish, total_amount_paid | `payment_application_of`→contract | `payment_application_pending_or_unpaid`, `payment_application_retainage_held` |

Signal gates: unexecuted = `executed` falsy (CO also requires `signature_required`); unpaid =
`paid` falsy AND (`invoiced_date` present OR status approved/executed); schedule-impact /
retainage-held = positive amount; payment pending = status not paid/closed.

## 3. Live-sync wiring (fail-closed until promotion)

The 6 normalizers are registered in `_NORMALIZER_BY_ID` and a guard block calls
`project_owner_contract_family` for `OWNER_ENDPOINTS`. Because the registry keeps all 6
`live_verified=False`, the orchestrator returns `not_live_verified` with
`no_live_call_performed=True` **before** the normalizer lookup — proven by
`tests/test_procore_live_gate.py::test_live_sync_phase05_financial_endpoint_fails_closed_without_transport`
(a real `prime-contracts` sync attempt with a transport that raises if hit — it is never hit).
The N+1 per-parent *fetch* orchestration + live promotion are Prompt 10.

## 4. Tests

- `tests/test_procore_owner_contract_normalizers.py` (6): amounts preserved (negative +
  high-precision decimals byte-for-byte); free text hash-only (no raw description/notes/`<html>`);
  attachment URL query stripped (`?sig=…&token=…` → path); no person name/email in output; g702
  amounts read.
- `tests/test_procore_owner_projection.py` (5): rows in all financial tables; amount facts
  (retainage/balance/payment_due) queryable via `read_financial_amount_facts`; edges
  (architect/contractor/change_order_of/payment_application_of); company label preserved + person
  PII hashed; attachment path-only (no signed query); the 7 signals under the right conditions;
  idempotent (re-project → 1 row); line items linked to parent record_key.
- `tests/test_procore_endpoint_registry.py`: fail-closed test updated to the durable invariant
  (all 32 `live_verified=False`; `resolve_normalizer is None` only for not-yet-implemented ids);
  new `test_phase05_owner_endpoints_have_normalizers`.

## 5. Verification run

- `ruff check .` clean; `mypy src` → no issues in 110 source files.
- `pytest -m "not integration and not live and not manual"` → **1153 passed, 1 skipped,
  1 deselected** (was 1141; +12 new tests).

## 6. Acceptance criteria status

| Criterion | Status |
|---|---|
| Owner contract endpoints normalize and project safely | ✅ 6 normalizers + projection dispatcher, unit-tested |
| Parent/child relationships persisted as edges | ✅ architect/contractor/vendor/created_by + change_order_of/payment_application_of + attachment refs |
| Payment applications and retainage facts queryable | ✅ amount facts (current_payment_due/total_retainage/balance_to_finish) via `read_financial_amount_facts` |
| Tests cover no raw descriptions, no URL query strings, amount precision | ✅ hash-only free text, path-only URLs, decimal byte-for-byte tests |
