# 16 — Procore Contracts & Financials (Phase 05)

Status: **in progress** · Phase 05 Prompts 01–09 · Migration **V9** · registry 27 → 59 endpoints

Phase 05 extends the Procore subsystem into the contract / financial-control
surface (owner contracts, commitments, purchase orders, invoices, RFQs / change
events, budget). Prompt 00 produced the read-only endpoint inventory; **Prompt 01
adds the registry + live-gate shell** — making all 32 financial endpoints *known*
to the system while keeping every one fail-closed until per-endpoint smoke
evidence promotes it.

## Endpoint registry shells

`procore/endpoints.py` now carries 32 Phase 05 financial `EndpointAdapter` rows
appended after the 27 Phase 04A/04B operational rows (total 59). Every financial
row is:

- `live_verified=False` with `verification_reason="phase05_shell_pending_live_smoke"`
  (or, for `budget-details`, a fail-closed unresolved-path reason).
- `sensitivity="high"` and `review_required_default=True` (high-sensitivity
  business data posture).
- `sqlite_target="procore_live_records"` as a **placeholder** — the V8 financial
  projection target lands in Prompt 02; nothing is written while unverified.
- No normalizer registered — `live_sync.resolve_normalizer()` returns `None`, so
  even a hypothetical promotion fails closed (`normalizer_missing`). The real
  per-family normalizers are Prompts 03–09.

Parent/child linkage uses the existing `parent_path_template` /
`parent_record_id_field` fields (12 parents, 20 children). The `EndpointAdapter`
dataclass gains one **additive** trailing field, `response_envelope`
(`"array"` | `"object"` | `"object.data[]"`, default `"array"`), recording the
top-level wrapper shape from the endpoint matrix; the 27 pre-05 rows keep the
default and are otherwise unchanged.

## Fail-closed posture (no transport)

Unverified endpoints are command-visible (`procore live endpoints list` shows all
59 with their flags) but fail closed in `live_sync.py` **before** any transport:
the unverified branch returns `state="not_live_verified"`,
`no_live_call_performed=True`, `request_count=0`, reason
`endpoint_unverified_for_live`. This is locked in by
`tests/test_procore_endpoint_registry.py` (count/resolution/fail-closed/parent-child
consistency) and `tests/test_procore_live_gate.py`
(`test_live_sync_phase05_financial_endpoint_fails_closed_without_transport`, which
drives a real `prime-contracts` shell with a transport that raises if hit).

## Notable items

- **`budget-details`** has no resolved path in the source reference (Prompt 00
  §3.2). It is registered with a clearly non-routable sentinel
  (`path_template="unresolved:budget-details"`) so the id stays catalog-visible yet
  can never transport. The path is **not guessed**; it must be resolved (likely
  merged into `budget-detail-rows`) before promotion.
- **Commitments (v2) vs purchase orders (v1)** carry a double-counting risk
  (Prompt 00 §3.1); the v1 PO rows are registered as compatibility/backfill
  candidates pending live verification.
- Envelope / pagination / `sqlite_target` on unverified rows are **provisional**
  metadata, re-confirmed at live promotion.

## V8 financial schema & repository (Prompt 02)

`store/migrator.py` V8 adds **13 financial projection tables** (additive;
`apply()` now returns 8). The first 10 (`procore_financial_contracts`,
`_line_items`, `_change_orders`, `_payment_applications`, `_invoice_items`,
`_rfqs`, `_change_events`, `_budget_views`, `_budget_rows`, `_amount_facts`) are
transcribed **verbatim** from the package
`resources/sql/phase_05_financial_schema_additions.sql`. The last 3
(`_change_order_line_items`, `_budget_changes`, `_compliance_documents`) are
**HB-authored extensions** beyond the authoritative SQL — modeled on the ledger
prose + the verbatim schema conventions, flagged as provisional pending live
reconciliation.

- **Decimal-safe amounts:** every money column is `TEXT`; the repository stores
  amount values verbatim and never calls `float()` (TEXT affinity would re-format
  a float and lose precision). A test persists `-1234567.89012345` /
  `0.000000000001` and reads them back byte-for-byte.
