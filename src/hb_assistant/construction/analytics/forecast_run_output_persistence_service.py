"""Gated run-output DB-persistence orchestration (Phase P-E).

Lands a Generate-Forecast result into the app DB as durable rows (forecast_runs anchor + v63
run-output + v66 decision-support) by reusing the CFR gated live-write
``run_controlled_live_db_run_output_projection`` (backup → temp projection → tropical replace →
post-write certification). DB persistence is mandatory for success; no user-facing export/download
package is produced and no package path / run stamp / raw payload is ever surfaced.

Separation of concerns:
- ``persist_run_output`` — pure DB-persistence step over already-produced package dirs. Fully
  exercisable with fixture packages against a temp app DB (the projection is real).
- ``generate_and_persist`` — composes the (heavy, CFR) generation step with ``persist_run_output``;
  the generation step is the deferred seam mocked in tests.
"""

from __future__ import annotations

import contextlib
import io
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Coded, path-free failure reasons (stored on the request row; returned to the UI).
FAILURE_DB_PERSISTENCE = "db_persistence_failed"
FAILURE_OUTPUT_WRITE = "forecast_output_write_failed"
FAILURE_CALCULATION = "generation_calculation_failed"
FAILURE_DISABLED = "run_output_db_write_disabled"
FAILURE_NOT_ELIGIBLE = "project_not_eligible_for_db_write"


@dataclass(frozen=True)
class GenerationPackages:
    """Ephemeral internal package dirs produced by generation (never exposed to API/UI)."""

    analysis_package: Path
    source_package: Path
    work_root: Path
    context_stamp: str
    monthly_package: Path | None = None
    probability_package: Path | None = None
    comprehensive_package: Path | None = None
    staffing_package: Path | None = None
    accuracy_package: Path | None = None
    context_package: Path | None = None


@dataclass(frozen=True)
class RunOutputPersistenceReceipt:
    """Redaction-safe outcome of a run-output DB persistence attempt (no paths/run_id/raw_json)."""

    db_persisted: bool
    package_generated: bool = False
    forecast_output_id: str | None = None
    certified: bool = False
    counts: dict[str, int] = field(default_factory=dict)
    failure_code: str | None = None


def _gen_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _latest_output_id(db_path: Path, project_key: str) -> str | None:
    try:
        conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = conn.execute(
            "SELECT output_id FROM forecast_outputs WHERE project_key=? "
            "ORDER BY created_utc DESC, output_id DESC LIMIT 1",
            (project_key,),
        ).fetchone()
        return str(row[0]) if row and row[0] is not None else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def persist_run_output(
    *, project_key: str, db_path: Path, packages: GenerationPackages, run_id: str | None = None
) -> RunOutputPersistenceReceipt:
    """Run the gated live-DB run-output projection over ``packages`` and return a safe receipt.

    Success requires the post-write certification to match. Any projection error or a non-certified
    result yields a coded failure receipt (no rows trusted). Never returns paths/run_id/raw_json.
    """
    from hb_assistant.construction.analytics.forecast_run_service import _ensure_cfr_importable

    _ensure_cfr_importable()
    from construction_financial_review.workflows.live_db_run_output_projection import (
        DECISION_CERTIFIED,
        LiveDbRunOutputProjectionError,
        run_controlled_live_db_run_output_projection,
    )

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            report = run_controlled_live_db_run_output_projection(
                analysis_package=packages.analysis_package,
                source_package=packages.source_package,
                work_root=packages.work_root,
                context_stamp=packages.context_stamp,
                run_id=run_id or _gen_run_id(),
                live_db_path=Path(db_path),
                project_key=project_key,
                allow_live_db_write=True,
                allow_replace_existing=True,
                monthly_package=packages.monthly_package,
                probability_package=packages.probability_package,
                comprehensive_package=packages.comprehensive_package,
                staffing_package=packages.staffing_package,
                accuracy_package=packages.accuracy_package,
                context_package=packages.context_package,
            )
    except LiveDbRunOutputProjectionError:
        return RunOutputPersistenceReceipt(db_persisted=False, failure_code=FAILURE_DB_PERSISTENCE)
    except Exception:
        return RunOutputPersistenceReceipt(db_persisted=False, failure_code=FAILURE_OUTPUT_WRITE)

    certified = report.get("decision") == DECISION_CERTIFIED and report.get("status") == "ready"
    if not certified:
        return RunOutputPersistenceReceipt(db_persisted=False, failure_code=FAILURE_DB_PERSISTENCE)

    by_table = report.get("write_result", {}).get("by_table", {}) or {}
    counts = {k: int(v) for k, v in by_table.items() if isinstance(v, int)}
    return RunOutputPersistenceReceipt(
        db_persisted=True,
        package_generated=False,
        forecast_output_id=_latest_output_id(Path(db_path), project_key),
        certified=True,
        counts=counts,
    )


