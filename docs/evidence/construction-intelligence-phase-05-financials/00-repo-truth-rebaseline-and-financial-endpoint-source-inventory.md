# Phase 05 Prompt 00 — Repo Truth Rebaseline & Financial Endpoint Source Inventory

> **Scope:** read-only rebaseline + endpoint source inventory. **No behavior changes.**
> No code, schema, migrations, normalizers, live GETs, or writeback were performed.
> Financial data (contracts, invoices, budgets, change orders) is treated as
> **high-sensitivity business data**; this inventory captures **field names + types only**,
> never values. Companion artifacts:
> [`phase05-financial-endpoint-inventory.json`](./phase05-financial-endpoint-inventory.json) ·
> [`phase05-financial-normalizer-coverage-baseline.md`](./phase05-financial-normalizer-coverage-baseline.md)

---

## 1. Repo truth rebaseline

### 1.1 Starting SHA — divergence documented (benign)

| Item | Value |
|---|---|
| Expected baseline SHA (prompt) | `0d8a1f64931e8687f8c9d2e033e9236522049c07` |
| **Actual `HEAD`** | **`74d89d54c1546f10e0a2f44bf426e4eba5d8659a`** |
| `HEAD` is a descendant of expected? | **Yes** (`git merge-base --is-ancestor 0d8a1f6 HEAD` → exit `0`) |
| Working tree | Clean except untracked `.code-graph/` (left untouched) |

The expected SHA `0d8a1f6` is the Phase 04B final-validation closeout commit. `HEAD` is
**two doc-only commits ahead** of it; the financial code surface is therefore unchanged
since Phase 04B closeout. No rebase or reset performed.

Commits since the expected baseline (`git log --oneline 0d8a1f6..HEAD`):

| SHA | Subject | Touches financial code? |
|---|---|---|
| `74d89d5` | docs(evidence): refresh MVP local runtime harness and delegated-graph outputs | No (docs/evidence only) |
| `58bf29d` | chore(workspace): replace CLAUDE.md with project-specific agent guidance | No (CLAUDE.md only) |

**Conclusion:** divergence is benign and fully accounted for; the Phase 05 starting point
is a clean descendant of the Phase 04B closeout.

### 1.2 Current Procore code surface (no financial endpoints exist)

- **`src/hb_assistant/procore/endpoints.py`** — 27 live-verified endpoints, all
  operational/safety/workflow (projects, RFIs, submittals, observations, meetings, 11
  daily-log subtypes, punch items, schedules/activities, inspections + sections + items).
  **Zero financial endpoints** (no contracts, commitments, POs, invoices, RFQs, budget).
- **`resources/config/procore_endpoint_contract.seed.yaml`** — four financial entries
  exist as `status: sensitive_validated`, `sensitivity: high` placeholders only —
  **no adapters, no normalizers, no projection tables**: `list-commitments`
  (`/rest/v2.0/.../commitment_contracts`), `list-prime-contracts`
  (`/rest/v1.0/projects/{project_id}/prime_contracts`), `list-invoices`
  (`/rest/v1.1/requisitions`), `list-change-events` (`/rest/v1.1/change_events`).
- **`resources/config/procore_endpoint_reference.phase03_unverified.seed.yaml`** — a
  larger set of `category: financials`, `mvp_status: candidate_unverified` reference
  candidates (budget views/rows/snapshots, commitments + line items + change orders,
  prime-contract change orders, direct costs, owner/subcontractor invoices). Reference
  only; not wired to code.
- **Store schema is at V7** (`src/hb_assistant/store/migrator.py`). No financial
  projection tables exist. Phase 05's V8 financial schema is **out of scope for this
  prompt** (Prompt 02).
- **Normalizers** (`src/hb_assistant/procore/normalizers/`) cover RFI, submittal,
  observation, meeting, daily-log (+ live subtypes), punch item, schedule, inspection,
  plus `hashing.py`/`entities.py` utilities. **No financial normalizer module exists.**

