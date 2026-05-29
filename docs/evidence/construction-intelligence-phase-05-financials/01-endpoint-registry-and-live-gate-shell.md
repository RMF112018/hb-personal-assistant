# Phase 05 Prompt 01 — Endpoint Registry & Live-Gate Shell

> **Scope:** add the 32 financial endpoints to the canonical Procore registry as
> **fail-closed shells** (`live_verified=False`), visible to catalog/listing but with
> **no transport** until per-endpoint smoke evidence. No normalizers, no schema, no live
> calls. Companion artifacts: [`00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md`](./00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md) ·
> [`phase05-financial-endpoint-inventory.json`](./phase05-financial-endpoint-inventory.json) ·
> [`phase05-financial-normalizer-coverage-baseline.md`](./phase05-financial-normalizer-coverage-baseline.md)

## 1. Registry delta

| | Before | After |
|---|---|---|
| `endpoints.py` rows (`list_all()`) | 27 | **59** |
| `live_verified=True` (`list_verified()`) | 27 | 27 (unchanged) |
| `live_verified=False` | 0 | **32** (all Phase 05 financial) |

Source of truth: `src/hb_assistant/procore/endpoints.py`. The 32 rows are appended after the
27 operational rows. The contract-seed YAML (`procore_endpoint_contract.seed.yaml`, 16 rows)
is a separate source and is **untouched**.

### `EndpointAdapter` change (additive)

One trailing field added: `response_envelope: str = "array"` — records the top-level wrapper
(`array` / `object` / `object.data[]`) per the endpoint matrix. Defaulted, so the 27 pre-05
rows are unchanged (frozen-dataclass defaults must be trailing). Only the 32 financial rows
set it explicitly. `mypy src` clean; no consumer reads it yet, so no behavior change.

## 2. The 32 financial rows (all `live_verified=False`, `sensitivity=high`)

Common values: `legacy_endpoint_alias=None`, `record_id_field="id"`,
`review_required_default=True`, `sqlite_target="procore_live_records"` (placeholder — V8
target is Prompt 02), `pagination="page+per_page"` (except singleton `commitment-compliance`
and the `budget-details` sentinel → `none`),
`verification_reason="phase05_shell_pending_live_smoke"`.

| Group | endpoint_id | parent_endpoint (path) | envelope |
|---|---|---|---|
| Owner contracts | `prime-contracts` | — | array |
| Owner contracts | `prime-contract-line-items` | prime-contracts | object.data[] |
| Owner contracts | `prime-contract-attachments` | prime-contracts | object.data[] |
| Owner contracts | `prime-change-orders` | — | object |
| Owner contracts | `prime-change-order-line-items` | prime-change-orders | object.data[] |
| Owner billing | `payment-applications` | prime-contracts | array |
| Commitments | `commitment-contracts` | — | object.data[] |
| Commitments | `commitment-line-items` | commitment-contracts | object.data[] |
| Commitments | `commitment-attachments` | commitment-contracts | object.data[] |
| Commitments | `commitment-compliance` | commitment-contracts | object |
| Commitments | `commitment-change-orders` | — | object |
| Commitments | `commitment-change-order-line-items` | commitment-change-orders | object.data[] |
| Purchase orders | `purchase-order-contracts` | — | array |
| Purchase orders | `purchase-order-line-items` | purchase-order-contracts | array |
| Purchase orders | `purchase-order-detail-line-items` | purchase-order-contracts | array |
| Invoices | `billing-periods` | — | array |
| Invoices | `subcontractor-invoices` | — | array |
| Invoices | `subcontractor-invoice-contract-items` | subcontractor-invoices | array |
| Invoices | `subcontractor-invoice-contract-detail-items` | subcontractor-invoices | array |
| Invoices | `subcontractor-invoice-change-order-items` | subcontractor-invoices | array |
| RFQs / change events | `rfqs` | — | array |
| RFQs / change events | `rfq-responses` | rfqs | array |
| RFQs / change events | `rfq-quotes` | rfqs | array |
| RFQs / change events | `change-events` | — | object |
| RFQs / change events | `change-event-comments` | change-events | object.data[] |
| Budget | `budget-views` | — | array |
| Budget | `budget-detail-columns` | budget-views | array |
| Budget | `budget-details` | budget-views | array (**sentinel path** — §4) |
| Budget | `budget-detail-rows` | budget-views | array |
| Budget | `budget-change-history` | — | object |
| Budget | `budget-change-line-items` | budget-change-history | object.data[] |
| Budget | `budget-modifications` | — | array |

