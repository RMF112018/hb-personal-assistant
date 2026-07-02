"""Backend runner guard and proof tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.api import create_app
from hb_assistant.store.migrator import SQLiteMigrator
from scripts.dev_schedule_clean_db_backend import build_startup_proof


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_live_db_path_rejected() -> None:
    live = str(PathPolicy().get_db_path())
    with pytest.raises(ValueError, match="live"):
        build_startup_proof(
            db_path=live,
            port=8000,
            confirm_clean_copy=True,
            allow_custom_copy_path=True,
        )


def test_missing_confirm_rejected(tmp_path: Path) -> None:
    db = tmp_path / "copy.sqlite"
    db.write_bytes(b"")
    with pytest.raises(ValueError, match="confirm-clean-copy"):
        build_startup_proof(
            db_path=str(db),
            port=8000,
            confirm_clean_copy=False,
            allow_custom_copy_path=True,
        )


def test_custom_path_outside_clean_db_rejected(tmp_path: Path) -> None:
    db = tmp_path / "outside.sqlite"
    db.write_bytes(b"")
    with pytest.raises(ValueError, match="local-sensitive"):
        build_startup_proof(
            db_path=str(db),
            port=8000,
            confirm_clean_copy=True,
            allow_custom_copy_path=False,
        )


def test_proof_only_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    clean = repo / "local-sensitive" / "clean-db" / "copy.sqlite"
    clean.parent.mkdir(parents=True)
    SQLiteMigrator(db_path=str(clean)).apply()
    monkeypatch.setattr(PathPolicy, "resolve_repo_root", lambda self: repo)
    proof = build_startup_proof(
        db_path=str(clean),
        port=8010,
        confirm_clean_copy=True,
        allow_custom_copy_path=False,
    )
    assert proof["clean_copy_guard_passed"] is True
    assert proof["db_path_is_live_db"] is False
    assert proof["mode"] == "schedule_clean_db_backend"


def test_create_app_receives_db_path(tmp_path: Path) -> None:
    db = tmp_path / "app.db"
    SQLiteMigrator(db_path=str(db)).apply()
    app = create_app(db_path=str(db))
    assert app.state.db_path == str(db.resolve())
