"""Phase 08B Prompt 12 — V34 daily-brief open-receipt schema additions.

Proves V34 additively (1) creates the open-receipts table that ships empty, (2) declares + enforces
the canonical no-raw / no-writeback guard `CHECK(col = 0)` columns, (3) pins
`open_target IN ('vault','html')` and `mode IN ('dry_run','apply')`, (4) enforces the daily_brief_runs
FK, (5) is idempotent and leaves V1-V33 intact, and (6) the lifecycle contract classifies the table
operational_empty_expected at count 151.
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.construction.data_quality import build_table_inventory_report
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_V34_TABLES = ["daily_brief_open_receipts"]

_GUARD_NAME_RE = re.compile(
    r"(raw_email_body_persisted|raw_document_text_persisted|raw_calendar_payload_persisted|"
    r"raw_prompt_persisted|raw_response_persisted|retrieved_context_persisted|"
    r"signed_url_persisted|download_url_persisted|external_writeback_performed)"
)


def _migrate(db: Path) -> int:
    return SQLiteMigrator(db_path=str(db)).apply()


def _names(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _ddl(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    assert row is not None, f"missing table {table}"
    return str(row[0])


def test_v34_is_latest_and_creates_open_table() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert LATEST_SCHEMA_VERSION >= 34
        conn = sqlite3.connect(str(db))
        tables = _names(conn)
        for t in _V34_TABLES:
            assert t in tables, f"missing V34 table {t}"
            assert conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0


def test_v34_guard_columns_present_and_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        for t in _V34_TABLES:
            guards = set(_GUARD_NAME_RE.findall(_ddl(conn, t)))
            for col in (
                "raw_prompt_persisted",
                "raw_response_persisted",
                "signed_url_persisted",
                "download_url_persisted",
                "external_writeback_performed",
            ):
                assert col in guards, f"{t} missing guard {col}"
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO daily_brief_open_receipts "
                "(open_receipt_id, brief_date, open_target, open_status, mode, external_writeback_performed) "
                "VALUES ('r1','2026-06-02','vault','opened','apply',1)"
            )


def test_v34_open_target_is_pinned_to_local_artifacts() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        # Non-local / unknown targets are rejected at the DB layer.
        for target in ("email", "slack", "browser_remote", "vault_html"):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO daily_brief_open_receipts "
                    "(open_receipt_id, brief_date, open_target, open_status, mode) "
                    "VALUES (?,?,?, 'opened','apply')",
                    (f"r-{target}", "2026-06-02", target),
                )
        # Both local targets are accepted.
        for target in ("vault", "html"):
            conn.execute(
                "INSERT INTO daily_brief_open_receipts "
                "(open_receipt_id, brief_date, open_target, open_status, mode) "
                "VALUES (?,?,?, 'opened','apply')",
                (f"r-ok-{target}", "2026-06-02", target),
            )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM daily_brief_open_receipts").fetchone()[0] == 2


def test_v34_mode_check_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO daily_brief_open_receipts "
                "(open_receipt_id, brief_date, open_target, open_status, mode) "
                "VALUES ('r1','2026-06-02','vault','opened','sendmail')"
            )


def test_v34_daily_brief_runs_fk_enforced() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        _migrate(db)
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO daily_brief_open_receipts "
                "(open_receipt_id, brief_run_id, brief_date, open_target, open_status, mode) "
                "VALUES ('r1','does-not-exist','2026-06-02','vault','opened','apply')"
            )


def test_v34_is_idempotent_and_preserves_prior_versions() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        assert _migrate(db) == LATEST_SCHEMA_VERSION
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE version = 34").fetchone()[0]
        assert n == 1
        tables = _names(conn)
        for t in (
            "assistant_runs",
            "daily_brief_runs",
            "daily_brief_delivery_receipts",
            "daily_brief_notification_receipts",
        ):
            assert t in tables


def test_v34_table_classified_in_lifecycle_contract() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v34.db"
        _migrate(db)
        report = build_table_inventory_report(db_path=str(db))
        assert report["contract_table_count"] == 194
        by_name = {t["table_name"]: t for t in report["tables"]}
        for t in _V34_TABLES:
            assert t in by_name, f"{t} absent from live inventory"
            assert by_name[t]["lifecycle_status"] == "operational_empty_expected"
            assert by_name[t].get("source") == "contract"
        assert report["reconciliation"]["in_db_not_in_contract"] == []
