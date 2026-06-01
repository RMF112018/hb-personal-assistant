# 40 — Phase 07C: Data Quality Gates (document intelligence)

**Phase:** 07C (Document Intelligence Promotion) — Prompt 11.
**Status:** Implemented and live.
**Evidence:** `docs/evidence/construction-intelligence-phase-07c-document-intelligence/11-data-quality-gates.json`.

Adds six machine-readable, deterministic, offline data-quality gates for the V24 document-intelligence chain to
`construction-agent data-quality gates` (the seventh, `document_card_population_status`, already existed). No
schema change — `data_quality_gate_results.gate_name` is free-text.

## The six 07C gates

`construction/data_quality/gates.py`, each `future_phase="07C"`, boolean (`is_boolean=True`) so the status stays
within the allowed vocabulary (pass / warning / fail_blocking / deferred_not_blocking / not_applicable):

- **`document_classification_coverage`** — every materialized card has a classification candidate
  (`COUNT(DISTINCT document_card_id)` in classification ≥ card count).
- **`document_project_match_coverage`** — every card has a project-match candidate.
- **`document_extraction_eligibility_status`** — no card is still `extraction_eligibility='not_evaluated'`.
- **`document_relationship_population_status`** — document→record relationship candidates have been generated
  (presence; relationships are advisory/sparse).
- **`document_source_scope_compliance`** — `evaluate_source_scope_compliance(load_source_registry(),
  load_document_source_policy())["all_compliant"]`; load failure → `not_applicable`.
- **`document_intelligence_safety_scan`** — a runtime safety check over the six V24 tables: the guard CHECK columns
  sum to 0 **and** there are zero URL/token/secret pattern hits (`http(s)://`, `token=`, `access_token`,
  `bearer `, `-----begin`) across the persisted hashed/typed evidence columns (`signals_json`,
  `source_reference_json`, `preview_redacted`, `warnings_json`). The observed value is a boolean — the offending
  text is never read into the report (LIKE-counted in SQL only).

The six run in `run()` immediately after `_gate_document_card_population`, are listed in `_CORE_GATE_NAMES` and
`_PHASE_ASSIGNMENTS`, and are appended to `meeting_prep_prerequisites` in
`resources/json/phase_07b_data_quality_gates.json`.

## Readiness integration

`meeting_prep_readiness` is driven by `meeting_prep_prerequisites`; `ready` is true only when **no** prerequisite
is non-pass, and `auto_readiness_allowed` stays false. Adding the six 07C gates can only *add* potential blockers,
never flip `ready` to true — so **missing/incomplete 07C data blocks readiness** (the prompt's requirement)
without overstating 07D readiness. When 07C data is absent a gate returns `deferred_not_blocking` (falsy
observed + future_phase) and appears in `blocked_by`.

## Live result

21 total gates. The new gates: `document_classification_coverage`, `document_project_match_coverage`,
`document_extraction_eligibility_status`, `document_relationship_population_status`,
`document_intelligence_safety_scan` all **pass**; **`document_source_scope_compliance` is
`deferred_not_blocking`** — a truthful finding: the live source registry contains at least one source that is not
scope-compliant under the document source policy (e.g. a OneDrive scope without an explicit folder allowlist), so
`all_compliant=false`. `meeting_prep_readiness.ready=false`, `blocked_by=[document_source_scope_compliance,
review_required_routing_presence]`, `meeting_prep_readiness_claim="blocked"` — readiness is correctly **not**
overstated. The gate name→status map is identical across `PYTHONHASHSEED` 1/2/3. `raw_content_leakage_scan` /
`external_writeback_scan` / `document_card_population_status` remain pass.

## Guardrails / deferrals

Gates are machine-readable JSON, deterministic, offline; persisted only to the local `data_quality_gate_results`
table (no external writeback). The safety gate emits a boolean/count — never raw text. No card mutation, no
auto-promotion, no 07D readiness overstatement. This prompt adds a **runtime data-quality gate** over the V24
tables; the **static no-writeback / no-secret / no-raw-text proof** over those same tables remains deferred to
**Prompt 12** (not claimed here). Final 07C validation/closeout is Prompt 13.
