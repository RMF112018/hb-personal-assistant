"""Phase 10 — source-ref gate + model-facing contract (daily-brief usefulness repair).

Proves the model only sees source-linked candidates: linked rows included, ref-less rows withheld,
mixed rows include only the linked ones, all-withheld blocks synthesis (fail-closed), unsupported
model bullets are dropped, coverage metrics are reported, and no raw content leaks into the context.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_brief_candidate_writer import (
    persist_candidate_with_refs,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_llm_synthesis import (
    synthesize_daily_brief,
)
from hb_assistant.construction.second_brain.local_ai.daily_brief_window import (
    compute_daily_brief_window,
)
from hb_assistant.construction.second_brain.local_ai.source_ref_gate import (
    drop_unsupported_bullets,
    executive_coverage_ok,
    gate_model_candidate_context,
)
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-08T00:00:00+00:00"
BRIEF_DATE = "2026-06-08"


def _linked(store: ConstructionStore, group_key: str, section: str = "procore") -> None:
    persist_candidate_with_refs(
        store,
        brief_date=BRIEF_DATE,
        section=section,
        title_redacted=f"linked {group_key}",
        confidence=0.9,
        project_key="tropical",
        priority=10,
        reason_redacted="Overdue",
        group_key=group_key,
        source_refs=[{"source_family": "procore_action_signals", "source_ref": group_key}],
    )


def _unlinked(store: ConstructionStore, group_key: str, section: str = "procore") -> None:
    store.insert_daily_brief_action_candidate(
        brief_date=BRIEF_DATE,
        section=section,
        title_redacted=f"unlinked {group_key}",
        confidence=0.5,
        project_key="tropical",
        priority=30,
        group_key=group_key,
    )


def test_source_linked_row_is_included(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _linked(s, "g1")
    by_section, report = gate_model_candidate_context(s, BRIEF_DATE)
    assert report["source_linked_candidates"] == 1
    assert report["coverage"] == 1.0
    assert any(item["title"] == "linked g1" for item in by_section.get("procore", []))


def test_missing_ref_row_is_withheld(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _unlinked(s, "g1")
    by_section, report = gate_model_candidate_context(s, BRIEF_DATE)
    assert report["source_linked_candidates"] == 0
    assert report["withheld_candidate_count"] == 1
    assert by_section == {}
    assert report["withhold_synthesis"] is True
    assert report["verdict"] == "degraded_no_source_linked_context"


def test_mixed_rows_include_only_linked(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _linked(s, "g1")
    _unlinked(s, "g2")
    by_section, report = gate_model_candidate_context(s, BRIEF_DATE)
    assert report["total_candidates"] == 2
    assert report["source_linked_candidates"] == 1
    assert report["coverage"] == 0.5
    titles = [i["title"] for i in by_section.get("procore", [])]
    assert titles == ["linked g1"]
    # executive section coverage is below 100% → not success-eligible
    assert executive_coverage_ok(report) is False


def test_executive_coverage_full_when_all_linked(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _linked(s, "g1")
    _linked(s, "g2")
    _, report = gate_model_candidate_context(s, BRIEF_DATE)
    assert report["executive_coverage"] == 1.0
    assert executive_coverage_ok(report) is True


def test_drop_unsupported_model_bullets(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _linked(s, "g1")
    _, report = gate_model_candidate_context(s, BRIEF_DATE)
    supported = set(report["supported_short_ids"])
    good_id = report["supported_short_ids"][0]
    bullets = [
        {"text": "real", "source_id": good_id},
        {"text": "hallucinated", "source_id": "dbac-nonexistent"},
        {"text": "no source at all", "source_id": ""},
    ]
    kept, dropped = drop_unsupported_bullets(bullets, supported)
    assert [b["text"] for b in kept] == ["real"]
    assert {b["text"] for b in dropped} == {"hallucinated", "no source at all"}


def test_all_withheld_blocks_synthesis(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    _unlinked(s, "g1")  # a candidate with no source ref
    window = compute_daily_brief_window(datetime.fromisoformat(NOW), "America/New_York")
    r = synthesize_daily_brief(
        store=s, brief_date=BRIEF_DATE, window=window, now_utc=NOW, db_path=db, dry_run=True
    )
    # Fail-closed: the model is never called; the run is degraded with a clear reason.
    assert r.status == "blocked"
    assert r.degraded is True
    assert r.synthesis is None
    assert r.degraded_reason == "no_source_linked_context"


def test_no_candidates_does_not_block(tmp_path: Path) -> None:
    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _, report = gate_model_candidate_context(s, BRIEF_DATE)
    assert report["verdict"] == "no_candidates"
    assert report["withhold_synthesis"] is False
    assert report["coverage"] == 1.0


def test_no_raw_in_gate_context(tmp_path: Path) -> None:
    import json

    s = ConstructionStore(db_path=str(tmp_path / "t.sqlite"))
    _linked(s, "g1")
    by_section, report = gate_model_candidate_context(s, BRIEF_DATE)
    blob = json.dumps({"by_section": by_section, "report": report})
    # source refs are surfaced only as a count, never the raw/hashed ref value
    assert "source_ref_hash" not in blob
    assert "g1" not in blob or "linked g1" in blob  # the only "g1" is inside the safe title
