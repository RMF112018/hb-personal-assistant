# Forecast-Model Gap Validation Report

**Stamp:** 20260623T080628Z · **Scope:** validate 10 prior-audit forecast-model gaps against live
repo truth (origin/main code + copied-DB evidence) and produce a phased remediation plan.
**This is validation/planning only — no forecast-logic code was changed.**

Repo truth (code, tests, schema, copied-DB, generated output) is authoritative. Every classification
below cites code (`file:line` from `origin/main`) and/or copied-DB output reproduced in the sibling
evidence files in this directory.

---

## 1. Executive conclusion

- **The prior audit was largely correct.** 8 of 10 gaps are **confirmed**, 1 is **partially
  confirmed** (Gap 5), and **1 prior finding was wrong/overstated** (Gap 8 — external-forecast
  evaluation is in fact fully implemented, tested, and live).
- **The forecasting feature is NOT production ready** as a *DB-native, multi-project forecasting
  model*. The DB-native **plumbing** is solid and proven end-to-end (v58–v66 schema, output/decision
  projection, read-model API, the gated live-write executed this session, external-forecast
  evaluation, operator-assumption CRUD). The **model layer** has hard gaps.
- **Top production blockers:**
  1. **Project header totals are never aggregated** (Gap 1). The single live `forecast_outputs` row
     has all five totals NULL; the projector hardcodes them to `None`. The UI/API cannot show a
     project EAC / cost-to-complete / variance. *The forecast value exists per budget code; only the
     project-level rollup is missing.*
  2. **Tropical-only hard guards** (Gap 4). 25 fail-closed `project_key != SUPPORTED_PROJECT_KEY`
     checks across 19 CFR files block any second project without code changes.
- **High-priority hardening:** operator assumptions are captured but inert (Gap 2); model execution
  still requires hand-assembled packages as source-of-truth (Gap 3 — exactly the friction hit during
  this session's live-write, where the source package had to be located on the Synology root and
  copied out); no model registry/versioning/governance (Gap 6); no current-vs-prior-run comparison
  (Gap 7); zero forecast-correctness/assumption-consumption tests (Gap 10).
- **Medium hardening:** maturity/availability logic is shallow (Gap 5 — availability is
  v59-table-presence-only and mislabels commitment/schedule "unavailable" even though the same run
  produced 127 commitment-exposure and 58 schedule-phasing rows from packages); explainability lacks
  narratives/model-version/override lineage (Gap 9).
- **Corrected prior finding:** Gap 8 (external/operator forecast evaluation) is **not a gap** —
  ingest → map → compare → anomaly → persist is implemented with V61 tables, API routes, and
  isolation tests. Only XLSX, auto-live-projection, and multi-project discovery are deferred.

---

## 2. Repo state verified

