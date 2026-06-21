"""External forecast evaluation project eligibility tests."""

from __future__ import annotations

import pytest

from hb_assistant.construction.analytics.forecast_external_ingest import ForecastExternalError
from hb_assistant.forecasting.project_eligibility import (
    assert_eval_project_eligible,
    is_eval_project_eligible,
    load_eval_project_allowlist,
)


def test_default_allowlist_includes_tropical_and_fixtureproj() -> None:
    allowlist = load_eval_project_allowlist()
    assert "tropical" in allowlist
    assert "fixtureproj" in allowlist


def test_env_allowlist_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", "alpha,beta")
    allowlist = load_eval_project_allowlist()
    assert allowlist == frozenset({"alpha", "beta"})
    assert is_eval_project_eligible("alpha")
    assert not is_eval_project_eligible("tropical")


def test_invalid_project_raises() -> None:
    with pytest.raises(ForecastExternalError, match="not eligible"):
        assert_eval_project_eligible("unknown-project-xyz")