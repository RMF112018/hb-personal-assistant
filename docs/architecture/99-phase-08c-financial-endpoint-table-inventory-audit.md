# 99 — Phase 08C Financial Endpoint and Table Inventory Audit (Prompt 02)

**Baseline**: Post-P01 at `82fe198` (V35, 161 tables, 08C substrate + gates + CLI + proof.md). On ancestry of 08B closeout `dcecea875ee8eb643cff8665c362eb0f1927df0a`.

**Objective** (per prompt): Repo-truth inventory only (no code/schema changes). 1. Inspect Procore endpoint registry + normalizers. 2. Inventory financial SQLite tables + field types. 3. Classify 32 endpoints (live-verified / fail-closed / deferred / stale / unknown). 4. Identify amount / currency / WBS/cost-code / line-item-type / source_field_path fields. 5. Generate `financial-endpoint-inventory-audit.json` and `financial-table-inventory-audit.json` (metadata only).

**No re-read of context implementation files**; all inspection via terminal grep / python -c open+parse / hb-assistant CLI --json (read-only).

## Results

### Endpoints (32 total)
- **live-verified**: 29 (reason: "phase05_live_smoke_verified_2026-05-29", state live_eligible). Families: owner_contracts (prime-contracts, line-items, attachments, change-orders, co-line-items), commitments (6), purchase_orders (contracts, line-items), billing (payment-applications, billing-periods), subcontractor_invoices (5), change_management (rfqs+responses+quotes, change-events+comments), budget (views, detail-columns, detail-rows, change-history, modifications).
- **fail-closed**: 3
  - purchase-order-detail-line-items (shell_pending_live_smoke)
  - budget-details (unresolved_path_fail_closed_prompt00-3.2; path_template="unresolved:budget-details" sentinel)
  - budget-change-line-items (shell_pending_live_smoke)
- 0 deferred / stale / unknown among the financial 32.
- All 32 use shared normalizer `financial.py` (parse_amount -> Optional[str] verbatim source, never float coercion for storage; extract_currency_config; extract_wbs_cost_code) + family (owner_contract.py, commitment_contract.py, subcontractor_invoice.py, rfq_change_event.py, budget.py).
- 4 sensitive_validated in procore_endpoint_contract.seed.yaml (high-sensitivity financial families).
- path_templates from registry (some v1.0/v2.0, project/company scoped); live_gate where applicable.
- money: parse_amount preserves str; no binary float calc; outputs advisory + GUARDRAILS.

See `docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-endpoint-inventory-audit.json` (full per-endpoint: id, family, live_verified, state, reason, path, normalizers list, amount/currency/wbs lists, classification, notes).

### Tables (25 financial)
- **15 procore_financial_* (V8/V9, phase_owner=05, operational_populated)**: contracts, line_items, change_orders, payment_applications, invoice_items, rfqs, change_events, budget_views, budget_rows, amount_facts, change_order_line_items, budget_changes, compliance_documents, billing_periods, subcontractor_invoices.
  - amount fields (TEXT): grand_total, original/revised_contract_sum, approved/pending_change_orders_amount, amount, scheduled_value, schedule_impact_amount, total_amount_paid/retainage/contract_sum_to_date, subcontractor_claimed_amount, estimated_amount, owner/commitment_cost_amount, adjustment/from/to_amount, total_claimed_amount, ...
  - currency: currency_iso_code, base_*, exchange_rate.
  - wbs/cost/line: wbs_code_id, wbs_flat_code, wbs_description_redacted, cost_code_id, line_item_type_id (in items/rows/changes).
  - source: source_field_path (esp. in amount_facts for traceability).
  - guard: raw_body_persisted=0 (procore family).
- **10 08C (V35, phase_owner=08C, operational_empty_expected)**: second_brain_financial_fact_normalization_runs, _amount_facts_normalized, _currency_completeness_snapshots, _wbs_cost_code_snapshots, _source_coverage_snapshots, _exposure_summary_items, _forecast_readiness_runs, _review_required_items, _readiness_agent_runs, second_brain_phase_08c_validation_runs.
  - amount: canonical_decimal_text (TEXT), minor_units (INTEGER), amount_ref / normalized_amount_ref (refs only), amount_field_count.
  - currency: currency_code/status, currency_field_count.
  - wbs/cost/line: *_present_count fields, wbs_cost_code_field_count.
  - source: source_record_ref, source_field_path (in normalized/coverage).
  - guards (9-10 per table): raw_financial_source_payload_persisted=0, financial_determination_performed=0, payment_determination_performed=0, claim_or_entitlement_determination_performed=0, advisory_only=1, + raw_email/document/calendar/procore/prompt/response_persisted=0.
- Total in lifecycle contract: 161. 08C tables empty_expected (readiness substrate, no raw, no det).
- money policy (from 08c-gates + DDL + normalizers): canonical_decimal TEXT + minor_units INTEGER when known; float_allowed=false, sqlite_real_allowed=false; Decimal(str) only for safe checks in Python; never float for persisted money.

See `docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-table-inventory-audit.json` (per-table: name, v, owner, status, expected_pop, key_amount/curr/wbs/src lists, guard_columns, notes).

### CLI Surfaces (read-only)
- `procore live financial` (summary, contracts, changes, invoices, exposure, coverage, budget, risk) — --json, str amounts (e.g. "10200000.0"), counts, GUARDRAILS + "Advisory/review aid only. Not payment approvals...".
- `procore obsidian financial` (register; --apply opt-in, marker-bounded, no raw).
- `second-brain financial` (readiness, coverage, exposure-summary, review-items) — advisory_only=true, full guardrails dict (local_first, read_only, no_external_writeback, no_raw_financial_payload, financial_determination_forbidden, advisory_only), contract-backed, no det.
- `second-brain data-quality phase-08c-gates` (and no-writeback-proof) — pass, amount_normalization gate confirms TEXT/INTEGER/no-float, endpoint_inventory pass, all snapshots/guards pass.

### Verification at Run
- procore validate: ok.
- phase-08c-gates: ok=true, schema=35, all gates pass (incl amount_normalization, no_writeback..., cli_operator_status).
- no-writeback-proof: proof_passed=true.
- 08b-gates (from prior): automation_execution pass context, readiness_overstated=false.
- construction-agent validate: green.
- Evidence JSONs contain only field names, counts, classifications, reasons, lists, policy notes — zero raw payloads, zero secrets, zero URLs, zero float money values, zero bodies.
- Sensitive scan (grep forbidden patterns on JSONs): clean.
- Stops not tripped; README ledger accurate (08B closed, handoff to 08C financial readiness; no overstatement).
- Git: ancestor of dcecea8; LATEST=35; only new files + this arch will be staged.

## Artifacts
- `docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-endpoint-inventory-audit.json`
- `docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-table-inventory-audit.json`
- This file + index update in 00-README.md
- No src/ changes. No schema. 08C not closed.

**Package ref (for title only)**: HB_Construction_Intelligence_Phase_08C_Financial_Readiness_Implementation_Package/00_PACKAGE_MANIFEST.md (v1.4.0-phase-08c-planning per prompt; repo truth authoritative, package not read for claims).

**Commit discipline**: Staged only the 2 JSONs + this arch doc + 00-README index edit. Focused evidence. Traditional commit summary only output after land.

All per prompt guardrails + "repo truth authoritative" + "do not re-read context files" (used terminal/grep/python-CLI only for procore/endpoints/migrator/cli/store + prior evidence/arch). 

Next (if any): Prompt 03+ on 08C (not this).