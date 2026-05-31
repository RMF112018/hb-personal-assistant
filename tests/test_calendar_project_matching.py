"""Phase 07B Prompt 05 — calendar event → project matching.

Proves deterministic project-number matching (over the full-number hash stored by
P04), heuristic project-name-token matching (moderate/weak, review-required),
conflicting-signal review routing, no auto-promotion (candidates only; the event
index is never written), dry-run/apply gating, idempotency, and that no raw
project number / subject / email appears in persisted candidates or signals_json.
"""

from __future__ import annotations

import json
import sqlite3
import types
from pathlib import Path

from hb_assistant.construction.calendar.project_matcher import CalendarProjectMatcher
from hb_assistant.construction.config.models import ProjectIdentity
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

_NUMBER = "23-435-01"


def _registry() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        projects=[
            ProjectIdentity(
                project_key="tropical-plaza", display_name="Tropical Plaza", project_number=_NUMBER
            ),
            ProjectIdentity(
                project_key="banyan-tower", display_name="Banyan Tower", project_number="24-100-02"
            ),
        ]
    )


def _tokens(*words: str, number: str | None = None) -> str:
    hashes = {hash_value(w.lower()) for w in words}
    if number:
        hashes.add(hash_value(number))
    return json.dumps(sorted(h for h in hashes if h))


def _store_with_events(tmp_path: Path) -> tuple[ConstructionStore, str]:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    store.upsert_calendar_source_location(source_id="primary_calendar", mailbox_owner_hash="owner")

    def ev(eid: str, g: str, thj: str | None, *, priv: bool = False, rev: bool = False) -> None:
        store.upsert_calendar_event_index(
            event_index_id=eid,
            source_id="primary_calendar",
            graph_event_id_hash=g,
            start_datetime_utc="2026-06-01T00:00:00Z",
            end_datetime_utc="2026-06-01T01:00:00Z",
            subject_token_hashes_json=thj,
            is_private=priv,
            review_required=rev,
        )

    ev("EVDET", "g1", _tokens("walk", "site", number=_NUMBER))
    ev("EVNAME2", "g2", _tokens("tropical", "plaza", "sync"))
    ev("EVNAME1", "g3", _tokens("banyan", "meeting"))
    ev("EVCONF", "g4", _tokens("tropical", "plaza", "banyan", "tower"))
    ev("EVPRIV", "g5", None, priv=True, rev=True)
    ev("EVNONE", "g6", _tokens("standup", "coffee"))
    return store, db


def test_dry_run_persists_no_candidates(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    report = CalendarProjectMatcher(store, registry=_registry()).match(dry_run=True)
    assert report.summary["candidates_created"] == 5
    assert report.summary["deterministic"] == 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM calendar_project_match_candidates").fetchone()[0] == 0


def test_apply_persists_with_confidence_and_review(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    CalendarProjectMatcher(store, registry=_registry()).match(dry_run=False)
    conn = sqlite3.connect(db)
    det = conn.execute(
        "SELECT candidate_type, confidence_class, confidence, deterministic, review_required,"
        " promotion_status FROM calendar_project_match_candidates WHERE event_index_id='EVDET'"
    ).fetchone()
    assert det == ("project_number", "deterministic", 0.95, 1, 0, "candidate")
    assert conn.execute(
        "SELECT confidence_class, review_required FROM calendar_project_match_candidates"
        " WHERE event_index_id='EVNAME2'"
    ).fetchone() == ("moderate", 1)
    assert conn.execute(
        "SELECT confidence_class, review_required FROM calendar_project_match_candidates"
        " WHERE event_index_id='EVNAME1'"
    ).fetchone() == ("weak", 1)


def test_conflicting_signals_route_all_to_review(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    CalendarProjectMatcher(store, registry=_registry()).match(dry_run=False)
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT review_required, signals_json FROM calendar_project_match_candidates"
        " WHERE event_index_id='EVCONF'"
    ).fetchall()
    assert len(rows) >= 2
    assert all(r[0] == 1 for r in rows)
    assert all(json.loads(r[1])["conflicting"] is True for r in rows)


def test_private_and_unmatched_produce_no_candidate(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    report = CalendarProjectMatcher(store, registry=_registry()).match(dry_run=False)
    conn = sqlite3.connect(db)
    for eid in ("EVPRIV", "EVNONE"):
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM calendar_project_match_candidates WHERE event_index_id=?",
                (eid,),
            ).fetchone()[0]
            == 0
        )
    assert report.summary["events_unmatched"] == 1  # EVNONE (private not counted)


def test_no_auto_promotion(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    CalendarProjectMatcher(store, registry=_registry()).match(dry_run=False)
    conn = sqlite3.connect(db)
    # The event index project_key is never written by matching.
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM calendar_event_index WHERE project_key IS NOT NULL"
        ).fetchone()[0]
        == 0
    )
    # Every candidate stays a candidate.
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM calendar_project_match_candidates"
            " WHERE promotion_status != 'candidate'"
        ).fetchone()[0]
        == 0
    )


def test_no_raw_values_and_guardrail_columns(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    CalendarProjectMatcher(store, registry=_registry()).match(dry_run=False)
    conn = sqlite3.connect(db)
    signals = " ".join(
        r[0] for r in conn.execute("SELECT signals_json FROM calendar_project_match_candidates")
    )
    # Raw project number never persisted; only its hash is present in matched tokens.
    assert _NUMBER not in signals
    assert hash_value(_NUMBER) in signals
    # CHECK guardrail columns remain 0.
    assert conn.execute(
        "SELECT SUM(raw_body_persisted), SUM(external_writeback_performed)"
        " FROM calendar_project_match_candidates"
    ).fetchone() == (0, 0)


def test_apply_is_idempotent(tmp_path: Path) -> None:
    store, db = _store_with_events(tmp_path)
    matcher = CalendarProjectMatcher(store, registry=_registry())
    matcher.match(dry_run=False)
    conn = sqlite3.connect(db)
    n1 = conn.execute("SELECT COUNT(*) FROM calendar_project_match_candidates").fetchone()[0]
    matcher.match(dry_run=False)
    n2 = conn.execute("SELECT COUNT(*) FROM calendar_project_match_candidates").fetchone()[0]
    assert n1 == n2 == 5
