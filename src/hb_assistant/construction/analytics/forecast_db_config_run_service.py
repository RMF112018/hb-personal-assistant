"""DB-config-backed comprehensive generation service (Run Center).

Wraps the CFR ``run_forecast_db_config_backed_generation`` workflow so the Run Center can generate the
comprehensive forecast package CONSUMING the live config snapshot (so a PROMOTED config drives
generation, not just the viewer). The live config DB is the live app DB (``PathPolicy().get_db_path()``
— where Phase 16/E2 hold the snapshots) and is opened READ-ONLY; writes are confined to an isolated
runs-root. Default-OFF: requires the ``HB_FORECAST_DB_CONFIG_RUN_ENABLED`` opt-in.

Fail-closed: refuses unless the opt-in is on and ``data_root`` (read-only input) + ``runs_root``
(isolated output, never under the data root) are valid. The CFR workflow's coded refusal reasons are
mapped to path-free, user-facing messages; the workflow report (path-saturated) is never surfaced —
only redacted summary fields are persisted.
"""

from __future__ import annotations

import contextlib
import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_db_config_run_dto import (
    db_config_run_record_to_list_item,
    db_config_run_record_to_summary,
)
from hb_assistant.construction.analytics.forecast_run_service import (
    ForecastRunError,
    _ensure_cfr_importable,
)

_SURFACE = "analytics.forecast_db_config_run"
_RECORD_NAME = "db_config_run_record.json"
_SUPPORTED_PROJECT = "tropical"

# Coded refusal reasons surfaced as path-free messages (the CFR workflow's first ":"-token is reused).
_FRIENDLY_REASONS: dict[str, str] = {
    "db_config_run disabled": "Generating from live config isn't enabled in this environment.",
    "no_config_snapshot": "No configuration snapshot is available to generate from.",
    "config_fidelity_failed": "The configuration could not be verified; the run was stopped for safety.",
    "predecessor_packages_missing": (
        "Required upstream forecasts (context, intelligence, monthly) aren't available yet."
    ),
    "cost_frequency_package_missing": (
        "The cost-frequency forecast is required but hasn't been generated yet."
    ),
    "live_db_not_quiescent": "The forecast database is being updated right now; try again shortly.",
}


class ForecastDbConfigRunError(RuntimeError):
    """Raised when DB-config-backed generation is refused (fail closed) or a run is unknown.

    The first ``:``-delimited token of the message is a stable coded reason for the route mapper.
    """


def _guardrails() -> dict[str, Any]:
    return {
        "writes_isolated_work_root": True,
        "no_live_db_write": True,
        "live_db_opened_read_only": True,
        "no_live_data_root_write": True,
        "no_llm": True,
        "config_snapshot_consumed": True,
        "local_first": True,
    }


def _coded_reason(message: str) -> str:
    return message.split(":", 1)[0].strip()


