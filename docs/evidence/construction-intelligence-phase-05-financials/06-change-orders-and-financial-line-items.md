# Phase 05 Prompt 06 — Change Orders and Financial Line Items

> **Scope:** vendor-side change orders (`commitment-change-orders`,
> `commitment-change-order-line-items`) — normalizers + projections + amount facts + edges +
> signals, plus shared line-item hardening (change-event linkage across prime / commitment /
> change-order line items). **No live GETs**; both endpoints stay `live_verified=False`
> (fail-closed) until operator smoke. Companions:
> [`04-…payment-applications.md`](./04-prime-contracts-prime-change-orders-and-payment-applications.md),
> [`05-…compliance.md`](./05-commitments-purchase-orders-attachments-and-compliance.md).

## 1. What changed (additive — no migration / repository / registry-row changes)

V8 already carries `procore_financial_change_orders` +
`procore_financial_change_order_line_items` and the
`upsert_financial_change_order` / `upsert_financial_change_order_line_item`
repository functions (Prompt 02), and both endpoint adapters are already registered
(Prompt 01). Prompt 06 only adds normalizers, projections, two shared helpers, and
the live_sync wiring.

### `src/hb_assistant/procore/normalizers/commitment_contract.py` (ruff-checked)
- **`normalize_commitment_change_order`** — amounts `grand_total` +
  `schedule_impact_amount` verbatim (decimal-safe); scalars `number`, `contract_id`,
  `status`, `executed`, `paid`, `private`, `field_change`, `signature_required`,
  `type`, `revision`, `billing_schedule_of_values_status`, dates; currency config;
  `title` / `description` / `review_notes` **hash-only**; parties (`created_by`,
  `received_from`, `designated_reviewer`, `reviewed_by`) hashed.
- **`normalize_commitment_change_order_line_item`** — reuses the shared
  `_line_item_canonical`.

### `src/hb_assistant/procore/normalizers/financial.py` — shared line-item hardening
- **`change_event_line_item_summary(raw)`** — redacts the `change_event_line_item`
  block once for **all** line-item normalizers: keeps ids
  (`change_event_line_item_id`, `change_event_id`, `change_event_number`) and WBS /
  cost-code metadata; the change-event **title** and the line-item **description**
  are free text → **hash-only**. Returns `None` when no linkage is present. Both
  `_line_item_canonical` functions (owner + commitment) now call it (and keep
  `commitment_line_item_id` / `prime_line_item_id` cross-references).

### `src/hb_assistant/store/procore_commitment_projection.py` (store layer)
`project_commitment_family` gains two routes; `COMMITMENT_ENDPOINTS` gains the two ids.

| Endpoint | Table | Notes |
|---|---|---|
| commitment-change-orders | `procore_financial_change_orders` (family `commitment`) | facts `grand_total` + `schedule_impact_amount`; `change_order_of` edge to parent commitment (`contract_id`); parties hashed; signals below |
| commitment-change-order-line-items | `procore_financial_change_order_line_items` (family `commitment`) | `amount` fact (precision preserved); WBS kept; `change_event_line_item` edge to source change event |

Signals (mirror the owner prime-CO set):
- `commitment_change_order_unexecuted` — not executed **and** `signature_required`.
- `commitment_change_order_unpaid` — not paid **and** (`invoiced_date` present or status billable).
- `commitment_change_order_schedule_impact` — positive `schedule_impact_amount`.

### `src/hb_assistant/store/procore_financial_projection.py` — shared edge primitive
- **`emit_change_event_edge(...)`** — emits a `change_event_line_item` record edge
  from a CO line item to the change-event record key
  `record_key(project_key, "change-events", None, event_id)`. No-op when the linkage
  block / event id is absent. The change-events endpoint lands in Prompt 08, so this
  is a **forward reference** (same pattern as the existing `change_order_of` edge).
  Wired into both the new commitment-CO line items and the existing owner prime-CO
  line items (`store/procore_owner_projection.py`).

## 2. Required-logic mapping (from the prompt)

| Required logic | Where |
|---|---|
| Link change orders to parent contracts by `contract_id` | `change_order_of` edge + `contract_record_key` column |
| Link CO line items to change-event line items where available | `emit_change_event_edge` → `change_event_line_item` edge |
| Preserve WBS / cost-code metadata | `_wbs(...)` (projection) + `extract_wbs_cost_code` (normalizer) |
| Preserve schedule impact and grand total | amount facts `grand_total`, `schedule_impact_amount` |
| Emit amount facts for pending/approved/paid/unpaid amounts | CO grand_total/schedule + line-item amount facts |

## 3. Live-sync wiring

The two normalizers are registered in `_NORMALIZER_BY_ID`; the existing
`COMMITMENT_ENDPOINTS` guard block now dispatches both ids to
`project_commitment_family`. Both stay `live_verified=False` — the orchestrator
fail-closes before the normalizer lookup (no transport) until promotion. CLI
`procore live endpoints list --json` → **total 59, verified 27, unverified 32**
(unchanged).

## 4. Tests

- `tests/test_procore_commitment_normalizers.py` (+2): CCO amounts preserved
  (negative/high-precision) + dates kept + parties hashed + title/description/notes
  not raw; CCO line-item `change_event_line_item` redacted (ids + WBS kept;
  change-event title, CE description, line description hash-only) + amount precision.
- `tests/test_procore_commitment_projection.py` (+4): CCO row + facts
  (`grand_total`, `schedule_impact_amount`) + `change_order_of` edge + the 3 signals;
  **CCO line item with `change_event_line_item` emits the `change_event_line_item`
  edge to the change event** + amount precision preserved; no edge when linkage
  absent; executed+paid CCO emits no signal.
- `tests/test_procore_endpoint_registry.py`: both ids added to
  `_COMMITMENT_IMPLEMENTED` (fail-closed invariant + have-normalizers tests cover
  them automatically).

## 5. Verification run

- `ruff check .` clean; `ruff format --check` clean on edited source files;
  `mypy src` → no issues in 111 source files.
- `pytest -m "not integration and not live and not manual"` → **1171 passed,
  1 skipped, 1 deselected** (was 1165; +6 new tests).
- Targeted: normalizers / projection / owner-projection / registry / live-gate → all pass.

## 6. Acceptance criteria status

| Criterion | Status |
|---|---|
| Commitment change orders and line items are projected | ✅ two projections + tables, unit-tested |
| Shared line-item projection works for all line-item response shapes | ✅ shared `change_event_line_item_summary` + `emit_change_event_edge`; reused by prime / commitment / CO line items |
| Change-event linkage is represented by edges | ✅ `change_event_line_item` edge, tested (present + absent) |
| CCO line item with `change_event_line_item` emits edge to change event | ✅ `test_commitment_co_line_item_amount_and_change_event_edge` |
| Schedule-impact CCO emits signal | ✅ `commitment_change_order_schedule_impact` |
| Unexecuted/unpaid CCO emits signal | ✅ `commitment_change_order_unexecuted` / `_unpaid` |
| Line-item amount precision preserved | ✅ `0.000000000001` byte-for-byte (normalizer + projection) |
| No live GETs; fail-closed posture preserved | ✅ both `live_verified=False`; 59/27/32 unchanged |
