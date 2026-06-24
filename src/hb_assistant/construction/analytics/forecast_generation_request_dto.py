"""DTOs + validation for the forecast generation-request contract (Phase P-C).

Pure, dependency-light helpers: parse + validate the request body into a normalized shape with
coded errors, and project a stored request row into a redaction-safe public dict. User-facing copy
lives in the frontend; here everything is coded/deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

_GENERATOR_KINDS = ("comprehensive", "model_controls", "monthly", "probability")


def _valid_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_request(body: dict[str, Any] | None, *, mode: str) -> tuple[dict[str, Any], list[str]]:
    """Return (parsed, errors). errors is a list of coded strings (empty == valid).

    parsed always carries: project_key, generator_kind (db_config only, else None),
    forecast_start_date, forecast_cutoff_date, forecast_cutoff_date_basis.
    """
    body = body or {}
    errors: list[str] = []

    project_key = str(body.get("project_key") or "").strip()
    if not project_key:
        errors.append("missing_project_key")

    generator_kind: str | None = None
    if mode == "db_config":
        generator_kind = body.get("generator_kind", "comprehensive")
        if generator_kind not in _GENERATOR_KINDS:
            errors.append("invalid_generator_kind")

    start_raw = body.get("forecast_start_date")
    cutoff_raw = body.get("forecast_cutoff_date")
    start_date = str(start_raw).strip() if start_raw not in (None, "") else None
    cutoff_date = str(cutoff_raw).strip() if cutoff_raw not in (None, "") else None

    if start_date is not None and not _valid_iso_date(start_date):
        errors.append("invalid_forecast_start_date")
        start_date = None
    if cutoff_date is not None and not _valid_iso_date(cutoff_date):
        errors.append("invalid_forecast_cutoff_date")
        cutoff_date = None
    if start_date is not None and cutoff_date is not None and start_date > cutoff_date:
        errors.append("forecast_start_after_cutoff")

    parsed = {
        "project_key": project_key,
        "generator_kind": generator_kind,
        "forecast_start_date": start_date,
        "forecast_cutoff_date": cutoff_date,
        # P-C: an operator-supplied cut-off is the only basis. Schedule-derived defaulting is P-D.
        "forecast_cutoff_date_basis": "operator_supplied" if cutoff_date is not None else None,
    }
    return parsed, errors


def request_row_to_public(row: dict[str, Any]) -> dict[str, Any]:
    """Project a stored request row into a redaction-safe public dict (no *_json, paths, free text)."""
    return {
        "request_id": row.get("request_id"),
        "run_id": row.get("run_id"),
        "project_key": row.get("project_key"),
        "generation_mode": row.get("generation_mode"),
        "generator_kind": row.get("generator_kind"),
        "request_status": row.get("request_status"),
        "validation_status": row.get("validation_status"),
        "forecast_start_date": row.get("forecast_start_date"),
        "forecast_cutoff_date": row.get("forecast_cutoff_date"),
        "forecast_cutoff_date_basis": row.get("forecast_cutoff_date_basis"),
        "readiness_status_at_request": row.get("readiness_status_at_request"),
        "readiness_reasons": _loads_list(row.get("readiness_reasons_json")),
        "failure_code": row.get("failure_code"),
        "created_utc": row.get("created_utc"),
        "updated_utc": row.get("updated_utc"),
    }


def _loads_list(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return [str(v) for v in value] if isinstance(value, list) else []
    except (ValueError, TypeError):
        return []
