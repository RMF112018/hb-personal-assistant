# P9 — UI/API readiness + operator workflow (Gaps 1/5/6/7/9 surface)

- Phase: forecast-model remediation **P9**
- ADR: `docs/architecture/310-forecast-p9-ui-api-readiness.md`
- Scope: read-only UI/API only — **no schema/migration/`table_count` change, no live-DB write, no
  external system, no CFR source change → no sensitive-op gate.**

## What landed

1. **Read-model** (`construction/analytics/forecast_run_readmodel.py`): `read_narratives(output_id)`
   curates the P8 `forecast_output_narratives` per scope (`_curate_narrative` whitelist), dropping
   stamp-format keys and scrubbing the free-text narrative (`_redact_stamps`); `list_projects()`;
   `variance_to_prior_forecast` added to `list_outputs`.
2. **API** (`construction/analytics/api.py`): `GET /api/forecast/db/projects` and
   `GET /api/forecast/db/outputs/{output_id}/narratives` (viewer-role, reusing the existing service
   factory + 404 wrapper).
3. **Frontend** (`frontend/`): new `ForecastNarrativesPanel`; `ForecastDecisionSupportPanel` +
   `ForecastOperatorAssumptionsPanel` prop-ified (`project`); `ForecastRunCenterPage` multi-project
   selector threading `project` into all three panels; `api.ts` client fns + interfaces +
   `variance_to_prior_forecast` on the summary type.

## Key decisions

- **Backup split to P9b.** The spec's "durable live-write backup" is a sensitive CFR live-write-path
  change → deferred to a separate gated PR. P9 is read-only.
- **Narrative redaction is load-bearing.** The P8 narrative *free-text* embeds run stamps
  (`source_qa` forecast_period, `lineage` prior_run). The curator drops the structured stamp keys AND
  scrubs the narrative string; the no-raw-leak test seeds both forms of bait.

## Validation

`validation.txt` / `new_tests.txt`. Forecasting bundle 898 passed / 0 failed (895 P8 baseline + 3);
frontend typecheck clean; vitest 16 passed / 0 failed (incl. the new narratives panel + the
multi-project selector). `find_redaction_leaks` clean with stamp bait in fields and narrative text.
