"""External forecast evaluation project eligibility tests."""

from __future__ import annotations

import sqlite3

import pytest

from hb_assistant.construction.analytics.forecast_external_ingest import ForecastExternalError
from hb_assistant.forecasting.project_eligibility import (
    assert_eval_project_eligible,
    is_eval_project_eligible,
    load_eval_project_allowlist,
    resolve_eligible_eval_projects,
)


def test_default_allowlist_includes_tropical_and_fixtureproj() -> None:
    resolved = resolve_eligible_eval_projects()
    assert "tropical" in resolved["projects"]
    assert "fixtureproj" in resolved["projects"]


def test_env_allowlist_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", "alpha,beta")
    assert load_eval_project_allowlist() == frozenset({"alpha", "beta"})
    resolved = resolve_eligible_eval_projects()
    assert resolved["source"] == "env_allowlist"
    assert is_eval_project_eligible("alpha")
    assert not is_eval_project_eligible("tropical")


def test_forecast_projects_enabled_discovery(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", raising=False)
    db = tmp_path / "forecast.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE forecast_projects (project_key TEXT PRIMARY KEY, enabled INTEGER, created_utc TEXT, updated_utc TEXT)"
    )
    conn.execute(
        "INSERT INTO forecast_projects VALUES ('caretta', 1, 't', 't'), ('disabledproj', 0, 't', 't')"
    )
    conn.commit()
    conn.close()
    resolved = resolve_eligible_eval_projects(db_path=db)
    assert "caretta" in resolved["projects"]
    assert "disabledproj" not in resolved["projects"]
    assert resolved["source"] == "defaults_plus_forecast_projects"


def test_invalid_project_raises() -> None:
    with pytest.raises(ForecastExternalError, match="not eligible"):
        assert_eval_project_eligible("unknown-project-xyz")