| Item | Value |
|---|---|
| Audit code revision | `origin/main` @ `ecde2367` (PR #101 merge) — verified via fresh worktree `/tmp/hb-gap-audit` |
| Main checkout branch | `feature/schedule-test-fd-hygiene` (concurrent schedule session) — **dirty**, does **not** contain PR #101 |
| PR #101 status | **MERGED** into origin/main (`ecde2367`); operator-assumptions code present |
| Working tree (audit) | clean origin/main worktree (no source edits; only this evidence dir added) |
| `LATEST_SCHEMA_VERSION` | **71** (origin/main migrator); live + copied DB at v71 |
| Copied DB | `/tmp/hb-forecast-model-gap-validation.sqlite` (`VACUUM INTO`, read-only on live; migrator re-applied idempotent; `PRAGMA integrity_check = ok`) |
| Live DB | **never mutated** (read-only copy only) |
| Evidence path | `docs/evidence/forecast-model-gap-validation/20260623T080628Z/` |
| Test commands | targeted 4-file suite (25 passed); scoped 67-file forecast suite (12 failed — all environmental/stale, see §below) |
| no-raw-leak scan | clean — `unsafe_finding_count: 0` over the evidence dir |

**Test results (honest).** Targeted suite — `test_forecast_decision_support_coverage.py`,
`test_fastapi_forecast_run_readmodel.py`, `test_forecast_live_db_run_output_projection.py`,
`test_fastapi_forecast_operator_assumptions.py` — **25 passed, 0 failed**
(`pytest-targeted-forecast.txt`). Broader 67-file forecast suite — **12 failed**
(`pytest-forecast-suite.txt`), and **none are forecast model-logic failures**:
- **8 stale hardcoded schema-version assertions** — tests pin `schema_version == 61` (phase 10/11/12/13
  synthetic-DB tests) or `LATEST_SCHEMA_VERSION == 67/70` (v65 schedule migrator tests); actual is 71.
  These fail on origin/main independent of this audit → pre-existing **test-debt** as the schema
  advanced (61→71, largely via schedule phases).
- **2 test-isolation leaks** — `test_unconfigured_is_503` / `test_unconfigured_fails_closed_503`
  assert `200 == 503`; they expect an *unconfigured* runtime but pick up this machine's real managed
  forecast config, so the endpoint returns 200.
- **2 subprocess interpreter issues** — evidence-script tests spawn bare `python3` (no `pydantic`) →
  `ModuleNotFoundError`. Environmental, not logic.
- CFR subrepo tests (`subrepos/construction-financial-review/tests`) were **out of scope** here
  (separate pytest env; collection errors under this PYTHONPATH are environmental).

---

## 3. Gap validation matrix

| # | Prior finding | Status | Repo-truth evidence | Affected output | Severity | Copied-DB confirms | Priority |
|---|---|---|---|---|---|---|---|
| **1** | Header totals null/unpopulated | **confirmed** | `forecast/output_projection_engine.py:187-191` hardcodes `estimated_final_cost/forecast_at_completion/cost_to_complete/variance_to_budget/variance_to_prior_forecast = None`; `forecast_output_tables.py` cols TEXT-nullable; `forecast_run_readmodel.py:99-113` passthrough. Per-code values DO exist. | project EAC/CTC/variance in API+UI | **production_blocker** | yes — 1/1 row, all 5 NULL (`forecast-output-header-null-audit.txt`); per-code `recommended_projected_cost` populated 94/127 | P1 |
| **2** | Assumptions captured, not consumed | **confirmed** | `analytics/forecast_operator_assumptions.py` pure CRUD; 0 reads in `decision_support_engine.py`/`output_projection_engine.py`/CFR; `decision_support_repository.py:10` ("ship empty until a follow-on slice") | forecast value/confidence/gate/narrative | high_priority_hardening | yes — `forecast_operator_assumptions`=0, `forecast_required_assumptions`=0 | P2 |
| **3** | Execution package-source-first, not DB-native | **confirmed** | `output_projection_engine.py:138-145` (Path inputs, docstring "No DB access"); `source_domain_engine.py:114-150` reads JSONL; `forecast_run_service.py:142-165` wraps file workflow; `final_forecast_runner.py:65-77` requires `context_package` Path; `forecast_db_config_run_service.py:30-32` refuses without predecessor packages. DB reads limited to v59 source-domain adapter + config snapshots. | operational (packages must be hand-assembled) | high_priority_hardening | indirect — live-write this session required locating the source package on Synology and copying it out | P3 |
| **4** | Tropical/single-project hardcoding | **confirmed** | 25 `!= SUPPORTED_PROJECT_KEY` guards across 19 CFR files (`final_forecast_runner.py:79`; `common/package_resolution.py:87,120,173`; `config_registry.py:312,435,669`; 15 `workflows/*` incl. `live_db_run_output_projection.py:260`). `SUPPORTED_PROJECT_KEY="tropical"`; hardcoded `twn_cost_forecast_json_package`. See `forecast-tropical-hardcoding-summary.txt`. | multi-project execution | **production_blocker** (multi-project) | n/a (code) | P4 |
| **5** | Maturity/availability incomplete | **partially_confirmed** | `decision_support_engine.py:87-97` maturity M0–M4 (no M5/closeout); `:158-167` `lifecycle_signal=None`; `:64-65` `_DB_DOMAINS=(budget,cost_actuals,monthly_actuals)`,`_ABSENT_DOMAINS=(owner,commitment,schedule,staffing)`; availability = v59 row-presence only; `:233-241` `completeness/mapping_quality/maturity/score=None`; `:249` never blocks (penalty only). | confidence/readiness signal accuracy | medium_priority_hardening | yes — `forecast-decision-support-domain-audit.txt`: M4 lifecycle null; 7 domains; commitment/schedule "unavailable" despite 127/58 output rows; score/completeness/mapping_quality all null | P5 |
| **6** | Model registry/selection/weighting governance | **confirmed** | CFR `forecast_accuracy/estimators.py:22-24` hardcoded `INDEPENDENT_METHODS`/`ERP_METHODS`; `backtest.py:140-165` weights runtime-only (not persisted/versioned); `config_registry.py:183-206` governs operator config not model params; `forecast_db_config_run_service.py:113-160` record has no estimator/threshold/calibration version; `method_eligibility`/`model_selection` populated only if `accuracy_package` threaded into decision-support (not in the run-output path). | auditability, trust, governance | high_priority_hardening | yes — `forecast_method_eligibility`=0, `forecast_model_selection_decisions`=0 after a full certified run | P6 |
| **7** | Prior-forecast comparison incomplete | **confirmed** | `output_projection_engine.py:191` `variance_to_prior_forecast=None`; `:307-308` `change_type="integrated_vs_accepted"`, `prior_run_id=None`; no prior-run query. | current-vs-prior delta (project + per-code) | high_priority_hardening | yes — `forecast_output_changes.change_type` only `integrated_vs_accepted`; header `variance_to_prior` NULL | P1 (with headers) |
| **8** | External/operator forecast only partially evaluated | **not_confirmed / superseded** | Implemented+tested+live: `forecast_external_{ingest,eval_service,dto,mapping,compare,anomaly,baselines,metrics}.py`; V61 tables (`migrator.py:6590-6744`); API `api.py:2102-2148`; isolation/anomaly tests. Deferred only: XLSX, auto-live-projection, multi-project auto-discovery. | n/a (works) | low_priority_refinement | n/a | P7 (small) |
| **9** | Explainability/audit trail incomplete | **confirmed** | `forecast_output_tables.py:224-239` `forecast_output_narratives` schema with **0 writers**; no model-version metadata; no human-override history; source-QA rationale = "rows present / no rows" only. Present: `confidence_factors` (per-factor reason), maturity thresholds, DB-row provenance (`run_id`/`created_utc`/`raw_json`), `source_package`+`source_sha256`. | reason trail / audit | medium_priority_hardening | yes — `forecast_output_narratives`=0; `confidence_factors`=131 | P8 |
| **10** | Tests prove projection/read-model, not forecast correctness | **confirmed** | ~67 forecast test files: projection/schema/API/redaction/isolation. **Zero** tests assert a forecast VALUE given inputs, assumption-consumption impact, multi-project behavior, or prior-vs-current delta. | confidence in model math | high_priority_hardening | n/a | P10 |

---

## 4. Forecast data hierarchy (corrected to repo truth)

| Input | Source family | Table / file / package | Consuming function | Affects | Impact class | Ranking basis |
|---|---|---|---|---|---|---|
| Budget (revised/projected) | v59 source-domain (from `twn_cost_forecast_json_package`) | `forecast_budget_details` | CFR analysis generator → per-code recommended cost | value | **critical_primary_driver** | calculation sequence (basis of recommendation) |
| Job-to-date actuals | v59 source-domain | `forecast_cost_entries` | CFR analysis (floor-to-actuals increase rule) | value | **critical_primary_driver** | explicit rule (actuals floor is absolute) |
| Monthly actuals | v59 source-domain | `forecast_monthly_actuals_by_budget_code` | maturity (`completed_month_count`) + monthly phasing | value + readiness | high_impact_driver | calculation sequence + gating |
| Analysis recommendations | generated package | `forecast_analysis_package_*` | `output_projection_engine.plan_run_output_projection` | value | **critical_primary_driver** | the projected per-code forecast value source |
| Integrated change explanation | comprehensive package | `integrated_change_explanation.jsonl` → `forecast_output_changes` | output projection | narrative/context | medium_impact_driver | within-run integrated-vs-accepted (NOT prior-run) |
| Probability bands | probability package | `forecast_output_probability` (P10/P50/P90) | output projection | confidence/context | confidence_only_signal | confidence scoring |
| Commitment exposure | context package `canonical/budget_codes.jsonl` | `forecast_output_commitment_exposure` | output projection | context | medium_impact_driver | computed but NOT reflected in availability |
| Schedule phasing | monthly package | `forecast_output_schedule_phasing` | output projection | context | medium_impact_driver | computed but NOT reflected in availability |
| Estimators + reconciliation weights | CFR constants | `forecast_accuracy/estimators.py`, `backtest.py` | CFR generation | value | **critical_primary_driver** but **ungoverned** | hardcoded constants, runtime weights (no persistence/version) |
| Owner / commitment / schedule / staffing availability | (no v59 table yet) | `forecast_data_availability_profiles` | `decision_support_engine` | confidence (penalty) | confidence_only_signal | penalty, never a block |
| Operator assumptions | runtime (PR #101) | `forecast_operator_assumptions` | — (none) | — | **configured_but_not_consumed** | written, never read by engine |
| Required assumptions | runtime (PR #101) | `forecast_required_assumptions` | — (none) | — | **configured_but_not_consumed** | written, never gates a run |
| Prior forecast run | DB | `forecast_outputs`/`forecast_runs` (prior) | — (none) | — | **documented_but_not_implemented** | `variance_to_prior`/`prior_run_id` hardcoded None |
| Method eligibility / model selection | decision-support | `forecast_method_eligibility`, `forecast_model_selection_decisions` | `_emit_method_rollups` (only if `accuracy_package` passed) | rationale | **documented_but_not_implemented** (empty in run-output path) | not populated in practice |
| Narratives | output | `forecast_output_narratives` | — (none) | narrative | **documented_but_not_implemented** | schema with 0 writers |
| ERP EAC | v59 / sidecar | (reference) | reconciliation reference | fallback | fallback_only_signal | reference-only, never summed |
| External/operator forecasts | upload | V61 tables | `forecast_external_eval_service` | separate evaluation | implemented (isolated) | independent eval track |

---

## 5. Production-readiness gap matrix

Ranked: **production_blocker** → **high_priority_hardening** → **medium_priority_hardening** →
**low_priority_refinement**.

### production_blocker

**B1 — Project header totals not aggregated (Gap 1) + no prior-run delta (Gap 7).**
- Evidence: `output_projection_engine.py:187-191,307-308`; DB null-audit 1/1.
- Why it matters: the Run Center / API expose no project EAC/CTC/variance; the headline number a PM
  needs is blank even though per-code values exist.
- Files/tables: `output_projection_engine.py`; `forecast_outputs`, `forecast_output_changes`.
- Direction: aggregate per-code `recommended_projected_cost`/`recommended_cost_to_complete` →
  header; compute `variance_to_budget` (header vs budget sum) and `variance_to_prior_forecast` +
  `prior_run_id`/`current_vs_prior` from the prior run for the project.
- Tests required: header-aggregation equals sum of per-code (Decimal); prior-delta on a 2-run fixture.
- Copied-DB evidence: re-run header null-audit → 0 nulls; prior-delta nonzero on 2 runs.
- Acceptance: API `…/outputs/{id}` returns non-null EAC/CTC/variance equal to per-code aggregates;
  `variance_to_prior_forecast` populated when a prior run exists.

**B2 — Tropical-only hard guards (Gap 4).**
- Evidence: 25 `!= SUPPORTED_PROJECT_KEY` guards / 19 files (`forecast-tropical-hardcoding-summary.txt`).
- Why it matters: a second project cannot run without code changes.
- Direction: replace constant guards with a project-registry/eligibility check (reuse
  `src/hb_assistant/forecasting/project_eligibility.py`); parameterize the source-package name.
- Tests: a second fixture project runs context→analysis→projection.
- Acceptance: a non-tropical eligible project completes a controlled run; ineligible still fails closed.

### high_priority_hardening
- **H1 — Assumptions inert (Gap 2):** wire `forecast_operator_assumptions`/`forecast_required_assumptions`
  into decision-support/output as value overrides, confidence modifiers, and a required-satisfaction gate.
- **H2 — Package-as-source (Gap 3):** add DB-native model-input accessors so a run can source from
  v59/runtime storage, packages as fallback; stage full package removal.
- **H3 — Model governance (Gap 6):** DB-backed model registry + versioned estimators/weights/thresholds
  + persisted `method_eligibility`/`model_selection` with rationale + per-run model-version metadata.
- **H4 — No correctness tests (Gap 10):** add model-value, assumption-consumption, prior-delta, and
  multi-project tests; keep no-raw-leak/no-live-writeback coverage.
- **H5 — Stale schema-version test debt:** bump the 8 `== 61/67/70` assertions to track
  `LATEST_SCHEMA_VERSION`, and fix the 2 `unconfigured→503` test-isolation leaks + 2 subprocess
  interpreter (`python3`→venv) issues. (Not a forecast-logic defect, but the suite is red on main.)

### medium_priority_hardening
- **M1 — Maturity/availability (Gap 5):** add M5/closeout + `lifecycle_signal`; make availability
  package/output-aware; populate `completeness/mapping_quality/score`; add changes/assumptions/procore/
  risk/probability domains.
- **M2 — Explainability (Gap 9):** populate `forecast_output_narratives`; add model-version metadata,
  human-override history, source-QA rationale, and a package-sha256 chain.

### low_priority_refinement
- **L1 — External eval (Gap 8):** XLSX ingest + multi-project discovery (auto-live-projection optional).
- **L2 — Operator workflow:** durable backup location for the live-write (current backup lands in `/tmp`).

---

## 6. Comprehensive remediation plan (phased)

Common guardrails for **every** phase: copied-DB evidence only (never mutate live DB); no Procore/live
calls; no external writeback; no raw-payload/source-path/`raw_json` in user-facing API; no `git add .`;
one concern per PR (no mixing forecast/runtime/UI); confirm in code/tests/DB, not docs. Execute each in
its own origin/main worktree; open one PR per phase.

### Phase 1 — Header totals + prior-run deltas (Gaps 1, 7) — *blocker, lowest effort*
- **Objective:** populate `forecast_outputs` header totals + current-vs-prior deltas.
- **Scope:** aggregate per-code → header (EAC/CTC/variance_to_budget); compute `variance_to_prior_forecast`,
  populate `forecast_output_changes.prior_run_id` + a `current_vs_prior` change_type from the prior run.
- **Out-of-scope:** model math changes; multi-project; assumptions.
- **Files:** `construction/forecast/output_projection_engine.py` (header block ~187-191, changes block ~307-308);
  read-model already surfaces (`forecast_run_readmodel.py`).
- **Schema/DB:** none (columns exist). Decimal math only.
- **Tests:** header == Decimal sum of per-code; prior-delta correctness on a 2-run fixture; readmodel surfaces values.
- **Copied-DB evidence:** header null-audit → 0 nulls; 2-run prior-delta nonzero.
- **Acceptance:** non-null header totals equal to aggregates; prior delta populated when prior run exists.
- **Rollback:** projection is re-derivable; gated live-write re-certifies; revert is a code revert + re-projection.

### Phase 2 — Operator assumptions as consumed inputs (Gap 2)
- **Objective:** make captured assumptions influence forecasts.
- **Scope:** read assumptions in decision-support/output; apply value overrides (operator-supplied),
  confidence modifiers (`confidence_impact`), and a required-assumption satisfaction gate.
- **Out-of-scope:** UI (Phase 9).
- **Files:** `decision_support_engine.py`, `output_projection_engine.py`, repository readers,
  `forecast_db_config_run_service.py`.
- **Schema/DB:** none (tables exist).
- **Tests:** assumption value alters output; `confidence_impact` shifts scorecard; unsatisfied required → gated/flagged.
- **Copied-DB evidence:** seed assumptions in copied DB → show output/confidence delta.
- **Acceptance:** a seeded override changes the per-code recommendation; an unsatisfied required assumption is surfaced.
- **Rollback:** feature-flag the consumption path; default off until validated.

### Phase 3 — DB-native model input accessors (Gap 3)
- **Objective:** reduce package-as-source dependency.
- **Scope:** DB-backed accessors feeding the engine from v59/runtime storage; packages as fallback.
- **Out-of-scope:** removing packages entirely (later stage).
- **Files:** `source_domain_engine.py`, CFR `context/context_generation_runner.py` (extend DB-backed mode), runner services.
- **Schema/DB:** read-only from v59; possibly a runtime input view.
- **Tests:** DB-backed run parity vs package run (byte/row equivalence).
- **Acceptance:** a run completes from DB with no package directory for the covered inputs.
- **Rollback:** toggle; package path remains default.

### Phase 4 — Multi-project generalization (Gap 4) — *blocker*
- **Objective:** remove tropical-only guards.
- **Scope:** replace 25 `SUPPORTED_PROJECT_KEY` guards with project-registry/eligibility checks; parameterize source-package name.
- **Files:** CFR `final_forecast_runner.py`, `common/package_resolution.py`, `config_registry.py`, 15 `workflows/*`; reuse `forecasting/project_eligibility.py`.
- **Schema/DB:** project registry table if not already sufficient.
- **Tests:** second fixture project end-to-end; ineligible still fails closed.
- **Acceptance:** non-tropical eligible project runs; multi-project coverage proven.
- **Rollback:** eligibility allowlist defaults to tropical.

### Phase 5 — Maturity/availability/confidence completion (Gap 5)
- **Scope:** M5/closeout + `lifecycle_signal`; package/output-aware availability; populate
  `completeness/mapping_quality/score`; add changes/assumptions/procore/risk/probability domains.
- **Files:** `decision_support_engine.py`; `forecast_decision_support_tables.py` (only if columns added → migration).
- **Tests:** early/mid/late/closeout staging; availability reflects package evidence; domain coverage.
- **Acceptance:** availability no longer mislabels commitment/schedule "unavailable" when outputs exist; scores populated.

### Phase 6 — Model registry/versioning/weighting/calibration governance (Gap 6)
- **Scope:** DB-backed model registry; versioned estimators/weights/thresholds; persist
  `method_eligibility`/`model_selection` with rationale; per-run model-version metadata; thread `accuracy_package`.
- **Files:** new registry module + tables (migration v72+); `forecast_db_config_run_service.py` record fields; decision-support method-rollup wiring.
- **Tests:** model-selection behavior; version provenance per run.
- **Acceptance:** `method_eligibility`/`model_selection` populated with rationale; per-run model version recorded.

### Phase 7 — External forecast eval completion (Gap 8, small)
- **Scope:** XLSX ingest + multi-project discovery (auto-live-projection deferred).
- **Files:** `forecast_external_ingest.py`, eligibility.
- **Tests:** XLSX parse; second project eval.

### Phase 8 — Explainability/audit trail (Gap 9)
- **Scope:** populate `forecast_output_narratives`; add model-version metadata, human-override history, source-QA rationale, package-sha256 chain.
- **Files:** `output_projection_engine.py`, `decision_support_engine.py`, tables (migration if new).
- **Tests:** narrative present; lineage completeness.

### Phase 9 — UI/API readiness + operator workflow
- **Scope:** surface header totals, prior deltas, assumption impact, maturity/availability, model rationale; multi-project selector; durable live-write backup.
- **Files:** `forecast_run_readmodel.py`, `analytics/api.py`, `frontend/src/components/forecast/*`.
- **Tests:** vitest + API; no-raw-leak.

### Phase 10 — Test + evidence hardening (Gap 10)
- **Scope:** model-value correctness, assumption-consumption, prior-delta, multi-project, copied-DB integration tests; fix the §2 stale/isolation/subprocess failures.
- **Acceptance:** a forecast value is asserted against expected given inputs; the forecast suite is green on main.

**Suggested order:** P1 + P4 (blockers) → P2, P3, P6, P10 → P5, P8, P9 → P7.

---

## 7. Local-agent implementation prompts (copy/paste; do NOT run yet)

Each prompt is scoped to one clean PR. Run each from a fresh worktree off `origin/main`; copied-DB
evidence only; no live mutation; no `git add .`.

> **P1 — Forecast output header totals + prior-run deltas.** In `origin/main`, in
> `src/hb_assistant/construction/forecast/output_projection_engine.py`, replace the hardcoded
> `None` header block (~lines 187-191) so `estimated_final_cost`, `forecast_at_completion`, and
> `cost_to_complete` are Decimal aggregates of the per-budget-code `recommended_projected_cost` /
> `recommended_cost_to_complete`, and `variance_to_budget` = header EAC − budget sum. Compute
> `variance_to_prior_forecast` and populate `forecast_output_changes.prior_run_id` +
> `change_type="current_vs_prior"` by querying the most recent prior `forecast_outputs`/`forecast_runs`
> for the project (keep the existing `integrated_vs_accepted` rows). No schema change (columns exist).
> Add tests asserting header == sum of per-code (Decimal, no float) and prior-delta on a 2-run fixture.
> Validate with a copied-DB header null-audit (expect 0 nulls). One PR.

> **P4 — Multi-project generalization.** Replace the 25 `project_key != SUPPORTED_PROJECT_KEY`
> fail-closed guards across the 19 CFR files (`analysis/final_forecast_runner.py`,
> `common/package_resolution.py`, `config_registry.py`, and 15 `workflows/*`) with a project-eligibility
> check reusing `src/hb_assistant/forecasting/project_eligibility.py`; parameterize the hardcoded
> `twn_cost_forecast_json_package` source-package name. Keep fail-closed for ineligible projects. Add a
> second-project fixture and prove context→analysis→projection end-to-end. One PR.

> **P2 — Consume operator assumptions.** Make `forecast_operator_assumptions` /
> `forecast_required_assumptions` influence forecasts: read them in `decision_support_engine.py` /
> `output_projection_engine.py`; apply per-code value overrides, `confidence_impact` modifiers to the
> confidence scorecard, and a required-assumption satisfaction gate (unsatisfied → flagged/gated, not
> silently ignored). Behind a default-off flag until validated. Tests must prove an assumption changes a
> forecast value and a confidence label, and that an unsatisfied required assumption is surfaced. One PR.

> **P3 — DB-native model input accessors.** Add DB-backed accessors so the forecast engine can source
> model inputs from the v59 source-domain/runtime tables (packages as fallback), extending the existing
> Phase-4 `context_generation_runner` DB-backed mode. Prove row/byte parity between a DB-backed run and a
> package-backed run on a copied DB. Do not remove package support. One PR.

> **P6 — Model registry & governance.** Add a DB-backed model registry (migration v72+) with versioned
> estimator order, reconciliation weights, thresholds, and calibration provenance; persist
> `forecast_method_eligibility` / `forecast_model_selection_decisions` rows with rationale on every run
> (thread `accuracy_package` into decision-support); record per-run model-version metadata in the run
> record. Tests must prove method-selection behavior and version provenance. One PR.

> **P10 — Forecast-correctness & isolation test hardening.** Add tests that assert forecast VALUES given
> inputs (header == per-code aggregate; floor-to-actuals rule; P50 bands), assumption-consumption impact,
> prior-vs-current delta, and a second-project run. Separately fix the red forecast suite on main: bump
> the 8 stale `schema_version == 61/67/70` assertions to track `LATEST_SCHEMA_VERSION`, isolate the two
> `unconfigured→503` tests from the real managed config, and make the evidence-script subprocess use the
> venv interpreter (not bare `python3`). One PR for correctness tests, one for the suite-hardening fixes.

> **P5 — Maturity/availability/confidence.** Add an M5/closeout tier + `lifecycle_signal`; make
> data-availability package/output-aware (so commitment/schedule are not "unavailable" when
> `forecast_output_commitment_exposure`/`_schedule_phasing` rows exist); populate
> `completeness`/`mapping_quality`/`score`; extend domains to changes/assumptions/procore/risk/probability.
> Tests for each lifecycle stage and domain. One PR.

> **P8 — Explainability/audit trail.** Populate `forecast_output_narratives` per output; add
> model-version metadata, a human-override history table, source-data QA rationale (null/zero/dup checks
> + staleness), and a package-sha256 chain across context→analysis→output. Tests for narrative presence
> and lineage completeness. One PR.

> **P9 — UI/API readiness.** Surface header totals, prior deltas, assumption impact, maturity/availability,
> and model rationale through `forecast_run_readmodel.py` + `analytics/api.py` + the Run Center frontend;
> add a multi-project selector; move the gated live-write backup to a durable location. vitest + API +
> no-raw-leak tests. One PR.

> **P7 — External eval refinement.** Add XLSX ingest and multi-project discovery to the external-forecast
> evaluation pipeline (`forecast_external_ingest.py` + eligibility); keep isolation guarantees. Tests for
> XLSX parsing and a second-project evaluation. One PR.