def _run_generation(*, project_key: str, work_root: Path) -> GenerationPackages:
    """Produce the ephemeral internal packages for a run (the analysis spine).

    Real CFR generation seam: runs the controlled context->analysis chain (file mode) to produce the
    analysis_package spine + resolve the upstream source_package from the configured data root. The
    analysis spine yields forecast_outputs + budget-code + risk rows; downstream enrichment
    (monthly/probability/comprehensive/staffing/accuracy/context) is deferred to a later phase. This
    function performs real generation against the configured data root and is monkeypatched in unit
    tests; ``generate_and_persist`` maps any failure here to a coded calculation failure.
    """
    from hb_assistant.construction.analytics.forecast_run_service import _ensure_cfr_importable
    from hb_assistant.construction.analytics.forecast_runtime_config import resolve_data_root

    data_root = resolve_data_root(None)
    if not data_root:
        raise RuntimeError("data root not configured")
    data_root_path = Path(data_root)
    # Upstream source package consumed by the v59 source-domain projection.
    source_candidates = sorted(data_root_path.glob("*cost_forecast_json_package"))
    if not source_candidates:
        raise RuntimeError("source package not found under data root")

    _ensure_cfr_importable()
    from construction_financial_review.workflows.controlled_db_context_analysis import (
        run_controlled_context_analysis_workflow,
    )

    context_stamp = uuid.uuid4().hex[:14]
    with contextlib.redirect_stdout(io.StringIO()):
        report = run_controlled_context_analysis_workflow(
            data_root=data_root_path,
            work_root=work_root,
            context_stamp=context_stamp,
            mode="file",
            project_key=project_key,
        )
    return GenerationPackages(
        analysis_package=Path(report["analysis_package"]),
        source_package=source_candidates[0],
        work_root=Path(report.get("work_root", work_root)),
        context_stamp=str(report.get("context_stamp", context_stamp)),
        context_package=Path(report["context_package"]) if report.get("context_package") else None,
    )


def generate_and_persist(
    *, project_key: str, db_path: Path, work_root: Path, run_id: str | None = None
) -> RunOutputPersistenceReceipt:
    """Run generation then the gated DB persistence; coded fail-closed on calculation failure."""
    try:
        packages = _run_generation(project_key=project_key, work_root=work_root)
    except Exception:
        return RunOutputPersistenceReceipt(db_persisted=False, failure_code=FAILURE_CALCULATION)
    return persist_run_output(
        project_key=project_key, db_path=Path(db_path), packages=packages, run_id=run_id
    )


def verify_run_output_persistence(db_path: Path, project_key: str) -> dict[str, int]:
    """Count run-output rows for a project (test-support / runtime verification). Read-only."""
    counts = {
        "forecast_outputs_count": 0,
        "budget_code_rows_count": 0,
        "monthly_rows_count": 0,
        "probability_rows_count": 0,
        "risk_rows_count": 0,
        "schedule_phasing_rows_count": 0,
        "package_manifest_rows_created": 0,
        "evidence_package_rows_created": 0,
    }
    table_for = {
        "forecast_outputs_count": "forecast_outputs",
        "budget_code_rows_count": "forecast_output_budget_codes",
        "monthly_rows_count": "forecast_output_monthly",
        "probability_rows_count": "forecast_output_probability",
        "risk_rows_count": "forecast_output_risks",
        "schedule_phasing_rows_count": "forecast_output_schedule_phasing",
        "package_manifest_rows_created": "forecast_package_manifests",
        "evidence_package_rows_created": "forecast_evidence_packages",
    }
    try:
        conn = sqlite3.connect(f"{Path(db_path).resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return counts
    try:
        for key, table in table_for.items():
            with contextlib.suppress(sqlite3.Error):
                row = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE project_key=?", (project_key,)
                ).fetchone()
                counts[key] = int(row[0]) if row and row[0] is not None else 0
    finally:
        conn.close()
    return counts
