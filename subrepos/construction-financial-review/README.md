# Construction Financial Review

Deterministic, local-first toolkit for construction financial forecast review, owner/Procore scope
crosswalk application, and review-package generation. It consumes locally-generated forecast packages
and an authoritative owner SOV scope crosswalk and emits structured JSON/JSONL review artifacts. It
makes **no live external calls** and performs **no database, Excel, or source mutation**.

## Current proven workflow

1. **Forecast context package** — consolidate BudgetDetails, CostEntries, owner pay-apps, and Procore
   subcontractor pay-apps into one agent-ingestible context package with deterministic mapping.
2. **Forecast analysis package** — per-budget-code forecast recommendations, risk register, and
   evidence alignment (review only).
3. **Mapping-discrepancy workpaper** — explain owner-vs-Procore mismatches as structural vs true
   progress discrepancies; emit advisory recalibration inputs.
4. **Authoritative owner SOV scope crosswalk** — the user-approved scope relationships
   (`config/crosswalks/tropical/`).
5. **Crosswalk-aware forecast analysis v2** — compare owner vs Procore vs actuals at the correct
   owner-scope rollup level using the authoritative crosswalk.
6. **Schedule-integrated forecast** — layer the P6/XER-derived schedule package onto the crosswalk-v2
   recommendations as **timing / remaining-work / sequencing / risk** evidence: remaining-exposure
   flags, forecast-exhaustion risk, decrease guardrails, and a cash-flow timing curve. Schedule data
   never becomes actual cost and never sets a number on its own
   (`docs/workflow/06_schedule_integrated_forecast.md`).
7. **Forecast accuracy & confidence** — independent multi-method EAC/ETC estimates (burn-rate, owner
   %-complete, commitment floor, schedule ETC, CPI proxy) reconciled into an **advisory**
   `model_recommended_projected_cost` (floored to actuals, human-gated), a **backtest-calibrated** 0-1
   confidence, ERP forecast-adequacy flags, and an optional advisory **local-Ollama** narrative layer.
   Accounting actuals stay truth; nothing overrides them
   (`docs/workflow/07_forecast_accuracy.md`).
8. **Forecast intelligence / monthly / probability** — anticipated final cost + overrun detection,
   month-by-month time-phasing, and a Monte Carlo probabilistic validation of the estimate
   (`docs/workflow/08_*`, `09_*`, `10_forecast_probability.md`).
9. **Forecast history-informed** — additive evidence layer that mines prior cash-flow + GC/GR forecast
   assumptions and validates each against CostEntries actuals, surfacing **advisory** recommendations,
   confidence/uncertainty shifts and monthly-shape signals. Historical forecast is prior-assumption
   evidence — never actual cost, never a cap; nothing accepted is mutated
   (`docs/workflow/11_forecast_history_informed.md`).
10. **Forecast cost-frequency / billing-cadence** — additive evidence layer that classifies each
    canonical code's cost-incurrence cadence from real CostEntries (transaction dates + per-month entry
    counts), recognizes the configured weekly internal-staffing codes with weekday-normalized daily
    rates from the latest **complete** actual month, revalidates cadence before each run, and emits
    **advisory** monthly phasing. The same cadence logic is wired into **forecast monthly** as an
    additive timing source (staffing codes phase by weekday count) — timing/shape only; cost-to-complete
    and accepted final cost are reconciled and unchanged (`docs/workflow/12_forecast_cost_frequency.md`).
11. **Forecast comprehensive** — top-level integration layer that **discovers and consumes** every
    accepted evidence package (context, intelligence, monthly, probability, history-informed,
    cost-frequency; crosswalk-v2 + schedule-integrated for completeness) into a per-budget-code evidence
    registry, scores advisory evidence at **bounded, de-duplicated** weights with explicit
    accept/downgrade/reject reason codes, and emits integrated final-cost / monthly / probability
    recommendations with full lineage, an evidence-conflict register, and a human-acceptance review
    queue. Accepted intelligence is the base; CostEntries are truth; actual cost to date is the only
    floor; no evidence is a cap; cadence shapes timing only; probability is a **deterministic transform**
    of the accepted package (not a fresh Monte Carlo). Standalone packages are never mutated
    (`docs/workflow/13_forecast_comprehensive.md`).
12. **Forecast improvement audit** — additive, advisory, read-only audit that validates the seven
    forecasting-priority improvements against repo + data truth and implements each only where the
    available JSON packages / SQLite tables support it: a Basis of Estimate (+ coverage audit),
    calibration enhancements with sample-size/denominator guards, actual-cost lag diagnostics, a schedule
    cost-loading readiness posture, GC/GR behavior classification, change-order exposure from the
    read-only DB, and the **fee projected-budget cap** governance. CostEntries are truth and the only
    floor; reference values never cap NON-fee forecasts, but FEE codes (currently `20-18-110 CONTRACTORS
    FEE`) **are** capped by the projected budget value subject to the actuals floor (missing cap value →
    data gap, never an invented cap). Nothing is applied into accepted outputs; unsupported pieces are
    reported as data gaps (`docs/workflow/14_forecast_improvement_audit.md`).
