"""Unit tests for the forecast launch bootstrap (Live App Bootstrap/Launcher phase).

Asserts: ``ensure_forecast_roots`` creates ONLY configured+valid write-roots (never read-roots),
is idempotent, skips a write-root nested under the data root, is a no-op when nothing is configured,
and that its readiness report leaks no path strings (find_redaction_leaks clean with real paths).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.construction.analytics import forecast_bootstrap as boot
from hb_assistant.construction.analytics import forecast_runtime_config as rc
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks

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
    assert report["created"] == ["runs_root"]
    assert report["roots"]["runs_root"]["valid"] is True


def test_is_idempotent(cfg_path: Path, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _write(cfg_path, runs_root=str(runs))

    first = boot.ensure_forecast_roots()
    assert first["created"] == ["runs_root"]

    second = boot.ensure_forecast_roots()
    assert second["created"] == []  # already exists → not re-reported
    assert runs.is_dir()


def test_never_creates_read_roots(cfg_path: Path, tmp_path: Path) -> None:
    # A missing data_root (a read-root) must stay missing and be surfaced as a blocker, not created.
    data = tmp_path / "data"  # deliberately not created
    _write(cfg_path, data_root=str(data))

    report = boot.ensure_forecast_roots()

    assert not data.exists()
    assert report["created"] == []
    assert report["roots"]["data_root"]["blocker"] == rc.BLOCKER_MISSING


def test_skips_write_root_under_data_root(cfg_path: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    runs_under_data = data / "runs"  # nested under data_root → forbidden write-root
    _write(cfg_path, data_root=str(data), runs_root=str(runs_under_data))

    report = boot.ensure_forecast_roots()

    assert not runs_under_data.exists()
    assert report["created"] == []
    assert report["roots"]["runs_root"]["blocker"] == rc.BLOCKER_UNDER_LIVE_DATA_ROOT


def test_noop_when_unconfigured(cfg_path: Path, tmp_path: Path) -> None:
    # No settings file written, no env → every write-root resolves to None → nothing created.
    report = boot.ensure_forecast_roots()
    assert report["created"] == []
    assert not (tmp_path / "runs").exists()


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
