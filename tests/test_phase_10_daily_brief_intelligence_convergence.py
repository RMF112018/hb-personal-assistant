"""Phase 10 convergence — unified Model Enriched Intelligence object (offline, synthetic).

Proves the converged ``build_model_enriched_intelligence`` object: default-on vs disabled, source-link
filtering (alias mapping, unknown ids dropped, no-survivors → withheld), model-unavailable → withheld
with deterministic fallback, the exact label, and that the status block is raw-free.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.daily_brief_intelligence import (
    build_daily_brief_intelligence,
)
from hb_assistant.construction.second_brain.local_ai.model_enriched_intelligence import (
    MODEL_ENRICHED_INTELLIGENCE_LABEL,
    build_model_enriched_intelligence,
    status_block,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore

_PRESENT = {"mistral-nemo:12b", "qwen2.5:7b-instruct", "default_extract"}
_BRIEF_DATE = "2026-06-09"


def _store(td: str) -> ConstructionStore:
    return ConstructionStore(db_path=str(Path(td) / "mei.db"))


def _seed_candidate(store: ConstructionStore, *, section: str = "actions", title: str = "Send RFI") -> None:
    store.insert_daily_brief_action_candidate(
        brief_date=_BRIEF_DATE,
        section=section,
        title_redacted=title,
        confidence=0.8,
        project_key="P1",
        recommended_next_action="Send the response",
    )


def _adapter_json(*, source_ids: list[str]) -> str:
    return json.dumps(
        {
            "executive_catchup": ["Two items need attention today."],
            "top_priorities": [
                {"text": "Respond to the RFI", "source_ids": source_ids, "confidence": 0.9,
                 "reason_code": "due_today"}
            ],
            "open_loops": [],
            "waiting_on_me": [],
            "waiting_on_others": [],
            "meeting_prep": [],
            "project_risk": [],
        }
    )


def _intel_result(store: ConstructionStore, *, source_ids: list[str], present=_PRESENT):
    candidates = store.list_daily_brief_action_candidates(brief_date=_BRIEF_DATE, limit=200)
    return build_daily_brief_intelligence(
        candidates=candidates,
        profiles=load_local_model_profiles(),
        present_models=present,
        backend=StaticOutputClient(_adapter_json(source_ids=source_ids)),
        dry_run=True,
        brief_date=_BRIEF_DATE,
    )


def test_default_on_available_with_source_linked_bullet() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store)
        result = _intel_result(store, source_ids=["c1"])
        mei = build_model_enriched_intelligence(
            store=store, brief_date=_BRIEF_DATE, enabled=True,
            intelligence_result=result, pending_section={"available": False, "count": 0, "items": []},
        )
        assert mei["enabled"] is True
        assert mei["available"] is True
        assert mei["label"] == MODEL_ENRICHED_INTELLIGENCE_LABEL == "Model Enriched Intelligence"
        assert mei["bullets_kept"] == 1
        assert mei["source_link_count"] == 1
        assert mei["degraded"] is False
        assert mei["withheld_reason"] is None


def test_disabled_returns_envelope_without_model_call() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store)
        mei = build_model_enriched_intelligence(
            store=store, brief_date=_BRIEF_DATE, enabled=False,
            pending_section={"available": False, "count": 0, "items": []},
        )
        assert mei["enabled"] is False
        assert mei["available"] is False
        assert mei["withheld_reason"] == "disabled"
        assert mei["label"] == "Model Enriched Intelligence"
        assert mei["intelligence"] is None


def test_unknown_source_ids_dropped_and_withheld_when_none_survive() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store)
        # The bullet cites an id that maps to no real candidate → dropped → nothing survives.
        result = _intel_result(store, source_ids=["does-not-exist"])
        mei = build_model_enriched_intelligence(
            store=store, brief_date=_BRIEF_DATE, enabled=True,
            intelligence_result=result, pending_section={"available": False, "count": 0, "items": []},
        )
        assert mei["available"] is False
        assert mei["withheld_reason"] == "no_source_linked_bullets"
        assert mei["bullets_kept"] == 0
        assert mei["unknown_source_ids_count"] >= 1


def test_model_unavailable_withholds_but_pending_survives() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store)
        # No backend + present_models=None (daemon down) → adapter route blocked → withheld.
        result = build_daily_brief_intelligence(
            candidates=store.list_daily_brief_action_candidates(brief_date=_BRIEF_DATE, limit=200),
            profiles=load_local_model_profiles(),
            present_models=None,
            dry_run=True,
            brief_date=_BRIEF_DATE,
        )
        mei = build_model_enriched_intelligence(
            store=store, brief_date=_BRIEF_DATE, enabled=True,
            intelligence_result=result,
            pending_section={"available": True, "count": 2, "items": [{"a": 1}, {"a": 2}]},
        )
        assert mei["available"] is False
        assert mei["degraded"] is True
        assert mei["withheld_reason"] is not None
        # Pending (deterministic) survives the degraded path.
        assert mei["pending_followup_count"] == 2


def test_status_block_is_raw_free_and_compact() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = _store(td)
        _seed_candidate(store, title="Confidential vendor RFI")
        result = _intel_result(store, source_ids=["c1"])
        mei = build_model_enriched_intelligence(
            store=store, brief_date=_BRIEF_DATE, enabled=True,
            intelligence_result=result, pending_section={"available": False, "count": 0, "items": []},
        )
        sb = status_block(mei)
        blob = json.dumps(sb)
        assert sb["label"] == "Model Enriched Intelligence"
        assert "intelligence" not in sb  # no bullet bodies in the status block
        for forbidden in ("http://", "https://", "@", "Bearer ", "<html"):
            assert forbidden not in blob
