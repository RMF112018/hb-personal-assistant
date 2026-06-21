"""Wire the forecast generators to CONSUME the live DB config snapshot (productionizes Phases 17-20).

Phases 17-20 PROVED the real generators produce parity-equivalent output when they read a materialized
DB config snapshot through the ``CFR_CONFIG_ROOT`` bridge. This module is the productionized,
operator-facing entry point for that path. The gated machinery — materialize (read-only) -> fidelity
gate -> quiescence preflight -> ``CFR_CONFIG_ROOT`` bridge -> redacted report — lives in
:mod:`forecast_db_config_backed_core`; per-generator differences are captured by a
``GeneratorDescriptor`` registry there.

``run_forecast_db_config_backed_generation`` keeps its original signature and behaviour (the
comprehensive generator) so existing callers/tests are unaffected;
``run_forecast_db_config_backed_generation_for_kind`` selects any of the four generators
(comprehensive / model_controls / monthly / probability). The live DB is opened ``mode=ro`` only —
never written, migrated, or copied.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import (
    config_registry as cr,  # re-exported: tests monkeypatch genwf.cr.create_forecast_config_snapshot
)
from . import forecast_db_config_backed_core as _core
from .forecast_db_config_backed_core import (
    DB_BACKED_SUBDIR,
    DEFAULT_PREFLIGHT_STABILITY_SECONDS,
    DEFAULT_PROBABILITY_RUNS,
    DEFAULT_PROBABILITY_SEED,
    REASON_COST_FREQ,
    REASON_FIDELITY,
    REASON_GENERATOR_REFUSED,
    REASON_NO_SNAPSHOT,
    REASON_NOT_QUIESCENT,
    REASON_PREDECESSOR,
    REASON_UNSUPPORTED_KIND,
    STATUS_GENERATED,
    STATUS_VALIDATION_FAILED,
    SUPPORTED_GENERATOR_KINDS,
    SUPPORTED_PROJECT_KEY,
    ForecastDbConfigGenerationError,
    get_descriptor,
)

__all__ = [
    "DB_BACKED_SUBDIR",
    "REASON_COST_FREQ",
    "REASON_FIDELITY",
    "REASON_GENERATOR_REFUSED",
    "REASON_NO_SNAPSHOT",
    "REASON_NOT_QUIESCENT",
    "REASON_PREDECESSOR",
    "REASON_UNSUPPORTED_KIND",
    "STATUS_GENERATED",
    "STATUS_VALIDATION_FAILED",
    "SUPPORTED_GENERATOR_KINDS",
    "SUPPORTED_PROJECT_KEY",
    "ForecastDbConfigGenerationError",
    "cr",
    "run_forecast_db_config_backed_generation",
    "run_forecast_db_config_backed_generation_for_kind",
]

DEFAULT_RUN_STAMP = _core.DEFAULT_RUN_STAMP


def run_forecast_db_config_backed_generation_for_kind(
    *,
    generator_kind: str = "comprehensive",
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_db_path: Path,
    work_root: Path,
    data_root: Path | None = None,
    config_snapshot_id: str | None = None,
    run_stamp: str | None = None,
    source_config_root: Path | None = None,
    require_live_snapshot: bool = True,
    prove_file_equivalence: bool = False,
    preflight_stability_seconds: float = DEFAULT_PREFLIGHT_STABILITY_SECONDS,
    runs: int = DEFAULT_PROBABILITY_RUNS,
    seed: int = DEFAULT_PROBABILITY_SEED,
    forecast_start_month: str | None = None,
) -> dict[str, Any]:
    """Generate ``generator_kind``'s forecast package consuming the live DB config snapshot.

    ``runs`` / ``seed`` / ``forecast_start_month`` are probability-only (ignored for other kinds).
    """
    descriptor = get_descriptor(
        generator_kind, runs=runs, seed=seed, forecast_start_month=forecast_start_month
    )
    return _core.run_db_config_backed_generation(
        descriptor=descriptor,
        project_key=project_key,
        live_db_path=live_db_path,
        work_root=work_root,
        data_root=data_root,
        config_snapshot_id=config_snapshot_id,
        run_stamp=run_stamp,
        source_config_root=source_config_root,
        require_live_snapshot=require_live_snapshot,
        prove_file_equivalence=prove_file_equivalence,
        preflight_stability_seconds=preflight_stability_seconds,
    )


def run_forecast_db_config_backed_generation(
    *,
    project_key: str = SUPPORTED_PROJECT_KEY,
    live_db_path: Path,
    work_root: Path,
    data_root: Path | None = None,
    config_snapshot_id: str | None = None,
    run_stamp: str | None = None,
    source_config_root: Path | None = None,
    require_live_snapshot: bool = True,
    prove_file_equivalence: bool = False,
    preflight_stability_seconds: float = DEFAULT_PREFLIGHT_STABILITY_SECONDS,
) -> dict[str, Any]:
    """Generate the comprehensive forecast package consuming the live DB config snapshot (PR #66 path)."""
    return run_forecast_db_config_backed_generation_for_kind(
        generator_kind="comprehensive",
        project_key=project_key,
        live_db_path=live_db_path,
        work_root=work_root,
        data_root=data_root,
        config_snapshot_id=config_snapshot_id,
        run_stamp=run_stamp,
        source_config_root=source_config_root,
        require_live_snapshot=require_live_snapshot,
        prove_file_equivalence=prove_file_equivalence,
        preflight_stability_seconds=preflight_stability_seconds,
    )
