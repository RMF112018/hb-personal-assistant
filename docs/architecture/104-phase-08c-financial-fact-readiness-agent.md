# Phase 08C Prompt 07: Financial Fact Readiness Agent

## Scope (from manifest)
Implement the deterministic Financial Fact Readiness Agent controller.

Required:
1. Add an agent module consistent with existing second-brain agent architecture.
2. Orchestrate inventory, amount normalization, completeness checks, source coverage, exposure marts, forecast-readiness gates, and review-required outputs.
3. Emit an agent run receipt with guard columns and advisory labels.
4. Ensure model use is absent or strictly optional/mock-safe and never required for deterministic readiness.
5. Generate `financial-readiness-agent-proof.json`.

Stop if the agent makes, implies, or persists a financial determination.

## Approach
- The "agent module" is the orchestration controller in `construction/second_brain/financial_completeness.py` (the established 08C financial fact layer, consistent with P03-P06 sub-builders and 08B agent receipt pattern via V35 table).
- `run_financial_fact_readiness_agent` calls/collects from subs (run_financial_completeness for amount/completeness, build_*_coverage, build_exposure_mart_preview, forecast/review via contracts or gates), aggregates items_evaluated + review_required_count.
- Emits receipt: INSERT to second_brain_financial_readiness_agent_runs (run_id, project_key, status, counts, all 19 guard CHECK cols: advisory_only=1, no raw_*, no *_decision_performed).
- Proof JSON: financial-readiness-agent-proof.json with run_id/status, sub_results (coverage/exposure summaries etc.), guardrails (model_use: "absent_or_mock_safe_only"), notes ("deterministic orchestration... advisory review aids only — no determinations..."), stop_checks (no raw, no determination, no model required).
- Wiring: "second-brain financial readiness --json" (CLI) calls agent, surfaces agent_run_receipt + proof_path + summary.
- "readiness_agent" gate (in 08C data-quality) calls agent, asserts status/advisory/guards/no det.
- Model: the agent itself has zero LLM dep; subs are deterministic (facts/signals/tables). Optional mock only if a sub (e.g. review) needs classification.
- All prior P01-P06 + V35 + contracts + agents/ architecture (for consistency note) reused.

## Key Artifacts
- financial_completeness.py (agent fn + receipt + proof writer).
- cli/second_brain.py (readiness cmd now runs agent + proof_path).
- data_quality.py (readiness_agent gate real).
- test_phase_08c_financial_completeness.py (agent test: receipt, proof, CLI, no model/det).
- Generated: financial-readiness-agent-proof.json (in 08C evidence).
- Arch: this file + 00-README entry.

## Verification (executed)
- ruff/format/mypy on touched py (surgical).
- pytest -k "readiness or agent or fact" (new test passes).
- 08C CLIs: construction-agent validate, second-brain financial readiness (real receipt + proof_path + summary), coverage/exposure/review, data-quality phase-08c-gates (readiness_agent pass), no-writeback-proof.
- Python attest on proof: has run_id/status, items_evaluated, review_required_count, sub_results, guardrails (advisory_only, financial_determination_forbidden, model_use absent_or_mock), notes ("deterministic", "advisory review aids only", "no model required"), stop_checks (raw false, determination false); no positive "final determination"/claim/entitlement/forecast language; no raw values in text.
- DB: row in readiness_agent_runs with matching guards/counts.
- git staged exactly the 7 required for this prompt.
- No stop violations.

## Commit
Traditional per manifest (title with 00_PACKAGE_MANIFEST.md + v1.4.0... — Prompt 07: Financial Fact Readiness Agent). Staged only the 7. 08C not closed. All outputs advisory; model absent for core readiness.

See the generated proof json + session evidence for full attestation.
