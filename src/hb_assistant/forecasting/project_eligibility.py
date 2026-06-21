"""Project eligibility policy for external forecast evaluation."""

from __future__ import annotations

import os

_DEFAULT_ALLOWLIST = frozenset({"tropical", "fixtureproj"})


def load_eval_project_allowlist() -> frozenset[str]:
    """Return configured allowlist; env overrides built-in defaults."""
    raw = os.environ.get("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", "")
    if raw.strip():
        return frozenset(part.strip() for part in raw.split(",") if part.strip())
    return _DEFAULT_ALLOWLIST


def is_eval_project_eligible(project_key: str) -> bool:
    return project_key in load_eval_project_allowlist()


def assert_eval_project_eligible(project_key: str) -> None:
    allowlist = load_eval_project_allowlist()
    if project_key not in allowlist:
        from hb_assistant.construction.analytics.forecast_external_ingest import (  # noqa: I001
            ForecastExternalError,
        )

        raise ForecastExternalError(
            f"project_key {project_key!r} is not eligible for external forecast evaluation; "
            f"allowed projects: {sorted(allowlist)}. "
            "Set HB_FORECAST_EVAL_PROJECT_ALLOWLIST to extend (comma-separated)."
        )