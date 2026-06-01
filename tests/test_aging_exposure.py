"""Phase 07D Prompt 09 — aging & exposure reporting (V25).

Covers band assignment, financial exposure, missing-status / unknown-age handling, review-required
flagging, empty no-op, no-raw-content (status normalization), idempotency, dry-run, and status
coverage over aging_exposure_report_items.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.aging_exposure import (
    AgingExposureBuilder,
    project_aging_exposure_status,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ", re.IGNORECASE
)
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_GUARDS = (
    "raw_email_body_persisted", "raw_document_text_persisted",
    "raw_calendar_payload_persisted", "raw_prompt_persisted", "raw_response_persisted",
    "signed_url_persisted", "download_url_persisted", "external_writeback_performed",
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_aging_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _live(
    db: str, endpoint: str, rid: str, status: str | None, ts: str | None, *, review: int = 0
) -> None:
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            "INSERT INTO procore_live_records "
            "(project_key, procore_project_id, endpoint_id, parent_procore_id, procore_record_id, "
            " canonical_json_redacted, review_required, first_seen_at_utc, last_seen_at_utc, "
            " last_sync_run_id, raw_body_persisted, status, updated_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tropical", "PP1", endpoint, "", rid, "{}", review, "2026-01-01T00:00:00Z",
                "2026-05-30T00:00:00Z", "run1", 0, status, ts,
            ),
        )
        raw.commit()
    finally:
        raw.close()


def _by_family(store: ConstructionStore) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for it in store.list_aging_exposure_report_items():
        out[it["record_family"]] = it
    return out


def _assert_guards_zero(db: str) -> None:
    raw = sqlite3.connect(db)
    try:
        cols = ", ".join(_GUARDS)
        for row in raw.execute(f"SELECT {cols} FROM aging_exposure_report_items"):
            assert set(row) <= {0}, "aging_exposure_report_items has a non-zero guard column"
    finally:
        raw.close()


# ---------------------------------------------------------------------------


def test_band_assignment() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "rfis", "1", "open", "2026-05-28T00:00:00Z")       # 4d -> current
        _live(db, "submittals", "2", "approved", "2026-05-10T00:00:00Z")  # 22d -> aging
        _live(db, "rfis", "3", "open", "2026-04-20T00:00:00Z")       # 42d -> stale
        _live(db, "inspections", "4", "open", "2026-01-01T00:00:00Z")  # 151d -> critical_review
        report = AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        assert report["ok"] is True
        assert report["summary"]["by_threshold_band"] == {
            "aging": 1, "critical_review": 1, "current": 1, "stale": 1
        }
        items = {it["record_ref"].split("|")[-1]: it for it in store.list_aging_exposure_report_items()}
        assert items["3"]["threshold_band"] == "stale" and items["3"]["stale_flag"] is True
        assert items["4"]["threshold_band"] == "critical_review"
        assert items["4"]["review_required"] is True  # critical band
        assert items["1"]["stale_flag"] is False
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_financial_exposure() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "subcontractor-invoices", "1", "open", "2026-01-01T00:00:00Z")  # 151d critical
        _live(db, "commitment-contracts", "2", "open", "2026-04-25T00:00:00Z")    # 37d stale
        report = AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        fin = report["summary"]["financial_exposure"]
        assert fin["total_financial"] == 2
        assert fin["critical_review"] == 1
        assert fin["stale"] == 1
        fams = _by_family(store)
        # financial family in a stale/critical band is flagged review-required
        assert fams["subcontractor-invoices"]["review_required"] is True
        assert fams["commitment-contracts"]["review_required"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_missing_status_flag() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "rfis", "1", None, "2026-05-20T00:00:00Z")
        AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_aging_exposure_report_items()[0]
        assert it["missing_status_flag"] is True
        assert it["status"] == "unknown"
    finally:
        Path(db).unlink(missing_ok=True)


def test_unknown_age_when_no_timestamp() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "meetings", "1", "scheduled", None)
        AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_aging_exposure_report_items()[0]
        assert it["threshold_band"] == "unknown"
        assert it["confidence_class"] is None
        assert it["age_days"] == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_required_from_source_flag() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        # young, non-financial record but flagged review_required at the source
        _live(db, "rfis", "1", "open", "2026-05-30T00:00:00Z", review=1)
        AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_aging_exposure_report_items()[0]
        assert it["threshold_band"] == "current"
        assert it["review_required"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_empty_source_writes_no_items() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        report = AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        assert report["summary"]["items_written"] == 0
        assert store.count_aging_exposure_report_items() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content_and_status_normalization() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "rfis", "1", "{'id': 20577, 'name': 'Open', 'mapped_to_status': 'open'}",
              "2026-05-20T00:00:00Z")
        AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_aging_exposure_report_items()[0]
        assert it["status"] == "open"
        blob = json.dumps(store.list_aging_exposure_report_items(), default=str)
        assert _LEAK.search(blob) is None
        assert "mapped_to_status" not in blob and "'name'" not in blob
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_apply() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "rfis", "1", "open", "2026-04-20T00:00:00Z")
        _live(db, "subcontractor-invoices", "2", "open", "2026-01-01T00:00:00Z")
        builder = AgingExposureBuilder(store)
        builder.build(dry_run=False, now_utc=_NOW)
        builder.build(dry_run=False, now_utc=_NOW)
        assert store.count_aging_exposure_report_items() == 2
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_dry_run_writes_nothing() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "rfis", "1", "open", "2026-05-28T00:00:00Z")
        report = AgingExposureBuilder(store).build(dry_run=True, now_utc=_NOW)
        assert report["mode"] == "dry_run"
        assert report["summary"]["items_planned"] == 1
        assert report["summary"]["items_written"] == 0
        assert store.count_aging_exposure_report_items() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _live(db, "rfis", "1", "open", "2026-04-20T00:00:00Z")  # stale
        _live(db, "subcontractor-invoices", "2", "open", "2026-01-01T00:00:00Z")  # critical financial
        AgingExposureBuilder(store).build(dry_run=False, now_utc=_NOW)
        status = project_aging_exposure_status(store)
        assert status["ok"] is True
        assert status["summary"]["items"] == 2
        assert status["summary"]["stale"] == 2
        assert status["summary"]["financial_exposure"]["total_financial"] == 1
    finally:
        Path(db).unlink(missing_ok=True)
