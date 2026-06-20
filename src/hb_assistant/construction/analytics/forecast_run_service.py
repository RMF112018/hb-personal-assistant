"""Forecast Run Center service (Implementation Phase 3).

Generates a deterministic context->analysis package chain by wrapping the existing CFR Phase 9
controlled workflow (``run_controlled_context_analysis_workflow`` in ``file`` mode). This is the
first write-bearing surface, but writes are confined to an explicitly-configured **isolated
runs-root**: it reads the source ``data_root`` read-only, never writes the live data root or the
live DB, and never calls an LLM.

CFR integration: ``construction_financial_review`` is not installed in the hb_assistant venv, so
the service injects the subrepo ``src`` onto ``sys.path`` and ``PYTHONPATH`` (so the Phase 7
subprocess inherits it) before importing the workflow — no install, no CFR edit, no extra deps.

Fail-closed: refuses unless ``data_root`` (read-only input) and ``runs_root`` (isolated output,
never under the data root) are explicitly configured and valid. Payloads are redacted DTOs.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.forecast_run_dto import (
    run_record_to_list_item,
    run_record_to_summary,
)

ENV_DATA_ROOT = "HB_FORECAST_DATA_ROOT"
ENV_RUNS_ROOT = "HB_FORECAST_RUNS_ROOT"
ENV_CFR_SRC = "HB_FORECAST_CFR_SRC"

_SURFACE = "analytics.forecast_run"
_RECORD_NAME = "run_record.json"
_SUPPORTED_PROJECT = "tropical"


class ForecastRunError(RuntimeError):
    """Raised when the run service is misconfigured (fail closed) or a run is unknown."""


def _guardrails() -> dict[str, Any]:
    # Honest about the posture: this surface WRITES (isolated work-root) but never the live root/DB.
    return {
        "writes_isolated_work_root": True,
        "no_live_db_write": True,
        "no_live_data_root_write": True,
        "no_llm": True,
        "no_live_endpoint_calls": True,
        "local_first": True,
    }


def _cfr_src() -> Path:
    override = os.environ.get(ENV_CFR_SRC)
    src = (
        Path(override)
        if override
        else Path(__file__).resolve().parents[4] / "subrepos" / "construction-financial-review" / "src"
    )
    if not src.is_absolute() or not src.exists() or not src.is_dir():
        raise ForecastRunError("the construction-financial-review source is not available")
    return src


def _ensure_cfr_importable() -> None:
    """Inject the CFR src onto sys.path + PYTHONPATH so the workflow (and its subprocess) resolve."""
    s = str(_cfr_src())
    if s not in sys.path:
        sys.path.insert(0, s)
    existing = os.environ.get("PYTHONPATH", "")
    parts = existing.split(os.pathsep) if existing else []
    if s not in parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([s, *parts]) if parts else s


def _summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    """Extract ONLY safe fields from the workflow report (no paths, no stamps)."""
    checks = report.get("safety_checks") if isinstance(report.get("safety_checks"), dict) else {}
    packages: list[str] = []
    if report.get("context_package"):
        packages.append("context")
    if report.get("analysis_package"):
        packages.append("analysis")
    no_live = (
        report.get("mode") == "file"
        and report.get("db_backed") is False
        and bool(checks.get("work_root_outside_live_root"))
    )
    return {"packages": packages, "checks": dict(checks), "no_live_writes": bool(no_live)}


class ForecastRunService:
    """Triggers and lists isolated context->analysis generation runs."""

    def __init__(self, data_root: str | None = None, runs_root: str | None = None) -> None:
        self._data_root_override = data_root
        self._runs_root_override = runs_root

    # -- fail-closed config ---------------------------------------------------

    def _data_root(self) -> Path:
        raw = self._data_root_override or os.environ.get(ENV_DATA_ROOT)
        if not raw:
            raise ForecastRunError("forecast data root is not configured")
        p = Path(raw)
        if not p.is_absolute() or not p.exists() or not p.is_dir():
            raise ForecastRunError("forecast data root is not a valid directory")
        return p

    def _runs_root(self) -> Path:
        raw = self._runs_root_override or os.environ.get(ENV_RUNS_ROOT)
        if not raw:
            raise ForecastRunError("forecast runs root is not configured")
        p = Path(raw)
        if not p.is_absolute():
            raise ForecastRunError("forecast runs root must be an absolute path")
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ForecastRunError("forecast runs root could not be created") from exc
        return p

    @staticmethod
    def _is_under(child: Path, parent: Path) -> bool:
        try:
            c = child.resolve(strict=False)
            r = parent.resolve(strict=False)
            return c == r or c.is_relative_to(r)
        except OSError:
            return True  # fail closed

    # -- record IO ------------------------------------------------------------

    def _write_record(self, runs_root: Path, run_id: str, record: dict[str, Any]) -> None:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / _RECORD_NAME).write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )

    def _read_record(self, runs_root: Path, run_id: str) -> dict[str, Any] | None:
        path = runs_root / run_id / _RECORD_NAME
        try:
            with path.open("r", encoding="utf-8") as fh:
                obj = json.load(fh)
            return obj if isinstance(obj, dict) else None
        except (OSError, ValueError):
            return None

    # -- public API -----------------------------------------------------------

    def start_run(self, project_key: str = _SUPPORTED_PROJECT) -> dict[str, Any]:
        data_root = self._data_root()
        runs_root = self._runs_root()
        # Defense-in-depth: never write runs into (or under) the source/live data root.
        if self._is_under(runs_root, data_root):
            raise ForecastRunError("forecast runs root must not be under the data root")
        _ensure_cfr_importable()

        run_id = uuid.uuid4().hex[:12]
        created_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 (local run stamp)
        work_root = runs_root / run_id
        record: dict[str, Any] = {
            "run_id": run_id,
            "created_stamp": created_stamp,
            "project_key": project_key,
            "mode": "file",
        }
        try:
            from construction_financial_review.workflows.controlled_db_context_analysis import (
                run_controlled_context_analysis_workflow,
            )

            # Suppress the generators' stdout (they print progress JSON) so it never pollutes
            # the server console or the response thread; the structured report is the return value.
            with contextlib.redirect_stdout(io.StringIO()):
                report = run_controlled_context_analysis_workflow(
                    data_root=data_root,
                    work_root=work_root,
                    context_stamp=created_stamp,
                    mode="file",
                    project_key=project_key,
                )
            record.update(_summarize_report(report))
            record["status"] = "succeeded"
        except Exception as exc:  # noqa: BLE001 — record any generation failure as a failed run
            record["status"] = "failed"
            record["packages"] = []
            record["checks"] = {}
            record["no_live_writes"] = True  # failure occurs at/before generation; no live write path
            record["message"] = f"Forecast generation did not complete ({type(exc).__name__})."
        self._write_record(runs_root, run_id, record)
        return {
            "surface": _SURFACE + ".run",
            **run_record_to_summary(record).public(),
            "guardrails": _guardrails(),
        }

    def list_runs(self) -> dict[str, Any]:
        runs_root = self._runs_root()
        records: list[dict[str, Any]] = []
        try:
            children = [p for p in runs_root.iterdir() if p.is_dir()]
        except OSError:
            children = []
        for child in children:
            rec = self._read_record(runs_root, child.name)
            if rec is not None:
                records.append(rec)
        records.sort(key=lambda r: str(r.get("created_stamp") or ""), reverse=True)
        return {
            "surface": _SURFACE + ".runs",
            "runs": [run_record_to_list_item(r).public() for r in records],
            "guardrails": _guardrails(),
        }

    def read_run(self, run_id: str) -> dict[str, Any]:
        runs_root = self._runs_root()
        rec = self._read_record(runs_root, run_id)
        if rec is None:
            raise ForecastRunError(f"unknown run_id: {run_id!r}")
        return {
            "surface": _SURFACE + ".run",
            **run_record_to_summary(rec).public(),
            "guardrails": _guardrails(),
        }
