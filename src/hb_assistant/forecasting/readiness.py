"""Forecast semantic-gate readiness adapter for Phase 08C integration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from hb_assistant.forecasting.gates import run_all_forecasting_gates

GateMode = Literal["warn", "strict"]


def _map_gate_status(*, ok: bool, warning_count: int, error_count: int) -> str:
    if error_count > 0:
        return "fail_blocking"
    if not ok or warning_count > 0:
        return "warning"
    return "pass"


def evaluate_forecast_semantic_gates(
    *,
    db_path: str | Path,
    mode: GateMode = "warn",
) -> dict[str, Any]:
    """Run combined forecast semantic gates with readiness-compatible JSON shape."""
    report = run_all_forecasting_gates(db_path=db_path, mode=mode)
    warning_count = int(report["summary"]["warning_count"])
    error_count = int(report["summary"]["error_count"])
    gate_status = _map_gate_status(
        ok=bool(report["ok"]),
        warning_count=warning_count,
        error_count=error_count,
    )
    return {
        **report,
        "gate_status": gate_status,
        "readiness_note": (
            "Semantic forecast gates are advisory; warnings indicate unresolved precedence "
            "or projection drift — not automatic forecast defects."
        ),
    }