- **Redaction guards:** every table carries
  `CHECK(raw_body_persisted = 0)` and (except `_amount_facts`)
  `CHECK(redaction_applied = 1)`.
- **`amount_facts`** is the cross-object aggregation ledger (one normalized row
  per named amount with deterministic `amount_fact_id`), enabling rollups without
  per-endpoint SQL.

`store/procore_financials.py` is the standalone repository: free-function
upserts for each table (DRY `_persist` core building a parameterized
`INSERT … ON CONFLICT(pk) DO UPDATE`), `emit_financial_amount_fact`
(deterministic id → idempotent), and deterministic read views
(`read_financial_contract_summary`, `read_financial_amount_facts`,
`read_financial_risk_view`). Redaction is enforced at this boundary
(`*_redacted` excerpt-masked, `description_summary_json` → hash+len+excerpt,
`attachment_path_redacted` → path-only). Unknown columns fail closed. **No
live-sync wiring** — the dispatch that calls these lands in Prompt 10.

## Shared financial normalizers & redaction utilities (Prompt 03)

Two new shared modules give the per-endpoint normalizers (Prompts 04–09) and the
live-sync dispatch (Prompt 10) one toolkit each layer:

- **`procore/normalizers/financial.py`** (pure, no DB) — decimal-safe
  `parse_amount` (preserves source string, never float/Decimal re-coercion that
  drops trailing zeros/sign), `extract_currency_config`, `extract_wbs_cost_code`,
  `mask_excerpt` (PII), `html_to_text` + `summarize_text` (HTML→text
  hash+len+masked-excerpt; raw never returned), `attachment_path` (path-only,
  drops signed-URL query), `custom_field_policy` (decimal/bool/lov preserved,
  strings hashed), and `build_amount_facts` (generic value-level emitter). It
  re-exposes the shared `hashing` / `entities` primitives (person PII hashed,
  company labels preserved) so callers have one import.
- **`store/procore_financial_projection.py`** (store layer) — the shared
  projection primitives: `emit_amount_facts` (generic store-layer amount-fact
  emitter over Prompt 02's `emit_financial_amount_fact` — idempotent, decimal
  preserved) and `link_record_entities` (people hashed + company/vendor labels
  preserved, emitting relationship edges via the Phase 04B enrichment
  primitives). Per-endpoint `project_*` functions are added in later prompts.

Posture: money/labels preserved as structured business facts usable for
aggregation; person PII, free text/HTML, contact info, and signed-URL query
strings never persist raw.

## Owner-side family — prime contracts / COs / payment applications (Prompt 04)

First per-endpoint family. `normalizers/owner_contract.py` (6 normalizers) +
`store/procore_owner_projection.py` (`project_owner_contract_family`) implement the
owner side; both are **wired into live_sync** (`_NORMALIZER_BY_ID` + a guard block)
but the 6 endpoints stay **`live_verified=False`** — the chain fail-closes before
the normalizer lookup, so nothing transports until an operator runs a bounded smoke
(no live GETs were performed here).

- **Normalize:** amounts/quantities/rates kept verbatim (decimal-safe); free text
  (title/description/inclusions/exclusions/review_notes) → **hash-only** summary (no
  excerpt — high-sensitivity); parties → `person_hash_summary`; attachment URLs →
  path-only; payment-application amounts read from the nested `g702` AIA object.
- **Project:** rows into `procore_financial_contracts` / `_line_items` /
  `_change_orders` / `_change_order_line_items` / `_payment_applications`; amount facts
  for contract sums, approved COs, grand totals, payment due, retainage, balance to
  finish; edges contract→architect/created_by (people, hashed) + contractor/vendor
  (companies, labels preserved) + change_order_of / payment_application_of; attachment
  refs path-only. Financial table rows carry **structured facts only** (no free text).
- **Signals:** `prime_contract_unexecuted`, `prime_contract_private`,
  `prime_change_order_unexecuted`/`_unpaid`/`_schedule_impact`,
  `payment_application_pending_or_unpaid`, `payment_application_retainage_held`.
