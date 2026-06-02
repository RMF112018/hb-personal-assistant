"""Phase 07D Prompt 06 — meeting-prep brief materialization (V25).

Covers success, prerequisite-blocked, review-required, deferred-section, no-raw-content,
idempotency, and dry-run-writes-nothing paths over the two V25 brief tables.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hb_assistant.construction.meeting_prep import (
    MeetingPrepBriefBuilder,
    meeting_prep_brief_status,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator

_LEAK = re.compile(
    r"https?://|@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|BEGIN:V|-----BEGIN|Bearer |eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}", re.IGNORECASE
)
_READY = {"ready": True, "blocked_by": [], "auto_readiness_allowed": False}
_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_GUARDS = (
    "raw_email_body_persisted", "raw_document_text_persisted",
    "raw_calendar_payload_persisted", "raw_prompt_persisted", "raw_response_persisted",
    "signed_url_persisted", "download_url_persisted", "external_writeback_performed",
)


def _fresh_db() -> str:
    fd, db = tempfile.mkstemp(suffix=".sqlite", prefix="test_mpbrief_")
    os.close(fd)
    SQLiteMigrator(db_path=db).apply()
    return db


def _seed_candidate(store: ConstructionStore, cid: str, **over: object) -> None:
    kw: dict = {
        "candidate_id": cid,
        "source_family": "document",
        "source_record_type": "document_card",
        "source_record_ref": "card:" + cid,
        "target_family": "procore",
        "target_record_type": "procore_rfi",
        "target_record_ref": "rfi:" + cid,
        "relationship_type": "references",
        "confidence_score": 1.0,
        "confidence_class": "deterministic",
        "source_reference_json": json.dumps({"s": cid}),
        "deterministic": True,
        "review_required": False,
        "project_key": "tropical",
        "evidence_trail_id": "et_" + cid,
    }
    kw.update(over)
    store.upsert_cross_source_relationship_candidate(**kw)  # type: ignore[arg-type]
    store.upsert_source_evidence_trail(
        evidence_trail_id="et_" + cid, evidence_kind="cross_source_relationship",
        source_refs_json=json.dumps({"refs": [cid]}), confidence_class="deterministic",
        project_key="tropical",
    )


def _seed_promoted(store: ConstructionStore, rid: str) -> None:
    store.upsert_cross_source_relationship(
        relationship_id=rid, source_family="procore", source_record_type="rfi",
        source_record_ref="rfi:" + rid, target_family="procore", target_record_type="submittal",
        target_record_ref="sub:" + rid, relationship_type="references",
        confidence_class="deterministic", source_reference_json=json.dumps({"r": rid}),
        project_key="tropical", evidence_trail_id="et_" + rid,
    )


def _seed_event(db: str, eid: str, *, days: int, project_key: str | None) -> None:
    """Seed a calendar event via a raw FK-off connection (mirrors the substrate tests)."""
    start = (_NOW + timedelta(days=days)).isoformat()
    end = (_NOW + timedelta(days=days, hours=1)).isoformat()
    raw = sqlite3.connect(db)
    try:
        raw.execute(
            "INSERT INTO calendar_event_index "
            "(event_index_id, source_id, graph_event_id_hash, start_datetime_utc, "
            " end_datetime_utc, organizer_domain, project_key, project_match_method) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                eid, "cal", "h_" + eid, start, end, "hedrickbrothers.com", project_key,
                "deterministic" if project_key else None,
            ),
        )
        raw.commit()
    finally:
        raw.close()


def _sections(store: ConstructionStore) -> dict[str, dict]:
    return {s["section_kind"]: s for s in store.list_meeting_prep_brief_sections()}


def _assert_guards_zero(db: str) -> None:
    raw = sqlite3.connect(db)
    try:
        cols = ", ".join(_GUARDS)
        for table in ("meeting_prep_brief_runs", "meeting_prep_brief_sections"):
            for row in raw.execute(f"SELECT {cols} FROM {table}"):
                assert set(row) <= {0}, f"{table} has a non-zero guard column"
    finally:
        raw.close()


# ---------------------------------------------------------------------------


def test_success_materializes_all_eight_sections() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        _seed_candidate(store, "c1")
        _seed_promoted(store, "r0")
        _seed_event(db, "ev_match", days=3, project_key="tropical")
        _seed_event(db, "ev_other", days=4, project_key=None)
        report = MeetingPrepBriefBuilder(store).build(
            dry_run=False, readiness=_READY, now_utc=_NOW
        )
        assert report["ok"] is True
        assert report["summary"]["blocked"] is False
        assert report["summary"]["runs_written"] == 1
        assert report["summary"]["sections_written"] == 8
        secs = _sections(store)
        assert set(secs.keys()) == {
            "meeting_context", "project_context", "open_items", "aging_items",
            "recent_activity", "risk_exposure_watchlist", "review_required_warnings",
            "confidence_and_stale_unknown_warnings",
        }
        mc = json.loads(secs["meeting_context"]["section_redacted"])
        assert mc["project_matched_meetings"] == 1
        assert mc["unmatched_upcoming_meetings"] == 1
        ra = json.loads(secs["recent_activity"]["section_redacted"])
        assert ra["promoted_relationships"] == 1
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_prerequisite_block_writes_no_sections() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        # No readiness injection -> gates evaluated on a fresh DB -> not ready -> blocked.
        report = MeetingPrepBriefBuilder(store).build(dry_run=False, now_utc=_NOW)
        assert report["ok"] is True
        assert report["summary"]["blocked"] is True
        assert report["summary"]["sections_written"] == 0
        runs = store.list_meeting_prep_brief_runs()
        assert len(runs) == 1
        assert runs[0]["status"] == "blocked"
        assert store.count_meeting_prep_brief_sections() == 0
        assert report["prerequisite_readiness"]["ready"] is False
    finally:
        Path(db).unlink(missing_ok=True)


def test_review_required_surfaced() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0", review_required=True)
        report = MeetingPrepBriefBuilder(store).build(
            dry_run=False, readiness=_READY, now_utc=_NOW
        )
        secs = _sections(store)
        rr = secs["review_required_warnings"]
        assert rr["review_required"] is True
        assert json.loads(rr["section_redacted"])["review_required_count"] == 1
        run = store.list_meeting_prep_brief_runs()[0]
        assert run["review_required_count"] >= 1
        assert report["summary"]["review_required"] >= 1
    finally:
        Path(db).unlink(missing_ok=True)


def test_deferred_sections_are_honest_placeholders() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        MeetingPrepBriefBuilder(store).build(dry_run=False, readiness=_READY, now_utc=_NOW)
        secs = _sections(store)
        for kind, table in (
            ("aging_items", "project_issue_history_items"),
            ("risk_exposure_watchlist", "project_risk_digest_items"),
        ):
            payload = json.loads(secs[kind]["section_redacted"])
            assert payload["available"] is False
            assert payload["deferred_source"] == table
            assert secs[kind]["confidence_class"] == "stale_or_unresolved"
            flags = secs[kind]["stale_unknown_flags_json"]
            assert flags is not None and flags["deferred_source"] == table
    finally:
        Path(db).unlink(missing_ok=True)


def test_no_raw_content_in_brief() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        _seed_promoted(store, "r0")
        _seed_event(db, "ev_match", days=2, project_key="tropical")
        MeetingPrepBriefBuilder(store).build(dry_run=False, readiness=_READY, now_utc=_NOW)
        blob = json.dumps(
            store.list_meeting_prep_brief_runs() + store.list_meeting_prep_brief_sections(),
            default=str,
        )
        assert _LEAK.search(blob) is None
    finally:
        Path(db).unlink(missing_ok=True)


def test_idempotent_apply() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        builder = MeetingPrepBriefBuilder(store)
        builder.build(dry_run=False, readiness=_READY, now_utc=_NOW)
        builder.build(dry_run=False, readiness=_READY, now_utc=_NOW)
        assert store.count_meeting_prep_brief_runs() == 1
        assert store.count_meeting_prep_brief_sections() == 8
        _assert_guards_zero(db)
    finally:
        Path(db).unlink(missing_ok=True)


def test_dry_run_writes_nothing_but_plans() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        report = MeetingPrepBriefBuilder(store).build(
            dry_run=True, readiness=_READY, now_utc=_NOW
        )
        assert report["mode"] == "dry_run"
        assert report["summary"]["sections_planned"] == 8
        assert report["summary"]["sections_written"] == 0
        assert store.count_meeting_prep_brief_runs() == 0
        assert store.count_meeting_prep_brief_sections() == 0
    finally:
        Path(db).unlink(missing_ok=True)


def test_status_reports_coverage() -> None:
    db = _fresh_db()
    try:
        store = ConstructionStore(db_path=db)
        _seed_candidate(store, "c0")
        MeetingPrepBriefBuilder(store).build(dry_run=False, readiness=_READY, now_utc=_NOW)
        status = meeting_prep_brief_status(store)
        assert status["ok"] is True
        assert status["summary"]["runs"] == 1
        assert status["summary"]["materialized_runs"] == 1
        assert status["summary"]["sections"] == 8
        assert len(status["summary"]["by_section_kind"]) == 8
    finally:
        Path(db).unlink(missing_ok=True)
