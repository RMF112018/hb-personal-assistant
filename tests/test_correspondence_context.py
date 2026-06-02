"""Phase 07D Prompt 10 — review-controlled correspondence context (read-only projection).

Covers success (thread ties to records + meeting), blocked (no relationships), review-required,
no-raw-content, idempotency (deterministic, nothing persisted), and status coverage.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.correspondence import (
    CorrespondenceContextBuilder,
    correspondence_context_status,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}", re.IGNORECASE
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_corrctx_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _thread(store: ConstructionStore, key: str, *, last: str) -> None:
    store.upsert_email_thread_summary(
        thread_key=key, project_key="tropical", message_count=2,
        first_message_datetime="2026-05-01T00:00:00Z", last_message_datetime=last,
        summary_redacted=f"thread: {key} (2 messages)", summary_policy="metadata_only",
    )


def _message(db: str, mid: str, thread_key: str) -> None:
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            "INSERT INTO email_messages "
            "(message_id, thread_key, source_id, extraction_policy, review_required, "
            " full_body_persisted, mailbox_mutation_allowed) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, thread_key, "sx", "metadata_only", 0, 0, 0),
        )
        raw.commit()
    finally:
        raw.close()


def _edge(store: ConstructionStore, cid: str, mid: str, rel: str, tf: str, tt: str, tref: str,
          *, cc: str = "deterministic") -> None:
    store.upsert_cross_source_relationship_candidate(
        candidate_id=cid, source_family="email", source_record_type="email_message",
        source_record_ref=mid, target_family=tf, target_record_type=tt, target_record_ref=tref,
        relationship_type=rel, confidence_score=1.0, confidence_class=cc,
        source_reference_json=json.dumps({"x": cid}), review_required=(cc != "deterministic"),
        project_key="tropical", evidence_trail_id="et_" + cid,
    )


def _meeting_tie(db: str, cid: str, event: str, thread_key: str, *, cc: str = "strong_heuristic",
                 review: int = 0) -> None:
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            "INSERT INTO meeting_email_relationship_candidates "
            "(candidate_id, event_index_id, thread_key_hash, project_key, candidate_type, "
            " source_reference_json, confidence, confidence_class, review_required, "
            " promotion_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cid, event, hash_value(thread_key), "tropical", "time_and_domain", "{}", 0.8, cc,
             review, "candidate"),
        )
        raw.commit()
    finally:
        raw.close()


# ---------------------------------------------------------------------------


def test_success_ties_thread_to_records_and_meeting() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _thread(store, "T1", last="2026-05-28T00:00:00Z")
        _message(db, "m1", "T1")
        _message(db, "m2", "T1")
        _edge(store, "e1", "m1", "procore_notification", "procore", "procore_rfi", "2525840")
        _edge(store, "e2", "m2", "attachment_filename", "project", "sharepoint_drive_item", "docX")
        _edge(store, "e3", "m1", "project_match", "project", "project", "tropical")
        _meeting_tie(db, "me1", "ev99", "T1")
        report = CorrespondenceContextBuilder(store).context(project_filter="tropical")
        assert report["ok"] is True
        assert report["summary"]["threads_linked"] == 1
        assert report["summary"]["project_confirmations"] == 1
        t = report["threads"][0]
        assert t["thread_key"] == "T1"
        assert t["project_confirmed"] is True
        assert set(t["related"].keys()) == {"rfis", "documents", "meetings"}
        assert t["related"]["rfis"][0]["ref"] == "2525840"
        assert t["related"]["meetings"][0]["ref"] == "ev99"
    finally:
        Path(db).unlink(missing_ok=True)


def test_blocked_when_no_relationships() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _thread(store, "T1", last="2026-05-28T00:00:00Z")  # thread but no edges
        report = CorrespondenceContextBuilder(store).context(project_filter="tropical")
        assert report["summary"]["threads_total"] == 1
        assert report["summary"]["threads_linked"] == 0
        assert report["threads"] == []
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_required_from_weak_edge() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _thread(store, "T1", last="2026-05-28T00:00:00Z")
        _message(db, "m1", "T1")
        _edge(store, "e1", "m1", "financial_keyword_in_preview", "procore", "procore_contract",
              "c9", cc="weak_heuristic")
        report = CorrespondenceContextBuilder(store).context(project_filter="tropical")
        t = report["threads"][0]
        assert t["review_required"] is True
        assert t["related"]["commitments"][0]["review_required"] is True
        assert report["summary"]["review_required_threads"] == 1
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _thread(store, "T1", last="2026-05-28T00:00:00Z")
        _message(db, "m1", "T1")
        _edge(store, "e1", "m1", "procore_notification", "procore", "procore_rfi", "2525840")
        _meeting_tie(db, "me1", "ev99", "T1")
        report = CorrespondenceContextBuilder(store).context(project_filter="tropical")
        assert _LEAK.search(json.dumps(report, default=str)) is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_read_only_no_persistence() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _thread(store, "T1", last="2026-05-28T00:00:00Z")
        _message(db, "m1", "T1")
        _edge(store, "e1", "m1", "procore_notification", "procore", "procore_rfi", "2525840")
        builder = CorrespondenceContextBuilder(store)
        r1 = builder.context(project_filter="tropical")
        r2 = builder.context(project_filter="tropical")
        assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
        # read-only: the candidate table is unchanged (only the seeded edge present)
        assert store.count_cross_source_relationship_candidates() == 1
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _thread(store, "T1", last="2026-05-28T00:00:00Z")
        _message(db, "m1", "T1")
        _edge(store, "e1", "m1", "procore_notification", "procore", "procore_rfi", "2525840")
        status = correspondence_context_status(store, project_filter="tropical")
        assert status["ok"] is True
        assert status["summary"]["threads_linked"] == 1
        assert status["summary"]["by_category"]["rfis"] == 1
        assert "threads" not in status  # coverage-only, no per-thread detail
    finally:
        Path(db).unlink(missing_ok=True)