- Shared store-layer helpers `record_key` / `coerce_amount` / `is_positive_amount` /
  `bool_to_int` added to `procore_financial_projection.py` for reuse by later families.

## Vendor-side family — commitments / POs / compliance (Prompt 05)

`normalizers/commitment_contract.py` (7 normalizers) + `store/procore_commitment_projection.py`
(`project_commitment_family`) implement commitment contracts + line items + attachments +
compliance and the v1 purchase-order compatibility surface; wired into live_sync the same way
(registered + guard block; endpoints stay `live_verified=False`, fail-closed).

- **Compliance** projects each `compliance_documents[]` + `insurance_documents[]` entry into
  `procore_financial_compliance_documents` — preserving document status / type / effective +
  expiration dates, `compliant` flag; **notes are hash-only** (`notes_summary_redacted`),
  attachment URLs path-only. Signals on the parent commitment: `commitment_non_compliant`,
  `commitment_insurance_not_compliant`, `commitment_compliance_document_expiring` (per doc with
  `expires_at` within 30d of `now_utc`, status ≠ expired).
- **Commitment-vs-PO de-duplication (data-driven):** a PO is a duplicate only when a
  `commitment` contract with the same `(project_key, contract_id)` already exists (v2 coverage).
  The PO row is still stored (queryable) but its amount facts are **skipped** — committed cost is
  never double-counted. Self-corrects regardless of v2 coverage; live determination deferred to
  operator smoke (Prompt 10). Canonical identity: `project_key|contract_family|procore_contract_id|
  source_endpoint`.
- Other signals: `commitment_unexecuted`, `purchase_order_processing`,
  `purchase_order_delivery_due` (`delivery_date` within 14d, non-terminal status).

## Change orders & shared line items (Prompt 06)

Closes the vendor-side change-order gap and hardens the line-item path. Two
registered-but-unwired endpoints — `commitment-change-orders` and
`commitment-change-order-line-items` — get normalizers (added to
`normalizers/commitment_contract.py`) + projections (added to
`store/procore_commitment_projection.py`), wired into live_sync the same way
(registered in `_NORMALIZER_BY_ID`; the existing `COMMITMENT_ENDPOINTS` guard now
includes both ids). Both stay **`live_verified=False`** — fail-closed before the
normalizer lookup. **No migration / repository / registry-row changes** — V8 already
carries `procore_financial_change_orders` + `procore_financial_change_order_line_items`
and the `upsert_financial_change_order` / `_change_order_line_item` repository
functions (Prompt 02).

- **Commitment change orders** mirror the owner-side prime-CO projection
  (`change_order_family="commitment"`): linked to the parent commitment by
  `contract_id` (`change_order_of` edge); amount facts for `grand_total` +
  `schedule_impact_amount`; parties (`created_by` / `received_from` /
  `designated_reviewer` / `reviewed_by`) hashed; title/description/review_notes
  hash-only. Signals: `commitment_change_order_unexecuted` (unexecuted +
  signature_required), `commitment_change_order_unpaid` (unpaid + invoiced or
  billable status), `commitment_change_order_schedule_impact` (positive impact).
- **Shared line-item hardening:** a single `change_event_line_item_summary` helper
  in `normalizers/financial.py` redacts the `change_event_line_item` linkage block
  (ids + WBS kept; change-event title + line-item description hash-only) for **all**
  line-item normalizers (prime, commitment, prime-CO, commitment-CO). A shared
  `emit_change_event_edge` primitive in `store/procore_financial_projection.py`
  emits a `change_event_line_item` edge from a change-order line item to its source
  change event (`record_key(project_key, "change-events", None, event_id)`) — a
  forward reference (the change-events endpoint lands in Prompt 08), mirroring the
  forward-referencing `change_order_of` edge. Wired into both the new commitment-CO
  line items and the existing owner prime-CO line items.

## Subcontractor billing surface — billing periods + invoices + items (Prompt 07)