### 1.3 Redaction / PII posture inherited from Phase 04B (reuse target, unchanged)

Phase 05 will reuse the existing posture; nothing here is modified by this prompt.

| Layer | Location | Behavior |
|---|---|---|
| HTTP boundary redaction | `src/hb_assistant/procore/redaction.py` | Authorization/token/secret headers → `[REDACTED]`; request summary path-only (no query string); response body never logged (safe hash + rate-limit headers only) |
| Hash primitives | `src/hb_assistant/procore/normalizers/hashing.py` | `hash_summary` (SHA-256[:12]+length for free text), `hash_identifier` (PII names/emails), `person_hash_summary` (`{hash_prefix, numeric_id}`) |
| Entity/at-rest redaction | `src/hb_assistant/store/procore_enrichment.py` | `_hash12` (login/name → SHA-256 prefix), `_url_path` (drops signed-URL query strings), `_redact_excerpt` (free text → masked excerpt: `[email]`/`[phone]`/`[url]`) |
| Schema CHECK guards | `migrator.py` V6/V7 | `CHECK(raw_body_persisted = 0)`, `CHECK(redaction_applied = 1)` |
| History diffing | `src/hb_assistant/store/procore_history.py` | Diffs only over already-redacted canonical fields; deterministic SHA-256 dedup |

**Phase 05 posture intent (carried forward, not implemented here):** preserve financial
*amounts* as structured decimal-safe business facts (contract sums, revised totals,
approved/pending change amounts, retainage, percent complete, scheduled value,
billed/paid-to-date, balances, WBS/cost-code identifiers, currency config); redact/hash
PII, raw descriptions/notes/review/compliance/quote/invoice-item comments, HTML bodies,
addresses, phone numbers, emails, and attachment/signed URLs.

---

## 2. Financial endpoint source inventory (32 endpoints)

**Source:** the attached package reference
`HB_Construction_Intelligence_Phase_05_Procore_Contracts_Financials_Package/resources/json/phase05_endpoint_inventory_from_attached_reference.json`
(`source_status: sourced_from_attached_reference`). The package attributes its own upstream
origin to a pasted text capture (`source: "Pasted text(981).txt"`); the field inventory
contains **field names + types only — no values** (package manifest attestation, verified
on read). Full per-field path/type lists are in
[`phase05-financial-endpoint-inventory.json`](./phase05-financial-endpoint-inventory.json).

**Verified count: 32 endpoints, 1,604 field paths.** The package uses 8 source families;
they map to the prompt's 6 groups as below.

### Group 1 — Owner contracts (6)

