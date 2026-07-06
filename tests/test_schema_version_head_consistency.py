"""Head schema-version consistency guard (N2 schema-drift regression).

Pins the invariant that drifted before N2: the migrator defined/applied a v98
migration and recorded a ``schema_migrations`` row ``version=98``, but
``LATEST_SCHEMA_VERSION`` stayed 97. That made ``apply()`` / ``current_version()``
(both ``MAX(version) FROM schema_migrations``) disagree with the single source of
truth, and ``/health`` masked it via ``>=``. These tests fail if the recorded head
version and the ``LATEST_SCHEMA_VERSION`` constant ever diverge again.

All work is against ``tmp_path`` scratch DBs only — no live/production DB is touched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics.api import create_app
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _max_recorded_version(db: Path) -> int:
    with sqlite3.connect(db) as conn:
        return conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0]


def test_fresh_db_migrates_to_latest_constant(tmp_path: Path) -> None:
    # A fresh scratch DB must reach exactly the declared head version.
    db = tmp_path / "head.db"
    assert _migrate(db) == LATEST_SCHEMA_VERSION


def test_recorded_head_equals_latest_constant(tmp_path: Path) -> None:
    # The exact invariant that drifted: MAX(schema_migrations.version) == constant.
    db = tmp_path / "head.db"
    _migrate(db)
    assert _max_recorded_version(db) == LATEST_SCHEMA_VERSION


def test_v98_migration_row_present(tmp_path: Path) -> None:
    db = tmp_path / "head.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT name FROM schema_migrations WHERE version = 98").fetchone()
    assert row is not None
    assert row[0] == "v98_project_schedule_review_dispositions"


def test_v99_migration_row_present(tmp_path: Path) -> None:
    db = tmp_path / "head.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT name FROM schema_migrations WHERE version = 99").fetchone()
    assert row is not None
    assert row[0] == "v99_source_identity_root_scoped"


def test_v100_migration_row_present(tmp_path: Path) -> None:
    db = tmp_path / "head.db"
    _migrate(db)
    with sqlite3.connect(db) as conn:
        row = conn.execute("SELECT name FROM schema_migrations WHERE version = 100").fetchone()
    assert row is not None
    assert row[0] == "v100_assistant_claims"


def test_apply_is_idempotent(tmp_path: Path) -> None:
    # v98 is a destructive rebuild-and-rename guarded only by the outer
    # ``WHERE version = 98`` check; a second apply() must be a safe no-op.
    db = tmp_path / "head.db"
    first = _migrate(db)
    second = _migrate(db)
    assert first == second == LATEST_SCHEMA_VERSION
    assert _max_recorded_version(db) == LATEST_SCHEMA_VERSION


def test_health_reports_schema_ready_equality(tmp_path: Path, monkeypatch) -> None:
    # /health must report the migrated scratch DB as at-head with equal
    # version/expected (not merely ``schema_version >= schema_expected``).
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = tmp_path / "head.db"
    _migrate(db)
    client = TestClient(create_app(db_path=str(db)))
    payload = client.get("/health").json()
    assert payload["schema_version"] == LATEST_SCHEMA_VERSION
    assert payload["schema_expected"] == LATEST_SCHEMA_VERSION
    assert payload["schema_version"] == payload["schema_expected"]
    assert payload["schema_ready"] is True