12 parents + 20 children = 32. `budget-change-line-items` is grouped under
`budget-change-history` but its path carries no parent id token, so
`parent_record_id_field=None` (project-scoped adjustment-line-item list).

## 3. Fail-closed proof (no transport)

Unverified endpoints are catalog-visible but never transport. Verified at three levels:

- **Code:** `live_sync.py` returns `state="not_live_verified"`,
  `no_live_call_performed=True`, `request_count=0`, reason `endpoint_unverified_for_live`
  **before** normalizer lookup; `resolve_normalizer()` returns `None` for all 32 (would also
  fail closed as `normalizer_missing`).
- **CLI (read-only, executed):** `hb-assistant procore live endpoints list --json` →
  `total 59, verified 27, unverified 32`. `hb-assistant procore validate --json` →
  `28/28 passed` (no count regression).
- **Tests:** `tests/test_procore_endpoint_registry.py` —
  `test_phase05_financial_endpoint_count_is_intentional` (59 = 27 + 32),
  `test_phase05_financial_ids_all_resolve`, `test_phase05_financial_endpoints_are_fail_closed`
  (unverified + `resolve_normalizer is None`), `test_phase05_financial_endpoints_excluded_from_verified`,
  `test_budget_details_is_non_routable_sentinel`, `test_phase05_financial_parent_child_consistency`.
  `tests/test_procore_live_gate.py::test_live_sync_phase05_financial_endpoint_fails_closed_without_transport`
  drives a real `prime-contracts` shell through `procore live sync --apply --confirm-live-get`
  with a transport that raises if invoked — it is never invoked; output is the fail-closed receipt.

## 4. `budget-details` sentinel

The source reference has no resolved path (Prompt 00 §3.2). Registered with a clearly
non-routable `path_template="unresolved:budget-details"` (does not start with `/rest/`),
`required_path_params=()`, parent `budget-views`,
`verification_reason="phase05_unresolved_path_fail_closed_prompt00-3.2"`. The id stays
catalog-visible but can never transport. **The path is not guessed**; it must be resolved
(likely merged into `budget-detail-rows`) before any promotion.

## 5. Provisional-metadata note

`response_envelope`, `pagination`, and `sqlite_target` on the unverified rows are
**provisional** — sourced from the attached matrix and re-confirmed at live promotion.
`sqlite_target` stays `procore_live_records` only as a never-written placeholder; the V8
financial projection target is Prompt 02. The commitments(v2)-vs-purchase-orders(v1)
double-count risk (Prompt 00 §3.1) is unresolved by design at this stage; v1 PO rows are
registered as compatibility/backfill candidates pending live verification.

## 6. Verification run

- `ruff check .` clean; `ruff format` applied (target files formatted).
- `mypy src` → no issues in 108 source files.
- `pytest -m "not integration and not live and not manual"` → **1119 passed, 1 skipped,
  1 deselected** (was 1112; +7 new financial registry/fail-closed tests; the one Phase-04A
  endpoint-list count assertion updated 27 → 27 verified + 32 unverified = 59).

## 7. Acceptance criteria status

| Criterion | Status |
|---|---|
| Registry contains all accepted Phase 05 endpoint IDs | ✅ 32 added (59 total); all ids resolve |
| Unknown / unverified endpoints fail closed with no transport call | ✅ §3 — code + CLI + tests, incl. a real `prime-contracts` no-transport test |
| Tests prove endpoint matrix consistency | ✅ count, resolution, fail-closed, parent/child consistency tests |
| No live Procore call required | ✅ all financial rows `live_verified=False`; no transport |
