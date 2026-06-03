# Phase 08C Prompt 08: Forecast Readiness Gates

## Scope (from manifest)
Implement gates that determine readiness for trend analysis without generating forecasts.

Required work:
1. Implement gate evaluator with pass/warning/fail/deferred statuses.
2. Gate amount normalization, currency completeness, WBS/cost-code completeness, source coverage, relationship completeness, review backlog, no-writeback/no-raw proof, and advisory labeling.
3. Emit `forecast-readiness-gates.md` and `forecast-readiness-proof.json`.
4. Ensure wording says readiness report, not forecast.

Stop if outputs create forecast decisions or recommendations treated as final.

## Approach
- The gate evaluator lives in `construction/second_brain/financial_completeness.py` (the established 08C financial fact layer, consistent with P03-P07 sub-builders and agent orchestration).
- `evaluate_forecast_readiness_gates` (new): loads contracts (forecast_readiness_contract for 4 gate_status + 5 readiness_status + guards incl. forecast_output_allowed=False; data_quality_gates), loads prior artifacts (matrix for source_coverage, exposure for relationship, agent-proof for review count, norm for amount) or V35 fallback counts (never values/payloads); evaluates the 8 gates deterministically with conservative/fail-closed logic per contracts (amount_normalization from facts/norm count; currency/wbs from matrix/snapshots; source_coverage from matrix by_status fail_closed==0; relationship from exposure items/relationship_kind; review_backlog from agent count; no_writeback_no_raw from prior proofs stop_checks + flags; advisory_labeling from labels present on items); derives overall gate_status (pass/warning/fail_blocking/deferred_not_blocking) and readiness_status (5 vals for V35 table); INSERT OR REPLACE to second_brain_financial_forecast_readiness_runs (run_id, readiness_status, gate_status, counts, 19 guard CHECKs=1/0); builds and atomically writes forecast-readiness-proof.json (machine: gates[8], summary, guardrails, notes with "This is a forecast readiness report only...", stop_checks.forecast_decision_made=false) and forecast-readiness-gates.md (human: # Forecast Readiness Report, ## Summary, ## Gates table/list, ## Guardrails, ## Notes with exact "readiness report only... No forecasts are computed or recommended... advisory... Stop if...", ## Artifacts Used).
- Update to run_financial_fact_readiness_agent (same file): replace forecast stub with real call to evaluate... + sub_results["forecast_readiness"] = {readiness_status, gate_status, summary, proof_path, md_path}.
- Wiring in data_quality.py: in evaluate_phase_08c_data_quality_gates, replace the "forecast_readiness" stub append with try: fr = evaluate_forecast_readiness_gates(...); _gate("forecast_readiness", fr["gate_status"], readiness_status=..., proof=...); except warning. (import added).
- Model/decision: zero LLM; pure facts + counts + prior meta + contract flags. Explicit guard forecast_output_allowed=False; all notes/md/proof/return use only "readiness report", "support future (not performed here) trend analysis", "No forecasts are computed or recommended.", "advisory review aid only — not a final... or trend", stop_checks.forecast_decision_made=false. Test + harness enforce + scan.
- All prior P05 matrix, P06 exposure, P07 agent + V35 tables + 08C contracts reused (artifacts for meta only).
- 7 files only (completeness + data_quality + test + 2 generated evidence + 105 + 00-README); no cli edit (existing readiness and data-quality surfaces now real).
- Evidence + arch + verif + precise stage + traditional commit per manifest; 08C not closed.

## Key Artifacts
- financial_completeness.py (evaluator fn + V35 run + md/json writes + agent sub update).
- data_quality.py (forecast_readiness gate real in 08c evaluate).
- test_phase_08c_financial_completeness.py (focused test for evaluator: 8 gates, statuses, wording, DB, no decision, CLI).
- Generated: forecast-readiness-gates.md + forecast-readiness-proof.json (in 08C evidence).
- Arch: this file + 00-README entry.

## Verification (executed)
- ruff/format/mypy on touched py (surgical).
- pytest -k "forecast or gate or readiness" (new test passes).
- 08C CLIs: construction-agent validate, second-brain financial readiness (real forecast sub + proof ref), second-brain data-quality phase-08c-gates (real forecast_readiness gate + status + proof/md paths).
- Python attest on proof: 8 gates with allowed statuses, readiness in 5, guardrails (forecast_output_allowed:false), notes ("readiness report only", "No forecasts..."), stop_checks.forecast_decision_made:false, no raw/decision lang; md contains exact wording + gates list.
- DB: row in forecast_readiness_runs with guards + matching statuses/counts.
- git staged exactly the 7 required for this prompt.
- No stop violations (no forecast decision created).

## Commit
Traditional per manifest (title with 00_PACKAGE_MANIFEST.md + v1.4.0-phase-08c-planning — Prompt 08: Forecast Readiness Gates). Staged only the 7. 08C not closed. All outputs "readiness report" + advisory; no forecasts/decisions.

See the generated gates.md + proof json + session evidence for full attestation.