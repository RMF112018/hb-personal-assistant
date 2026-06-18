"""Phase 7 — controlled, default-off final-forecast (analysis) runner.

Wraps the existing downstream analysis generator (``generate_forecast_analysis_package.py`` —
the immediate layer that consumes ONLY the context package) so an operator or test harness can
intentionally run it against ONE explicit context package, from explicit inputs, under a temp
root. It proves the Phase 7 question: a DB-backed context package (built by the Phase 6 runner)
yields a parity-equivalent analysis package versus the file-backed one.

It does not refactor or alter the analysis generator, and changes no production defaults. It only:
  - validates controlled-run inputs and fails closed on unsafe inputs BEFORE the subprocess runs;
  - HARD-pins the upstream context via ``CFR_CONTEXT_STAMP`` (the resolver fails closed if the
    pinned package is absent — never latest-glob, never the live root);
  - redirects the analysis data root to the context package's parent via a temp run-lineage state
    (so the generator never writes under the live Synology root);
  - runs the generator as a subprocess with an explicit env (no global os.environ mutation) and
    returns the produced analysis package path + structured run metadata.

CFR-only / stdlib + run_lineage; no ``hb_assistant`` dependency (the DB-ness is already baked into
the context package by the Phase 6 runner; the analysis generator only reads files).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..common import run_lineage
from . import generate_forecast_analysis_package as _analysis_gen

# Phase 7 is Tropical-only, exactly like the existing CFR run-* commands.
SUPPORTED_PROJECT_KEY = "tropical"

_CONTEXT_PREFIX = "forecast_context_package_tropical_"
_ANALYSIS_GLOB = "forecast_analysis_package_tropical_*"
# Live/default Synology forecast root (single source of truth = the generator's own constant).
_LIVE_ROOT = _analysis_gen.DEFAULT_ROOT
_ANALYSIS_SCRIPT = Path(_analysis_gen.__file__).resolve()

# Minimal structural markers of a context package the analysis generator consumes.
_REQUIRED_CONTEXT_MEMBERS = ("manifest.json", "validation_report.json", "canonical", "summaries")


class FinalForecastRunnerError(RuntimeError):
    """Raised when a controlled final-forecast (analysis) run is rejected by a safety guard."""


def _is_at_or_under(path: Path, root: Path) -> bool:
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _analysis_packages_in(data_root: Path) -> list[Path]:
    """Analysis packages under ``data_root`` (excluding the crosswalk_v2 variant by shared prefix)."""
    return sorted(
        p for p in data_root.glob(_ANALYSIS_GLOB) if p.is_dir() and "_crosswalk_v2_" not in p.name
    )


def run_final_forecast_generation(
    *,
    context_package: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    run_id: str | None = None,
    deterministic: bool = True,
) -> dict[str, Any]:
    """Run the downstream analysis generator against one explicit context package, controlled.

    Returns structured metadata incl. the produced analysis package path under ``output_package``.
    Raises ``FinalForecastRunnerError`` (before the subprocess runs) on any unsafe input; lets the
    generator's fail-closed resolver error surface as a nonzero exit (mapped to the same error).
    """
    # --- Fail closed BEFORE subprocess execution. -------------------------------------------
    if not context_package:
        raise FinalForecastRunnerError("context_package is required for a controlled run")
    if project_key != SUPPORTED_PROJECT_KEY:
        raise FinalForecastRunnerError(
            f"unsupported project_key {project_key!r}; only {SUPPORTED_PROJECT_KEY!r} is supported "
            "in Phase 7"
        )
    if not deterministic:
        # The analysis generator has no LLM/external inference (repo truth); there is no
        # model-backed mode in Phase 7 to defer to. Refuse rather than fake one.
        raise FinalForecastRunnerError(
            "deterministic=False is not supported: the analysis generator has no LLM/external "
            "inference; Phase 7 supports deterministic runs only"
        )

    context_package = Path(context_package)
    if not context_package.is_dir():
        raise FinalForecastRunnerError(
            f"context_package not found or not a directory: {context_package}"
        )
    if not context_package.name.startswith(_CONTEXT_PREFIX):
        raise FinalForecastRunnerError(
            f"context_package is not a tropical context package: {context_package.name}"
        )
    missing = [m for m in _REQUIRED_CONTEXT_MEMBERS if not (context_package / m).exists()]
    if missing:
        raise FinalForecastRunnerError(
            f"context_package is structurally invalid (missing {missing}): {context_package}"
        )

    context_stamp = context_package.name[len(_CONTEXT_PREFIX) :]
    if not context_stamp:
        raise FinalForecastRunnerError(
            f"cannot derive a context stamp from package name: {context_package.name}"
        )

    data_root = context_package.parent
    if _is_at_or_under(data_root, _LIVE_ROOT):
        raise FinalForecastRunnerError(
            f"context data root is at/under the live forecast root (refused): {data_root}"
        )

    existing = [p.name for p in _analysis_packages_in(data_root)]
    if existing:
        raise FinalForecastRunnerError(
            f"an analysis package already exists in the controlled data root (refused): {existing}"
        )

    # Temp run-lineage state so the analysis subprocess uses THIS (temp) data root, never the live
    # default. start_run_state writes the state + its current_<project> pointer under data_root.
    state_path = data_root / "cfr_run_state_phase7.json"
    effective_run_id = run_id or "00000000_000000"
    run_lineage.start_run_state(project_key, data_root, effective_run_id, path=state_path)

    # Explicit env for the subprocess only (no global os.environ mutation to restore). The
    # CFR_CONTEXT_STAMP override is a HARD pin: the resolver fails closed if the named context
    # package is absent under the data root — it never falls back to latest-glob.
    env = dict(os.environ)
    env[run_lineage.ENV_STATE] = str(state_path)
    env["CFR_CONTEXT_STAMP"] = context_stamp

    proc = subprocess.run(
        [sys.executable, str(_ANALYSIS_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise FinalForecastRunnerError(
            f"analysis generation failed (exit {proc.returncode}); "
            f"stderr tail: {proc.stderr.strip()[-800:]}"
        )

    produced = _analysis_packages_in(data_root)
    if len(produced) != 1:
        raise FinalForecastRunnerError(
            f"expected exactly one analysis package under {data_root}, found {len(produced)}: "
            f"{[p.name for p in produced]}"
        )

    return {
        "ok": True,
        "mode": "analysis",
        "project_key": project_key,
        "context_package": str(context_package),
        "context_stamp": context_stamp,
        "data_root": str(data_root),
        "output_package": str(produced[0]),
        "run_id": effective_run_id,
        "lineage_source": "explicit_override",
    }
