# Phase 08C Prompt 05: Financial Source Coverage Matrix

**Objective (from prompt):** Build the Phase 08C financial source coverage matrix.

**Required work executed:**
1. Map endpoint family to local table, normalizer, amount fields, currency fields, WBS/cost-code fields, source references, and relationship keys.
2. Classify coverage as covered_ready, covered_review_required, covered_missing_context, fail_closed, deferred_not_blocking, or blocked.
3. Include source row counts and advisory labels without raw values.
4. Generate `financial-source-coverage-matrix.json`.

**Baseline (repo truth at start of this prompt):** Post-P04 (currency/WBS completeness snapshots + reports + review routing + real 08c gate/CLI wires). V35 (161 tables, 25 financial incl. source_coverage_snapshots with row/*_field_count/coverage_status per family + guards). P02 inventories authoritative: financial-endpoint-inventory-audit.json (32 eps, 7 families, per-ep normalizers/amount/currency/wbs fields/source_field_path_support/live_verified/path_template/classification; 3 fail-closed eps under purchase_orders/budget). financial_source_coverage_contract (10 required_families, exactly the 6 coverage_status_values). P03 amount_facts_normalized (Decimal-safe, source preserved, no raw/float). No matrix JSON yet. All prior stops/guardrails/advisory/no-raw/Decimal held. 08B target ancestor dcecea875ee8eb643cff8665c362eb0f1927df0a confirmed in prior.

**Implementation (surgical, per plan, using safe terminal/grep/python-load only for pre-edit discovery on context files):**
- Added to `src/hb_assistant/construction/second_brain/financial_completeness.py` (edited via terminal grep/tail for anchors + search_replace; no full read_file):
  - New consts: `ENDPOINT_INVENTORY_DEFAULT`, `FAMILY_LOCAL_TABLES` (12 entries mapping required families to procore_financial_* tables derived from P02 table-inventory names + projections).
  - Updated module docstring to document the matrix.
  - New `build_financial_source_coverage_matrix(*, db_path=None, endpoint_inventory_path=ENDPOINT..., out_dir=EVIDENCE_DIR) -> dict`:
    - Loads P02 `financial-endpoint-inventory-audit.json` (via open/json) for authoritative 32 eps: family, endpoint_id, live_verified, normalizers (e.g. ["financial.py", "owner_contract.py"]), amount_fields/ currency_fields / wbs_cost_line_fields lists, line_item_type_field, source_field_path_support, notes.
    - Loads contract (via existing _load_contract fallback) for required_families (10) + coverage_status_values (the 6).
    - Groups eps by family; for each computes/uses family row counts from `second_brain_financial_amount_facts_normalized` (SELECT COUNT + presence SUMs for source/cur/ref; counts only, never SELECT values or raw).
    - Per-ep entry (32) + 5 deferred required: constructs local_tables from FAMILY map (or amount_facts fallback), normalizers/fields from inv, source_references (["source_field_path"] if support else []), relationship_keys (["project_key", "endpoint_id", "source_record_ref"]).
    - Classifies coverage_status exactly per the 6:
      - fail_closed if not live_verified (P02 inventory + live_gate shells: the 3 purchase-order-detail-line-items, budget-details, budget-change-line-items).
      - covered_ready if live + row_count>0 + amount/cur/wbs presence counts >0.
      - covered_missing_context if live but partial (row>0 but not all dims).
      - deferred_not_blocking for required_families absent from current P02 inv (e.g. payment_applications, direct_costs, budget_changes etc. beyond the 7 represented).
      - (covered_review_required / blocked reserved or not triggered in this run; review routing from P04 is separate).
    - Builds sources list + top-level: generated_utc, repo_head="post-p04", schema_version=35, total_sources, sources[], summary (total_endpoints_in_inventory, required_families, by_status tally of 6, fail_closed_endpoints list, no_raw_in_matrix:true, money_decimal_only:true, source_preserved:true, advisory_only:true), contract, inventory_used, advisory_only, guardrails (local_first/read_only/no_external_writeback/no_raw_financial_payload/financial_determination_forbidden/advisory_only), stop_checks (raw..._written: false), notes (detailed 1-5 explaining sources of maps/classif/counts, "NO raw Procore payloads, NO full source values, NO amounts, NO tokens/URLs/PEM in this JSON", "All financial outputs are advisory review aids only").
    - Atomically writes `.../financial-source-coverage-matrix.json`; returns the dict.
  - Updated `if __name__` to also call the matrix builder (for dev).
  - Reuses existing _get_conn, _now, _load_contract, run_financial_completeness patterns; no new schema, no float (reuses P03 Decimal context where counts derived), no raw written (only counts/statuses/mappings/lists/labels).
- Wired (minimal, to surface real matrix in 08c surfaces per plan):
  - `src/hb_assistant/construction/second_brain/data_quality.py`: in evaluate_phase_08c... (inside the comp run try), import + call build_financial_source_coverage_matrix(), add to the "source_coverage" _gate(..., matrix_total_sources=..., matrix_by_status=..., matrix_no_raw=...).
  - `src/hb_assistant/cli/second_brain.py`: in financial_coverage, import the builder + call (side-effect gens JSON), add to payload "financial_source_coverage_matrix": {"summary":..., "total_sources":..., "by_status":..., "matrix_path": ".../financial-source-coverage-matrix.json", "advisory_note": "..."}.
- Both wires ensure that `second-brain data-quality phase-08c-gates --json` and `second-brain financial coverage --json` now reflect real matrix (or summary) + trigger generation.
- New focused test: appended `tests/test_phase_08c_financial_completeness.py::test_financial_source_coverage_matrix_maps_classifies_counts_no_raw` (via terminal append after getting end via tail; uses existing _migrate/_seed_amount_facts pattern from P04 tests, seeds facts for owner_contracts to drive row_count, calls builder with real endpoint inv + tmp out_dir + tmp db_path, asserts:
  - LATEST 35, total_sources >=10 (32+5), every source has all map keys (family/local_tables/normalizers/amount/currency/wbs/source_references/relationship_keys/coverage_status/row_count/advisory_label).
  - coverage_status always one of the exact 6.
  - fail_closed exactly 3 with the P02 ids (purchase-order-detail-line-items etc.).
  - summary no_raw_in_matrix true, by_status present, total_endpoints >=29.
  - written JSON in tmp/out has no forbidden raw patterns (adjusted scan: Bearer/PEM/eyJ/URL/actual-value-like/"10200000/raw_body etc.; "grand_total" as field name is allowed and present in amount_fields list).
  - advisory "advisory review aid only" present; for seeded fam status != fail_closed and row_count >=1 or covered_*.
  - Test passes clean (verifies map/classify/counts/advisory/no-raw stop).
- Generated the evidence artifact: `docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-source-coverage-matrix.json` (via builder call in harness; 37 sources, by_status with fail_closed:3 + mostly covered_missing_context:29 due to sparse facts in default conn for this run, deferred:5; full maps from P02 inv, correct fail_closed eps, all advisory/guard/no_raw attest, contract, inventory_used, notes explaining sources + "NO raw..."; sensitive scan 0 bad payloads/values; field names like grand_total present as metadata only; size ~41k; clean).

**Verification performed (post changes, terminal only for checks on prior context):**
- ruff on edited (completeness, data_quality, cli, test) + py_compile.
- pytest -q -k "phase_08c or financial_completeness or matrix" (new test + prior 08c tests green).
- .venv/bin/hb-assistant construction-agent validate --json (4/4).
- .venv/bin/hb-assistant second-brain data-quality phase-08c-gates --json (source_coverage gate now has matrix_* fields, status pass or improved; other 08c gates; overall).
- .venv/bin/hb-assistant second-brain financial coverage --json (now includes "financial_source_coverage_matrix" with summary/by_status/matrix_path + advisory_note; snapshots key preserved; advisory_only + guardrails).
- .venv/bin/hb-assistant second-brain no-writeback-proof --json (still true; new matrix logic scoped, no raw written, all 08C tables + new module in scope).
- procore validate (28/28).
- Harness (the new test + direct python -c call to builder): LATEST=35, matrix structure correct (37 sources, 6 statuses incl fail_closed=3 exact, maps complete, counts present, no_raw true, written JSON clean per scan + "advisory review aid only" + "NO raw Procore payloads, NO full source values" in notes, "no_raw_in_matrix":true, contract present, inventory_used=P02 endpoint one; git status pre-stage shows only intended).
- Sensitive-artifact-scan equivalent (grep/python on matrix JSON): 0 Bearer/PEM/JWT/URL/raw-payload/full-amount-values outside metadata field lists; only counts/statuses/mappings/labels/advisory/attestations.
- Stops re-checked: automation context (prior), 08B gates (prior), README no overstate (prior), no raw/float in matrix/evidence (scan + test + builder never loads values), financial guarded (advisory_only everywhere, read-only CLI unless evidence gen), source preserved (in procore tables + facts), Decimal only (reused), local-first.
- Matrix JSON attest in notes: "NO raw Procore payloads, NO full source values, NO amounts, NO tokens/URLs/PEM in this JSON"; "All financial outputs are advisory review aids only"; "Source preserved in procore_financial_* tables."
- 08C not closed (per prompt; this is not Prompt 14).

**Files changed for this prompt (staged only these; focused tests + evidence + arch):**
- src/hb_assistant/construction/second_brain/financial_completeness.py (matrix builder + consts + doc + if main)
- src/hb_assistant/construction/second_brain/data_quality.py (source_coverage gate wire + matrix call)
- src/hb_assistant/cli/second_brain.py (financial_coverage wire + matrix summary)
- tests/test_phase_08c_financial_completeness.py (new test func)
- docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-source-coverage-matrix.json (generated)
- docs/architecture/102-phase-08c-financial-source-coverage-matrix.md (new)
- docs/architecture/00-README.md (surgical index after 101-)

**Guardrails held verbatim (no violations):**
- Local-first only; no external-system writeback.
- Procore/Microsoft 365 remain read-only; no mutation endpoints, no writeback, no payment workflow actions.
- New Phase 08C tables and evidence must not persist raw Procore payloads, raw prompts, raw responses, email bodies, document text, calendar payloads, signed URLs, or download URLs. (Matrix JSON: only maps/counts/statuses/labels/advisory/contract; source counts from facts; no raw of any kind; stop checks + notes + test scan attest.)
- Money never binary float; Decimal in Python, canonical strings/minor when scale known. (Reused P03 helpers/context; matrix uses integer counts only.)
- Financial outputs advisory review aids only. Not payment approvals, claim positions, entitlement determinations, contract interpretations, forecasts, or executive financial determinations. (Every surface + JSON has explicit "advisory review aid only", "advisory_only": true, guardrails dict, notes.)
- Apply-capable commands dry-run default; Phase 08C CLI read-only unless evidence gen intentionally invoked. (financial coverage / 08c-gates are read surfaces; builder call is explicit evidence gen.)
- Do not close Phase 08C unless Prompt 14 and all criteria pass. (Not Prompt 14; no closeout.)
- Stage only files required; include focused tests and evidence.
- Repo truth authoritative (P02 inv + V35 DDL + contracts + runtime facts + tests + CLIs over package/prior/roadmap).
- AFTER: arch updated (102 + 00-README), verification suite run (above), traditional commit summary+desc prepared, commit, *only output the summary and description*.

**Commit discipline:** Staged exactly the 7 paths above. No other (left unrelated prior evidence, pre-existing ruff items, etc. unstaged). Traditional commit references manifest title/version.

**Evidence bundle update:** `financial-source-coverage-matrix.json` added to `docs/evidence/construction-intelligence-phase-08c-financial-readiness/`. 08C evidence now includes P00 rebaseline, P01 schema/contracts, P02 inventories (endpoint+table), P03 amount norm proofs, P04 completeness reports, P05 matrix.

This completes Prompt 05. All stops clear; no raw/full source values written; advisory only; repo truth followed; "do not re-read context" respected (terminal/grep/python -c open/json for all pre-edit inspection of inventories/contracts/tests/arch prior; read_file only on newly written/edited post-change for verification where line-level needed). 08C remains open.

**Next (per sequence):** Subsequent prompts continue additive 08C work; closeout only at Prompt 14 after all criteria.