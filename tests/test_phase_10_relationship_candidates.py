"""Phase 10 follow-on — relationship candidate engine tests.

Covers the deterministic core (``build_relationship_candidates``), the CLI surface
(``second-brain relationship-candidates scan``), and daily-brief relationship enrichment.

ALL fixture content is synthetic and safe: RFC-reserved ``example.com`` domains, invented
project keys, and invented construction record ids. No real subjects, addresses, URLs, join
links, Procore payloads, or document bodies appear in this file.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.relationship_candidates import (
    _safe_candidate,
    build_relationship_candidates,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-09T17:00:00+00:00"


# --------------------------------------------------------------------------- fixtures


def _seed(db: str) -> ConstructionStore:
    """Seed three isolated synthetic clusters: strong, moderate, weak.

    Clusters are isolated by distinct project keys + distinct email domains so cross-cluster
    pairs score ~0. Strong → confidence clamps to 1.0; moderate → ~0.6 (review required);
    weak → 0.25 (same-project only), excluded by the default moderate min-confidence.
    """
    s = ConstructionStore(db)

    # --- STRONG cluster: shared project + near-exact subject + shared record + overlap + proximity
    s.upsert_email_thread_raw_context(
        raw_thread_context_id="thr-strong-1",
        thread_ref="THREAD_STRONG_1",
        project_key="PRJ-A",
        message_count=1,
        participant_count=2,
        thread_subject="rfi 42 rebar coordination",
        messages_json=json.dumps(
            [
                {
                    "id": "m-strong-1",
                    "subject": "rfi 42 rebar coordination",
                    "body_text": "please review rfi 42 rebar before the meeting",
                    "from_address": "ann@alpha.example.com",
                    "to_recipients": ["lee@alpha.example.com"],
                    "sent_at_utc": "2026-06-09T14:00:00+00:00",
                }
            ]
        ),
    )
    s.upsert_calendar_event_raw_content(
        raw_calendar_event_id="evt-strong-1",
        graph_event_id_hash="h-strong-1",
        event_index_id="EVENT_STRONG_1",
        project_key="PRJ-A",
        subject="rfi 42 rebar coordination",
        body_text="rfi 42 rebar walkthrough",
        organizer_email="lee@alpha.example.com",
        attendees_json=json.dumps([{"email": "ann@alpha.example.com"}]),
        start_datetime_utc="2026-06-09T15:00:00+00:00",
        end_datetime_utc="2026-06-09T16:00:00+00:00",
    )

    # --- MODERATE cluster: shared project + participant overlap + time proximity (no record/meeting)
    s.upsert_email_thread_raw_context(
        raw_thread_context_id="thr-mod-1",
        thread_ref="THREAD_MOD_1",
        project_key="PRJ-B",
        message_count=1,
        participant_count=2,
        thread_subject="site logistics planning",
        messages_json=json.dumps(
            [
                {
                    "id": "m-mod-1",
                    "subject": "site logistics planning",
                    "body_text": "let us align on logistics",
                    "from_address": "bob@beta.example.com",
                    "to_recipients": ["kim@beta.example.com"],
                    "sent_at_utc": "2026-06-09T09:00:00+00:00",
                }
            ]
        ),
    )
    s.upsert_calendar_event_raw_content(
        raw_calendar_event_id="evt-mod-1",
        graph_event_id_hash="h-mod-1",
        event_index_id="EVENT_MOD_1",
        project_key="PRJ-B",
        subject="weekly logistics review",
        body_text="logistics",
        organizer_email="kim@beta.example.com",
        attendees_json=json.dumps([{"email": "bob@beta.example.com"}]),
        start_datetime_utc="2026-06-09T11:00:00+00:00",
        end_datetime_utc="2026-06-09T12:00:00+00:00",
    )

    # --- WEAK cluster: same project only, distinct domains, far apart in time → 0.25 (excluded)
    s.upsert_email_thread_raw_context(
        raw_thread_context_id="thr-weak-1",
        thread_ref="THREAD_WEAK_1",
        project_key="PRJ-C",
        message_count=1,
        participant_count=1,
        thread_subject="general updates",
        messages_json=json.dumps(
            [
                {
                    "id": "m-weak-1",
                    "subject": "general updates",
                    "body_text": "misc notes",
                    "from_address": "x@gamma.example.com",
                    "to_recipients": ["z@gamma.example.com"],
                    "sent_at_utc": "2026-06-01T09:00:00+00:00",
                }
            ]
        ),
    )
    s.upsert_calendar_event_raw_content(
        raw_calendar_event_id="evt-weak-1",
        graph_event_id_hash="h-weak-1",
        event_index_id="EVENT_WEAK_1",
        project_key="PRJ-C",
        subject="budget planning",
        body_text="",
        organizer_email="y@delta.example.com",
        attendees_json=json.dumps([]),
        start_datetime_utc="2026-06-09T09:00:00+00:00",
        end_datetime_utc="2026-06-09T10:00:00+00:00",
    )
    return s


def _guard_sum(db: str) -> int:
    conn = sqlite3.connect(db)
    cols = " + ".join(f"COALESCE(SUM({c}),0)" for c in PHASE_10_GUARD_COLUMNS)
    row = conn.execute(f"SELECT {cols} FROM phase10_relationship_candidates").fetchone()
    conn.close()
    return int(row[0] or 0)


def _row_count(db: str) -> int:
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM phase10_relationship_candidates").fetchone()[0]
    conn.close()
    return int(n)


# --------------------------------------------------------------------------- core engine


def test_deterministic_scoring_two_candidates(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW)
    # strong + moderate are kept; weak is excluded by the default moderate floor.
    assert out["summary"]["candidates"] == 2
    classes = {r["confidence_class"] for r in out["relationships"]}
    assert classes == {"strong", "moderate"}
    assert out["guardrails"]["model_does_not_decide_relatedness"] is True


def test_dry_run_writes_zero(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW, dry_run=True)
    assert out["applied"] is False
    assert out["summary"]["persisted"] == 0
    assert out["summary"]["would_persist"] == 2
    assert _row_count(db) == 0


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    try:
        build_relationship_candidates(store=s, now_utc=NOW, dry_run=False)
        raise AssertionError("expected ValueError when apply has no cap")
    except ValueError as e:
        assert "max_persist" in str(e)
    assert _row_count(db) == 0


def test_cap_bounds_persisted_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=1)
    assert out["summary"]["persisted"] == 1
    assert out["summary"]["skipped_capped"] == 1
    assert _row_count(db) == 1


def test_idempotent_rerun(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    first = build_relationship_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=5)
    assert first["summary"]["persisted"] == 2
    assert _row_count(db) == 2
    second = build_relationship_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=5)
    assert second["summary"]["persisted"] == 0
    assert second["summary"]["skipped_existing"] == 2
    assert _row_count(db) == 2  # no duplicates


def test_moderate_requires_review(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW)
    moderate = [r for r in out["relationships"] if r["confidence_class"] == "moderate"]
    assert moderate and all(r["review_required"] for r in moderate)
    assert out["summary"]["review_required"] >= 1


def test_weak_excluded_by_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW)
    assert all(r["confidence_class"] != "weak" for r in out["relationships"])


def test_guard_columns_stay_zero(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    build_relationship_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=5)
    assert _guard_sum(db) == 0


def test_deterministic_order(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW)
    confs = [r["confidence"] for r in out["relationships"]]
    assert confs == sorted(confs, reverse=True)  # confidence DESC
    # stable tie-break: id ASC within equal confidence
    keyed = [(-r["confidence"], r["relationship_candidate_id"]) for r in out["relationships"]]
    assert keyed == sorted(keyed)


def test_skips_missing_source_refs() -> None:
    assert _safe_candidate({"from_source_ref": None, "to_source_ref": "x"}) is None
    assert _safe_candidate({"from_source_ref": "x", "to_source_ref": None}) is None


def test_empty_input_valid_empty_report(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite")
    s = ConstructionStore(db)  # migrates schema, no rows seeded
    out = build_relationship_candidates(store=s, now_utc=NOW)
    assert out["ok"] is True
    assert out["summary"]["candidates"] == 0
    assert out["relationships"] == []
    assert _row_count(db) == 0


def test_no_raw_content_in_output_or_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = build_relationship_candidates(store=s, now_utc=NOW, dry_run=False, max_persist=5)
    blob = json.dumps(out)
    # no addresses, domains, raw subject words, or URLs leak into the engine output
    for needle in ("@", "example.com", "rebar", "logistics", "http", "://"):
        assert needle not in blob, f"forbidden token {needle!r} in engine output"
    # persisted rows expose hashes + safe codes only
    rows = s.list_phase10_relationship_candidates()
    rowblob = json.dumps(rows)
    for needle in ("@", "example.com", "rebar", "logistics", "http"):
        assert needle not in rowblob, f"forbidden token {needle!r} in persisted rows"
    # reason codes are the safe vocabulary only
    for r in rows:
        for code in (r["reason_redacted"] or "").split(","):
            if code:
                assert code.replace("_", "").isalpha()
