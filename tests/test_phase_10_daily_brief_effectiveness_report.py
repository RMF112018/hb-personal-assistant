"""Phase 10 V52 — effectiveness report renderer tests (raw-free)."""

from __future__ import annotations

from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_packets import (
    build_effectiveness_packets,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_effectiveness_report import (
    build_effectiveness_report,
)
from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
    scan_text_for_forbidden,
)
from hb_assistant.construction.second_brain.local_ai.ranking_policy_evaluator import (
    evaluate_ranking_policy,
)
from tests._phase_10_effectiveness_seed import (
    EVAL_NOW,
    WINDOW_END,
    WINDOW_START,
    seed_effectiveness_store,
)


def _report(tmp_path: Path):
    store = seed_effectiveness_store(str(tmp_path / "t.sqlite"))
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    ev = evaluate_ranking_policy(pkt, eval_mode="ablation")
    return build_effectiveness_report(pkt, ev)


def test_report_renders_required_sections(tmp_path: Path) -> None:
    report = _report(tmp_path)
    md = report["markdown"]
    for heading in (
        "# Daily Brief Effectiveness",
        "## Outcome Distribution",
        "## Source-Ref Coverage",
        "## Procore Noise",
        "## Model Profile Reliability",
        "## Duplicate / Similarity Proxy",
        "## Safe Next Tuning Actions",
        "## Guardrails",
    ):
        assert heading in md


def test_report_is_raw_free(tmp_path: Path) -> None:
    report = _report(tmp_path)
    assert report["raw_safety"]["raw_free"] is True
    assert scan_text_for_forbidden(report["markdown"]) == []


def test_model_degradation_and_procore_summary_present(tmp_path: Path) -> None:
    report = _report(tmp_path)
    assert "model_profiles" in report
    assert report["procore_noise"]["advisory"] is True
    assert "source_ref_coverage" in report


def test_insufficient_banner_when_small_sample(tmp_path: Path) -> None:
    # A single-candidate window produces an insufficient-sample banner.
    from hb_assistant.construction.second_brain.local_ai import run_candidate_ranking_and_assembly
    from hb_assistant.construction.store import ConstructionStore
    from tests._phase_10_effectiveness_seed import _event, _task

    db = str(tmp_path / "t.sqlite")
    store = ConstructionStore(db_path=db)
    _task(store, "solo", source_family="email")
    run_candidate_ranking_and_assembly(
        store=store,
        brief_date="2026-06-11",
        now_utc="2026-06-11T12:00:00+00:00",
        use_model=False,
        include_similarity=True,
        dry_run=False,
        max_persist=100,
    )
    _event(store, "solo", event_type="accept", new_state="accepted")
    pkt = build_effectiveness_packets(
        store, window_start=WINDOW_START, window_end=WINDOW_END, now_utc=EVAL_NOW
    )
    ev = evaluate_ranking_policy(pkt, eval_mode="observed")
    report = build_effectiveness_report(pkt, ev)
    assert report["data_sufficiency"] == "insufficient_sample"
    assert "Insufficient" in report["markdown"]


def test_guardrails_block_present(tmp_path: Path) -> None:
    report = _report(tmp_path)
    g = report["guardrails"]
    assert g["observational_only"] is True
    assert g["no_lifecycle_mutation"] is True
    assert g["no_source_ref_mutation"] is True
    assert g["no_external_writeback"] is True