Adds the vendor billing surface (5 endpoints): `billing-periods`,
`subcontractor-invoices` (requisitions), and the three child item families
(`-contract-items`, `-contract-detail-items`, `-change-order-items`). All were
already registered (Prompt 01); they stay **`live_verified=False`** (fail-closed,
no transport). New `normalizers/subcontractor_invoice.py` (5 normalizers) +
`store/procore_invoice_projection.py` (`project_invoice_family` + `INVOICE_ENDPOINTS`),
wired into live_sync the same way (registered + a guarded `INVOICE_ENDPOINTS` block).

- **Migration V9** (`apply()` now returns 9; additive, idempotent) adds two tables:
  `procore_financial_billing_periods` (period anchors: status + start/end/due dates)
  and `procore_financial_subcontractor_invoices` (requisition headers). Invoice
  **items reuse the V8 `procore_financial_invoice_items`** table (it already carries
  scheduled value / this-period work / stored materials / total-to-date / retainage /
  claimed amount / WBS-cost-code), keyed by `item_type` + `endpoint_id`.
- **Projection:** billing periods → queryable anchors. Invoices link to commitment
  (`invoice_of`), billing period (`billed_in_period`), previous invoice (`supersedes`),
  vendor (company label), and creator (hashed person). Amount facts from the AIA
  `summary` (current payment due, retainage, completed/stored, contract-sum-to-date,
  claimed) carry the requisition `period_start`/`period_end` for period + commitment
  aggregation; item facts carry WBS/cost code for cost aggregation.
- **Redaction:** the `summary_text` AIA cover block (subcontractor street / city /
  state / zip / name, GC text) is **never projected** — no column maps to it; item
  `description_of_work` → `description_summary_json` (hash+len+masked-excerpt);
  creator hashed; vendor label kept (organisation, not PII).
- **Signals:** `invoice_pending_approval`, `invoice_approved_not_paid`, `invoice_final`,
  `invoice_retainage_held`, `invoice_payment_due` (header); `invoice_materials_stored`
  (from a child item with `materials_presently_stored > 0`, anchored on the parent
  invoice); `billing_period_open`, `billing_period_due_soon` (due within 7 days,
  non-closed; deterministic from `now_utc`).
- **Read views** (`procore_financials.py`): `read_financial_billing_periods` and
  `read_financial_subcontractor_invoices` (filterable by status / billing_period_id /
  vendor_id — proves invoices query by status/period/vendor).
- `retainage_held` on items maps from `work_completed_retainage_retained_this_period`
  (documented mapping; provisional pending live smoke).

## Change-management surface — RFQs + change events (Prompt 08)

Adds the pricing/exposure surface (5 endpoints): `rfqs`, `rfq-responses`,
`rfq-quotes`, `change-events`, `change-event-comments` — linking the *informal*
pricing/change workflow to the *formal* change records. All were registered
(Prompt 01); they stay **`live_verified=False`** (fail-closed). New
`normalizers/rfq_change_event.py` (5 normalizers) +
`store/procore_rfq_change_event_projection.py` (`project_rfq_change_event_family` +
`RFQ_ENDPOINTS`), wired into live_sync the same way (registered + a guarded
`RFQ_ENDPOINTS` block).

- **No migration.** RFQs → the V8 `procore_financial_rfqs` table; change events →
  `procore_financial_change_events`. The package defines **no tables** for
  rfq-responses / rfq-quotes / change-event-comments — they project as **amount
  facts + edges + signals**; their hashed + masked-excerpt text lives only in the
  normalized live record (same pattern as rfi-replies / submittal-responses).
- **Cost/schedule exposure facts:** RFQ facts `estimated_amount`, `original_quote`,
  `estimated_schedule_impact`; quote facts `cost`, `schedule_impact`; change-event
  facts `estimated_cost`, `estimated_revenue`, `owner_cost_amount`,
  `commitment_cost_amount`, `schedule_impact_amount` (cost-code attached to facts
  when present).
- **Text never raw:** RFQ/change-event titles + descriptions, quote descriptions,
  response comments and change-event comment bodies → `summarize_text` (hash +
  length + PII-masked excerpt); creator/assignee hashed.
- **Edges:** rfq → commitment (`rfq_of_commitment`), → change event
  (`rfq_change_event`), → PCO/COR/CCO (`rfq_change_order`; prime-family refs map to
  the `prime-change-orders` namespace, commitment-family to `commitment-change-orders`
  — documented mapping), creator/assignee linked; quote `quote_of` → rfq; response
  `response_of` → rfq; comment `comment_of` → change event.
