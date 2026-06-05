from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from hb_assistant.config.models import AppConfig
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store import get_connection
from hb_assistant.store.errors import StoreReadinessError


def _policy_for_root(root: Path) -> PathPolicy:
    cfg = AppConfig()
    cfg.paths.application_support_root = str(root)
    return PathPolicy(cfg)


def test_ensure_db_ready_fails_when_db_parent_is_not_directory(tmp_path: Path) -> None:
    pp = _policy_for_root(tmp_path / "support")
    pp.ensure_dirs(create_sensitive=False)
    db_parent = pp.get_db_path().parent
    db_parent.rmdir()
    db_parent.write_text("not-a-dir", encoding="utf-8")

    report = pp.ensure_db_ready(return_report=True)
    assert report is not None
    assert report["ok"] is False
    assert report["error"] == "db_parent_not_directory"


def test_ensure_db_ready_fails_when_db_parent_not_writable(tmp_path: Path) -> None:
    pp = _policy_for_root(tmp_path / "support")
    pp.ensure_dirs(create_sensitive=False)

    with patch("os.access", return_value=False):
        report = pp.ensure_db_ready(return_report=True)

    assert report is not None
    assert report["ok"] is False
    assert report["error"] == "db_parent_not_writable"


def test_get_connection_maps_operational_error_to_store_readiness(tmp_path: Path) -> None:
    pp = _policy_for_root(tmp_path / "support")
    pp.ensure_dirs(create_sensitive=False)
    db_path = pp.get_db_path()

    with patch(
        "sqlite3.connect", side_effect=sqlite3.OperationalError("unable to open database file")
    ):
        with pytest.raises(StoreReadinessError) as ex:
            get_connection(db_path)

    assert ex.value.status == "blocked_db_unavailable"
    assert "unable to open database file" in str(ex.value)


def test_ensure_db_ready_reports_wal_probe(tmp_path: Path) -> None:
    pp = _policy_for_root(tmp_path / "support")
    pp.ensure_dirs(create_sensitive=False)
    report = pp.ensure_db_ready(return_report=True)
    assert report is not None
    assert report["ok"] is True
    assert report["checks"]["sqlite_openable"] is True
    assert report["checks"]["wal_mode"] in ("wal", "delete", "degraded", "unknown")
