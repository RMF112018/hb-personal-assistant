"""Unit tests for forecast runtime config wiring (Implementation Phase 6).

Asserts: resolver precedence (explicit > env > settings-file > managed_default > None);
whitelist-merge load with
fail-closed fallback; non-mutating validation maps to coded blockers; the status payload never
leaks a path (find_redaction_leaks clean even with real paths configured); and save_runtime_config
refuses a write-root under the resolved data root — including when data_root is supplied only via
the settings file (the resolve_eval_root env-only blind spot) — writing nothing on refusal.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
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


# -- precedence ---------------------------------------------------------------


def test_data_root_precedence(cfg_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(cfg_path, data_root="/settings/data")
    monkeypatch.setenv("HB_FORECAST_DATA_ROOT", "/env/data")

    assert rc.resolve_data_root("/explicit/data") == "/explicit/data"  # explicit wins
    assert rc.resolve_data_root(None) == "/env/data"  # env beats settings
    monkeypatch.delenv("HB_FORECAST_DATA_ROOT")
    assert rc.resolve_data_root(None) == "/settings/data"  # settings beats None
    cfg_path.unlink()
    assert rc.resolve_data_root(None) == rc.managed_forecast_paths()["data_root"]


def test_package_roots_precedence(cfg_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write(cfg_path, package_roots=["/settings/a", "/settings/b"])
    assert rc.resolve_package_roots(["/explicit"]) == ["/explicit"]
    assert rc.resolve_package_roots(None) == ["/settings/a", "/settings/b"]
    monkeypatch.setenv("HB_FORECAST_PACKAGE_ROOTS", "/env/a")
    assert rc.resolve_package_roots(None) == ["/env/a"]  # env beats settings


# -- load / whitelist-merge ---------------------------------------------------


def test_load_drops_unknown_keys_and_falls_back(cfg_path: Path) -> None:
    cfg_path.write_text(json.dumps({"data_root": "/d", "evil_key": "x"}), encoding="utf-8")
    cfg = rc._load_config()
    assert cfg["data_root"] == "/d"
    assert "evil_key" not in cfg

    cfg_path.write_text("{ not valid json", encoding="utf-8")
    assert rc._load_config() == rc.DEFAULT_CONFIG  # fail closed to defaults


# -- validation → coded blockers (status is redaction-safe) -------------------


def test_status_blocker_codes(cfg_path: Path, tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    a_file = tmp_path / "f.txt"
    a_file.write_text("x", encoding="utf-8")
    _write(
        cfg_path,
        data_root=str(missing),  # missing
        runs_root="relative/path",  # not_absolute
        eval_root=str(a_file),  # exists but not a directory
    )
    status = rc.build_runtime_status()
    assert status["roots"]["data_root"]["blocker"] == rc.BLOCKER_MISSING
    assert status["roots"]["runs_root"]["blocker"] == rc.BLOCKER_NOT_ABSOLUTE
    assert status["roots"]["eval_root"]["blocker"] == rc.BLOCKER_NOT_A_DIRECTORY
    assert status["roots"]["package_roots"]["blocker"] == rc.BLOCKER_MISSING
    # The whole status payload — built from real /private|/tmp paths — must leak nothing.
    assert find_redaction_leaks(status) == []


def test_status_valid_when_fully_configured(cfg_path: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    runs = tmp_path / "runs"
    eval_root = tmp_path / "eval"
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    cfr = tmp_path / "cfr"
    cfr.mkdir()
    db = tmp_path / "base.sqlite"
    db.write_text("", encoding="utf-8")
    _write(
        cfg_path,
        package_roots=[str(pkg)],
        data_root=str(data),
        runs_root=str(runs),
        eval_root=str(eval_root),
        db_path=str(db),
        cfr_src=str(cfr),
        config_edit_root=str(tmp_path / "config_edits"),
    )
    status = rc.build_runtime_status()
    assert all(r["valid"] for r in status["roots"].values())
    assert status["surfaces_ready"] == {
        "catalog": True,
        "config": True,
        "run_center": True,
        "external_eval": True,
        "config_edit": True,
        # config_promotion additionally requires the explicit opt-in (off by default here).
        "config_promotion": False,
        # db_config_run additionally requires the explicit opt-in (off by default here).
        "db_config_run": False,
    }
    assert find_redaction_leaks(status) == []


def test_db_config_run_enabled_precedence(cfg_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(rc.ENV_DB_CONFIG_RUN_ENABLED, raising=False)
    assert rc.resolve_db_config_run_enabled() is False  # default OFF
    _write(cfg_path, db_config_run_enabled=True)
    assert rc.resolve_db_config_run_enabled() is True  # settings-file beats default
    monkeypatch.setenv(rc.ENV_DB_CONFIG_RUN_ENABLED, "0")
    assert rc.resolve_db_config_run_enabled() is False  # env beats settings
    assert rc.resolve_db_config_run_enabled(True) is True  # explicit beats all


def test_save_persists_db_config_run_flag(cfg_path: Path) -> None:
    rc.save_runtime_config({"db_config_run_enabled": True})
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["db_config_run_enabled"] is True


# -- save: fail-closed write-root cross-check ---------------------------------


def test_save_refuses_runs_root_under_data_root(cfg_path: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(rc.ForecastRuntimeConfigError) as exc:
        rc.save_runtime_config({"data_root": str(data), "runs_root": str(data / "inside")})
    assert exc.value.args[0] == f"runs_root:{rc.BLOCKER_UNDER_LIVE_DATA_ROOT}"
    assert not cfg_path.exists()  # nothing persisted on refusal


def test_save_refuses_eval_root_under_settings_only_data_root(
    cfg_path: Path, tmp_path: Path
) -> None:
    # data_root reaches the guard ONLY via the supplied config (no env). This is the
    # resolve_eval_root env-only blind spot that the cross-check closes.
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(rc.ForecastRuntimeConfigError) as exc:
        rc.save_runtime_config({"data_root": str(data), "eval_root": str(data / "ev")})
    assert exc.value.args[0] == f"eval_root:{rc.BLOCKER_UNDER_LIVE_DATA_ROOT}"
    assert not cfg_path.exists()


def test_save_refuses_config_edit_root_under_data_root(cfg_path: Path, tmp_path: Path) -> None:
    # The Phase E config-edit root is a write root and must not sit under the live data root.
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(rc.ForecastRuntimeConfigError) as exc:
        rc.save_runtime_config({"data_root": str(data), "config_edit_root": str(data / "edits")})
    assert exc.value.args[0] == f"config_edit_root:{rc.BLOCKER_UNDER_LIVE_DATA_ROOT}"
    assert not cfg_path.exists()


# -- db_path advisory probe (redaction-safe, non-blocking) --------------------


def _make_config_db(path: Path, *, version: int = 61, snapshots: int = 2) -> None:
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
        conn.executemany("INSERT INTO schema_migrations (version) VALUES (?)", [(v,) for v in range(1, version + 1)])
        conn.execute("CREATE TABLE forecast_config_snapshots (config_snapshot_id TEXT)")
        conn.executemany(
            "INSERT INTO forecast_config_snapshots (config_snapshot_id) VALUES (?)",
            [(f"snap-{i}",) for i in range(snapshots)],
        )
        conn.commit()
    finally:
        conn.close()


def test_db_advisory_present_for_valid_config_db(cfg_path: Path, tmp_path: Path) -> None:
    db = tmp_path / "config.sqlite"
    _make_config_db(db, version=61, snapshots=2)
    _write(cfg_path, db_path=str(db))

    status = rc.build_runtime_status()
    db_root = status["roots"]["db_path"]
    assert db_root["valid"] is True
    assert db_root["schema_version"] == 61
    assert db_root["config_snapshot_count"] == 2
    # Advisory is ints only — the whole status payload (real /private|/tmp db path) must not leak.
    assert find_redaction_leaks(status) == []


def test_db_advisory_absent_when_db_missing_or_unrecognized(cfg_path: Path, tmp_path: Path) -> None:
    # Missing → not even configured-valid; no advisory keys.
    _write(cfg_path, db_path=str(tmp_path / "nope.sqlite"))
    missing = rc.build_runtime_status()["roots"]["db_path"]
    assert "schema_version" not in missing and "config_snapshot_count" not in missing

    # Exists but is not a recognizable HB DB (no schema_migrations) → graceful empty advisory.
    junk = tmp_path / "junk.sqlite"
    junk.write_text("not a database", encoding="utf-8")
    _write(cfg_path, db_path=str(junk))
    bad = rc.build_runtime_status()["roots"]["db_path"]
    assert bad["valid"] is True  # existence-level validity is unchanged
    assert "schema_version" not in bad and "config_snapshot_count" not in bad


def test_db_advisory_keeps_root_keyset_stable(cfg_path: Path, tmp_path: Path) -> None:
    db = tmp_path / "config.sqlite"
    _make_config_db(db)
    _write(cfg_path, db_path=str(db))
    status = rc.build_runtime_status()
    # The advisory is additive INSIDE db_path; the root key set is unchanged.
    assert set(status["roots"]) == {
        "package_roots",
        "data_root",
        "runs_root",
        "eval_root",
        "db_path",
        "cfr_src",
        "config_edit_root",
    }


def test_seed_runtime_config_if_incomplete_writes_managed_defaults(cfg_path: Path) -> None:
    seeded = rc.seed_runtime_config_if_incomplete()
    assert set(seeded) >= {
        "package_roots",
        "data_root",
        "runs_root",
        "eval_root",
        "db_path",
        "config_edit_root",
    }
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    managed = rc.managed_forecast_paths()
    assert cfg["data_root"] == managed["data_root"]
    assert cfg["db_path"] == managed["db_path"]


def test_seed_preserves_existing_settings(cfg_path: Path, tmp_path: Path) -> None:
    custom = str(tmp_path / "custom-data")
    _write(cfg_path, data_root=custom)
    seeded = rc.seed_runtime_config_if_incomplete()
    assert "data_root" not in seeded
    assert json.loads(cfg_path.read_text(encoding="utf-8"))["data_root"] == custom


def test_reset_runtime_config_to_managed_defaults(cfg_path: Path, tmp_path: Path) -> None:
    _write(cfg_path, data_root=str(tmp_path / "custom"))
    status = rc.reset_runtime_config_to_managed_defaults()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["data_root"] == rc.managed_forecast_paths()["data_root"]
    assert status["storage_mode"] == "app_managed"


def test_is_managed_db_path_matches_path_policy() -> None:
    managed = str(PathPolicy().get_db_path())
    assert rc.is_managed_db_path(managed) is True
    assert rc.is_managed_db_path("/tmp/other.sqlite") is False


def test_save_allows_db_path_under_data_root(cfg_path: Path, tmp_path: Path) -> None:
    # db_path is read-only (mode=ro) and not a write hazard, so it is NOT write-guarded.
    data = tmp_path / "data"
    data.mkdir()
    db = data / "source.sqlite"
    db.write_text("", encoding="utf-8")
    status = rc.save_runtime_config({"data_root": str(data), "db_path": str(db)})
    assert cfg_path.exists()  # persisted
    assert status["roots"]["db_path"]["valid"] is True
    persisted = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert persisted["db_path"] == str(db)
    assert persisted["schema_version"] == 1
