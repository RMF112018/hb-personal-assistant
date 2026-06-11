"""Phase 10 V52 — model-profile evaluator tests (receipt metadata only)."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
    RANKING_TASK_TYPE,
    build_effectiveness_packets,
)
from hb_assistant.construction.second_brain.local_ai.model_profile_evaluator import (
    _percentile,
    evaluate_model_profiles,
)
from tests._phase_10_effectiveness_seed import (
    EVAL_NOW,
    WINDOW_END,
    WINDOW_START,
    seed_effectiveness_store,
)


def test_model_telemetry_missing_when_no_receipts(tmp_path: Path) -> None:
    store = seed_effectiveness_store(str(tmp_path / "t.sqlite"))
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    rows = evaluate_model_profiles(pkt)
    assert len(rows) == 1
    assert rows[0]["status"] == "model_telemetry_missing"
    assert rows[0]["attempt_count"] == 0
    assert rows[0]["sample_sufficient"] is False


def test_aggregates_from_receipts(tmp_path: Path) -> None:
    store = seed_effectiveness_store(str(tmp_path / "t.sqlite"))
    # Inject deterministic-id receipts (metadata only — no raw prompt/response).
    for i, (status, schema_valid, fallback, latency) in enumerate(
        [("ok", True, False, 100), ("ok", True, False, 200), ("timeout", False, True, 500)]
    ):
        store.insert_local_model_run_receipt(
            model_run_receipt_id=f"mrr-{i}",
            profile_id="default_extract",
            provider="ollama",
            model_name="llama-test",
            task_type=RANKING_TASK_TYPE,
            status=status,
            input_context_hash=f"in{i}",
            output_hash=f"out{i}",
            schema_name="CandidateRankingAdvice",
            schema_valid=schema_valid,
            latency_ms=latency,
            fallback_used=fallback,
        )
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    rows = evaluate_model_profiles(pkt)
    row = next(r for r in rows if r["model_name"] == "llama-test")
    assert row["attempt_count"] == 3
    assert row["success_count"] == 2
    assert row["timeout_count"] == 1
    assert row["fallback_count"] == 1
    assert row["avg_latency_ms"] is not None
    assert row["model_degradation_rate"] == round(1 / 3, 4)
    assert row["status"] == "ok"


def test_percentile_is_deterministic() -> None:
    assert _percentile([], 95) is None
    assert _percentile([100.0], 95) == 100.0
    assert _percentile([100.0, 200.0, 300.0, 400.0], 95) == 400.0
