# Phase 05 — Financial Normalizer Coverage Baseline

> **Baseline at `HEAD` = `74d89d54c1546f10e0a2f44bf426e4eba5d8659a`.** This is the
> **zero-state** measurement the later Phase 05 prompts (03–09) are measured against.
> Source of truth: repo normalizers
> (`src/hb_assistant/procore/normalizers/`) and the endpoint registry
> (`src/hb_assistant/procore/endpoints.py`) diffed against the 32-endpoint financial
> inventory in [`phase05-financial-endpoint-inventory.json`](./phase05-financial-endpoint-inventory.json).
> **Names only — no raw values.**

## Method

Each financial endpoint is classified by its current repo state:

- **net-new** — no registry adapter, no normalizer, no projection table at `HEAD`.
- **partial** — referenced in a seed/contract YAML but lacking adapter + normalizer + table.

At `HEAD`, **every financial endpoint is `net-new`** for code, with four also present as
inert `sensitive_validated` placeholders in `procore_endpoint_contract.seed.yaml` (no
adapter/normalizer/table). There is **no financial normalizer module** in the repo.

## Existing (non-financial) normalizer context

For reference, these normalizers exist today and define the redaction/structuring patterns
Phase 05 will follow (none handle financial records):
`rfi`, `submittal`, `observation`, `meeting`, `daily_log` (+ `daily_log_live` subtypes),
`punch_item`, `schedule`, `inspection`, plus utilities `hashing` and `entities`.

Reusable redaction utilities (Phase 04B posture — Phase 05 will reuse, not modify):
`normalizers/hashing.py` (`hash_summary`, `hash_identifier`, `person_hash_summary`),
`procore/redaction.py` (HTTP boundary), `store/procore_enrichment.py`
(`_hash12`, `_url_path`, `_redact_excerpt`).

## Coverage matrix — 32 financial endpoints (all net-new)

| Group | endpoint_id | fields | registry adapter | normalizer | projection table | status |
|---|---|---:|---|---|---|---|
| Owner contracts | `prime-contracts` | 235 | none | none | none | net-new |
| Owner contracts | `prime-contract-line-items` | 18 | none | none | none | net-new |
| Owner contracts | `prime-contract-attachments` | 6 | none | none | none | net-new |
| Owner contracts | `prime-change-orders` | 68 | none | none | none | net-new |
| Owner contracts | `prime-change-order-line-items` | 30 | none | none | none | net-new |
| Owner contracts | `payment-applications` | 49 | none | none | none | net-new |
| Commitments | `commitment-contracts` | 35 | placeholder¹ | none | none | net-new |
| Commitments | `commitment-line-items` | 30 | none | none | none | net-new |
| Commitments | `commitment-attachments` | 6 | none | none | none | net-new |
| Commitments | `commitment-compliance` | 46 | none | none | none | net-new |
| Commitments | `commitment-change-orders` | 70 | none | none | none | net-new |
| Commitments | `commitment-change-order-line-items` | 31 | none | none | none | net-new |
| Purchase orders | `purchase-order-contracts` | 53 | none | none | none | net-new |
| Purchase orders | `purchase-order-line-items` | 82 | none | none | none | net-new |
| Purchase orders | `purchase-order-detail-line-items` | 9 | none | none | none | net-new |
| Invoices | `billing-periods` | 9 | none | none | none | net-new |
| Invoices | `subcontractor-invoices` | 184 | placeholder¹ | none | none | net-new |
| Invoices | `subcontractor-invoice-contract-items` | 35 | none | none | none | net-new |
| Invoices | `subcontractor-invoice-contract-detail-items` | 31 | none | none | none | net-new |
| Invoices | `subcontractor-invoice-change-order-items` | 34 | none | none | none | net-new |
| RFQs / change events | `rfqs` | 248 | none | none | none | net-new |
| RFQs / change events | `rfq-responses` | 14 | none | none | none | net-new |
| RFQs / change events | `rfq-quotes` | 21 | none | none | none | net-new |
| RFQs / change events | `change-events` | 133 | placeholder¹ | none | none | net-new |
| RFQs / change events | `change-event-comments` | 17 | none | none | none | net-new |
| Budget | `budget-views` | 13 | none | none | none | net-new |
| Budget | `budget-detail-columns` | 7 | none | none | none | net-new |
| Budget | `budget-details` | 29 | none | none | none | net-new (path unresolved²) |
| Budget | `budget-detail-rows` | 30 | none | none | none | net-new |
| Budget | `budget-change-history` | 9 | none | none | none | net-new |
| Budget | `budget-change-line-items` | 13 | none | none | none | net-new |
| Budget | `budget-modifications` | 9 | none | none | none | net-new |

¹ Present only as an inert `status: sensitive_validated` entry in
`resources/config/procore_endpoint_contract.seed.yaml` (`list-prime-contracts`,
`list-commitments`, `list-invoices`, `list-change-events`) — no adapter, no normalizer,
no table. Prime-contracts maps to the `list-prime-contracts` placeholder; it is marked
"none" above because the inventory's `prime-contracts` adapter does not yet exist.

² `budget-details` has `path_template: null` in the source reference — see §3.2 of
[`00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md`](./00-repo-truth-rebaseline-and-financial-endpoint-source-inventory.md). Path must be confirmed/merged before implementation.

## Baseline totals

| Metric | Value |
|---|---|
| Financial endpoints in inventory | 32 |
| Implemented in `endpoints.py` | 0 |
| Financial normalizers | 0 |
| Financial projection tables (V7) | 0 |
| Inert contract placeholders | 4 |
| Total field paths to classify | 1,604 |

## Planned normalizer → redaction-utility mapping (forward-looking, not implemented)

| Group | Amounts to preserve (decimal-safe) | Fields to redact/hash | Utilities to reuse |
|---|---|---|---|
| Owner contracts | original/revised sums, approved/pending change amounts, retainage, % complete, billed/paid-to-date, balance | vendor/contact names, descriptions, notes, attachment URLs | `hash_identifier`, `hash_summary`, `_url_path` |
| Commitments | commitment sum, revised total, change amounts, retainage, compliance status | vendor/person names, compliance notes, attachment URLs | `hash_identifier`, `hash_summary`, `_url_path` |
| Purchase orders | PO total, line amounts, tax | vendor names, descriptions | `hash_identifier`, `hash_summary` |
| Invoices | scheduled value, current due, retainage held/released, billed/paid-to-date | vendor/person names, invoice item comments | `hash_identifier`, `hash_summary` |
| RFQs / change events | RFQ estimated/quoted amounts, change-event ROM cost/revenue | descriptions, quote comments, change-event comments | `hash_summary`, `_redact_excerpt` |
| Budget | original/revised/forecast/actual/remaining, change amounts | row labels if PII, free-text notes | `hash_summary` |
