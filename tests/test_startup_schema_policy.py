"""Tests for startup schema policy gating."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator
from hb_assistant.store.startup_schema_policy import (
    StartupSchemaPolicyError,
    apply_startup_schema_policy,
    evaluate_startup_schema,
)


def _write_receipt(path: Path, *, schema_version: int = LATEST_SCHEMA_VERSION - 1) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_utc": "2026-07-04T00:00:00Z",
                "schema_version": schema_version,
                "backup_path": "/volume2/personal-assistant/app-support/db/backups/test.sqlite",
            }
        ),
        encoding="utf-8",
    )


def test_schema_at_head_allows_without_apply(tmp_path: Path) -> None:
    db = tmp_path / "api.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    decision = evaluate_startup_schema(db)
    assert decision.action == "allow"
    report = apply_startup_schema_policy(db)
    assert report["migration_performed"] is False
    assert report["schema_version"] == LATEST_SCHEMA_VERSION


def test_schema_ahead_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "api.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    conn_path = db
    import sqlite3

    conn = sqlite3.connect(str(conn_path))
    try:
        conn.execute(
            "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
            (LATEST_SCHEMA_VERSION + 1, "future", "2026-07-04T00:00:00Z"),
        )
        conn.commit()
    finally:
        conn.close()

    decision = evaluate_startup_schema(db)
    assert decision.action == "fail"
    with pytest.raises(StartupSchemaPolicyError):
        apply_startup_schema_policy(db)


def test_schema_behind_requires_operator_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "api.sqlite"
    conn_path = db
    import sqlite3

    conn = sqlite3.connect(str(conn_path))
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (1, 'v1_initial_schema', '2026-07-04T00:00:00Z');
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.delenv("HB_ALLOW_STARTUP_MIGRATIONS", raising=False)
    decision = evaluate_startup_schema(db)
    assert decision.action == "fail"
    assert decision.reason == "schema_behind_requires_operator_flag"


def test_schema_behind_with_flag_requires_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "api.sqlite"
    import sqlite3

    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (1, 'v1_initial_schema', '2026-07-04T00:00:00Z');
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("HB_ALLOW_STARTUP_MIGRATIONS", "1")
    monkeypatch.delenv("HB_STARTUP_MIGRATION_BACKUP_RECEIPT", raising=False)
    decision = evaluate_startup_schema(db)
    assert decision.reason == "schema_behind_requires_backup_receipt"


def test_schema_behind_with_flag_and_receipt_migrates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "api.sqlite"
    receipt = tmp_path / "receipt.json"
    _write_receipt(receipt)
    import sqlite3

    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            INSERT INTO schema_migrations (version, name, applied_at)
            VALUES (1, 'v1_initial_schema', '2026-07-04T00:00:00Z');
            """
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("HB_ALLOW_STARTUP_MIGRATIONS", "1")
    monkeypatch.setenv("HB_STARTUP_MIGRATION_BACKUP_RECEIPT", str(receipt))
    report = apply_startup_schema_policy(db)
    assert report["migration_performed"] is True
    assert report["schema_version"] == LATEST_SCHEMA_VERSION


def test_missing_db_fails_on_nas_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    db = tmp_path / "missing.sqlite"
    decision = evaluate_startup_schema(db)
    assert decision.action == "fail"
    assert decision.reason == "db_missing_nas_runtime"


def test_missing_db_bootstraps_in_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    db = tmp_path / "missing.sqlite"
    decision = evaluate_startup_schema(db)
    assert decision.action == "migrate"
    report = apply_startup_schema_policy(db)
    assert report["migration_performed"] is True
    assert db.is_file()
