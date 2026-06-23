"""CFR-local project-eligibility + source-package-name policy (P4).

Proves the stdlib-only helper that replaced the per-module tropical-only guards: the default
allowlist (tropical + fixtureproj), the env allowlist override, the ``forecast_projects``
registry union, and the fail-closed source-package-name resolution.
"""

from __future__ import annotations

import sqlite3

import pytest
from construction_financial_review.common.project_eligibility import (
    SUPPORTED_PROJECT_KEY,
    eligible_projects,
    is_project_eligible,
    source_package_name,
)

_ALLOWLIST_ENV = "HB_FORECAST_EVAL_PROJECT_ALLOWLIST"
_SOURCE_ENV = "HB_FORECAST_SOURCE_PACKAGE_NAME"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(_ALLOWLIST_ENV, raising=False)
    monkeypatch.delenv(_SOURCE_ENV, raising=False)


def test_default_allowlist_includes_tropical_and_fixtureproj():
    projects = eligible_projects()
    assert SUPPORTED_PROJECT_KEY == "tropical"
    assert "tropical" in projects
    assert "fixtureproj" in projects
    assert is_project_eligible("tropical")
    assert is_project_eligible("fixtureproj")


def test_ineligible_project_fails_closed():
    assert not is_project_eligible("other")
    assert "other" not in eligible_projects()


def test_env_allowlist_overrides_defaults(monkeypatch):
    monkeypatch.setenv(_ALLOWLIST_ENV, "alpha, beta")
    projects = eligible_projects()
    assert projects == frozenset({"alpha", "beta"})
    # env allowlist is authoritative -> the built-in defaults no longer apply
    assert not is_project_eligible("tropical")
    assert is_project_eligible("alpha")


def test_forecast_projects_registry_unions_with_defaults(tmp_path):
    db = tmp_path / "registry.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE forecast_projects (project_key TEXT PRIMARY KEY, enabled INTEGER NOT NULL)"
    )
    conn.executemany(
        "INSERT INTO forecast_projects (project_key, enabled) VALUES (?, ?)",
        [("hilltop", 1), ("dormant", 0)],
    )
    conn.commit()
    conn.close()
    projects = eligible_projects(db_path=db)
    assert {"tropical", "fixtureproj", "hilltop"} <= projects
    assert "dormant" not in projects  # enabled = 0 is excluded
    assert is_project_eligible("hilltop", db_path=db)


def test_missing_db_or_table_returns_defaults_never_raises(tmp_path):
    # no file
    assert eligible_projects(db_path=tmp_path / "nope.sqlite") == frozenset(
        {"tropical", "fixtureproj"}
    )
    # file exists but no forecast_projects table
    db = tmp_path / "empty.sqlite"
    sqlite3.connect(str(db)).close()
    assert eligible_projects(db_path=db) == frozenset({"tropical", "fixtureproj"})


def test_source_package_name_maps_tropical():
    assert source_package_name("tropical") == "twn_cost_forecast_json_package"


def test_source_package_name_env_override(monkeypatch):
    monkeypatch.setenv(_SOURCE_ENV, "custom_source_package")
    assert source_package_name("tropical") == "custom_source_package"
    assert source_package_name("anything") == "custom_source_package"


def test_source_package_name_unknown_fails_closed():
    with pytest.raises(KeyError):
        source_package_name("fixtureproj")  # eligible but no mapped source package
