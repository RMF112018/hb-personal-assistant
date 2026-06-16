# Workflow 13 — Forecast Comprehensive

Top-level integration layer. Run it after the accepted intelligence / monthly / probability /
history-informed packages exist; it discovers and consumes them (and auto-generates cost-frequency into
the data root if absent) into one integrated, human-reviewable forecast.

## Run

```bash
cd subrepos/construction-financial-review
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-comprehensive \
    --project tropical --frozen-stamp 20260101_000000 --out-root /tmp/fc
```

`--with-llm` adds advisory (non-numeric) narratives for review-queue items. Omit `--frozen-stamp` for a
live timestamped package under the data root. If no cost-frequency package is on the data root, the run
generates one first (additive, deterministic) then consumes it; otherwise it degrades with an explicit
`cost_frequency_package_missing` warning recorded in `audit/frequency_consumption_audit.json`.

## What it produces

`forecast_comprehensive_package_tropical_<stamp>/`:

- `integrated_forecast_by_budget_code.jsonl` — master per-code row (accepted vs integrated final cost +
  CTC, bounded history weight, six `*_consumption_status` fields, human-acceptance fields).
- `integrated_evidence_registry_by_budget_code.jsonl` / `integrated_evidence_weights_by_budget_code.jsonl`
  — normalized evidence + bounded de-duplicated weights with reason codes.
- `integrated_final_cost_recommendations.jsonl`, `integrated_monthly_forecast_by_budget_code.jsonl`,
  `integrated_monthly_project_forecast.jsonl`, `integrated_probability_by_budget_code.jsonl`,
  `integrated_probability_project_summary.json`.
- `integrated_risk_register.jsonl`, `integrated_human_review_queue.jsonl`,
  `integrated_change_explanation.jsonl`, `evidence_conflict_register.jsonl`, `model_package_inventory.json`,
  `project_comprehensive_forecast_summary.json`, `top_*`, `data_quality_warnings.jsonl`.
- `audit/*` — evidence_registry, evidence_weighting (no-double-count), history_consumption,
  frequency_consumption, monthly_reconciliation (per-code + project), probability_adjustment
  (deterministic, non-MC), no_upper_cap, actuals_floor, **model_evidence_completeness_matrix**,
  source_packages_used, source_hashes_before_after, safety_scan. `README.md`/`SCHEMA.md`/`manifest.json`/
  `input_inventory.json`/`validation_report.json`. `llm/*` advisory, excluded from determinism.

## How a reviewer reads it

- **`project_comprehensive_forecast_summary.json`** — packages consumed/missing, codes covered,
  integrated totals (accepted vs integrated final + delta), conflict counts by class, review-item count.
- **`audit/model_evidence_completeness_matrix.json`** — every model output: discovered / consumed /
  partially_consumed / downgraded / missing / intentionally_excluded / blocked_by_validation.
- **`integrated_human_review_queue.jsonl`** (priority-ordered) + **`evidence_conflict_register.jsonl`**
  (seven classes) — what a human must adjudicate; each row is `acceptance_status: pending`.
- **`integrated_forecast_by_budget_code.jsonl`** — per code, the accepted base vs the integrated
  recommendation, which families were accepted/downgraded/rejected (`reason_codes` + consumption
  statuses), floored at actuals, never capped.
- **`audit/monthly_reconciliation_audit.json`** — proves Σ integrated monthly == integrated CTC per code
  and at the project total. **`audit/probability_adjustment_audit.json`** — confirms the deterministic
  (non-Monte-Carlo) method + seed.

## Accepted vs pending

This package PROPOSES an integrated forecast; nothing is formally accepted. The standalone intelligence /
monthly / probability packages remain authoritative. An operator reviews and accepts/rejects per code;
there is no live acceptance store, so every recommendation stays `pending`.

## Guardrails

- CostEntries/Sage incurred cost is accounting truth; actual cost to date is the only hard floor; no
  evidence is ever a hard cap.
- Accepted intelligence is the base final cost; advisory evidence is bounded + contradiction-collapsed +
  de-duplicated by independence group.
- Cost-frequency shapes monthly timing + timing-risk only — never final cost by itself.
- Probability is a deterministic transform of the accepted package, not a fresh Monte Carlo.
- No source / accepted package / SQLite / Excel mutation; no live external calls (localhost Ollama only).
- Deterministic: same frozen stamp + same input packages ⇒ byte-identical quantitative core.
