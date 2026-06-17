# Forecast Comprehensive — Integrated Forecast Model Layer

Top-level integrator (`forecast_comprehensive`, CLI `forecast-comprehensive`, package
`forecast_comprehensive_package_tropical_<stamp>/`) that wires every accepted forecast evidence package
into one integrated forecast with full lineage and a human-acceptance review queue. It **consumes the
accepted package OUTPUT rows** — it never re-runs the heavy generators and never mutates any package.

## Why

The slices (context → analysis → crosswalk-v2 → schedule-integrated → accuracy → intelligence → monthly
→ probability → history-informed → cost-frequency) each emit high-value evidence, but the newest advisory
families (history-informed, cost-frequency) were only partially consumed by the active model chain. This
layer converts every family into **scored, weighted, auditable** evidence and produces integrated
intelligence / monthly / probability recommendations, documenting exactly when evidence was consumed,
downgraded, rejected, or missing.

## Pipeline

1. **Discover** (`package_discovery`): glob the data root for the latest of each package (config globs);
   verify manifest integrity. Missing required (context/intelligence/monthly) → fail-closed. Missing
   cost-frequency → **generate it first** into the data root (additive, validated) then consume, or
   degrade with an explicit reason (`allow_degraded_without_frequency_package`).
2. **Registry** (`evidence_schema` + `evidence_registry`): for each of the 127 canonical codes, normalize
   one evidence item per present family (19 families) with uniform lineage
   (`source_package_type/path/file/row_id`), `evidence_family`, `independence_group`, support flags, and
   contradiction score. History/cost-frequency rows are joined on the canonical key; null-key rows are
   never invented into the universe.
3. **Score** (`evidence_scoring`): bounded, contradiction-collapsed advisory weights —
   `history_final_cost_weight` (collapses to 0 when actuals contradict), `history_monthly_shape_weight`
   (only when reliability adequate + not contradicted), `history_probability_weight`,
   `frequency_monthly_weight` (weekday cadence only). `independence_group` prevents double-counting a
   signal (e.g. CostEntries trend) that surfaces in several packages. Emits per-family
   accept/downgrade/reject reason codes + the six `*_consumption_status` fields.
4. **Intelligence** (`intelligence_consumer`): accepted `recommended_final_cost` is the BASE; history is
   one bounded advisory family (frequency carries **zero** final-cost weight). Integrated final is
   **floored at actual cost to date and never capped**. After operator controls + dormancy, the
   deterministic **cost-basis** decision (see `forecast_cost_basis.md`) may select the BudgetDetails
   projected-cost basis — corrective/asymmetric, raising a proven under-forecast, never capping an
   overrun to ERP — driving the integrated final/CTC the monthly and probability consumers then consume.
   Before that, the **staffing basis** (see `forecast_staffing_basis.md`) may select the operator
   staffing-plan remaining for a mapped `.LAB` code (raise-only). A `full_run_lineage_consistent` gate
   proves all upstream packages consumed one consistent context (see `common/lineage.py`).
5. **Monthly** (`monthly_consumer`): accepted monthly base reshaped by the bounded frequency weekday
   vector + a bounded history curve-shape tilt, then allocated to the integrated CTC via the reused
   `monthly_reconcile._allocate`. Reconciles per code **and** at the project total. Six source shares.
6. **Probability** (`probability_consumer`): **deterministic** reshaping of the accepted per-code band
   around P50 by a bounded sigma multiplier (history × bounded weight + cadence-change widening) and a
   tail shift; floored at actuals, never capped. `probability_method =
   accepted_distribution_deterministic_adjustment` — **not a fresh Monte Carlo**.
7. **Conflicts** (`conflicts`): classify the seven useful conflict types (actuals-vs-history,
   schedule-vs-monthly-shape, invoice-vs-cost-trend, probability-vs-confidence, cadence-vs-actuals,
   owner-vs-sub pay-app, projected-vs-integrated).
8. **Human acceptance** (`human_acceptance`): stamp every posture-changing row `acceptance_status=pending`
   (+ null accepted_by/at/notes); build the review queue from material changes + high-severity conflicts.
9. **Assemble + validate** (`final_package`, `generate_*`, `validation`): rollups, completeness matrix,
   determinism self-check, audits, manifest (title **"Comprehensive Integrated Forecast Package —
   Tropical World Nursery"** v1.0.0), fail-closed gates.

## Module map

| Module | Responsibility |
|---|---|
| `package_discovery.py` | Glob latest of each package; manifest check; required/degraded status. |
| `evidence_schema.py` | Canonical evidence-item factory + family + independence-group vocabulary. |
| `evidence_registry.py` | Load accepted rows; normalize per-code evidence items + consolidated `per_code`. |
| `evidence_scoring.py` | Bounded, de-duplicated weights + accept/downgrade/reject reasons + consumption statuses. |
| `intelligence_consumer.py` | Integrated final cost (accepted base + bounded history; floored; uncapped). |
| `monthly_consumer.py` | Integrated phasing (frequency + history tilt) reconciled to integrated CTC. |
| `probability_consumer.py` | Deterministic adjustment of the accepted probability band (non-MC). |
| `conflicts.py` | Seven-class evidence-conflict register. |
| `human_acceptance.py` | Acceptance stamping + review queue. |
| `final_package.py` | Completeness matrix, inventory, rollups, summary. |
| `validation.py` | Fail-closed gates. |
| `generate_comprehensive_forecast_package.py` | Orchestrator: discover → registry → score → consumers → conflicts → audits → package. |

## How the comprehensive package differs from the standalone packages

The standalone intelligence / monthly / probability packages remain the accepted, authoritative model
outputs. The comprehensive package is **additive and advisory**: it overlays the standalone outputs with
integrated recommendations (final cost / monthly / probability) that fold in the advisory evidence
families at bounded weights, plus the evidence registry, conflict register, completeness matrix, and
review queue. Nothing here is formally accepted — an operator reviews and accepts/rejects per code.

## Posture / guardrails

CostEntries/Sage incurred cost is accounting truth; actual cost to date is the only hard floor; no
evidence (history / pay-app / owner SOV / ERP budget / commitment / prior forecast / probability) is ever
a cap. Cost-frequency shapes monthly timing + timing-risk only — never final cost by itself. Probability
is a deterministic transform of the accepted distribution. Every recommendation requires human acceptance
(default pending). No source / accepted package / SQLite / Excel mutation; no live external calls
(localhost Ollama only, advisory non-numeric, excluded from determinism). Deterministic: same frozen
stamp + same input packages ⇒ byte-identical quantitative core.
