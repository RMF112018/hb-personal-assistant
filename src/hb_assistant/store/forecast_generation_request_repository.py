"""Repository for forecast_generation_requests rows (Phase P-C).

Durable, DB-first ledger of Generate-Forecast requests. One row per generation attempt records
the request contract (project / dates / mode / kind), the readiness snapshot and request-contract
validation state at request time, and the resulting run linkage + terminal outcome. Writes go to
the app-managed SQLite DB (never a package manifest, log line, or frontend state).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .connection import open_connection, transaction

_COLUMNS = (
    "request_id",
    "run_id",
    "project_key",
    "generation_mode",
    "generator_kind",
    "forecast_start_date",
    "forecast_cutoff_date",
    "forecast_cutoff_date_basis",
    "schedule_version_key",
    "config_snapshot_id",
    "model_version_key",
    "requested_by_role",
    "request_status",
    "validation_status",
    "validation_errors_json",
    "readiness_status_at_request",
    "readiness_reasons_json",
    "created_utc",
    "updated_utc",
    "started_utc",
    "completed_utc",
    "failed_utc",
    "failure_code",
    "failure_message",
)

# request_status values that stamp a terminal/lifecycle timestamp column.
_STATUS_TIMESTAMP = {
    "running": "started_utc",
    "completed": "completed_utc",
    "failed": "failed_utc",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class ForecastGenerationRequestRepository:
    """Create / read / update / list forecast_generation_requests rows."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path

    # -- writes ---------------------------------------------------------------

    def create(
        self,
        *,
        project_key: str,
        generation_mode: str,
        request_status: str,
        validation_status: str,
        generator_kind: str | None = None,
        forecast_start_date: str | None = None,
        forecast_cutoff_date: str | None = None,
        forecast_cutoff_date_basis: str | None = None,
        schedule_version_key: str | None = None,
        config_snapshot_id: str | None = None,
        model_version_key: str | None = None,
        requested_by_role: str | None = None,
        validation_errors: list[str] | None = None,
        readiness_status_at_request: str | None = None,
        readiness_reasons: list[str] | None = None,
    ) -> str:
        """Insert one request row and return its request_id."""
        now = _utc_now()
        row: dict[str, Any] = {
            "request_id": _new_request_id(),
            "run_id": None,
            "project_key": project_key,
            "generation_mode": generation_mode,
            "generator_kind": generator_kind,
            "forecast_start_date": forecast_start_date,
            "forecast_cutoff_date": forecast_cutoff_date,
            "forecast_cutoff_date_basis": forecast_cutoff_date_basis,
            "schedule_version_key": schedule_version_key,
            "config_snapshot_id": config_snapshot_id,
            "model_version_key": model_version_key,
            "requested_by_role": requested_by_role,
            "request_status": request_status,
            "validation_status": validation_status,
            "validation_errors_json": json.dumps(validation_errors or []),
            "readiness_status_at_request": readiness_status_at_request,
            "readiness_reasons_json": json.dumps(readiness_reasons or []),
            "created_utc": now,
            "updated_utc": now,
            "started_utc": now if request_status == "running" else None,
            "completed_utc": None,
            "failed_utc": now if request_status in ("failed", "rejected") else None,
            "failure_code": None,
            "failure_message": None,
        }
        names = ", ".join(_COLUMNS)
        placeholders = ", ".join("?" for _ in _COLUMNS)
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                conn.execute(
                    f"INSERT INTO forecast_generation_requests ({names}) VALUES ({placeholders})",
                    tuple(row[c] for c in _COLUMNS),
                )
        return row["request_id"]

    def update_status(self, request_id: str, request_status: str, **fields: Any) -> None:
        """Update request_status (+ optional fields), bumping updated_utc and any terminal stamp."""
        now = _utc_now()
        updates: dict[str, Any] = {"request_status": request_status, "updated_utc": now, **fields}
        stamp_col = _STATUS_TIMESTAMP.get(request_status)
        if stamp_col and stamp_col not in updates:
            updates[stamp_col] = now
        sets = ", ".join(f"{k}=?" for k in updates)
        with open_connection(self._db_path) as conn:
            with transaction(conn):
                conn.execute(
                    f"UPDATE forecast_generation_requests SET {sets} WHERE request_id=?",
                    (*updates.values(), request_id),
                )

    def attach_run(self, request_id: str, run_id: str) -> None:
        self.update_status(request_id, "running", run_id=run_id)

    def record_validation_rejection(
        self,
        *,
        project_key: str,
        generation_mode: str,
        validation_errors: list[str],
        generator_kind: str | None = None,
        forecast_start_date: str | None = None,
        forecast_cutoff_date: str | None = None,
        forecast_cutoff_date_basis: str | None = None,
        requested_by_role: str | None = None,
        readiness_status_at_request: str | None = None,
        readiness_reasons: list[str] | None = None,
    ) -> str:
        """Persist a rejected request whose contract failed validation (no generation invoked)."""
        return self.create(
            project_key=project_key,
            generation_mode=generation_mode,
            request_status="rejected",
            validation_status="invalid",
            generator_kind=generator_kind,
            forecast_start_date=forecast_start_date,
            forecast_cutoff_date=forecast_cutoff_date,
            forecast_cutoff_date_basis=forecast_cutoff_date_basis,
            requested_by_role=requested_by_role,
            validation_errors=validation_errors,
            readiness_status_at_request=readiness_status_at_request,
            readiness_reasons=readiness_reasons,
        )

    def record_failure(
        self,
        request_id: str,
        failure_code: str,
        failure_message: str | None = None,
        *,
        request_status: str = "failed",
    ) -> None:
        self.update_status(
            request_id,
            request_status,
            failure_code=failure_code,
            failure_message=failure_message,
        )

    # -- reads ----------------------------------------------------------------

    def get(self, request_id: str) -> dict[str, Any] | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM forecast_generation_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def list_recent(
        self, project_key: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        bounded = max(1, min(int(limit), 100))
        with open_connection(self._db_path) as conn:
            if project_key:
                cur = conn.execute(
                    "SELECT * FROM forecast_generation_requests WHERE project_key=? "
                    "ORDER BY created_utc DESC, request_id DESC LIMIT ?",
                    (project_key, bounded),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM forecast_generation_requests "
                    "ORDER BY created_utc DESC, request_id DESC LIMIT ?",
                    (bounded,),
                )
            return [dict(r) for r in cur.fetchall()]
