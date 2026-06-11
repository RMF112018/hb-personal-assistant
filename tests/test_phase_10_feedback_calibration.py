"""Phase 10 V51 — feedback calibration tests.

Verifies calibration applies only above the sample threshold, clamps its effect, is raw-free, and
never transfers one family's outcomes onto an unrelated family (no negative transfer).
"""

from __future__ import annotations

import json

from hb_assistant.construction.second_brain.local_ai.feedback_calibration import (
    MAX_CALIBRATION_ADJUSTMENT,
    MIN_FEEDBACK_SAMPLES,
    NEUTRAL_FEEDBACK_SCORE,
    build_calibration,
    feedback_score_for_family,
)


def _summary(by_family: dict, rates: dict) -> dict:
    return {"by_family": by_family, "acceptance_rate_by_family": rates}


def test_below_threshold_stays_neutral() -> None:
    cal = build_calibration(_summary({"task": MIN_FEEDBACK_SAMPLES - 1}, {"task": 1.0}))
    assert feedback_score_for_family("task", cal) == NEUTRAL_FEEDBACK_SCORE
    assert cal["families"]["task"]["applied"] is False


def test_high_acceptance_boosts_within_clamp() -> None:
    cal = build_calibration(_summary({"task": MIN_FEEDBACK_SAMPLES}, {"task": 1.0}))
    score = feedback_score_for_family("task", cal)
    # +MAX adjustment on the 0..1 scale → +10 points; clamp keeps it bounded.
    assert score == NEUTRAL_FEEDBACK_SCORE + MAX_CALIBRATION_ADJUSTMENT * 100
    assert abs(cal["families"]["task"]["adjustment"]) <= MAX_CALIBRATION_ADJUSTMENT


def test_low_acceptance_penalises_within_clamp() -> None:
    cal = build_calibration(_summary({"task": 10}, {"task": 0.0}))
    score = feedback_score_for_family("task", cal)
    assert score == NEUTRAL_FEEDBACK_SCORE - MAX_CALIBRATION_ADJUSTMENT * 100


def test_no_negative_transfer_across_families() -> None:
    # 'task' is heavily rejected; 'commitment' has no signal and must stay neutral.
    cal = build_calibration(_summary({"task": 20}, {"task": 0.0}))
    assert feedback_score_for_family("commitment", cal) == NEUTRAL_FEEDBACK_SCORE
    assert cal["no_negative_transfer"] is True


def test_calibration_is_raw_free() -> None:
    cal = build_calibration(_summary({"task": 5}, {"task": 0.8}))
    blob = json.dumps(cal).lower()
    for forbidden in ("http://", "https://", "@", "bearer", "secret", "body"):
        assert forbidden not in blob


def test_unknown_family_is_neutral() -> None:
    cal = build_calibration(_summary({}, {}))
    assert feedback_score_for_family(None, cal) == NEUTRAL_FEEDBACK_SCORE
    assert feedback_score_for_family("nope", cal) == NEUTRAL_FEEDBACK_SCORE
