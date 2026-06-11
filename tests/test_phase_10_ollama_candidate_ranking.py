"""Phase 10 V51 — bounded Ollama advisory layer tests.

Verifies the advisory layer fails closed to deterministic on unavailable/invalid model output,
drops advice citing unknown aliases, withholds the whole layer on leaky narrative, and that its
receipt carries only hashes/metadata (never prompts/responses).
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.candidate_ranking_packets import (
    build_candidate_ranking_packet,
)
from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.ollama_candidate_ranking import (
    build_ranking_advice,
)
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from tests._phase_10_ranking_seed import BRIEF_DATE, NOW, seed_ranking_store


def _packet(db: str) -> dict:
    store = seed_ranking_store(db)
    return build_candidate_ranking_packet(store, brief_date=BRIEF_DATE, now_utc=NOW)


def _profiles():
    profiles = load_local_model_profiles()
    profile = next(p for p in profiles.profiles if p.profile_id == "default_extract")
    return profile, profiles


def _advice(db: str, backend) -> dict:
    packet = _packet(db)
    profile, profiles = _profiles()
    return build_ranking_advice(
        {"packet": packet["packet"], "alias_map": packet["alias_map"]},
        profile=profile,
        profiles=profiles,
        backend=backend,
        dry_run=True,
    )


def test_model_unavailable_falls_back(tmp_path: Path) -> None:
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient(raise_unavailable=True))
    assert res["status"] == "degraded"
    assert res["model_scores"] == {}
    assert res["degraded_reason"].startswith("model_")


def test_invalid_json_falls_back(tmp_path: Path) -> None:
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient("not json at all"))
    assert res["status"] == "degraded"
    assert res["model_scores"] == {}


def test_valid_advice_produces_bounded_scores(tmp_path: Path) -> None:
    mock = json.dumps(
        {"items": [{"alias": "c1", "priority_hint": 1}, {"alias": "c2", "priority_hint": 2}]}
    )
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient(mock))
    assert res["status"] == "ok"
    assert res["model_scores"]  # at least one candidate scored
    assert all(0.0 <= v <= 100.0 for v in res["model_scores"].values())


def test_unknown_alias_is_dropped(tmp_path: Path) -> None:
    mock = json.dumps(
        {"items": [{"alias": "c1", "priority_hint": 1}, {"alias": "zzz", "priority_hint": 1}]}
    )
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient(mock))
    assert res["dropped_unknown_alias"] == 1
    # No score is attributed to the unknown alias.
    assert len(res["model_scores"]) <= 1


def test_leaky_narrative_withholds_layer(tmp_path: Path) -> None:
    mock = json.dumps(
        {"items": [{"alias": "c1", "why_this_matters": "ping https://x.example/secret"}]}
    )
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient(mock))
    assert res["status"] == "withheld"
    assert res["degraded_reason"] == "raw_leak_in_model_output"
    assert res["model_scores"] == {}


def test_all_advice_dropped_is_degraded(tmp_path: Path) -> None:
    mock = json.dumps({"items": [{"alias": "zzz", "priority_hint": 1}]})
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient(mock))
    assert res["status"] == "degraded"
    assert res["degraded_reason"] == "all_model_advice_dropped"


def test_receipt_is_hash_only(tmp_path: Path) -> None:
    mock = json.dumps({"items": [{"alias": "c1", "priority_hint": 1}]})
    res = _advice(str(tmp_path / "t.sqlite"), StaticOutputClient(mock))
    receipt = res["would_write_receipt"]
    assert "input_context_hash" in receipt
    blob = json.dumps(res).lower()
    for forbidden in ("prompt", "response", "raw_", "http://", "https://"):
        assert forbidden not in blob
