"""Phase 10 V52 — effectiveness rollup builder tests."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
    build_effectiveness_packets,
)
from hb_assistant.construction.second_brain.local_ai.effectiveness_rollups import (
    SCOPE_CANDIDATE_FAMILY,
    SCOPE_DAILY,
    SCOPE_MODEL_PROFILE,
    SCOPE_PROJECT,
    SCOPE_SOURCE_FAMILY,
    SCOPE_WINDOW,
    build_rollups,
)
from tests._phase_10_effectiveness_seed import (
    EVAL_NOW,
    WINDOW_END,
    WINDOW_START,
    seed_effectiveness_store,
)


def _packet(tmp_path: Path):
    store = seed_effectiveness_store(str(tmp_path / "t.sqlite"))
    return build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )


def test_builds_all_rollup_scopes(tmp_path: Path) -> None:
    rollups = build_rollups(_packet(tmp_path), model_degradation_rate=1.0)
    scopes = {r["scope"] for r in rollups}
    assert {
        SCOPE_WINDOW,
        SCOPE_DAILY,
        SCOPE_PROJECT,
        SCOPE_CANDIDATE_FAMILY,
        SCOPE_SOURCE_FAMILY,
        SCOPE_MODEL_PROFILE,
    } <= scopes


def test_window_rollup_carries_window_only_metrics(tmp_path: Path) -> None:
    rollups = build_rollups(_packet(tmp_path), model_degradation_rate=0.5)
    window = next(r for r in rollups if r["scope"] == SCOPE_WINDOW)
    assert window["model_degradation_rate"] == 0.5
    assert window["candidate_count"] == 5
    assert window["outcome_count"] == 5


def test_missing_dimensions_normalize_to_unknown(tmp_path: Path) -> None:
    rollups = build_rollups(_packet(tmp_path))
    for r in rollups:
        assert r["scope_key"] != ""
        assert r["scope_key"] is not None
    # model_profile scope key is "unknown" for the deterministic (no-profile) run.
    model_rollups = [r for r in rollups if r["scope"] == SCOPE_MODEL_PROFILE]
    assert any(r["scope_key"] == "unknown" for r in model_rollups)


def test_rollup_rates_are_deterministic(tmp_path: Path) -> None:
    rollups = build_rollups(_packet(tmp_path))
    window = next(r for r in rollups if r["scope"] == SCOPE_WINDOW)
    assert window["accepted_rate"] == 0.2
    assert window["rejected_rate"] == 0.4
    assert window["snoozed_rate"] == 0.2
    assert window["ignored_rate"] == 0.2