| endpoint_id | method | path_template | parent | envelope | fields |
|---|---|---|---|---|---|
| `prime-contracts` | GET | `/rest/v1.0/prime_contracts` | — | array | 235 |
| `prime-contract-line-items` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/prime_contracts/{prime_contract_id}/line_items` | prime-contracts | object.data[] | 18 |
| `prime-contract-attachments` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/prime_contracts/{prime_contract_id}/attachments` | prime-contracts | object.data[] | 6 |
| `prime-change-orders` | GET | `/rest/v1.0/projects/{project_id}/prime_change_orders` | — | object | 68 |
| `prime-change-order-line-items` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/prime_change_orders/{prime_change_order_id}/line_items` | prime-change-orders | object.data[] | 30 |
| `payment-applications` | GET | `/rest/v1.0/prime_contracts/{prime_contract_id}/payment_applications` | prime-contracts | array | 49 |

*(Package families `owner_contracts` (5) + `owner_billing` (1).)*

### Group 2 — Commitments (6)

| endpoint_id | method | path_template | parent | envelope | fields |
|---|---|---|---|---|---|
| `commitment-contracts` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts` | — | object.data[] | 35 |
| `commitment-line-items` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts/{commitment_contract_id}/line_items` | commitment-contracts | object.data[] | 30 |
| `commitment-attachments` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_contracts/{commitment_contract_id}/attachments` | commitment-contracts | object.data[] | 6 |
| `commitment-compliance` | GET | `/rest/v1.0/projects/{project_id}/work_order_contracts/{contract_id}/compliance` | commitment-contracts | object | 46 |
| `commitment-change-orders` | GET | `/rest/v1.0/projects/{project_id}/commitment_change_orders` | — | object | 70 |
| `commitment-change-order-line-items` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/commitment_change_orders/{commitment_change_order_id}/line_items` | commitment-change-orders | object.data[] | 31 |

### Group 3 — Purchase orders (3)

| endpoint_id | method | path_template | parent | envelope | fields |
|---|---|---|---|---|---|
| `purchase-order-contracts` | GET | `/rest/v1.0/purchase_order_contracts` | — | array | 53 |
| `purchase-order-line-items` | GET | `/rest/v1.0/purchase_order_contracts/{purchase_order_contract_id}/line_items` | purchase-order-contracts | array | 82 |
| `purchase-order-detail-line-items` | GET | `/rest/v1.0/purchase_order_contracts/{purchase_order_contract_id}/line_item_contract_details` | purchase-order-contracts | array | 9 |

### Group 4 — Invoices (5)

| endpoint_id | method | path_template | parent | envelope | fields |
|---|---|---|---|---|---|
| `billing-periods` | GET | `/rest/v1.0/projects/{project_id}/billing_periods` | — | array | 9 |
| `subcontractor-invoices` | GET | `/rest/v1.1/requisitions` | — | array | 184 |
| `subcontractor-invoice-contract-items` | GET | `/rest/v1.0/requisitions/{requisition_id}/contract_items` | subcontractor-invoices | array | 35 |
| `subcontractor-invoice-contract-detail-items` | GET | `/rest/v1.0/requisitions/{requisition_id}/contract_detail_items` | subcontractor-invoices | array | 31 |
| `subcontractor-invoice-change-order-items` | GET | `/rest/v1.0/requisitions/{requisition_id}/change_order_items` | subcontractor-invoices | array | 34 |

*(Package families `billing` (1) + `subcontractor_invoices` (4).)*

### Group 5 — RFQs / change events (5)

| endpoint_id | method | path_template | parent | envelope | fields |
|---|---|---|---|---|---|
| `rfqs` | GET | `/rest/v1.0/rfqs` | — | array | 248 |
| `rfq-responses` | GET | `/rest/v1.0/rfqs/{rfq_id}/responses` | rfqs | array | 14 |
| `rfq-quotes` | GET | `/rest/v1.0/rfqs/{rfq_id}/quotes` | rfqs | array | 21 |
| `change-events` | GET | `/rest/v1.1/change_events` | — | object | 133 |
| `change-event-comments` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/change_events/{change_event_id}/comments` | change-events | object.data[] | 17 |

### Group 6 — Budget (7)

