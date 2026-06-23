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
| P2 | Operator assumptions as consumed model inputs | 2 | high | pending | — | — | — | — |
| P3 | DB-native model input accessors (reduce package-as-source) | 3 | high | pending | — | — | — | — |
| P6 | Model registry / versioning / weighting / calibration governance | 6 | high | pending | — | — | — | — |
| P10 | Forecast-correctness & isolation test hardening | 10 | high | pending | — | — | — | — |
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
- **P2** — consume `forecast_operator_assumptions`/`forecast_required_assumptions` as value overrides,
  confidence modifiers, and a required-satisfaction gate. Default-off flag until validated.
- **P3** — DB-backed model-input accessors (v59/runtime) with packages as fallback; prove parity.
- **P6** — DB-backed model registry (migration v72+); versioned estimators/weights/thresholds; persist
  `forecast_method_eligibility`/`forecast_model_selection_decisions` with rationale; per-run model-version metadata.
- **P10** — add model-value, assumption-consumption, prior-delta, multi-project, copied-DB tests; fix the
  red forecast suite (stale `schema_version == 61/67/70` asserts, `unconfigured->503` isolation leaks,
  evidence-script subprocess interpreter).
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