class ForecastDbConfigRunService:
    """Triggers and lists DB-config-backed comprehensive generation runs."""

    def __init__(
        self,
        *,
        data_root: str | None = None,
        runs_root: str | None = None,
        cfr_src: str | None = None,
        db_config_run_enabled: bool = False,
    ) -> None:
        # Reuse the Phase 3 run service for the validated data_root/runs_root + record IO + CFR import.
        from hb_assistant.construction.analytics.forecast_run_service import ForecastRunService

        self._base = ForecastRunService(data_root=data_root, runs_root=runs_root)
        self._cfr_src = cfr_src
        self._enabled = db_config_run_enabled

    def _live_config_db(self) -> Path:
        """The live app DB holding the config registry snapshots (opened read-only downstream)."""
        p = Path(PathPolicy().get_db_path())
        if not p.exists():
            raise ForecastDbConfigRunError("config_db_not_ready: live config DB is not available")
        return p

    def start_db_config_run(
        self, project_key: str = _SUPPORTED_PROJECT, *, snapshot_id: str | None = None
    ) -> dict[str, Any]:
        if not self._enabled:
            raise ForecastDbConfigRunError("db_config_run disabled")
        try:
            data_root = self._base._data_root()
            runs_root = self._base._runs_root()
        except ForecastRunError as exc:
            raise ForecastDbConfigRunError(f"not_configured: {exc}") from exc
        if self._base._is_under(runs_root, data_root):
            raise ForecastDbConfigRunError("not_configured: runs root must not be under the data root")
        live_db = self._live_config_db()
        _ensure_cfr_importable()

        run_id = uuid.uuid4().hex[:12]
        created_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 (local run stamp)
        work_root = runs_root / run_id
        record: dict[str, Any] = {
            "run_id": run_id,
            "created_stamp": created_stamp,
            "project_key": project_key,
            "mode": "db_config",
        }
        try:
            from construction_financial_review.workflows.forecast_db_config_backed_generation import (
                ForecastDbConfigGenerationError,
                run_forecast_db_config_backed_generation,
            )

            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    report = run_forecast_db_config_backed_generation(
                        project_key=project_key,
                        live_db_path=live_db,
                        work_root=work_root,
                        data_root=data_root,
                        config_snapshot_id=snapshot_id,
                        require_live_snapshot=True,
                    )
            except ForecastDbConfigGenerationError as exc:
                code = _coded_reason(str(exc))
                record["status"] = "failed"
                record["config_snapshot_consumed"] = False
                record["no_live_writes"] = True
                record["message"] = _FRIENDLY_REASONS.get(
                    code, "The forecast generation was stopped for safety."
                )
                self._base._write_record(runs_root, run_id, record)
                return self._summary(record)

            # Success: extract ONLY safe fields (the report is path-saturated — never surface it).
            integ = report.get("live_db_integrity") if isinstance(report.get("live_db_integrity"), dict) else {}
            record["status"] = (
                "generated" if report.get("status") == "generated" else "generated_validation_failed"
            )
            record["config_snapshot_consumed"] = bool(report.get("config_snapshot_consumed"))
            record["snapshot_display"] = report.get("snapshot_name")
            record["snapshot_item_count"] = int(report.get("snapshot_item_count") or 0)
            record["fidelity_gate_passed"] = bool(
                (report.get("fidelity_gate") or {}).get("passed")
            )
            record["validation_passed"] = bool(report.get("validation_passed"))
            record["package_generated"] = bool(report.get("output_package"))
            record["live_db_unchanged"] = bool(integ.get("unchanged"))
            record["no_live_writes"] = bool(integ.get("unchanged"))
        except ForecastDbConfigRunError:
            raise
        except Exception as exc:  # noqa: BLE001 — record any generation failure as a failed run
            record["status"] = "failed"
            record["config_snapshot_consumed"] = False
            record["no_live_writes"] = True
            record["message"] = f"Forecast generation did not complete ({type(exc).__name__})."
        self._base._write_record(runs_root, run_id, record)
        return self._summary(record)

    def _summary(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            "surface": _SURFACE + ".run",
            **db_config_run_record_to_summary(record).public(),
            "guardrails": _guardrails(),
        }

    def list_db_config_runs(self) -> dict[str, Any]:
        runs_root = self._base._runs_root()
        records: list[dict[str, Any]] = []
        try:
            children = [p for p in runs_root.iterdir() if p.is_dir()]
        except OSError:
            children = []
        for child in children:
            rec = self._base._read_record(runs_root, child.name)
            # Only DB-config runs (the runs_root is shared with the Phase 3 file-config runs).
            if rec is not None and rec.get("mode") == "db_config":
                records.append(rec)
        records.sort(key=lambda r: str(r.get("created_stamp") or ""), reverse=True)
        return {
            "surface": _SURFACE + ".runs",
            "runs": [db_config_run_record_to_list_item(r).public() for r in records],
            "guardrails": _guardrails(),
        }

    def read_db_config_run(self, run_id: str) -> dict[str, Any]:
        runs_root = self._base._runs_root()
        rec = self._base._read_record(runs_root, run_id)
        if rec is None or rec.get("mode") != "db_config":
            raise ForecastDbConfigRunError(f"unknown run_id: {run_id!r}")
        return self._summary(rec)
