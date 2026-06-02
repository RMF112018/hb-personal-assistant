"""Phase 07D Prompt 07 — project issue-history materialization (V25).

Covers grouping (deterministic + strong only), strong→review-required, weak/model/sensitive
exclusion, activity/status resolution + normalization, no-raw-content, idempotency, dry-run, and
status coverage over project_issue_history_items.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from hb_assistant.construction.issue_history import (
    IssueHistoryBuilder,
    project_issue_history_status,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}", re.IGNORECASE
)
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_GUARDS = (
    "raw_email_body_persisted", "raw_document_text_persisted",
    "raw_calendar_payload_persisted", "raw_prompt_persisted", "raw_response_persisted",
    "signed_url_persisted", "download_url_persisted", "external_writeback_performed",
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_issuehist_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _cand(store: ConstructionStore, cid: str, src_ref: str, **over: object) -> None:
    cc = str(over.pop("confidence_class", "deterministic"))
    kw: dict = {
        "candidate_id": cid,
        "source_family": "procore",
        "source_record_type": "procore_record",
        "source_record_ref": src_ref,
        "target_family": "procore_entity",
        "target_record_type": "entity",
        "target_record_ref": "ent_" + cid,
        "relationship_type": "created_by",
        "confidence_score": 1.0,
        "confidence_class": cc,
        "source_reference_json": json.dumps({"s": cid}),
        "deterministic": cc == "deterministic",
        "review_required": False,
        "project_key": "tropical",
        "evidence_trail_id": "et_" + cid,
    }
    kw.update(over)
    store.upsert_cross_source_relationship_candidate(**kw)  # type: ignore[arg-type]


def _live(db: str, endpoint: str, rid: str, status: str, ts: str | None) -> None:
    """Seed a procore_live_records row via a raw FK-off connection."""
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            "INSERT INTO procore_live_records "
            "(project_key, procore_project_id, endpoint_id, parent_procore_id, procore_record_id, "
            " canonical_json_redacted, review_required, first_seen_at_utc, last_seen_at_utc, "
            " last_sync_run_id, raw_body_persisted, status, updated_at_utc) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "tropical", "PP1", endpoint, "", rid, "{}", 0, "2026-01-01T00:00:00Z",
                "2026-05-30T00:00:00Z", "run1", 0, status, ts,
            ),
        )
        raw.commit()
    finally:
        raw.close()


def _items(store: ConstructionStore) -> dict[str, dict]:
    return {i["issue_kind"]: i for i in store.list_project_issue_history_items()}


def _assert_guards_zero(db: str) -> None:
    raw = sqlite3.connect(db)
    try:
        cols = ", ".join(_GUARDS)
        for row in raw.execute(f"SELECT {cols} FROM project_issue_history_items"):
            assert set(row) <= {0}, "project_issue_history_items has a non-zero guard column"
    finally:
        raw.close()


# ---------------------------------------------------------------------------


def test_success_groups_per_anchor_record() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        # two deterministic edges on the same anchor -> one family
        _cand(store, "c0", "tropical|rfis||100")
        _cand(store, "c1", "tropical|rfis||100", target_family="procore",
              target_record_type="procore_record")
        report = IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        assert report["ok"] is True
        assert report["summary"]["families_written"] == 1
        items = store.list_project_issue_history_items()
        assert len(items) == 1
        it = items[0]
        assert it["confidence_class"] == "deterministic"
        assert it["review_required"] is False
        assert it["issue_kind"] == "rfis"
        assert set(it["source_families_json"]) == {"procore", "procore_entity"}
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_strong_heuristic_family_is_review_required() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|change-orders||9", confidence_class="strong_heuristic")
        IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_project_issue_history_items()[0]
        assert it["confidence_class"] == "strong_heuristic"
        assert it["review_required"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_weak_model_sensitive_excluded_from_grouping() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|a||1", confidence_class="weak_heuristic")
        _cand(store, "c1", "tropical|b||2", model_proposed=True,
              confidence_class="strong_heuristic")
        _cand(store, "c2", "tropical|c||3", sensitive_high_impact=True)
        report = IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        assert report["summary"]["families_written"] == 0
        assert store.count_project_issue_history_items() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_activity_resolution_and_status_normalization() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|rfis||100")
        # messy dict-string status from Procore must normalize to a bounded token.
        _live(db, "rfis", "100", "{'id': 20577, 'name': 'Open', 'mapped_to_status': 'open'}",
              "2026-05-20T00:00:00Z")
        IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_project_issue_history_items()[0]
        assert it["status"] == "open"
        assert it["latest_activity_utc"] == "2026-05-20T00:00:00Z"
        assert it["age_days"] == 12  # 2026-06-01 - 2026-05-20
        assert it["stale_unknown_flags_json"] is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_unresolved_anchor_flags_stale_unknown() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|rfis||404")  # no matching live record
        IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        it = store.list_project_issue_history_items()[0]
        assert it["latest_activity_utc"] is None
        assert it["status"] == "unknown"
        assert it["age_days"] == 0
        assert it["stale_unknown_flags_json"]["no_source_activity_timestamp"] is True
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content_or_status_payload() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|rfis||100")
        _live(db, "rfis", "100", "{'id': 20577, 'name': 'Open', 'mapped_to_status': 'open'}",
              "2026-05-20T00:00:00Z")
        IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        blob = json.dumps(store.list_project_issue_history_items(), default=str)
        assert _LEAK.search(blob) is None
        # the raw Procore status dict-string must not be persisted verbatim
        assert "mapped_to_status" not in blob and "'name'" not in blob
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_apply() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|rfis||100")
        _cand(store, "c1", "tropical|change-orders||9", confidence_class="strong_heuristic")
        builder = IssueHistoryBuilder(store)
        builder.build(dry_run=False, now_utc=_NOW)
        builder.build(dry_run=False, now_utc=_NOW)
        assert store.count_project_issue_history_items() == 2
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_dry_run_writes_nothing() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|rfis||100")
        report = IssueHistoryBuilder(store).build(dry_run=True, now_utc=_NOW)
        assert report["mode"] == "dry_run"
        assert report["summary"]["families_planned"] == 1
        assert report["summary"]["families_written"] == 0
        assert store.count_project_issue_history_items() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _cand(store, "c0", "tropical|rfis||100")
        _cand(store, "c1", "tropical|change-orders||9", confidence_class="strong_heuristic")
        IssueHistoryBuilder(store).build(dry_run=False, now_utc=_NOW)
        status = project_issue_history_status(store)
        assert status["ok"] is True
        assert status["summary"]["items"] == 2
        assert status["summary"]["review_required"] == 1
        assert status["summary"]["by_confidence_class"] == {
            "deterministic": 1, "strong_heuristic": 1
        }
    finally:
        Path(db).unlink(missing_ok=True)