13. **Forecast controls** — operator-controlled stop-date / closeout-constraint layer. Loads a
    project-level operator control file, maps each control to a canonical budget code, resolves
    precedence (**accepted > pending**), and emits applied decisions, a monthly-adjustment preview, a
    human-review queue, warnings, and fail-closed audits. A posture-changing control (post-stop zeroing
    or a dollar change) applies ONLY when human-accepted; pending controls are queued, not applied.
    Consumed by `forecast-monthly` (stop-date timing) and `forecast-comprehensive` (the
    `operator_forecast_control` evidence family + conflict register). CostEntries are truth and actual
    cost to date is the only floor — no hidden caps; stop-date timing without an accepted amount keeps
    the dollar total model-derived (`docs/workflow/15_forecast_controls.md`).
14. **Forecast staffing plan** — operator-supplied planned-staffing forecast layer. Discovers + validates
    the extracted staffing JSON package, resolves each source cost code to a canonical `.LAB` budget-code
    key (**LAB-only numeric**, allocation 1.0000; the `.LAB`/`.LBN`/`.MAT` family is date-context only),
    and emits the per-code **bridge** (actual / accepted vs plan-implied final + CTC / deltas), BOTH the
    plan-implied and current-CTC-reconciled monthly forecasts, a mapping review queue, conflicts (incl.
    `staffing_plan_conflicts_with_current_accepted_ctc`), warnings, and fail-closed audits. A cost code
    applies numerically only when it resolves to exactly one `.LAB` AND an operator override accepts it;
    ambiguous / unmapped / pending codes are review-only. Consumed by `forecast-cost-frequency` (the plan
    is the forward-looking timing source; cadence preserved as diagnostic), `forecast-monthly` (plan
    timing shape; rows disclose plan-implied vs CTC-reconciled applied amounts), and
    `forecast-comprehensive` (the `operator_staffing_plan` evidence family + conflict register). The plan
    never hides a stale accepted CTC; plan-driven final-cost changes are advisory until operator
    acceptance. CostEntries are truth and actual cost to date is the only floor — no hidden caps
    (`docs/workflow/16_forecast_staffing_plan.md`).

## Current project supported

Tropical World Nursery Senior Living Facility — `tropical` / `23-435-01` / `2026-June`.

## Data posture

Local files only. No live external calls (no Procore/Sage/Graph/SharePoint/OneDrive/email/calendar).
No DB mutation, no Excel mutation. JSON/JSONL outputs. Deterministic validation and safety scan on
emitted artifacts. Outputs are written only to new timestamped package folders.

## Core rules

- BudgetDetails is the **master budget-code universe** (keys are never invented).
- CostEntries are **accounting actual-cost truth**.
- Owner pay apps are **owner-recognized billing/progress evidence**.
- Procore pay apps are **subcontractor/vendor progress evidence**.
- The **authoritative crosswalk governs** owner/procore scope relationships.
- **No fuzzy matching** (no description-only, edit-distance, or semantic matching).
- **No pay-app value replaces actual cost.**

## Approved Tropical decisions

- `budget_amount = budget_amounts.revised_budget`
- `current_projected_cost = budget_amounts.projected_costs`
- materiality = **$25,000 AND 10%**
- actuals exceeding projected cost **floor the forecast up to actuals** (floor-to-actuals increase)
- owner/procore comparisons use the **owner-scope rollup** with **sell-value-vs-cost caution**
- `10-XX-XXX` is **description-sensitive** (GENERAL REQUIREMENTS vs non-GR)
- **all 127** canonical BudgetDetails codes are covered by the final crosswalk (42/42 Procore latest WBS)

## Setup and commands (from the subproject root)

```bash
cd /Users/bobbyfetting/hb-personal-assistant/subrepos/construction-financial-review
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```

Run the one fully-wired command **without installing** (uses `PYTHONPATH=src`):

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli validate-crosswalk --project tropical
```

The `run-*` commands (`run-context`, `run-analysis`, `run-mapping-workpaper`, `run-crosswalk-v2`) are
**Tropical-only** for now — they shell out to the verbatim, validated generators under
`src/construction_financial_review/{context,analysis,mapping}/`, which currently carry hardcoded
Tropical/2026-June paths. They fail clearly for any non-tropical project. Parameterizing the
generators is **deferred work** (see `docs/decisions/tropical_2026_june_decisions.md`).

The schedule-integrated forecast generator is **config-driven** (import-dispatched, not a hardcoded
generator). It discovers the latest schedule / context / crosswalk-v2 / mapping-workpaper packages
from the project config and the forecast data root, then writes one new timestamped output package:

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli \
    schedule-integrate-forecast --project tropical
# optional: --data-root <path> --out-root <path> --frozen-stamp <YYYYMMDD_HHMMSS> (determinism check)
```

The forecast-accuracy generator is also config-driven. It builds independent EAC models, calibrates
confidence with a backtest, flags ERP forecast adequacy, and (with `--with-llm`) adds an advisory
local-Ollama narrative layer. The quantitative core is deterministic; the LLM layer is advisory,
safety-scanned, and excluded from the determinism gate:

```bash
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-accuracy --project tropical
# advisory local model narratives (Ollama running locally):
PYTHONPATH=src python3 -m construction_financial_review.cli forecast-accuracy --project tropical --with-llm
```

## Layout

```
src/construction_financial_review/   library (common/), CLI, verbatim generators, schedule_analysis/
config/projects/tropical.json        project config + approved decisions
config/crosswalks/tropical/          authoritative owner SOV scope crosswalk (jsonl + csv + report)
docs/workflow/                       one doc per pipeline stage
docs/decisions/                      approved decisions + deferred work
schemas/                             output schema references
scripts/                             run_tropical_*.sh runners
tests/                               pytest suite (stdlib-only library)
```
