"""Tests for neutral db_path_guard."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hb_assistant.config.db_path_guard import (
    assert_clean_copy_path,
    get_live_db_path,
    is_live_db_path,
    resolve_clean_copy_guard,
)
from hb_assistant.config.path_policy import PathPolicy


def test_live_db_path_matches_policy(tmp_path: Path) -> None:
    live = get_live_db_path()
    assert is_live_db_path(live) is True
    assert is_live_db_path(tmp_path / "fixture.db") is False


def test_unresolvable_path_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_path: Path) -> Path:
        raise OSError("resolve failed")

    monkeypatch.setattr(Path, "resolve", _boom)
    assert is_live_db_path("/any/path.db") is True


def test_clean_copy_guard_requires_subdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    clean = repo / "local-sensitive" / "clean-db" / "copy.sqlite"
    clean.parent.mkdir(parents=True)
    clean.write_bytes(b"")
    monkeypatch.setattr(PathPolicy, "resolve_repo_root", lambda self: repo)
    guard = resolve_clean_copy_guard(clean)
    assert guard["clean_copy_guard_passed"] is True
    outside = tmp_path / "outside.sqlite"
    outside.write_bytes(b"")
    guard2 = resolve_clean_copy_guard(outside)
    assert guard2["clean_copy_guard_passed"] is False


def test_schedule_clean_db_guards_no_forecast_import() -> None:
    before = set(sys.modules)
    import hb_assistant.construction.schedule_clean_db.guards  # noqa: F401

    imported = set(sys.modules) - before
    assert not any("forecast" in name for name in imported)
