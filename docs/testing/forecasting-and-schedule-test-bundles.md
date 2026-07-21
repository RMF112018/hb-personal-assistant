# Forecasting and Schedule Test Bundles

The forecasting and schedule test bundles are focused validation suites for local development. They provide relevant domain coverage without requiring the full default test suite. They do not replace the full suite for broad regression, release, or major cross-domain changes.

Test selection and failure disposition are governed by:

```text
.ai/project-sources/11_REPOSITORY_TEST_SELECTION_STANDARD.md
docs/decisions/DECISION-PROPORTIONAL-TEST-SELECTION-001.md
```

## Commands

Run the forecasting-focused bundle:

```bash
scripts/test-forecasting.sh
```

Run the schedule-focused bundle:

```bash
scripts/test-schedule.sh
```

Both scripts run pytest with:

```bash
-m "not integration and not manual and not live"
```

The scripts also put the fresh worktree source roots first on `PYTHONPATH`:

```bash
src:subrepos/construction-financial-review/src
```

Additional pytest arguments can be passed through to either script. For example:

```bash
scripts/test-forecasting.sh --collect-only
scripts/test-schedule.sh --collect-only
```

## Selection Matrix

| Change surface or gate | Forecasting bundle | Schedule bundle | Full safe suite |
|---|---:|---:|---:|
| Isolated source-index repository, connector model/service, or directly related tests | Only with demonstrated forecasting dependency | Only with demonstrated schedule dependency | No, unless required by merge/release gate |
| Forecast generation, configuration, read models, semantic/readiness gates, forecast API/UI, or forecast-related financial normalization | Yes | No, unless a schedule dependency is demonstrated | No during inner loop |
| Schedule ingestion, XER/XML/MSP parsing, schedule quality, CPM, mapping, cost controls, projections, or schedule migration | No, unless a forecasting dependency is demonstrated | Yes | No during inner loop |
| `src/hb_assistant/store/migrator.py`, shared schema/bootstrap, or common DB infrastructure used by both domains | Yes | Yes | Conditional on blast radius and gate |
| Shared CLI/API/data contract spanning both domains | Yes | Yes | Conditional on blast radius and gate |
| Global fixtures, test discovery, dependency configuration, packaging, or runtime bootstrap | Applicable affected bundles | Applicable affected bundles | Yes at candidate/merge gate |
| Broad cross-domain refactor, merge readiness, or release readiness | Applicable affected bundles | Applicable affected bundles | Yes |
| Documentation-only change with no executable contract effect | No | No | No |

Do not run either bundle merely because it was required by an earlier work item or generic evidence template. Every mandatory bundle must map to an acceptance criterion, changed dependency, shared-infrastructure risk, named regression risk, or merge/release gate.

## Execution Frequency

- Inner-loop edits use the smallest relevant test node, class, file, or changed-module static check.
- A coherent implementation slice uses directly affected files and integration seams.
- Candidate validation uses the complete bounded work-item suite.
- Expensive bundles normally run once per materially different committed candidate SHA when their trigger condition is satisfied.
- Bookkeeping-only turns do not rerun tests when SHA, command, dependencies, environment, inputs, and evidence purpose are unchanged.
- Full safe-suite execution is reserved for the gates identified in the selection matrix.

## Forecasting Bundle Coverage

`scripts/test-forecasting.sh` uses an explicit list of existing pytest targets that cover forecast API and browser surfaces, forecast configuration, runtime configuration, DB schema and migrations, DB-backed read repositories, context generation, output persistence, semantic gates, readiness gates, model-engine readiness, and directly relevant financial source-domain normalization and projection tests.

It intentionally excludes broad Procore, Graph, Sage, live-sync, local-DB, evidence-package output, and unrelated scheduler tests. It also excludes `tests/test_forecast_context_generator_phase5.py::test_live_source_copy_smoke` because it reads a Synology-backed CloudStorage sample path, `tests/test_phase_08c_financial_completeness.py::test_evaluate_forecast_readiness_gates_produces_readiness_report_and_proof_no_decisions` because it assumes a worktree-local `.venv/bin/hb-assistant` console script, and `tests/test_forecast_model_controls_db_config_phase17.py::test_live_db_and_source_config_not_mutated` because it uses a byte-for-byte SQLite DB comparison that is not stable under the current local runtime. Marked `integration`, `manual`, and `live` tests remain in the repo but are outside this focused local bundle.

Run this bundle after changing forecast generation, forecast configuration, forecast read models, forecast readiness or semantic gates, forecast UI/API surfaces, forecast-related financial source-domain normalization, or shared infrastructure with a demonstrated forecasting dependency.

## Schedule Bundle Coverage

`scripts/test-schedule.sh` uses an explicit list of existing pytest targets that cover schedule import, XER/XML/MSP parsing, project association, activities, schedule versions, schedule quality, critical path and float behavior, cost mapping controls, schedule migrations, and Procore schedule projection and normalization.

It intentionally excludes general calendar/email scheduling tests, broad Procore live/auth/sync tests, `subrepos/construction-financial-review/tests`, generated evidence packages, local DB files, raw payload files, and external-service workflows. It also excludes stale schema-version tests that still assert schema 67 or 70 while current schema is 71, plus tests that read `~/Downloads/*.xer` or `~/Downloads/schedule-xml-files.zip`.

Run this bundle after changing schedule ingestion, schedule quality, construction schedule read models, schedule-to-project mapping, schedule cost mapping controls, schedule migration behavior, or shared infrastructure with a demonstrated schedule dependency.

The schedule bundle's migration/schema tests make it an appropriate cross-domain canary for changes to `src/hb_assistant/store/migrator.py` or verified common schema/bootstrap behavior. That does not make it a default canary for isolated source-index runtime work.

## Failure Disposition

Preserve every failure and classify it before assigning corrective ownership:

- **Candidate regression:** the active work item stops the affected checkpoint and fixes it.
- **Reproducible pre-existing defect:** reproduce on the immutable base SHA under a materially equivalent command/environment and create a separately authorized corrective work item.
- **Invalid or stale test:** correct under a bounded test-correction work item; do not silently weaken, skip, or delete it.
- **Flaky or nondeterministic test:** preserve repeated-run evidence and create a stabilization work item.
- **Environment/configuration failure:** correct or formally document the environment; do not report the product green from an invalid run.
- **Unknown relationship:** treat as potentially related until causality is established.

A separate corrective agent may run in parallel only with explicit authorization, separate registered branch/worktree and evidence, non-overlapping ownership, and no shared schema, migrator/bootstrap, global-fixture, dependency, security, or acceptance-evidence conflict. The primary agent may not self-authorize that stream.

No integrated candidate is merge-ready while a required safe test has an unresolved failure.

## Full Suite

Use the full default safe suite when validating broad release readiness, merge readiness, cross-domain refactors, test infrastructure changes, global fixtures, dependency or packaging changes, runtime bootstrap, or behavior that can affect unrelated areas. Full-suite results do not replace focused acceptance evidence, and focused evidence does not waive a failing full-suite gate when that gate is applicable.
