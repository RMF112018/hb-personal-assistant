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
