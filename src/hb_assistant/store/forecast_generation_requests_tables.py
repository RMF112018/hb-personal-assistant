"""V73 forecast generation-request table name and DDL statements.

Durable Generate-Forecast request contract (Phase P-C). Each generation attempt persists one
row capturing what the operator requested and how it resolved: the selected project, optional
forecast start/cut-off dates (with the cut-off basis), generation mode + generator kind, the
runtime/project readiness snapshot at request time, request-contract validation state, and the
resulting run linkage. This gives Generate Forecast a queryable DB-first request ledger instead
of leaving the request only in transient frontend state, logs, or run artifacts.

Coded enums (kept deterministic; user-facing copy lives in the API/UI translation layer):
- generation_mode            : file_config | db_config
- generator_kind             : comprehensive | model_controls | monthly | probability | NULL
- request_status             : created | queued | running | completed | failed | rejected
- validation_status          : valid | invalid
- forecast_cutoff_date_basis : operator_supplied | NULL  (schedule-derived basis is P-D)

Additive CREATE TABLE IF NOT EXISTS only; ships empty (operational_empty_expected) and is
populated at runtime by the generation routes writing to the app-managed DB.
"""

from __future__ import annotations

V73_TABLES: tuple[str, ...] = ("forecast_generation_requests",)

V73_STATEMENTS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS forecast_generation_requests (
      request_id TEXT PRIMARY KEY,
      run_id TEXT,
      project_key TEXT NOT NULL,
      generation_mode TEXT NOT NULL,
      generator_kind TEXT,
      forecast_start_date TEXT,
      forecast_cutoff_date TEXT,
      forecast_cutoff_date_basis TEXT,
      schedule_version_key TEXT,
      config_snapshot_id TEXT,
      model_version_key TEXT,
      requested_by_role TEXT,
      request_status TEXT NOT NULL,
      validation_status TEXT NOT NULL,
      validation_errors_json TEXT NOT NULL DEFAULT '[]',
      readiness_status_at_request TEXT,
      readiness_reasons_json TEXT NOT NULL DEFAULT '[]',
      created_utc TEXT NOT NULL,
      updated_utc TEXT NOT NULL,
      started_utc TEXT,
      completed_utc TEXT,
      failed_utc TEXT,
      failure_code TEXT,
      failure_message TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_forecast_generation_requests_project_created "
    "ON forecast_generation_requests(project_key, created_utc);",
]
