# 16 — Procore Contracts & Financials (Phase 05)

Status: **in progress** · Phase 05 Prompts 01–05 · Migration **V8** · registry 27 → 59 endpoints

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

Evidence: `docs/evidence/construction-intelligence-phase-05-financials/`
(`00-…source-inventory.md`, `phase05-financial-endpoint-inventory.json`,
`01-endpoint-registry-and-live-gate-shell.md`,
`02-v8-financial-schema-and-repository-model.md`,
`03-shared-financial-normalizers-and-redaction-utilities.md`,
`04-prime-contracts-prime-change-orders-and-payment-applications.md`,
`05-commitments-purchase-orders-attachments-and-compliance.md`).
