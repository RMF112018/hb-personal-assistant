# Phase 05 Prompt 05 — Commitments, Purchase Orders, Attachments & Compliance

> **Scope:** vendor-side family — normalizers + projections + amount facts + edges + signals +
> compliance projection for the 7 commitment/PO endpoints, wired into live_sync. **No live GETs**;
> endpoints stay `live_verified=False` (fail-closed) until operator smoke. Companion:
> [`04-prime-contracts-prime-change-orders-and-payment-applications.md`](./04-prime-contracts-prime-change-orders-and-payment-applications.md).

## 1. New modules

### `src/hb_assistant/procore/normalizers/commitment_contract.py` (ruff-checked)
`NORMALIZATION_SCHEMA_VERSION = 1`. Seven normalizers (same posture as owner): amounts verbatim
(decimal-safe), free text incl. **compliance/insurance notes hash-only**, parties hashed, vendor
labels kept, attachment URLs path-only: `normalize_commitment_contract`,
`normalize_commitment_line_item`, `normalize_commitment_attachment`,
`normalize_commitment_compliance` (keeps compliance/insurance status + per-document status
metadata, hashes notes), `normalize_purchase_order_contract`,
`normalize_purchase_order_line_item`, `normalize_purchase_order_detail_line_item`.

### `src/hb_assistant/store/procore_commitment_projection.py` (store layer)
`project_commitment_family(endpoint_id, raw, ...)` + `COMMITMENT_ENDPOINTS`.

| Endpoint | Table | Notes |
|---|---|---|
| commitment-contracts | `procore_financial_contracts` (family `commitment`) | facts grand_total + retainage_percent; edges vendor (company) + created_by (person); signal `commitment_unexecuted` |
| commitment-line-items | `procore_financial_line_items` (kind `commitment`) | amount fact; parent = contract rk |
| commitment-attachments | `procore_attachment_refs` | path-only |
| commitment-compliance | `procore_financial_compliance_documents` | per compliance/insurance doc; status/type/dates/`compliant`; **notes hash-only**, attachment path-only; signals below |
| purchase-order-contracts | `procore_financial_contracts` (family `purchase_order`) | dedup guard (below); signals `purchase_order_processing`, `purchase_order_delivery_due` |
| purchase-order-line-items | `procore_financial_line_items` (kind `purchase_order`) | amount fact |
| purchase-order-detail-line-items | `procore_financial_line_items` (kind `purchase_order_detail`) | parent = PO line-item rk |

## 2. Compliance projection

Each `compliance_documents[]` and `insurance_documents[]` entry → a
`procore_financial_compliance_documents` row keyed
`record_key(project_key, "commitment-compliance", contract_id, doc_id)`, linked to the parent
commitment contract record_key. Preserves `document_type`, `status`, `compliant` (derived from
status), `effective_date`, `expiration_date`. **Notes** → hash-only summary string in
`notes_summary_redacted` (no raw, no excerpt). **Attachment URL** → first attachment reduced to
path-only via the repository (`attachment_path_redacted`; signed-URL query stripped).

Signals (on the parent commitment record_key):
- `commitment_non_compliant` — `compliance_status`/`derived_compliance_status` present and not compliant.
- `commitment_insurance_not_compliant` — `insurance_status`/`derived_insurance_status` not compliant.
- `commitment_compliance_document_expiring` — one per doc whose `expires_at` is within 30 days of
  `now_utc` and `status != expired` (deterministic from `now_utc`, no wall-clock).

## 3. Commitment-vs-PO de-duplication (documented + tested)

Canonical contract identity: `project_key | contract_family | procore_contract_id | source_endpoint`.
PO contracts are a **compatibility/backfill** surface. The dedup is **data-driven**:
`_commitment_exists(project_key, contract_id)` checks for an existing `contract_family='commitment'`
row with the same `contract_id`. If found (v2 `commitment_contracts` already covered the PO), the
PO row is still upserted (queryable) but its **amount facts are skipped** so committed cost is
never double-counted, and the projection returns `duplicate_of_commitment=True`. This self-corrects
regardless of whether v2 covers POs in a given tenant; the live coverage determination is deferred
to operator smoke (Prompt 10). Tested by `test_purchase_order_dedup_against_commitment` (commitment
id=99 then PO id=99 → both rows stored, amount-fact count unchanged, flag True).

## 4. Live-sync wiring

The 7 normalizers are registered in `_NORMALIZER_BY_ID`; a guard block calls
`project_commitment_family` for `COMMITMENT_ENDPOINTS`. All 7 stay `live_verified=False`, so the
orchestrator fail-closes before the normalizer lookup (no transport) until promotion.

## 5. Tests

- `tests/test_procore_commitment_normalizers.py` (6): amounts preserved (negative/high-precision
  byte-for-byte); compliance/insurance notes + descriptions hash-only (no raw); attachment URL
  query stripped; address/PII not leaked; compliance statuses + document metadata preserved.
- `tests/test_procore_commitment_projection.py` (6): rows into contracts / line_items /
  compliance_documents; amount facts + edges (vendor/created_by/assignee); the 6 signals under the
  right conditions (incl. date-window expiring); **dedup test**; compliance notes hash-only +
  attachment path-only; idempotent.
- `tests/test_procore_endpoint_registry.py`: `_COMMITMENT_IMPLEMENTED` folded into the fail-closed
  invariant test; new `test_phase05_commitment_endpoints_have_normalizers`.

## 6. Verification run

- `ruff check .` clean; `mypy src` → no issues in 111 source files.
- `pytest -m "not integration and not live and not manual"` → **1165 passed, 1 skipped,
  1 deselected** (was 1153; +12 new tests).

## 7. Acceptance criteria status

| Criterion | Status |
|---|---|
| Commitment and PO data safely normalized | ✅ 7 normalizers + projection, unit-tested |
| Duplicate commitment/PO policy documented and tested | ✅ §3 + `test_purchase_order_dedup_against_commitment` |
| Compliance signals fire on non-compliant status | ✅ `commitment_non_compliant` / `_insurance_not_compliant` / `_compliance_document_expiring` tests |
| PII and compliance notes do not persist raw | ✅ notes hash-only, attachment path-only, person PII hashed — tested |
