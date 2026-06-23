# Forecast-Model Remediation Plan — Execution Tracker

Canonical status ledger for the 10-phase forecast-model remediation. This is the single source of
**phase status**; the authoritative **phase specs + copy/paste prompts** live in the gap-validation
report.

- **Source-of-truth report:** `docs/evidence/forecast-model-gap-validation/20260623T080628Z/forecast-model-gap-validation-report.md` (PR #102).
- **Execution tooling:** the `forecast-remediation-driver` skill drives one phase per invocation and
  updates this file; the `forecast-remediation-tracker` agent audits this ledger against repo truth.
- **Status values:** `pending` · `in-progress` · `in-review` · `merged` · `blocked`.

## Common guardrails (every phase)

Copied-DB evidence only (never mutate the live DB); no Procore/live/external calls; no external
writeback; no `raw_json`/source-path in user-facing API output; no `git add .`; one concern per PR
(never mix phases); confirm behavior in code/tests/DB, not docs. Each phase runs in a fresh worktree
off `origin/main` and opens one PR. Sensitive ops (migrations / live-DB / schema) gate through
`hb-sensitive-operation-gate`; plans gate through `hb-plan-gate-review`; tests select via
`hb-verification-router`; landed PRs close out through `hb-post-execution-closeout`.

## Recommended order

P1 & P4 (production blockers) → P2, P3, P6, P10 → P5, P8, P9 → P7.

## Phase ledger

| Phase | Title | Gaps | Severity | Status | PR | Evidence | Date | Blocked-by |
|---|---|---|---|---|---|---|---|---|
| P1 | Forecast output header totals + prior-run deltas | 1, 7 | production_blocker | merged | #104 | `docs/evidence/forecast-remediation/P1-header-totals-20260623T092610Z/` | 2026-06-23 | — |
| P4 | Multi-project generalization (remove tropical-only guards) | 4 | production_blocker | merged | #105 | `docs/evidence/forecast-remediation/P4-multi-project-20260623T101104Z/` | 2026-06-23 | — |
| P2 | Operator assumptions as consumed model inputs | 2 | high | merged | #107 | `docs/evidence/forecast-remediation/P2-assumptions-consume-20260623T141418Z/` | 2026-06-23 | — |
| P2b | Operator-assumption dollar value-overrides (output projection) | 2 | high | merged | #108 | `docs/evidence/forecast-remediation/P2b-value-overrides-20260623T162613Z/` | 2026-06-23 | — |
| P3 | DB-native model input accessors (reduce package-as-source) | 3 | high | merged | #109 | `docs/evidence/forecast-remediation/P3-db-native-inputs-20260623T193155Z/` | 2026-06-23 | — |
| P6 | Model registry / versioning / weighting / calibration governance | 6 | high | pending | — | — | — | — |
| P10 | Forecast-correctness & isolation test hardening | 10 | high | in-review | (PR1 pending) | `docs/evidence/forecast-remediation/P10-PR1-suite-hardening-20260623T205408Z/` | 2026-06-23 | — |
| P5 | Maturity / data-availability / confidence completion | 5 | medium | pending | — | — | — | — |
| P8 | Explainability / audit trail (narratives, model-version, override, QA, sha256 chain) | 9 | medium | pending | — | — | — | — |
| P9 | UI/API readiness + operator workflow | 1, 5, 6, 7, 9 (surface) | medium | pending | — | — | — | — |
| P7 | External forecast eval completion (XLSX, multi-project discovery) | 8 | low | pending | — | — | — | — |

## Phase summaries (see the report for full specs/prompts)

- **P1** — aggregate per-code recommended costs into `forecast_outputs` header (EAC/CTC/variance_to_budget);
  compute `variance_to_prior_forecast` + `prior_run_id` from the prior run. Files:
  `construction/forecast/output_projection_engine.py`. No schema change.
- **P4** — replace the 25 `project_key != SUPPORTED_PROJECT_KEY` guards (19 CFR files) with a
  project-eligibility check; parameterize the `twn_cost_forecast_json_package` source name.
- **P2** — consume `forecast_operator_assumptions`/`forecast_required_assumptions` as confidence
  modifiers + a required-satisfaction gate in `decision_support_engine`, behind a default-off flag.
  Dollar value-overrides delivered in **P2b**.
- **P2b** — operator dollar value-overrides in `output_projection_engine`: reserved `assumption_type`s
  (`projected_cost_override` / `cost_to_complete_override`) override per-code typed columns + re-aggregate
  the EAC/CTC header; auditable `operator_value_override` change rows; raw_json kept as source echo
  (parity-safe). Default-off `HB_FORECAST_ASSUMPTION_OVERRIDES_ENABLED`. No schema change.
- **P3** — DB-backed model-input accessors (v59/runtime) with packages as fallback; prove parity.
  Default-off `HB_FORECAST_DB_BACKED_INPUTS_ENABLED` routes `forecast_run_service.start_run` through
  the existing CFR controlled workflow in `db` mode (3 covered domains from a NON-LIVE v59 DB
  read-only); fail-closed before the workflow on a live/unconfigured db_path; flag-off byte-identical.
  No schema change. ADR 303.
- **P6** — DB-backed model registry (migration v72+); versioned estimators/weights/thresholds; persist
  `forecast_method_eligibility`/`forecast_model_selection_decisions` with rationale; per-run model-version metadata.
- **P10** — two PRs. **PR1 (suite hardening, in-review):** fixed the red suite via Group D (the P4b
  relative-import regression in the 4 bare-file generators → absolute), Group E (P4 "unsupported
  project_key" → "not eligible" message stragglers), Group B (6 stale `schema_version == 61` →
  `LATEST_SCHEMA_VERSION`; left the intentional v61 backward-compat fixture), Group C (2
  `unconfigured->503` isolation leaks), Group A (evidence-script bare `python3` → venv). `-k forecast`
  88→35, 53 fixed, 0 regressions; residual 35 are pre-existing, unmasked, 4 distinct root causes
  (`project_display_name`/`_run_comprehensive` project_key/proof perturb-callback/launcher env)
  documented for a focused follow-up. ADR 304. **PR2 (pending):** forecast-correctness VALUE tests
  (header == per-code Decimal sum, prior-delta, assumption consumption, P50 bands, multi-project).
- **P5** — M5/closeout tier + `lifecycle_signal`; package/output-aware availability; populate
  `completeness`/`mapping_quality`/`score`; add changes/assumptions/procore/risk/probability domains.
- **P8** — populate `forecast_output_narratives`; add model-version metadata, human-override history,
  source-QA rationale, package-sha256 chain.
- **P9** — surface header totals, prior deltas, assumption impact, maturity/availability, model rationale
  in read-model + API + Run Center; multi-project selector; durable live-write backup.
- **P7** — XLSX ingest + multi-project discovery for external-forecast evaluation.

## Changelog

_Append one line per phase transition (date · phase · status · PR · note)._

- 2026-06-23 · P1 · in-review · (PR pending) · header EAC/FAC/CTC/variance_to_budget aggregated from per-code rows; variance_to_prior_forecast + project-level `current_vs_prior` change row from the prior run; no schema change; evidence `P1-header-totals-20260623T092610Z`.
- 2026-06-23 · P1 · merged · PR #104 · landed to main at `1052f563`.
- 2026-06-23 · P4 · in-review · (PR pending) · 26 tropical-only guards → CFR-local stdlib `common/project_eligibility.py` (env allowlist + `forecast_projects` registry + {tropical, fixtureproj} default); `package_resolution` prefixes derived per project; `source_package_name(project_key)` replaces 5 hardcoded `EXPECTED_SOURCE_PACKAGE_NAME`; `_project_rowcount`/proof `gen.generate` threaded with project_key; synthetic `fixtureproj` proof; no schema change; CFR imports no hb_assistant. Deferred to **P4b**: `generate_forecast_context_package.py` detropicalization + live second-project E2E. Evidence `P4-multi-project-20260623T101104Z`.
- 2026-06-23 · P4 · merged · PR #105 · landed to main at `d131a28d`.
- 2026-06-23 · P4b · in-review · (PR pending) · detropicalize the context/analysis/crosswalk-v2/mapping/comprehensive generators + CLI to read project values from `config/projects/<key>.json` via new stdlib `common/project_config.py` (CFR_PROJECT_KEY env, default tropical); removed the `cmd_run_generator` tropical-only refusal (eligibility-gated; passes CFR_PROJECT_KEY to the subprocess); added `procore_export_folder`/cutoffs/`row_count_expectations`/`project_display_name` to `tropical.json` + new `fixtureproj.json`. Tropical byte-parity proven (config-equivalence tests + full CFR suite 670 passed incl. the real-generator proof tests); CFR imports no hb_assistant; no schema change. Deferred to **P4c**: synthetic `fixtureproj` data root + live second-project run. Evidence `P4b-generators-detropicalize-20260623T131334Z`.
- 2026-06-23 · P4b · merged · PR #106 · landed to main at `d9523fa7`; closeout audit (hb-commit-diff-auditor) PASS (+497/−41, 16 files, no reformat churn, tropical parity intact, no hb_assistant source change). Deferred to **P4c**: synthetic `fixtureproj` data root + live second-project run.
- 2026-06-23 · P2 · in-review · (PR pending) · consume operator/required assumptions in `decision_support_engine` behind default-off `HB_FORECAST_ASSUMPTION_CONSUMPTION_ENABLED`: new consume-only `forecast/assumptions_repository.py` (project-scoped `run_id IS NULL` reads of the v66 tables); confidence modifiers (`confidence_impact` raises/lowers/neutral → booster/penalty/neutral factor on the matching scorecard) + required-assumption gate (penalty factor + warning per unsatisfied required assumption); assumptions read read-only from the live managed DB (or explicit `assumptions_db_path`) and pre-hydrated into the planner (engines stay DB-decoupled); flag-off = byte-identical output. No schema change; no live-DB write. Dollar value-overrides deferred to **P2b**. Evidence `P2-assumptions-consume-20260623T141418Z`. ADR 301.
- 2026-06-23 · P2 · merged · PR #107 · landed to main at `d633d5e8`; closeout audit (hb-commit-diff-auditor) PASS; zero forecast-suite regressions.
- 2026-06-23 · P2b · in-review · (PR pending) · operator dollar value-overrides in `output_projection_engine` behind default-off `HB_FORECAST_ASSUMPTION_OVERRIDES_ENABLED`: reserved `assumption_type`s `projected_cost_override`/`cost_to_complete_override` (require budget_code_key + parseable value) override the per-code typed columns (raw_json kept as original source echo → parity-safe) and re-aggregate the EAC/FAC/CTC/variance header; one auditable `operator_value_override` change row per override; null-key/unmatched/unparseable → skip + warning; guarded post-pass so flag-off / no-override = byte-identical. Read read-only (`mode=ro`) from the live managed DB (or explicit `assumptions_db_path`) via a private engine hydrator (assumptions_repository stays conn-accepting). No schema change; no live-DB write. Evidence `P2b-value-overrides-20260623T162613Z`. ADR 302.
- 2026-06-23 · P2b · merged · PR #108 · landed to main at `398c6140`.
- 2026-06-23 · P3 · in-review · (PR pending) · DB-native model inputs behind default-off `HB_FORECAST_DB_BACKED_INPUTS_ENABLED`: `forecast_run_service.start_run` routes the run through the existing CFR controlled workflow in `db` mode (the 3 covered domains — budget_details/cost_entries/monthly_actuals — sourced from a NON-LIVE v59 DB read-only) when the flag is on; flag resolved locally (lazy import → no circular dep); fail-closed BEFORE the workflow on a live/default or unconfigured `db_path` (recorded as a failed run; workflow never called — `resolve_db_path()` defaults to the live DB, so a run never silently reads it); `_summarize_report` derives `no_live_writes` from `work_root_outside_live_root` (both modes); `record["mode"]` branched at both sites. File package remains default + fallback; flag-off byte-identical. No new DB adapter; no wiring into output/decision engines; no schema/CFR-source change; no live-DB write. Acceptance proven by 7 routing/flag/fail-closed tests + Phase 6 file-vs-DB parity; full heavy E2E gated by the pre-existing Group D env condition (CFR not importable → P10). Evidence `P3-db-native-inputs-20260623T193155Z`. ADR 303.
- 2026-06-23 · P3 · merged · PR #109 · landed to main at `c49ca031`.
- 2026-06-23 · P10 · in-review · (PR1 pending) · suite hardening. Group D: the P4b regression — 4 bare-file generators (`generate_forecast_analysis_package.py:77`, `generate_forecast_context_package.py:109`, `generate_forecast_analysis_crosswalk_v2.py:80`, `generate_mapping_discrepancy_workpaper.py:67`) ran a relative `from ..common.project_config import` under `__main__` (subprocess), which fails → converted to absolute (matching each file's sys.path bootstrap). NOTE: the P3-changelog "CFR not importable" framing was imprecise — the real cause was this relative import, not an env/install issue. Group E: 7 tests' `match="unsupported project_key"` → `"not eligible"` (P4 message drift). Group B: 6 forecast tests `schema_version == 61` → `LATEST_SCHEMA_VERSION` (left the intentional v61 backward-compat fixture `test_forecast_runtime_config.py:219`). Group C: 2 `unconfigured->503` tests monkeypatch the source-module resolver to None. Group A: evidence script bare `python3` → `${VENV_PYTHON:-.venv/bin/python}` + tests pass `sys.executable`. `-k forecast` 88→35 failing, 53 fixed, 0 regressions. Residual 35 pre-existing + unmasked (4 root causes: `project_display_name` KeyError, `_run_comprehensive` missing project_key, proof perturb-callback project_key, launcher `HB_FORECAST_EVAL_ROOT`) documented for a focused follow-up. No schema/hb_assistant-product change; Group D = 4× one-line CFR-source bug fix. Evidence `P10-PR1-suite-hardening-20260623T205408Z`. ADR 304.
