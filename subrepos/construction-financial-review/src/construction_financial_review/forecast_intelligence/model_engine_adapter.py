"""Adapter to the isolated model-engine runtime (Phase I PR 3) — 3.14 side, dependency-free.

Bridges the 3.14 core to a dedicated Python 3.12 statsforecast runtime across a subprocess + JSON
boundary, so the heavy scientific stack never enters the core import graph. Mirrors the subprocess
discipline of ``analysis/final_forecast_runner`` and the graceful-availability pattern of the Ollama
client (``forecast_accuracy/llm/client``): ``available()`` never raises; ``forecast_batch`` raises a
single domain exception so callers can fall back to the in-process classical engine.

Config (env): ``CFR_MODEL_ENGINE_PYTHON`` = path to the runtime venv's python; optional
``CFR_MODEL_ENGINE_RUNNER`` overrides the runner script (defaults to the in-repo
``model_engine_runtime/runner.py``). When unset/unavailable the caller uses the classical fallback.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

ENV_PYTHON = "CFR_MODEL_ENGINE_PYTHON"
ENV_RUNNER = "CFR_MODEL_ENGINE_RUNNER"
# Module the runtime interpreter must import to be considered ready (the real dep). Overridable so
# the subprocess boundary can be exercised in tests without the heavy statsforecast venv.
ENV_PROBE_IMPORT = "CFR_MODEL_ENGINE_PROBE_IMPORT"
_DEFAULT_PROBE = "statsforecast"

_AVAILABLE_TIMEOUT_S = 60.0
_BATCH_TIMEOUT_S = 600.0


class ModelEngineUnavailable(RuntimeError):
    """Raised when the isolated model-engine runtime is not configured, missing, or fails."""


def _runner_path() -> Path:
    override = os.environ.get(ENV_RUNNER)
    if override:
        return Path(override)
    # …/forecast_intelligence/model_engine_adapter.py -> subrepo root / model_engine_runtime/runner.py
    return Path(__file__).resolve().parents[3] / "model_engine_runtime" / "runner.py"


def _interpreter() -> str | None:
    return os.environ.get(ENV_PYTHON) or None


def available() -> tuple[bool, str]:
    """Return ``(ok, reason)``. Never raises. ``ok`` only when the interpreter + runner exist and the
    isolated runtime can import statsforecast."""
    py = _interpreter()
    if not py:
        return False, "not_configured"
    if not Path(py).exists():
        return False, "interpreter_not_found"
    if not _runner_path().exists():
        return False, "runner_not_found"
    probe = os.environ.get(ENV_PROBE_IMPORT) or _DEFAULT_PROBE
    try:
        proc = subprocess.run(
            [py, "-c", f"import {probe}"],
            capture_output=True,
            text=True,
            timeout=_AVAILABLE_TIMEOUT_S,
            env=dict(os.environ),
        )
    except Exception as exc:  # noqa: BLE001 - availability probe must never raise
        return False, f"probe_failed_{type(exc).__name__}"
    return (True, "ok") if proc.returncode == 0 else (False, f"{probe}_import_failed")


def forecast_batch(requests: list[dict[str, Any]], *, timeout: float = _BATCH_TIMEOUT_S) -> dict:
    """Forecast all requests in ONE subprocess call. ``requests`` = ``[{"id","series","horizon"}]``.

    Returns the parsed runtime response ``{"backend": str, "results": {id: {...}}}``. Raises
    ``ModelEngineUnavailable`` on missing config, nonzero exit, timeout, or unparseable output (the
    caller falls back to the classical in-process engine).
    """
    py = _interpreter()
    if not py:
        raise ModelEngineUnavailable("not_configured")
    runner = _runner_path()
    if not Path(py).exists() or not runner.exists():
        raise ModelEngineUnavailable("interpreter_or_runner_missing")
    payload = json.dumps({"requests": list(requests)})
    try:
        proc = subprocess.run(
            [py, str(runner)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(os.environ),
        )
    except subprocess.TimeoutExpired as exc:
        raise ModelEngineUnavailable("timeout") from exc
    except Exception as exc:  # noqa: BLE001 - any spawn failure -> fall back
        raise ModelEngineUnavailable(f"spawn_failed_{type(exc).__name__}") from exc
    if proc.returncode != 0:
        raise ModelEngineUnavailable(
            f"runtime_exit_{proc.returncode}: {proc.stderr.strip()[-300:]}"
        )
    try:
        data = json.loads(proc.stdout)
        if not isinstance(data, dict) or "results" not in data:
            raise ValueError("missing results")
    except (ValueError, json.JSONDecodeError) as exc:
        raise ModelEngineUnavailable("bad_response") from exc
    return data
