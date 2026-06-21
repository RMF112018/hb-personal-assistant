# External Forecast Evaluation Workflow

## Overview

External forecast evaluation ingests operator-provided forecast files (CSV), maps rows to canonical budget codes, compares against backend baselines, and writes an **isolated** evidence package + per-run eval SQLite. It never mutates the live production DB.

## Project eligibility

Resolved by `resolve_eligible_eval_projects()` in priority order:

1. **Environment allowlist** — `HB_FORECAST_EVAL_PROJECT_ALLOWLIST=proj1,proj2` (highest priority)
2. **`forecast_projects` table** — `enabled = 1` rows merged with defaults
3. **Built-in defaults** — `tropical`, `fixtureproj` (tests)

Disabled or unknown projects fail closed with `ForecastExternalError`.

## Eval root

- Default: resolved by `resolve_eval_root()` from `HB_FORECAST_EVAL_ROOT` or Application Support path
- Per evaluation: `{eval_root}/evaluations/{eval_id}/`
- Isolated DB: `{eval_dir}/eval.sqlite` (V61 tables only)
- Retention: operator-managed; no automatic purge in MVP

## Ingest

Service: `ForecastExternalIngestService.preview()`

- Input: base64 CSV content, `source_system`, `period`
- Output: `import_id`, row/column metadata, fingerprint hashes
- Rejected: malformed CSV, empty files (fail-closed)

## Mapping

Service: `ForecastExternalMappingService`

- Exact / normalized budget code match against `forecast_budget_details`
- Unmapped rows → review queue
- Ambiguous mappings → review items (no silent inference)

## Evaluation

`ForecastExternalEvalService.evaluate(import_id, column_roles, project_key)`

1. Eligibility check (with optional `HB_FORECAST_DB_PATH` for `forecast_projects`)
2. Mapping validation
3. Baseline load (newest comprehensive package or prior external eval)
4. Comparison + anomaly detection
5. Evidence package + eval DB projection

## Outputs

- `import_receipt.json`, `mapped_forecast_rows.csv`, `unmapped_rows.csv`
- `comparison_results.csv`, `accuracy_results.csv`
- `anomaly_findings.jsonl`, `human_review_queue.jsonl`
- `manifest.json` with eligible project list

## Safety guardrails

- `writes_isolated_eval_root: true`
- `no_live_db_write: true`
- `no_llm: true`
- `no_live_endpoint_calls: true`
- No raw upload bodies in committed evidence

## Operator commands

```bash
# Ingest preview (via API/CLI surfaces using ForecastExternalIngestService)
# Evaluate
HB_FORECAST_EVAL_ROOT=/path/to/eval HB_FORECAST_DB_PATH=/path/to/db.sqlite \
  python -c "from hb_assistant.construction.analytics.forecast_external_eval_service import ForecastExternalEvalService; ..."
```

## Known limitations

- Eligibility does not auto-discover all Procore projects — requires `forecast_projects` seeding or env allowlist
- XLSX ingest not implemented in MVP (CSV only)
- UI workflow documented for future SPFx/forecast UI integration