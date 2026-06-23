"""CFR-local project-eligibility + source-package-name policy.

Mirrors the policy of ``hb_assistant.forecasting.project_eligibility`` (env allowlist + the
``forecast_projects`` registry + a built-in default allowlist) WITHOUT importing hb_assistant:
CFR is vendored and must stay standalone (enforced by ``tests/test_model_engines_readiness``).
The two sides agree by convention on the env var name + default allowlist, not by sharing code.

Replaces the former per-module ``SUPPORTED_PROJECT_KEY = "tropical"`` guards: an eligible
project (tropical, fixtureproj, or any ``forecast_projects.enabled`` row / env allowlist member)
is allowed through; everything else still fails closed at each call site's own exception type.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# The historical single-project default; still the canonical fallback project key.
SUPPORTED_PROJECT_KEY = "tropical"

# Built-in eligible set when neither the env allowlist nor a forecast_projects registry applies.
# ``fixtureproj`` is the synthetic second project used by tests/fixtures.
_DEFAULT_ALLOWLIST = frozenset({"tropical", "fixtureproj"})

_ALLOWLIST_ENV = "HB_FORECAST_EVAL_PROJECT_ALLOWLIST"
_SOURCE_PACKAGE_ENV = "HB_FORECAST_SOURCE_PACKAGE_NAME"

# project_key -> source-domain package directory name. The name does not follow the
# ``*_{project_key}_*`` convention (it is a project-specific raw-data package), so it is mapped.
_SOURCE_PACKAGE_NAMES = {
    "tropical": "twn_cost_forecast_json_package",
}


def _env_allowlist() -> frozenset[str]:
    raw = os.environ.get(_ALLOWLIST_ENV, "")
    if raw.strip():
        return frozenset(part.strip() for part in raw.split(",") if part.strip())
    return frozenset()


def _forecast_projects_enabled(db_path: str | Path | None) -> frozenset[str]:
    """Enabled project keys from the ``forecast_projects`` registry (read-only).

    Returns an empty set on any of: no db_path, missing file, missing table, or sqlite error —
    never raises. The DB is opened ``mode=ro`` so this can never mutate the target.
    """
    if db_path is None:
        return frozenset()
    path = Path(db_path)
    if not path.exists():
        return frozenset()
    try:
        uri = f"file:{path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='forecast_projects' LIMIT 1"
            ).fetchone()
            if not has_table:
                return frozenset()
            rows = conn.execute(
                "SELECT project_key FROM forecast_projects WHERE enabled = 1"
            ).fetchall()
            return frozenset(str(r[0]) for r in rows if r and r[0])
    except sqlite3.Error:
        return frozenset()


def eligible_projects(*, db_path: str | Path | None = None) -> frozenset[str]:
    """Resolve the eligible project keys.

    Precedence: the ``HB_FORECAST_EVAL_PROJECT_ALLOWLIST`` env allowlist (authoritative when set),
    else the built-in defaults unioned with any ``forecast_projects.enabled`` rows.
    """
    env = _env_allowlist()
    if env:
        return env
    return frozenset(_DEFAULT_ALLOWLIST | _forecast_projects_enabled(db_path))


def is_project_eligible(project_key: str, *, db_path: str | Path | None = None) -> bool:
    """True when ``project_key`` is eligible to run the forecast pipeline (fail closed otherwise)."""
    return project_key in eligible_projects(db_path=db_path)


def source_package_name(project_key: str) -> str:
    """Resolve the source-domain package directory name for ``project_key`` (fail closed).

    ``HB_FORECAST_SOURCE_PACKAGE_NAME`` overrides the mapping when set. Note: that env override is
    project-key-agnostic (applies to whichever project is being queried) — fine for one project
    per run; revisit if a future run resolves two projects at once. Raises ``KeyError`` for an
    unmapped project so callers fail closed rather than guess a name.
    """
    override = os.environ.get(_SOURCE_PACKAGE_ENV, "").strip()
    if override:
        return override
    try:
        return _SOURCE_PACKAGE_NAMES[project_key]
    except KeyError as exc:
        raise KeyError(
            f"no source-domain package name mapped for project_key {project_key!r}; "
            f"known: {sorted(_SOURCE_PACKAGE_NAMES)}. Set {_SOURCE_PACKAGE_ENV} to override."
        ) from exc
