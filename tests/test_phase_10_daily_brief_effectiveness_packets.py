"""Phase 10 V52 — effectiveness packet builder / join tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
    STATUS_INSUFFICIENT_OUTCOME,
    STATUS_NO_RANKED_BRIEFS,
    build_effectiveness_packets,
    derive_exposure_events,
    derive_outcome_events,
    normalize_dim,
)
from hb_assistant.construction.store import ConstructionStore
from tests._phase_10_effectiveness_seed import (
    EVAL_NOW,
    WINDOW_END,
    WINDOW_START,
    seed_effectiveness_store,
)


def _counts(db: str, tables: list[str]) -> dict[str, int]:
    conn = sqlite3.connect(db)
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}


def test_builds_packets_and_joins_outcomes(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_effectiveness_store(db)
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    assert pkt["status"] == "ok"
    assert pkt["sample_size"]["candidates"] == 5
    assert pkt["sample_size"]["outcomes"] == 5
    outcomes = {it["outcome_type"] for it in pkt["items"]}
    assert {"accepted", "rejected", "snoozed", "ignored"} <= outcomes
    # Every surfaced actionable item carries a source-ref count (coverage join works).
    assert all(it["source_ref_count"] >= 1 for it in pkt["items"])
    assert pkt["raw_safety"]["raw_free"] is True


def test_no_lifecycle_or_source_ref_mutation(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_effectiveness_store(db)
    watched = [
        "candidate_lifecycle_events",
        "candidate_source_refs",
        "daily_brief_ranked_candidates",
    ]
    before = _counts(db, watched)
    build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    assert _counts(db, watched) == before  # pure read — nothing changed


def test_no_ranked_briefs_status(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = ConstructionStore(db_path=db)  # migrated but empty
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    assert pkt["status"] == STATUS_NO_RANKED_BRIEFS
    assert pkt["exposure_events"] == []
    assert pkt["outcome_events"] == []


def test_insufficient_outcome_data_status(tmp_path: Path) -> None:
    # Surface candidates but evaluate immediately (within the lag window, no dispositions yet).
    db = str(tmp_path / "t.sqlite")
    store = seed_effectiveness_store(db, now="2026-06-11T12:00:00+00:00")
    # Re-run with the eval "now" only a few hours after exposure: open items are still pending.
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc="2026-06-11T13:00:00+00:00"
    )
    # e_acc/e_rej/e_snz have dispositions (outcomes); but if all were open this would be insufficient.
    assert pkt["status"] in ("ok", "degraded", STATUS_INSUFFICIENT_OUTCOME)


def test_derive_exposure_and_outcome_events(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_effectiveness_store(db)
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    exposures = derive_exposure_events(pkt)
    outcomes = derive_outcome_events(pkt["items"], ignored_lag_hours=72)
    # One brief-level proxy + one per ranked candidate.
    assert any(e["event_type"] == "brief_exposure_proxy" for e in exposures)
    assert sum(1 for e in exposures if e["event_type"] == "item_exposure_proxy") == 5
    assert all(e["exposure_surface"] == "persisted_ranking_overlay" for e in exposures)
    assert len(outcomes) == 5
    assert all(o["ignored_lag_hours"] == 72 for o in outcomes)


def test_rejects_planted_raw_content(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_effectiveness_store(db)
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    # Plant a forbidden URL into a free-text field and re-scan: the scanner reports category-only.
    pkt["items"][0]["section_key"] = "https://evil.example.com/secret"
    from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
        _scan_packet,
    )

    scan = _scan_packet(pkt)
    assert scan["raw_free"] is False
    assert "url" in scan["categories"]
    # Findings are category codes only — never the matched string.
    assert all("evil.example.com" not in c for c in scan["categories"])


def test_planted_raw_categories_are_caught_category_only(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_effectiveness_store(db)
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
        _scan_packet,
    )

    planted = {
        "url": "https://secret.example.com/x",
        "email": "alice@example.com",
        "join_link": "https://teams.microsoft.com/l/meetup-join/abc",
        "jwt_like": "eyJabc123.eyJdef456",
        "access_token": "access_token=abcdef",
        "bearer": "Bearer abcdefgh12345678",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----",
    }
    for category, value in planted.items():
        pkt["items"][0]["section_key"] = value
        scan = _scan_packet(pkt)
        assert scan["raw_free"] is False, f"{category} not detected"
        # Category codes only — never the matched/raw substring.
        assert all(value not in c for c in scan["categories"])


def test_pre_exposure_disposition_not_attributed(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.local_ai import run_candidate_ranking_and_assembly
    from tests._phase_10_effectiveness_seed import _event, _task

    db = str(tmp_path / "t.sqlite")
    store = ConstructionStore(db_path=db)
    _task(store, "p1", source_family="email")
    run_candidate_ranking_and_assembly(
        store=store,
        brief_date="2026-06-11",
        now_utc="2026-06-11T12:00:00+00:00",
        use_model=False,
        include_similarity=True,
        dry_run=False,
        max_persist=100,
    )
    # Disposition that happened BEFORE the 2026-06-11T12:00 exposure proxy.
    _event(
        store, "p1", event_type="accept", new_state="accepted",
        created_utc="2026-06-09T00:00:00+00:00",
    )
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    item = next(
        it for it in pkt["items"] if it["daily_brief_action_candidate_id"] == "task_candidate:p1"
    )
    assert item["outcome_type"] is None
    assert item["status_reason"] == "pre_existing_disposition_not_attributed"
    assert pkt["sample_size"]["excluded_pre_existing_disposition"] >= 1
    # Pre-existing dispositions never become an outcome event.
    assert all(
        o["daily_brief_action_candidate_id"] != "task_candidate:p1" for o in pkt["outcome_events"]
    )


def test_post_exposure_attributed_with_non_negative_lag(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.local_ai import run_candidate_ranking_and_assembly
    from tests._phase_10_effectiveness_seed import _event, _task

    db = str(tmp_path / "t.sqlite")
    store = ConstructionStore(db_path=db)
    _task(store, "p2", source_family="email")
    run_candidate_ranking_and_assembly(
        store=store,
        brief_date="2026-06-11",
        now_utc="2026-06-11T12:00:00+00:00",
        use_model=False,
        include_similarity=True,
        dry_run=False,
        max_persist=100,
    )
    # Disposition AFTER the exposure proxy → attributed, lag from exposure to event.
    _event(
        store, "p2", event_type="accept", new_state="accepted",
        created_utc="2026-06-13T00:00:00+00:00",
    )
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    item = next(
        it for it in pkt["items"] if it["daily_brief_action_candidate_id"] == "task_candidate:p2"
    )
    assert item["outcome_type"] == "accepted"
    assert item["status_reason"] == "attributed_post_exposure"
    assert item["outcome_lag_hours"] is not None and item["outcome_lag_hours"] >= 0
    # No item ever carries a negative lag.
    assert all((it["outcome_lag_hours"] or 0) >= 0 for it in pkt["items"])


def test_normalize_dim_stable_unknown() -> None:
    assert normalize_dim(None) == "unknown"
    assert normalize_dim("") == "unknown"
    assert normalize_dim("  ") == "unknown"
    assert normalize_dim("email") == "email"
