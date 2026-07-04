"""Tests for NAS/dev SQLite DB storage guard."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from hb_assistant.config.db_storage_guard import (
    DbStorageGuardError,
    NAS_DEFAULT_DB_PATH,
    assert_db_storage_allowed,
    classify_db_storage,
    is_permissive_guard,
)


def test_nas_runtime_allows_production_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    monkeypatch.delenv("HB_DB_STORAGE_GUARD", raising=False)
    assert (
        classify_db_storage(NAS_DEFAULT_DB_PATH) == "nas_local"
    )
    assert assert_db_storage_allowed(NAS_DEFAULT_DB_PATH) == "nas_local"


def test_nas_runtime_allows_smoke_db(monkeypatch: pytest.MonkeyPatch) -> None:
    smoke_db = "/volume2/personal-assistant/app-support-smoke/db/hb-personal-assistant.sqlite"
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    assert classify_db_storage(smoke_db) == "nas_local"


def test_nas_runtime_rejects_volumes_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    bad = "/Volumes/NAS/share/db/hb-personal-assistant.sqlite"
    assert classify_db_storage(bad) == "blocked"
    with pytest.raises(DbStorageGuardError):
        assert_db_storage_allowed(bad)


def test_nas_runtime_rejects_mac_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    mac_db = str(
        Path.home()
        / "Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite"
    )
    assert classify_db_storage(mac_db) == "blocked"


def test_permissive_cannot_override_nas_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    monkeypatch.setenv("HB_DB_STORAGE_GUARD", "permissive")
    assert is_permissive_guard() is False
    bad = "/tmp/test.sqlite"
    assert classify_db_storage(bad) == "blocked"


def test_dev_tmp_path_allowed_without_nas_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    tmp_db = "/tmp/pytest-of-user/pytest-0/db.sqlite"
    assert classify_db_storage(tmp_db) == "dev_permissive"


def test_universal_deny_smb_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    with pytest.raises(DbStorageGuardError) as exc:
        assert_db_storage_allowed("smb://nas/share/db/hb-personal-assistant.sqlite")
    assert exc.value.reason == "network_scheme"


def test_universal_deny_relative_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    with pytest.raises(DbStorageGuardError) as exc:
        assert_db_storage_allowed("db/hb-personal-assistant.sqlite")
    assert exc.value.reason == "relative_path"
