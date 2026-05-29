# Phase 05 — N+1 parent→child orchestration + child promotion (2026-05-29)

> Generalize the live-sync N+1 mechanism so financial child endpoints (whose path needs a
> parent record id) can transport, then probe→reconcile→promote the children that cleanly
> match their live shapes. Read-only GET; bounded; fail-closed-on-divergence.

## Orchestration (registry-driven, generalized from the activities/meeting-detail N+1)

`live_sync.py`:
- `_N1_CHILD_ENDPOINTS` (17 children with a parent token). For these the orchestrator
  fetches the **parent list** via `parent_path_template`, then issues **one child GET per
  parent**, substituting `{project_id}` + `{company_id}` + the child's
  `{<parent_record_id_field>}` token via `_resolve_child_path`. Each fetched child is tagged
  with the parent id (reserved key `_hb_parent_procore_id`); the per-item
  `parent_id_for_upsert` derivation reads it so the financial projection receives the right
  `parent_procore_id`. Per-parent child transport errors are recorded
  (`detail_transport_error`) and the run continues. budget-change-line-items is **excluded**
  (flat project-scoped path, no parent token).
- `_record_id_of` synthetic-id fallback extended: `commitment-compliance` is an id-less
  blob (one per contract) → keyed by the parent contract id.

Offline regression: `tests/test_procore_live_sync_n1_children.py` drives
`commitment-line-items` with a path-aware fake transport (parent list → per-parent child
pages) and asserts parent-list fetch, per-parent child GETs, children upserted with the
correct `parent_procore_id`, the financial projection ran (line items + amount facts), a
per-parent transport error captured without aborting, and the reserved key never persisted.

## Live probe of the 22 unverified financials (in-memory promote, throwaway DB)

| Result | Endpoints |
|---|---|
| ✅ clean (success, normalized==retrieved, 0 proj err, rows) | prime-change-orders, commitment-change-orders, purchase-order-contracts, prime-contract-line-items, prime-change-order-line-items, commitment-line-items, commitment-attachments, commitment-change-order-line-items |
| ✅ reachable, valid empty envelope (0 live records) | prime-contract-attachments, change-event-comments |
| ✅ reconciled → clean | commitment-compliance (id-less blob → synthetic id from parent; **39 compliance docs** projected) |
| 🔒 held — child path **404** vs live API | purchase-order-line-items, purchase-order-detail-line-items, subcontractor-invoice-contract-items, -contract-detail-items, -change-order-items, rfq-responses (`404 "Contract not found"`), rfq-quotes, budget-detail-columns, budget-detail-rows |
| 🔒 held — **404** (registered flat path wrong; payment apps are nested under prime contracts) | payment-applications |
| 🔒 held — **403 FORBIDDEN** (token lacks permission) | budget-change-line-items |
| 🔒 sentinel | budget-details |

Held endpoints keep `live_verified=False`; the observed HTTP status is documented above —
the registered child paths diverge from the live API and the correct paths are not guessed
(reconcile with Procore API docs / operator before promotion).

## Promotion (committed)

`endpoints.py`: **11** flipped `live_verified=True`
(`verification_reason="phase05_live_smoke_verified_2026-05-29"`): the 3 parentless parents,
the 5 clean N+1 children, the 2 empty-but-valid children, and commitment-compliance.
Registry posture **36 → 47 live-verified / 12 fail-closed / 59 total**.

## Full live cadence on the 11 (smoke → sync → idempotent re-run)

All `success`, `retrieved==upserted`, `projection_error_count=0`, byte-stable re-runs, e.g.
prime-change-orders 50/50, commitment-line-items 50/50, commitment-attachments 50/50,
prime-contract-line-items 46/46, commitment-change-order-line-items 3/3, commitment-compliance
8/8, prime-contract-attachments + change-event-comments 0/0 (valid empty). Note: N+1 children
fan out one GET per parent, so the cadence must use bounded parent counts — a `--max-items 50`
sync over 50 parents exceeded a 180s wrapper and two children briefly hit transient
rate-limiting during the burst; both returned clean on a bounded retry (no data written on a
transport error — graceful).

## No-secret probe over the resulting real data

**2,109** real financial rows persisted across 12 tables (contracts 74, line_items 96,
change_orders 100, change_order_line_items 100, compliance_documents 73, amount_facts 1237,
subcontractor_invoices 100, budget_changes 195, change_events 100, billing_periods 21,
budget_views 6, rfqs 7) + 81 path-only attachment refs. Scan for Bearer/PEM/`sig=`/`token=`/
`access_token`/URL/email → **zero findings**; `raw_body_persisted=0` / `redaction_applied=1`
intact.

## Tests / verification

- `tests/test_procore_endpoint_registry.py`: `_PHASE05_PROMOTED` → 20.
- `tests/test_procore_live_gate.py`: endpoints-list counts 36/23 → **47/12**; the
  fail-closed-without-transport test now uses the permanent `budget-details` sentinel.
- New `tests/test_procore_live_sync_n1_children.py` (offline N+1 regression).
- `ruff check .` + `mypy src` clean (115 files); `pytest -m "not integration and not live
  and not manual"` → **1242 passed, 1 skipped, 1 deselected** (+1 new test).

## Residual fail-closed (12)

9 child paths that 404 against the live API (PO / requisition / rfq / budget-view children),
payment-applications (404 nested path), budget-change-line-items (403), budget-details
(sentinel). These need real Procore path/permission verification — held, not guessed.
