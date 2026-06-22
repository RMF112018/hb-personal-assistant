"""Unit tests for the forecast launch bootstrap (Live App Bootstrap/Launcher phase).

Asserts: ``ensure_forecast_managed_storage`` bootstraps app-managed layout from empty state;
``ensure_forecast_roots`` creates ONLY configured+valid write-roots (never custom read-roots),
is idempotent, skips a write-root nested under the data root, is a no-op when nothing is configured,
and that its readiness report leaks no path strings (find_redaction_leaks clean with real paths).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics import forecast_bootstrap as boot
from hb_assistant.construction.analytics import forecast_runtime_config as rc
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

ENV_VARS = (
    "HB_FORECAST_PACKAGE_ROOTS",
    "HB_FORECAST_DATA_ROOT",
    "HB_FORECAST_RUNS_ROOT",
    "HB_FORECAST_EVAL_ROOT",
    "HB_FORECAST_DB_PATH",
    "HB_FORECAST_CFR_SRC",
    "HB_FORECAST_CONFIG_EDIT_ROOT",
)


@pytest.fixture
def cfg_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "forecast_runtime_config.json"
    monkeypatch.setattr(rc, "_config_path", lambda: p)
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    return p


def _write(cfg_path: Path, **values: object) -> None:
    cfg_path.write_text(json.dumps(values), encoding="utf-8")


def test_managed_storage_bootstraps_from_empty(cfg_path: Path) -> None:
    report = boot.ensure_forecast_managed_storage()

    pp = PathPolicy()
    assert pp.get_forecast_packages_dir().is_dir()
    assert pp.get_forecast_data_dir().is_dir()
    assert pp.get_forecast_runs_dir().is_dir()
    assert pp.get_forecast_evaluations_dir().is_dir()
    assert pp.get_forecast_config_proposals_dir().is_dir()
    assert pp.get_forecast_imports_dir().is_dir()
    assert cfg_path.exists()
    assert report["storage_mode"] == "app_managed"
    assert set(report.get("seeded", [])) >= {"data_root", "db_path", "runs_root"}
    db_path = pp.get_db_path()
    assert db_path.exists()
    assert SQLiteMigrator(db_path=str(db_path)).current_version() == LATEST_SCHEMA_VERSION
    assert find_redaction_leaks(report) == []


def test_managed_storage_repair_is_idempotent(cfg_path: Path) -> None:
    first = boot.ensure_forecast_managed_storage(repair=True)
    second = boot.ensure_forecast_managed_storage(repair=True)
    assert first["storage_mode"] == "app_managed"
    assert second.get("seeded", []) == []


def test_creates_only_configured_write_roots(cfg_path: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    runs = tmp_path / "runs"
    eval_root = tmp_path / "eval"
    config_edit = tmp_path / "config_edits"
    _write(
        cfg_path,
        data_root=str(data),
        runs_root=str(runs),
        eval_root=str(eval_root),
        config_edit_root=str(config_edit),
    )

    report = boot.ensure_forecast_roots()

    assert runs.is_dir() and eval_root.is_dir() and config_edit.is_dir()
    assert sorted(report["created"]) == ["config_edit_root", "eval_root", "runs_root"]
    assert report["bootstrap"]["write_roots_only"] is True


def test_creates_write_root_with_missing_parents(cfg_path: Path, tmp_path: Path) -> None:
    # Mirrors the launcher auto-default: a write-root nested several levels under a not-yet-existing
    # container is creatable (mkdir parents=True) and must be created + reported valid.
    runs = tmp_path / "app-support" / "analytics" / "forecast" / "runs"
    _write(cfg_path, runs_root=str(runs))

    report = boot.ensure_forecast_roots()

    assert runs.is_dir()
    assert "runs_root" in report["created"]
    assert report["roots"]["runs_root"]["valid"] is True


def test_is_idempotent(cfg_path: Path, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(cfg_path, runs_root=str(runs))

    first = boot.ensure_forecast_roots()
    assert "runs_root" in first["created"]

    second = boot.ensure_forecast_roots()
    assert second["created"] == []  # already exists → not re-reported
    assert runs.is_dir()


def test_never_creates_read_roots(cfg_path: Path, tmp_path: Path) -> None:
    # A missing data_root (a read-root) must stay missing and be surfaced as a blocker, not created.
    data = tmp_path / "data"  # deliberately not created
    _write(cfg_path, data_root=str(data))

    report = boot.ensure_forecast_roots()

    assert not data.exists()
    assert report["roots"]["data_root"]["blocker"] == rc.BLOCKER_MISSING


def test_skips_write_root_under_data_root(cfg_path: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    runs_under_data = data / "runs"  # nested under data_root → forbidden write-root
    _write(cfg_path, data_root=str(data), runs_root=str(runs_under_data))

    report = boot.ensure_forecast_roots()

    assert not runs_under_data.exists()
    assert "runs_root" not in report["created"]
    assert report["roots"]["runs_root"]["blocker"] == rc.BLOCKER_UNDER_LIVE_DATA_ROOT


def test_write_roots_use_managed_defaults_when_unconfigured(cfg_path: Path) -> None:
    # No settings/env → resolvers fall through to managed_default write-roots (creatable under app-support).
    report = boot.ensure_forecast_roots()
    pp = PathPolicy()
    assert pp.get_forecast_runs_dir().is_dir()
    assert "runs_root" in report["created"]


def test_report_is_redaction_safe(cfg_path: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    _write(
        cfg_path,
        data_root=str(data),
        runs_root=str(tmp_path / "runs"),
        eval_root=str(tmp_path / "eval"),
        config_edit_root=str(tmp_path / "config_edits"),
    )

    report = boot.ensure_forecast_roots()

    # Built from real /private|/tmp paths — the whole report (incl. the `created` keys) must
    # carry no path string.
    assert find_redaction_leaks(report) == []
