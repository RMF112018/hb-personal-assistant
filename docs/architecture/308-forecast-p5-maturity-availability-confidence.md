# 308 — Forecast P5: maturity / data-availability / confidence completion (Gap 5)

- Status: accepted
- Date: 2026-06-24
- Phase: forecast-model remediation P5
- Gap: #5 (maturity / data-availability / confidence completion)

## Context

The decision-support engine (`construction/forecast/decision_support_engine.py`) persists a per-run
maturity snapshot and per-domain data-availability profiles, but key derivations were stubbed to
`None`, so the layer under-reported project state:

- `_maturity_tier` returned only M0–M4 ("M5 closeout deferred"); `lifecycle_signal` was hardcoded
  `None`.
- Data-availability came **only** from the v59 source-domain tables; the
  `owner/commitment/schedule/staffing` domains were **always "unavailable"** — even when the run's
  v63 output tables had rows.
- `completeness`, `mapping_quality`, `maturity`, `score` were `None` in every availability row.

All target columns already existed in the V66 DDL → **no migration**. The fix is pure derivation
logic. The decision-support engine writes only to a NON-LIVE temp DB (`is_live_db_path` guard) and
changes no forecast dollar values, so P5 ships **default-on (no flag)** — completing the derivation
is the spec's intended default behavior.

## Decision

1. **M5 closeout + `lifecycle_signal`.** `_maturity_tier` gains an M5 tier driven by output evidence:
   when the run has outputs and the header `forecast_outputs.cost_to_complete /
   estimated_final_cost <= M5_CLOSEOUT_CTC_FRACTION` (named constant `0.005`), the project is in
   closeout. A **ratio**, not absolute dollars, so a small retainage/warranty residual does not
   block it; the already-aggregated header is used (no re-sum of budget-code rows). `lifecycle_signal`
   is a coded enum per tier via `_LIFECYCLE_SIGNAL` (`pre_start`/`mobilizing`/`in_progress`/`mature`/
   `closeout`) — path-free, safe for the read-model/API surface.

   **Accepted risk:** a project stalled with budget exhausted *before* completion produces the same
   near-zero CTC and would be labeled closeout. The engine has no source signal to distinguish a
   genuine closeout from a stall; this is recorded as accepted for P5 (a future maturity/lifecycle
   signal — e.g., schedule % complete — could disambiguate).

2. **Output-aware, multi-domain availability.** Domains backed by a v63 output table
   (`commitment`→`forecast_output_commitment_exposure`, `schedule`→`forecast_output_schedule_phasing`,
   `changes`, `risk`, `probability`, `staffing`) flip to "available" when the run's rows exist,
   counted via a **two-hop join** (`child.output_id → forecast_outputs`, scoped by **both** `run_id`
   AND `project_key`, helper `_count_output_rows`). `assumptions` is counted run-scoped from the v66
   assumption tables. `owner` and `procore` have **no forecast backing table** (procore lives in the
   schedule source domain) and remain "unavailable" with an explicit coded reason.

3. **Populate `completeness` / `mapping_quality` / `maturity` / `score`.** For per-code output
   domains: `mapping_quality` = distinct domain budget_code_keys that resolve to a
   `forecast_budget_details` code ÷ distinct domain codes; `completeness` = mapped codes ÷ budget-code
   universe; both deterministic 4dp ratios (`_ratio`). `maturity` = the project tier on every row.
   `score` = the **availability-gated completeness** (a single count-derived ratio for per-code
   domains; the availability flag `1.0000`/`0.0000` otherwise) — **not** a multi-metric blend. The
   engine `GUARDRAILS["new_scoring_math"]` is updated from `False` to
   `"deterministic_count_derived_availability_score_only"` to name exactly this; no model/ML scoring
   is invented.

## Scope / deferrals

- The **confidence scorecard numeric `score`** stays `None` (deferred — it needs the accuracy
  artifact; an explainability concern, closer to P8).
- `owner` / `procore` availability stay unavailable (no forecast backing table — documented).
- No new schema/migration; no CFR change; no opt-in flag; no live-DB write.

## Validation

- New `tests/test_forecast_p5_maturity_availability.py` (added to the forecasting bundle): lifecycle
  staging M0–M4, M5 closeout vs material-CTC, output-aware availability (commitment/schedule flip;
  owner/procore stay unavailable), per-code completeness/mapping_quality values, maturity+score on
  every row.
- `scripts/test-forecasting.sh` + `scripts/test-schedule.sh` green. No live-DB write; temp/copied-DB
  only. Coded `lifecycle_signal`/`score` values are path-free (pass `find_redaction_leaks`).