| endpoint_id | method | path_template | parent | envelope | fields |
|---|---|---|---|---|---|
| `budget-views` | GET | `/rest/v1.0/budget_views` | — | array | 13 |
| `budget-detail-columns` | GET | `/rest/v1.0/budget_views/{budget_view_id}/budget_detail_columns` | budget-views | array | 7 |
| `budget-details` | GET | **`null` (unresolved — see §3.2)** | budget-views | array | 29 |
| `budget-detail-rows` | GET | `/rest/v1.0/budget_views/{budget_view_id}/detail_rows` | budget-views | array | 30 |
| `budget-change-history` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/budget_change_history` | — | object | 9 |
| `budget-change-line-items` | GET | `/rest/v2.0/companies/{company_id}/projects/{project_id}/budget_changes/adjustment_line_items` | budget-change-history | object.data[] | 13 |
| `budget-modifications` | GET | `/rest/v1.0/projects/{project_id}/budget_modifications` | — | array | 9 |

### Group counts

| Group | Count |
|---|---|
| Owner contracts | 6 |
| Commitments | 6 |
| Purchase orders | 3 |
| Invoices | 5 |
| RFQs / change events | 5 |
| Budget | 7 |
| **Total** | **32 ✓** |

---

## 3. Overlap & duplicate-counting risk

### 3.1 Commitments (v2) vs. purchase orders (v1) — primary double-count risk

The package warns that the newer v2 `commitment-contracts`
(`/rest/v2.0/.../commitment_contracts`) may already encompass both work-order contracts
**and** purchase orders, while the legacy v1 `purchase-order-*` endpoints
(`/rest/v1.0/purchase_order_contracts*`) cover purchase orders separately. Syncing both
without dedup would **double-count committed cost**.

**Mitigation rule (to be enforced in later prompts, documented here):** assign every
contract a canonical identity:

```
project_key | contract_family | procore_contract_id | source_endpoint
```

- If v2 `commitment-contracts` is verified to return POs with sufficient fields → treat v2
  as the canonical source and mark the v1 `purchase-order-*` endpoints as
  **compatibility/backfill only** (deprecated in evidence).
- If v2 does not fully cover POs → implement both with **explicit dedup** keyed on the
  canonical identity above.
- This must be verified against the real contract during Prompt 05; **do not guess** — if
  observed behavior differs from the package, fail closed and document the observed contract.

### 3.2 `budget-details` has no resolved path (fail-closed flag)

In the source reference, `budget-details` carries `path_template: null` (29 fields, parent
`budget-views`). The package did not resolve a distinct URL for it; it likely overlaps with
`budget-detail-rows` (`/rest/v1.0/budget_views/{budget_view_id}/detail_rows`) and/or
`budget-detail-columns`. **Per fail-closed posture, no path is invented here.** It is
recorded with `path_resolved: false` in the JSON and must be confirmed (or merged into
`budget-detail-rows`) before any registry entry or live call in a later prompt.

### 3.3 Parent/child fan-out duplication

Several endpoints are N+1 children whose amounts roll up into their parents — line items,
attachments, compliance, invoice contract/detail/change-order items, RFQ responses/quotes,
change-event comments, budget detail rows, and change line items. Aggregation logic must
sum **child line items** or **parent totals**, never both, to avoid inflating totals. The
amount-fact model planned for V8 (Prompt 02) is the intended single point of truth for
cross-object aggregation.

### 3.4 Change-order surfaces appear in multiple families

Change-order data surfaces as `prime-change-orders` (owner), `commitment-change-orders`
(vendor), `subcontractor-invoice-change-order-items` (invoice context), and
`budget-change-*` (budget context). These are **distinct record types**, not duplicates,
but downstream "total change" rollups must key on record type + contract identity to avoid
conflating owner-side and vendor-side change value.

---

## 4. Provenance & safety attestation

- **No raw payload values** are committed — the inventory is field **names + types only**,
  carried verbatim from the package reference (which itself contains no values).
- **No secrets, tokens, OAuth payloads, Authorization headers, signed-URL query strings, or
  raw response bodies** appear in any artifact.
- **No live GETs, no writeback, no schema/migration/code changes** were performed by this
  prompt.
- **Fail-closed:** where the source is ambiguous (`budget-details` path), the gap is
  recorded rather than guessed. If a real Procore endpoint contract later differs from this
  package, document the observed contract and stop — do not assume the package is correct.
- **Migrations remain additive/idempotent** (none added here; V8 is Prompt 02).

---

## 5. Acceptance criteria status

| Criterion | Status |
|---|---|
| Starting SHA verified or divergence documented | ✅ §1.1 — descendant of expected baseline, documented |
| All 32 endpoint candidates inventoried | ✅ §2 + JSON (32 endpoints, 1,604 field paths) |
| Endpoint overlaps and duplicate-counting risks documented | ✅ §3 |
| No code behavior changes (only read-only inventory tooling) | ✅ docs-only; verified by test/lint subset |
| No raw payload values committed | ✅ §4 — names + types only |
