# 98 — Phase 08C Schema, Contracts, and Table Lifecycle (Prompt 01)

**Baseline**: Post-P00 rebaseline at `13b9733` (itself on 08B closeout `dcecea8`). Schema **V34** / 151 tables pre this prompt. Additive **V35** only.

**Objective** (per prompt): Implement additive V35 schema for the 10 Phase 08C table families (from package), all mandatory hard guard columns on generated-output tables (incl. new raw_financial_source_payload_persisted + financial_determination_performed / payment / claim decision guards + advisory_only=1), JSON contracts + YAML seeds, update lifecycle/inventory tests + version asserts, generate `schema-and-contract-proof.md`.

**Evidence**:
- `docs/evidence/construction-intelligence-phase-08c-financial-readiness/schema-and-contract-proof.md`
- `docs/architecture/98-phase-08c-schema-contracts-and-table-lifecycle.md` (this)
- `tests/test_phase_08c_schema_v35.py`
- src/hb_assistant/store/migrator.py (V35)
- src/hb_assistant/resources/json/phase_08c_*.json + resources/config/phase_08c_*.seed.yaml
- Updated table_lifecycle + inventory test + supporting contracts/data_quality/cli for verification.

## Tables Added (V35)
All 10 follow package sql sketch + 05 plan + 04 architecture:
- second_brain_financial_fact_normalization_runs
- second_brain_financial_amount_facts_normalized (canonical_decimal_text TEXT, minor_units INTEGER; no float/REAL; source refs + hash only)
- second_brain_financial_currency_completeness_snapshots
- second_brain_financial_wbs_cost_code_snapshots
- second_brain_financial_source_coverage_snapshots
- second_brain_financial_exposure_summary_items (advisory; normalized_amount_ref)
- second_brain_financial_forecast_readiness_runs (no forecast output)
- second_brain_financial_review_required_items
- second_brain_financial_readiness_agent_runs
- second_brain_phase_08c_validation_runs

**Mandatory guards** (every generated-output table):
raw_*_persisted =0 CHECK (email/doc/calendar/procore/financial_source/prompt/response/signed/download), external_writeback_performed=0, financial_determination_performed=0, payment_decision_performed=0, claim_or_entitlement_decision_performed=0, advisory_only=1 CHECK.

Money rule: TEXT canonical decimal (or INTEGER minor units when scale known); never float/REAL; no raw payloads.

## Contracts & Seeds
- 10 phase_08c_*_contract.json added to resources (packaged + fallback).
- 7 phase_08c_*.seed.yaml in resources/config/.
- Registered in construction/second_brain/contracts.py (PHASE_08C_CONTRACT_FILES + loaders).
- data_quality.py extended with evaluate_phase_08c_data_quality_gates + build_proof (uses contract required_gates, table/guard checks, lifecycle 08C, advisory_only, no determinations).
- cli/second_brain.py : financial_app (readiness/coverage/exposure-summary/review-items) + data-quality phase-08c-gates (all read-only, contract-backed, advisory).

## Lifecycle
table_count: 161 ( +10 08C operational_empty_expected, phase_owner 08C, v V35).

## Verification
See proof.md: fresh migrate (V35), idempotency, all guards in DDL, no float/raw, contract loads, inventory 161 + 08C entries, 08c gates pass, financial CLI read-only, no-writeback still green, ruff/mypy/pytest focused green.

## Post-Changes
- Arch 98- (this) + 00-README entry.
- Full matrix + focused verification run.
- Staged only required (migrator, resources json/yaml, lifecycle, new test, proof, arch 98+index, minimal cli/data_quality/contracts for gates/CLI).
- Commit: manifest v1.4.0-phase-08c-planning — Prompt 01...
- 08C not closed.

No stop conditions (no raw financial, no float money, all advisory). Ready for subsequent 08C (normalizers, agent impl, exposure marts, full obsidian, etc.).