"""Forecast launch bootstrap (Live App Bootstrap/Launcher phase).

This is the **single** module allowed to create forecast filesystem roots. The companion
``forecast_runtime_config`` module is intentionally non-mutating (its validation never calls
``mkdir``); resolution + validation live there and are reused here unchanged.

``ensure_forecast_roots`` is the launch-time hook (called from the FastAPI ``lifespan`` startup and
available to the launcher). It idempotently creates the three configured-and-valid **write-roots**
(runs / eval / config-edit) and returns a redaction-safe readiness report. It NEVER touches the
read-roots (package_roots / data_root / db_path / cfr_src) — those point at live inputs that must
already exist and can never be auto-invented (fail-closed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics import forecast_runtime_config as rc

# The write-roots this bootstrap may create, paired with their resolver. Order is stable so the
# returned ``created`` list is deterministic. Read-roots are deliberately absent.
_WRITE_ROOTS: tuple[tuple[str, Any], ...] = (
    ("runs_root", rc.resolve_runs_root),
    ("eval_root", rc.resolve_eval_root_value),
    ("config_edit_root", rc.resolve_config_edit_root_value),
)


def ensure_forecast_roots() -> dict[str, Any]:
    """Create configured+valid forecast write-roots; return a redaction-safe readiness report.

    For each write-root: resolve it (explicit > env > settings-file > None) and run the exact same
    ``_write_root_blocker`` the status payload uses. A directory is created only when it is
    **configured** (not None) AND has **no blocker** (absolute, outside the resolved data root,
    parent creatable). ``mkdir(parents=True, exist_ok=True)`` makes the call idempotent.

    Returns the ``build_runtime_status`` shape plus:
      - ``created``: the write-root **keys** that did not exist before this call and now do (never
        path strings, so the report stays redaction-safe);
      - ``bootstrap``: a small coded marker block.
    """
    data_root = rc.resolve_data_root()
    created: list[str] = []
    for key, resolver in _WRITE_ROOTS:
        raw = resolver()
        if not raw:
            continue  # not configured → fail-closed, never invented
        if rc._write_root_blocker(raw, data_root) is not None:
            continue  # invalid (relative, under data_root, or not creatable) → skip, surfaced as blocker
        path = Path(raw)
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(key)

    status = rc.build_runtime_status()
    status["created"] = created
    status["bootstrap"] = {"ran": True, "idempotent": True, "write_roots_only": True}
    return status
