"""Phase 10 V51 — deterministic ranking engine tests.

Verifies stable deterministic ordering, the bounded model influence invariant (a clearly-higher
deterministic candidate can never be leapfrogged beyond ``MAX_RANK_MOVEMENT``), and the duplicate
penalty.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.construction.second_brain.local_ai.candidate_ranking import (
    MAX_RANK_MOVEMENT,
    deterministic_score,
    rank_candidates,
)

_EMPTY_CAL = {"families": {}}


def _item(
    cid: str, *, due: str = "none", group: Optional[str] = None, conf: float = 0.5
) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "subject_type": "accepted_task",
        "family": "accepted_task",
        "section": "actions",
        "lifecycle_state": "accepted",
        "due_bucket": due,
        "age_bucket": "today",
        "waiting_signal": "unknown",
        "project_key": "PRJ",
        "confidence": conf,
        "source_ref_count": 1,
        "source_ref_coverage_status": "ok",
        "duplicate_group_key": group,
        "actionable": False,
    }


def test_deterministic_ordering_is_stable() -> None:
    items = [_item("c1", due="overdue"), _item("c2", due="today"), _item("c3", due="none")]
    a = [r["candidate_id"] for r in rank_candidates(items, calibration=_EMPTY_CAL)]
    b = [r["candidate_id"] for r in rank_candidates(list(reversed(items)), calibration=_EMPTY_CAL)]
    assert a == b == ["c1", "c2", "c3"]


def test_ranks_assigned_1_based_and_contiguous() -> None:
    items = [_item(f"c{i}", due="today") for i in range(5)]
    ranked = rank_candidates(items, calibration=_EMPTY_CAL)
    assert [r["rank_position"] for r in ranked] == [1, 2, 3, 4, 5]


def test_model_cannot_leapfrog_beyond_bound() -> None:
    # Strictly decreasing deterministic score via due proximity.
    buckets = ["overdue", "today", "next_3d", "next_7d", "future", "none"]
    items = [_item(f"c{i}", due=b) for i, b in enumerate(buckets)]
    # Model maximally favours the WORST deterministic item and penalises the best.
    model_scores = {"c0": 0.0, "c5": 100.0}
    ranked = rank_candidates(items, calibration=_EMPTY_CAL, model_scores=model_scores)
    pos = {r["candidate_id"]: r["rank_position"] for r in ranked}
    # c5 (worst det, det rank 6) cannot reach the top: bounded to within MAX_RANK_MOVEMENT.
    assert pos["c5"] >= 6 - MAX_RANK_MOVEMENT
    assert pos["c5"] >= 3
    # c0 (best det) cannot be pushed past position 1 + MAX_RANK_MOVEMENT.
    assert pos["c0"] <= 1 + MAX_RANK_MOVEMENT


def test_duplicate_copy_is_penalised() -> None:
    primary = _item("a1", due="today", group="grp-x")
    copy = _item("a2", due="today", group="grp-x")
    ranked = rank_candidates([copy, primary], calibration=_EMPTY_CAL)
    pos = {r["candidate_id"]: r["rank_position"] for r in ranked}
    # The deterministic primary (lower candidate id) outranks the penalised duplicate copy.
    assert pos["a1"] < pos["a2"]
    scores = {r["candidate_id"]: r["deterministic_score"] for r in ranked}
    assert scores["a1"] > scores["a2"]


def test_deterministic_score_rewards_urgency_and_project() -> None:
    overdue = deterministic_score(_item("x", due="overdue"))
    none = deterministic_score(_item("y", due="none"))
    assert overdue > none


def test_empty_items_returns_empty() -> None:
    assert rank_candidates([], calibration=_EMPTY_CAL) == []
