# Forecasting and Schedule Test Bundles

The forecasting and schedule test bundles are fast, focused validation suites for local development. They provide relevant domain coverage without requiring the full default test suite. They do not replace the full suite for broad regression, release, or major cross-domain changes.

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

## Forecasting Bundle Coverage

`scripts/test-forecasting.sh` uses an explicit list of existing pytest targets that cover forecast API and browser surfaces, forecast configuration, runtime configuration, DB schema and migrations, DB-backed read repositories, context generation, output persistence, semantic gates, readiness gates, model-engine readiness, and directly relevant financial source-domain normalization and projection tests.

It intentionally excludes broad Procore, Graph, Sage, live-sync, local-DB, evidence-package output, and unrelated scheduler tests. It also excludes `tests/test_forecast_context_generator_phase5.py::test_live_source_copy_smoke` because it reads a Synology-backed CloudStorage sample path, `tests/test_phase_08c_financial_completeness.py::test_evaluate_forecast_readiness_gates_produces_readiness_report_and_proof_no_decisions` because it assumes a worktree-local `.venv/bin/hb-assistant` console script, and `tests/test_forecast_model_controls_db_config_phase17.py::test_live_db_and_source_config_not_mutated` because it uses a byte-for-byte SQLite DB comparison that is not stable under the current local runtime. Marked `integration`, `manual`, and `live` tests remain in the repo but are outside this fast local bundle.

Run this bundle after changing forecast generation, forecast configuration, forecast read models, forecast readiness or semantic gates, forecast UI/API surfaces, or forecast-related financial source-domain normalization.

## Schedule Bundle Coverage

`scripts/test-schedule.sh` uses an explicit list of existing pytest targets that cover schedule import, XER/XML/MSP parsing, project association, activities, schedule versions, schedule quality, critical path and float behavior, cost mapping controls, schedule migrations, and Procore schedule projection and normalization.

It intentionally excludes general calendar/email scheduling tests, broad Procore live/auth/sync tests, `subrepos/construction-financial-review/tests`, generated evidence packages, local DB files, raw payload files, and external-service workflows. It also excludes stale schema-version tests that still assert schema 67 or 70 while current schema is 71, plus tests that read `~/Downloads/*.xer` or `~/Downloads/schedule-xml-files.zip`.

Run this bundle after changing schedule ingestion, schedule quality, construction schedule read models, schedule-to-project mapping, schedule cost mapping controls, or schedule migration behavior.

## Full Suite

These bundles are intended for focused pre-PR validation and inner-loop development. Use the full default suite when validating broad release readiness, cross-domain refactors, test infrastructure changes, or behavior that can affect unrelated areas.
