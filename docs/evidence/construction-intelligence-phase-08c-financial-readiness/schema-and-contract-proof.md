# Phase 08C Prompt 01: Schema-and-Contract Proof

**Date:** 2026-06-03  
**Baseline HEAD:** `13b9733` (post P00 rebaseline on 08B closeout `dcecea8`)  
**Package:** `HB_Construction_Intelligence_Phase_08C_Financial_Readiness_Implementation_Package/00_PACKAGE_MANIFEST.md` v1.4.0-phase-08c-planning  
**Base schema:** V34 → **V35** (additive)

This proof documents the required tests: fresh DB migration, idempotency, guard checks (incl. new 08C financial_determination etc.), lifecycle inventory (161), contract load/validation. All per guardrails (no raw financial payloads, no float money, advisory outputs only).

## Verification Matrix (run during this prompt)

- `python -m compileall -q src` : exit 0
- `ruff check .` (in-scope): checks passed (pre-existing ruff issues in unrelated modules ignored per policy; focused on changed files had style notes only)
- `mypy src` (key files): success with benign notes (LATEST bump etc.)
- `pytest -m "not integration and not live and not manual" -q --tb=no` (focused): test_phase_08c_schema_v35.py ..... [100%] PASSED; test_data_quality_table_inventory.py (count assert updated) mostly pass (one unrelated cli sub test pre-existing)
- `construction-agent validate --json` : 4/4 (schema now 35 in runtime)
- `second-brain data-quality phase-08c-gates --json` : ok=true, schema_version=35, counts pass (after impl/patch), required gates from contract present
- `second-brain financial readiness --json` : ok=true, contract loaded, advisory_only, guardrails (no determination), note on empty tables
- `second-brain financial coverage/exposure-summary/review-items --json` : ok=true, contracts, advisory
- `second-brain data-quality no-writeback-proof --json` : proof_passed=true (new tables have guards, dynamic scan covers; 08C not breaking prior)
- Fresh DB migration (in v35 test + harness): _migrate(db) == 35, all 10 tables present + empty, DDL has all 13+ guards + advisory_only=1 CHECK + canonical_decimal_text/minor_units, no REAL for money
- Idempotency: re-migrate returns 35, schema_migrations count for 35 ==1
- Guard checks (v35 test + proof): all _V35_TABLES have the financial_source + determination + standard guards enforced (IntegrityError on violation)
- Lifecycle inventory: contract_table_count==161, 08C tables classified operational_empty_expected, phase_owner=08C, v=V35; reconciliation clean
- All phase_08c_* contracts load (via load_phase_08c_contract): data_quality_gates, financial_fact, amount_normalization (money_storage no float), coverage, exposure, etc. have advisory_only_required, no determination, etc.
- YAML seeds loadable (config).
- No raw financial/procore/prompt/response/urls or float money in any new table or output (enforced in DDL + contracts + cli/gates reports)

## Tables (V35)
See migrator V35_STATEMENTS (adapted from package resources/sql/phase_08c_schema_addendum.sql + 05 plan):
- 10 tables with full guard set (raw_email...raw_financial_source... + financial_determination_performed + payment_decision + claim_or... + external... + advisory_only=1)
- amount_facts_normalized: canonical_decimal_text TEXT, minor_units INTEGER (no float)
- All ship empty (operational_empty_expected)

## Contracts / Seeds Added
- 10 json in src/hb_assistant/resources/json/ + resources/json/ (packaged + fallback)
- 7 yaml in resources/config/
- Registered + loadable in second_brain/contracts.py
- 08c gates use the data_quality_gates_contract required_gates list

## CLI Surfaces (read-only)
- second-brain financial readiness/coverage/exposure-summary/review-items : contract-backed, advisory, no raw/det
- data-quality phase-08c-gates : evaluate + proof, 35, ok

## Stop Conditions
- No table stores raw financial payloads, raw prompts/responses, signed/download URLs.
- No money as float/REAL (TEXT + INTEGER minor only).
- All outputs advisory/review aids (no payment/claim/entitlement/forecast/determination).
- Dry-run posture preserved (read-only surfaces; apply not added here).

**No stop condition triggered.** Schema/contracts ready. 08C not closed.

Evidence generated from fresh runs at HEAD. See test_phase_08c_schema_v35.py for exact guard/migration asserts, and the v35 test + inventory for lifecycle/contract validation.

(Full outputs captured in session terminal logs + the runs above.)