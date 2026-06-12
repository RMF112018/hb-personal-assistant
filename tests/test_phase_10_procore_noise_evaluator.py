"""Phase 10 V52 — Procore noise + source-family evaluator tests (advisory only)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
    build_effectiveness_packets,
)
from hb_assistant.construction.second_brain.local_ai.procore_noise_evaluator import (
    evaluate_procore_noise,
    evaluate_source_families,
)
from tests._phase_10_effectiveness_seed import (
    EVAL_NOW,
    WINDOW_END,
    WINDOW_START,
    seed_effectiveness_store,
)


def _packet(tmp_path: Path):
    store = seed_effectiveness_store(str(tmp_path / "t.sqlite"))
    return store, build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )


def test_procore_noise_identifies_rejected_procore_item(tmp_path: Path) -> None:
    _store, pkt = _packet(tmp_path)
    result = evaluate_procore_noise(pkt)
    assert result["exposed_procore_candidates"] == 1
    assert result["procore_noise_score"] is not None
    assert result["procore_noise_score"] > 0.0  # the lone Procore item was rejected → noisy
    assert result["advisory"] is True
    assert result["no_suppression"] is True
    assert result["recommendations"]


def test_procore_noise_is_advisory_only_no_mutation(tmp_path: Path) -> None:
    store, pkt = _packet(tmp_path)
    db = store._db_path
    watched = [
        "candidate_suppression_rules",
        "candidate_lifecycle_events",
        "daily_brief_ranked_candidates",
    ]
    conn = sqlite3.connect(db)
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in watched}
    evaluate_procore_noise(pkt)
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in watched}
    assert after == before  # no suppression, no state change


def test_small_procore_sample_marked_insufficient(tmp_path: Path) -> None:
    _store, pkt = _packet(tmp_path)
    result = evaluate_procore_noise(pkt)
    # Only one exposed Procore candidate < MIN_GROUP_SAMPLE → insufficient.
    assert result["insufficient_sample"] is True


def test_source_family_usefulness_scores(tmp_path: Path) -> None:
    _store, pkt = _packet(tmp_path)
    rows = evaluate_source_families(pkt)
    families = {r["source_family"] for r in rows}
    assert "email" in families
    assert "procore" in families
    for r in rows:
        assert 0.0 <= r["usefulness_score"] <= 1.0
