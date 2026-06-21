"""Project eligibility policy for external forecast evaluation."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

_DEFAULT_ALLOWLIST = frozenset({"tropical", "fixtureproj"})


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path.resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _resolve_db_path(db_path: str | Path | None) -> Path | None:
    if db_path is not None:
        return Path(db_path)
    raw = os.environ.get("HB_FORECAST_DB_PATH", "").strip()
    return Path(raw) if raw else None


def load_eval_project_allowlist() -> frozenset[str]:
    """Return env-only allowlist override (empty when unset)."""
    raw = os.environ.get("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", "")
    if raw.strip():
        return frozenset(part.strip() for part in raw.split(",") if part.strip())
    return frozenset()


def load_forecast_projects_enabled(*, db_path: str | Path | None = None) -> frozenset[str]:
    """Return enabled project keys from forecast_projects when table exists."""
    path = _resolve_db_path(db_path)
    if path is None or not path.exists():
        return frozenset()
    try:
        with _connect_ro(path) as conn:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='forecast_projects' LIMIT 1"
            ).fetchone()
            if not row:
                return frozenset()
            rows = conn.execute(
                "SELECT project_key FROM forecast_projects WHERE enabled = 1"
            ).fetchall()
            return frozenset(str(r[0]) for r in rows if r and r[0])
    except sqlite3.Error:
        return frozenset()


def resolve_eligible_eval_projects(*, db_path: str | Path | None = None) -> dict[str, Any]:
    """Combine env allowlist, forecast_projects.enabled, and built-in defaults."""
    env_allowlist = load_eval_project_allowlist()
    if env_allowlist:
        return {
            "projects": env_allowlist,
            "source": "env_allowlist",
            "env_var": "HB_FORECAST_EVAL_PROJECT_ALLOWLIST",
        }
    db_projects = load_forecast_projects_enabled(db_path=db_path)
    combined = set(_DEFAULT_ALLOWLIST) | set(db_projects)
    source = "defaults_plus_forecast_projects" if db_projects else "defaults"
    return {
        "projects": frozenset(combined),
        "source": source,
        "forecast_projects_enabled_count": len(db_projects),
    }


def is_eval_project_eligible(project_key: str, *, db_path: str | Path | None = None) -> bool:
    resolved = resolve_eligible_eval_projects(db_path=db_path)
    return project_key in resolved["projects"]


def assert_eval_project_eligible(project_key: str, *, db_path: str | Path | None = None) -> None:
    resolved = resolve_eligible_eval_projects(db_path=db_path)
    allowlist = resolved["projects"]
    if project_key not in allowlist:
        from hb_assistant.construction.analytics.forecast_external_ingest import (  # noqa: I001
            ForecastExternalError,
        )

        raise ForecastExternalError(
            f"project_key {project_key!r} is not eligible for external forecast evaluation; "
            f"allowed projects: {sorted(allowlist)} (source={resolved['source']}). "
            "Set HB_FORECAST_EVAL_PROJECT_ALLOWLIST or enable project in forecast_projects."
        )