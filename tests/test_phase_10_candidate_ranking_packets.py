"""Phase 10 V51 — candidate ranking packet builder tests.

Verifies the packet excludes hidden lifecycle states, withholds source-missing actionable subjects,
keeps accepted/review-required items labeled honestly, computes hashes + coverage, and fails closed
on a planted raw leak.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.candidate_ranking_packets import (
    build_candidate_ranking_packet,
)
from hb_assistant.construction.store import ConstructionStore
from tests._phase_10_ranking_seed import (
    BRIEF_DATE,
    NOW,
    accept_task,
    pending_candidate,
    seed_ranking_store,
    snooze_future,
)


def _packet(db: str) -> dict:
    return build_candidate_ranking_packet(
        ConstructionStore(db_path=db), brief_date=BRIEF_DATE, now_utc=NOW
    )


def test_packet_includes_accepted_with_lifecycle_labels(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_ranking_store(db)
    res = _packet(db)
    assert res["status"] == "ok"
    items = res["packet"]["items"]
    assert len(items) == 3
    assert all(it["lifecycle_state"] == "accepted" for it in items)
    assert {it["alias"] for it in items} == {"c1", "c2", "c3"}
    assert res["packet"]["source_ref_coverage"] == 1.0
    assert res["packet"]["packet_guard_clean"] is True


def test_packet_excludes_rejected_and_future_snoozed(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_ranking_store(db)
    pending_candidate(store, "rej", review_status="rejected")
    snooze_future(store, "snz")
    res = _packet(db)
    surfaced = {res["alias_map"][a] for a in res["alias_map"]}
    assert not any("rej" in cid or "snz" in cid for cid in surfaced)
    # the three accepted tasks remain
    assert len(res["packet"]["items"]) == 3


def test_packet_includes_review_required_candidate(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_ranking_store(db)
    pending_candidate(store, "lowconf", review_status="pending", confidence=0.2)
    res = _packet(db)
    states = {it["candidate_id"]: it["lifecycle_state"] for it in res["packet"]["items"]}
    # low-confidence pending candidate is surfaced for review, honestly labeled.
    assert any(v == "needs_review" for v in states.values())


def test_packet_withholds_source_missing_and_degrades_coverage(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = seed_ranking_store(db)
    # An accepted task with NO source refs must lower coverage (accepted-missing-source).
    accept_task(store, "noref", waiting="unknown", project_key="PRJ-Z", refs=False)
    res = _packet(db)
    assert res["packet"]["source_ref_coverage"] < 1.0


def test_packet_source_missing_candidate_is_withheld(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = ConstructionStore(db_path=db)
    # A task candidate with no source refs resolves to source_missing and is withheld, not ranked.
    pending_candidate(store, "missing", review_status="pending", refs=False)
    res = _packet(db)
    assert res["withheld_source_missing_count"] >= 1
    assert all("missing" not in it["candidate_id"] for it in res["packet"]["items"])


def test_packet_no_eligible_candidates_is_honest(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    ConstructionStore(db_path=db)
    res = _packet(db)
    assert res["status"] == "no_eligible_candidates"
    assert res["packet"]["items"] == []


def test_packet_fails_closed_on_planted_leak(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    store = ConstructionStore(db_path=db)
    # Plant a JWT-like token the upstream redactor does NOT strip, proving the packet's own
    # defensive scan still fails closed on a leak that slipped through.
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
    accept_task(store, "leak", title=f"Review item {jwt} please", project_key="PRJ")
    res = _packet(db)
    assert res["status"] == "fail_closed"
    assert res["packet"]["packet_guard_clean"] is False
    assert "jwt_like" in res["leak_categories"]


def test_packet_hashes_are_stable(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    seed_ranking_store(db)
    a = _packet(db)["packet"]
    b = _packet(db)["packet"]
    assert a["candidate_set_hash"] == b["candidate_set_hash"]
    assert a["feedback_digest_hash"] == b["feedback_digest_hash"]
    assert a["candidate_set_hash"].startswith("cs:")
