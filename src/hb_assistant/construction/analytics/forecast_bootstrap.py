"""Forecast launch bootstrap (Live App Bootstrap/Launcher phase).

This is the **single** module allowed to create forecast filesystem roots. The companion
``forecast_runtime_config`` module is intentionally non-mutating (its validation never calls
``mkdir``); resolution + validation live there and are reused here unchanged.

``ensure_forecast_managed_storage`` is the launch-time hook (FastAPI lifespan, launcher readiness).
It idempotently:

  - ensures standard + app-managed forecast directories under Application Support;
  - seeds ``forecast_runtime_config.json`` when roots are missing (env still wins at runtime);
  - creates + migrates the managed app DB when ``db_path`` resolves to ``PathPolicy.get_db_path()``;
  - creates configured-and-valid **write-roots** (runs / eval / config-edit).

``ensure_forecast_roots`` remains the write-root-only helper (tests + legacy callers).

Custom-configured read-roots are never auto-invented (fail-closed).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics import forecast_runtime_config as rc

# Write-roots this bootstrap may create, paired with their resolver. Order is stable so the
# returned ``created`` list is deterministic.
_WRITE_ROOTS: tuple[tuple[str, Any], ...] = (
    ("runs_root", rc.resolve_runs_root),
    ("eval_root", rc.resolve_eval_root_value),
    ("config_edit_root", rc.resolve_config_edit_root_value),
)

# App-managed forecast dirs (keys only in reports — never path strings).
_MANAGED_DIRS: tuple[tuple[str, Any], ...] = (
    ("analytics_dir", lambda pp: pp.get_app_support() / "analytics"),
    ("package_roots", lambda pp: pp.get_forecast_packages_dir()),
    ("data_root", lambda pp: pp.get_forecast_data_dir()),
    ("runs_root", lambda pp: pp.get_forecast_runs_dir()),
    ("eval_root", lambda pp: pp.get_forecast_evaluations_dir()),
    ("config_edit_root", lambda pp: pp.get_forecast_config_proposals_dir()),
    ("imports_dir", lambda pp: pp.get_forecast_imports_dir()),
)


def _ensure_managed_directories() -> list[str]:
    """Create app-managed forecast dirs; return keys that did not exist before this call."""
    pp = PathPolicy()
    pp.ensure_dirs()
    created: list[str] = []
    for key, resolver in _MANAGED_DIRS:
        path = resolver(pp)
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(key)
    return created


def _ensure_managed_database() -> dict[str, Any]:
    """Create + migrate the managed app DB when ``db_path`` resolves to it."""
    from hb_assistant.store.startup_schema_policy import apply_startup_schema_policy

    db_raw = rc.resolve_db_path()
    if not rc.is_managed_db_path(db_raw):
        return {"managed": False, "migrated": False, "migration_performed": False}
    db_path = Path(db_raw)
    created = not db_path.exists()
    if created:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    report = apply_startup_schema_policy(db_path)
    report["created"] = created
    return report


def ensure_forecast_roots() -> dict[str, Any]:
    """Create configured+valid forecast write-roots; return a redaction-safe readiness report.

    For each write-root: resolve it (explicit > env > settings-file > managed_default > None) and
    run the exact same ``_write_root_blocker`` the status payload uses. A directory is created only
    when it is **configured** (not None) AND has **no blocker** (absolute, outside the resolved data
    root, parent creatable). ``mkdir(parents=True, exist_ok=True)`` makes the call idempotent.

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
            continue  # invalid → skip, surfaced as blocker in status
        path = Path(raw)
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created.append(key)

    status = rc.build_runtime_status()
    status["created"] = created
    status["bootstrap"] = {"ran": True, "idempotent": True, "write_roots_only": True}
    return status


def ensure_forecast_managed_storage(*, repair: bool = False) -> dict[str, Any]:
    """Bootstrap app-managed forecast storage (dirs, settings seed, DB, write-roots).

    Idempotent and safe on every launch. ``repair=True`` uses the same path — it recreates missing
    managed folders and fills missing settings keys without overwriting operator values.
    """
    dirs_created = _ensure_managed_directories()
    seeded = rc.seed_runtime_config_if_incomplete()
    db_report = _ensure_managed_database()
    roots_report = ensure_forecast_roots()

    status = rc.build_runtime_status()
    status["created"] = sorted(set(dirs_created + roots_report.get("created", [])))
    status["seeded"] = seeded
    status["bootstrap"] = {
        "ran": True,
        "idempotent": True,
        "repair": repair,
        "managed_storage": True,
        "db": db_report,
    }
    return status