"""Phase 10 — deterministic daily-brief candidate projection + source-ref linking (usefulness repair).

Proves the central writer (daily_brief_candidate_writer) persists action candidates AND their hashed
source refs for both calendar and Procore stages, that source-ref coverage is non-zero (the audit's
0.0 gap), idempotency holds on repeated apply, refs are hash-only (no raw), and empty sources degrade
gracefully.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import (
    build_calendar_prep_candidates,
    build_procore_action_digest,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer import (
    CANDIDATE_TYPE,
    candidate_source_ref_coverage,
    persist_candidate_with_refs,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-08T00:00:00+00:00"
BRIEF_DATE = "2026-06-08"

_PROCORE_COLS = (
    "action_signal_id, project_key, record_key, endpoint_id, signal_type, signal_status, "
    "importance, due_at_utc, owner_entity_key, title_redacted, summary_redacted, "
    "reason_codes_json, first_detected_at_utc, last_seen_at_utc, resolved_at_utc, "
    "source_change_event_id, metadata_json"
)


def _seed_calendar(db: str) -> ConstructionStore:
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO calendar_event_index
            (event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc,
             subject_redacted, location_redacted, organizer_domain, is_online_meeting,
             online_meeting_provider, is_cancelled, is_private, project_key)
        VALUES ('e1','src1','gh1','2026-06-09T15:00:00+00:00','2026-06-09T16:00:00+00:00',
                'TWN OAC','[redacted-loc]','hbcompany.com',0,NULL,0,0,NULL)
        """
    )
    conn.execute(
        """
        INSERT INTO calendar_event_raw_content
            (raw_calendar_event_id, event_index_id, graph_event_id_hash, subject, body_html,
             join_url, online_meeting_provider, attendees_json, start_datetime_utc,
             end_datetime_utc, project_key)
        VALUES ('raw-e1','e1','gh1','TWN OAC','<p>agenda</p>',NULL,NULL,'[]',
                '2026-06-09T15:00:00+00:00','2026-06-09T16:00:00+00:00',NULL)
        """
    )
    conn.commit()
    conn.close()
    return s


def _seed_procore(db: str) -> ConstructionStore:
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    conn.execute(
        f"INSERT INTO procore_action_signals ({_PROCORE_COLS}) VALUES "
        f"({', '.join(['?'] * 17)})",
        (
            "sig1", "tropical", "tropical|ep||sig1", "ep", "inspection_overdue", "open", "high",
            "2026-06-01T00:00:00+00:00", "owner-hash", "t", "sm", "[]",
            "2026-05-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00", None, None, "{}",
        ),
    )
    conn.commit()
    conn.close()
    return s


# --- calendar projection -------------------------------------------------------


def test_calendar_apply_persists_candidate_and_source_refs(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    out = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10
    )
    assert out["summary"]["persisted"] == 1
    cands = s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE, section="calendar")
    assert len(cands) == 1
    assert cands[0]["project_key"] == "tropical"  # category resolution wired in
    cid = cands[0]["daily_brief_action_candidate_id"]
    refs = s.list_candidate_source_refs(candidate_type=CANDIDATE_TYPE, candidate_id=cid)
    assert len(refs) == 1
    assert refs[0]["source_family"] == "calendar_event_raw_content"
    # hash-only: the source ref hash is not the raw cal: ref
    assert refs[0]["source_ref_hash"] and not refs[0]["source_ref_hash"].startswith("cal:")


def test_calendar_coverage_is_full_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    cov = candidate_source_ref_coverage(s, brief_date=BRIEF_DATE, section="calendar")
    assert cov["total_candidates"] == 1
    assert cov["coverage"] == 1.0
    assert cov["uncovered_candidate_ids"] == []


# --- procore projection --------------------------------------------------------


def test_procore_apply_persists_candidate_and_source_refs(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_procore(db)
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    assert out["summary"]["persisted"] == 1
    cands = s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE, section="procore")
    assert len(cands) == 1
    cid = cands[0]["daily_brief_action_candidate_id"]
    refs = s.list_candidate_source_refs(candidate_type=CANDIDATE_TYPE, candidate_id=cid)
    assert len(refs) == 1
    assert refs[0]["source_family"] == "procore_action_signals"


# --- writer contract -----------------------------------------------------------


def test_writer_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    kwargs: dict = {
        "brief_date": BRIEF_DATE,
        "section": "calendar",
        "title_redacted": "Meeting",
        "confidence": 0.9,
        "group_key": "cal:abc",
        "source_refs": [{"source_family": "calendar_event_raw_content", "source_ref": "cal:abc"}],
    }
    r1 = persist_candidate_with_refs(s, **kwargs)
    r2 = persist_candidate_with_refs(s, **kwargs)
    assert r1.inserted is True and r2.inserted is False
    assert r1.row_id == r2.row_id
    # exactly one candidate, one ref — no duplicates on repeat
    assert len(s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE)) == 1
    assert len(s.list_candidate_source_refs(candidate_type=CANDIDATE_TYPE, candidate_id=r1.row_id)) == 1


def test_empty_source_coverage_is_graceful(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    cov = candidate_source_ref_coverage(s, brief_date=BRIEF_DATE)
    assert cov["total_candidates"] == 0
    assert cov["coverage"] == 1.0  # vacuously full; usefulness gate handles "no candidates" itself


def test_candidate_without_refs_is_uncovered(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    # A row written WITHOUT source refs (e.g. a data-gap warning) lowers executive coverage.
    persist_candidate_with_refs(
        s,
        brief_date=BRIEF_DATE,
        section="calendar",
        title_redacted="Data gap",
        confidence=0.2,
        group_key="gap:1",
        source_refs=[],
    )
    cov = candidate_source_ref_coverage(s, brief_date=BRIEF_DATE)
    assert cov["total_candidates"] == 1
    assert cov["coverage"] == 0.0
    assert len(cov["uncovered_candidate_ids"]) == 1