- **Signals:** `rfq_overdue` (past due, non-terminal), `rfq_under_review`,
  `rfq_no_intent_to_quote`, `rfq_estimated_schedule_impact`,
  `rfq_estimated_cost_exposure`; `change_event_pending` (non-terminal status),
  `change_event_rom_cost_exposure`, `change_event_schedule_impact`;
  `change_event_comment_added` (per comment).
- **Read views** (`procore_financials.py`): `read_financial_rfqs` /
  `read_financial_change_events` (filter by status) — make the workflow queryable.

## Budget surface — views / rows / changes (Prompt 09)

Adds the budget surface (7 endpoints; **6 implemented, 1 deferred**): `budget-views`,
`budget-detail-columns`, `budget-detail-rows`, `budget-change-history`,
`budget-change-line-items`, `budget-modifications`. New `normalizers/budget.py`
(6 normalizers) + `store/procore_budget_projection.py` (`project_budget_family` +
`BUDGET_ENDPOINTS`), wired into live_sync (registered + a guarded `BUDGET_ENDPOINTS`
block). All implemented endpoints stay **`live_verified=False`** (fail-closed).

- **No migration.** Views → V8 `procore_financial_budget_views`; detail rows →
  `procore_financial_budget_rows`; change history / change line items / modifications →
  `procore_financial_budget_changes` via the `budget_change_kind` discriminator
  (`change_history` / `line_item` / `modification`). `budget-detail-columns` has no
  table → projects a `column_of` edge to its parent view (column names kept in the
  live record).
- **`budget-details` is DEFERRED** (acceptance allows "implemented or explicitly
  deferred with reason"): it was registered in Prompt 00 as a non-routable sentinel
  (`path_template="unresolved:budget-details"`) because the source reference carries no
  resolved REST path. It has **no normalizer**, is not in `BUDGET_ENDPOINTS`, and the
  fail-closed invariant + `test_budget_details_is_non_routable_sentinel` enforce it
  can never transport. To be resolved (likely merged into `budget-detail-rows`) before
  any live promotion.
- **Column-name-agnostic:** budget detail rows preserve their full structured value set
  verbatim in `column_values_json_redacted` (curated to amounts/codes only — free text
  excluded; non-PII so stored as structured JSON, not hashed) and emit amount facts per
  recognised named amount field (WBS/cost code attached to each fact). Row signals use a
  defensive optional-field lookup (no fixed tenant column names): `budget` =
  `revised_budget|original_budget_amount`, `forecast` = `budget_forecast.amount`,
  `actual` = first-present cost field, `variance` = `projected_over_under|variance|over_under`.
- **Signals:** `budget_change_posted` (change history + posted line items),
  `budget_modification_posted` (modifications), `budget_forecast_exceeds_budget`,
  `budget_actual_exceeds_budget`, `budget_variance_negative` (rows).
- **Read views** (`procore_financials.py`): `read_financial_budget_rows` (by
  view/WBS/cost) and `read_financial_budget_changes` (by kind/status); budget amount
  facts are queried by column (`amount_name`), row (`record_key`), and WBS/cost via the
  existing `read_financial_amount_facts`.

Evidence: `docs/evidence/construction-intelligence-phase-05-financials/`
(`00-…source-inventory.md`, `phase05-financial-endpoint-inventory.json`,
`01-endpoint-registry-and-live-gate-shell.md`,
`02-v8-financial-schema-and-repository-model.md`,
`03-shared-financial-normalizers-and-redaction-utilities.md`,
`04-prime-contracts-prime-change-orders-and-payment-applications.md`,
`05-commitments-purchase-orders-attachments-and-compliance.md`,
`06-change-orders-and-financial-line-items.md`,
`07-billing-periods-subcontractor-invoices-and-invoice-items.md`,
`08-rfqs-rfq-responses-rfq-quotes-change-events-and-comments.md`,
`09-budget-views-budget-details-budget-rows-and-budget-changes.md`).
