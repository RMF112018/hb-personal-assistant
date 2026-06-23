"""Phase 6 — controlled, default-off DB-backed context-generation runner.

This is the first operator-/test-facing workflow layer on top of the Phase 5 parameterized
context generator (``build_context_package(config)``) and the Phase 4 DB-backed source read
adapter. It lets an operator or test harness INTENTIONALLY drive the context generator in
either file-backed (default) or DB-backed mode from explicit inputs, while preserving today's
file-backed production defaults.

It does not change generator calculations, output schemas, validation, sorting, source row
shapes, or package semantics. It only:
  - validates controlled-run inputs and fails closed on unsafe inputs (before any output dir
    is created and before the build runs);
  - constructs a ``ContextPackageConfig`` directly from explicit arguments (no reliance on the
    ambient ``CFR_CONTEXT_*`` env vars);
  - sets the Phase 4 DB env toggles only for the duration of a DB-backed run, and restores the
    prior environment afterward (success or failure);
  - in file-backed mode, temporarily clears the DB toggles so ambient shell state cannot turn a
    file-backed controlled run into a DB-backed one;
  - returns the generated output package path and structured run metadata.

CFR keeps its stdlib-only independence: ``hb_assistant`` is imported LAZILY, only inside the
DB-backed branch (to refuse the live/default/unresolvable DB), mirroring the Phase 4 adapter.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from ..common.project_eligibility import eligible_projects, is_project_eligible
from .generate_forecast_context_package import (
    _DEFAULT_DATA_ROOT,
    ContextPackageConfig,
    build_context_package,
)

# Phase 6 is Tropical-only, exactly like the existing CFR run-* commands. Multi-project
# generalization is deferred to a later phase, not hidden scope inside this runner.
SUPPORTED_PROJECT_KEY = "tropical"

# Env toggles consumed by the Phase 4 adapter (db_source_adapter).
_ENV_DB_BACKED = "HB_FORECAST_DB_BACKED_READS"
_ENV_DB_PATH = "HB_FORECAST_DB_PATH"


class ContextRunnerError(RuntimeError):
    """Raised when a controlled context-generation run is rejected by a safety guard."""


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` equals or is nested under ``root`` (resolved, non-strict)."""
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def run_context_generation(
    *,
    data_root: Path,
    out_dir: Path,
    stamp: str,
    db_backed: bool = False,
    db_path: Path | None = None,
    project_key: str = SUPPORTED_PROJECT_KEY,
) -> dict[str, Any]:
    """Run the context generator once in a controlled, explicit-input workflow.

    Returns structured run metadata including the generated output package path under
    ``output_package``. Raises ``ContextRunnerError`` (before any output dir is created or the
    build runs) on any unsafe input; lets the Phase 4 adapter's fail-closed errors (e.g. missing
    v59 rows) propagate from the build. The prior DB env is always restored afterward.
    """
    # --- Fail closed BEFORE build execution / before any output directory is created. -------
    if not data_root:
        raise ContextRunnerError("data_root is required for a controlled run")
    if not out_dir:
        raise ContextRunnerError("out_dir is required for a controlled run")
    if not stamp:
        raise ContextRunnerError("stamp is required for a deterministic controlled run")
    if not is_project_eligible(project_key):
        raise ContextRunnerError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )

    data_root = Path(data_root)
    out_dir = Path(out_dir)

    # The generator itself refuses an existing output dir (OUT.mkdir(exist_ok=False)); reject it
    # here too so the controlled runner gives a clean, early error instead of a build-time crash.
    if out_dir.exists():
        raise ContextRunnerError(f"out_dir already exists (refusing to reuse): {out_dir}")

    # Never write a controlled package under the live Synology forecast data root.
    if _is_under(out_dir, _DEFAULT_DATA_ROOT):
        raise ContextRunnerError(
            f"out_dir is under the live forecast data root (refused): {out_dir}"
        )

    if db_backed:
        if not db_path:
            raise ContextRunnerError("db_backed=True requires an explicit db_path (fail closed)")
        db_path = Path(db_path)
        # Refuse the live/default DB and any unresolvable path. is_live_db_path() fails closed
        # (returns True) when the path cannot be resolved, so this one check covers both. Import
        # lazily so file-backed runs keep CFR's stdlib-only independence.
        try:
            from hb_assistant.construction.forecast.source_domain_engine import is_live_db_path
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise ContextRunnerError(
                f"cannot verify db_path against the live DB; hb_assistant unavailable: {exc}"
            ) from exc
        if is_live_db_path(db_path):
            raise ContextRunnerError(
                f"db_path resolves to the live/default DB (or is unresolvable): {db_path}"
            )

    # --- Explicit environment isolation around the single build. ----------------------------
    prior_backed = os.environ.get(_ENV_DB_BACKED)
    prior_path = os.environ.get(_ENV_DB_PATH)
    try:
        if db_backed:
            os.environ[_ENV_DB_BACKED] = "1"
            os.environ[_ENV_DB_PATH] = str(db_path)
        else:
            # Clear ambient DB toggles so a file-backed controlled run cannot be silently
            # promoted to DB-backed by leftover shell state.
            os.environ.pop(_ENV_DB_BACKED, None)
            os.environ.pop(_ENV_DB_PATH, None)

        config = ContextPackageConfig(data_root=data_root, out_dir=out_dir, stamp=stamp)
        output_package = build_context_package(config)
    finally:
        _restore_env(_ENV_DB_BACKED, prior_backed)
        _restore_env(_ENV_DB_PATH, prior_path)

    return {
        "ok": True,
        "project_key": project_key,
        "mode": "db_backed" if db_backed else "file_backed",
        "data_root": str(data_root),
        "out_dir": str(out_dir),
        "stamp": stamp,
        "db_path": str(db_path) if db_backed else None,
        "output_package": str(output_package),
    }


def _restore_env(name: str, prior: str | None) -> None:
    """Restore an env var to its prior value, including removing it if it was unset before."""
    if prior is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = prior
