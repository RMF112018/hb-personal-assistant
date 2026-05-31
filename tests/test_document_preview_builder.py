"""Phase 07C Prompt 09 — review-controlled document intelligence (project previews)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.document import build_document_intelligence_previews
from hb_assistant.construction.store.repositories import ConstructionStore

_GUARD_COLS = (
    "raw_document_text_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "external_writeback_performed",
)


def _seed_card(
    store: ConstructionStore,
    *,
    key: str,
    project_key: str,
    document_type: str,
    review_required: bool = True,
    relationship: bool = False,
) -> None:
    store.upsert_inventory_item(
        source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
        parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
    )
    store.upsert_document_card(
        card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
        file_extension="pdf", project_key=project_key, document_type="unknown",
        review_required=review_required, size_class="small",
    )
    store.upsert_document_classification_candidate(
        candidate_id="clf_" + key, document_card_id=key, document_type=document_type,
        classifier_name="deterministic_v1", signal_class="deterministic", confidence=0.9,
        confidence_class="deterministic" if document_type != "unknown_needs_review" else "unknown",
        review_required=review_required,
    )
    store.upsert_document_project_match_candidate(
        candidate_id="pm_" + key, document_card_id=key, project_key=project_key,
        candidate_type="deterministic", confidence=0.95, confidence_class="deterministic",
        deterministic=True, review_required=False,
    )
    if relationship:
        store.upsert_document_relationship_candidate(
            candidate_id="rel_" + key, document_card_id=key, target_system="procore",
            target_record_type="rfi", target_record_key_hash="hh", relationship_type="x",
            candidate_type="heuristic", confidence=0.55, confidence_class="moderate_heuristic",
            review_required=True,
        )


def _seed(store: ConstructionStore) -> None:
    # alpha: 4/5 classified -> 0.8 -> high_heuristic
    for i in range(4):
        _seed_card(store, key=f"a{i}", project_key="alpha", document_type="rfi",
                   relationship=(i == 0))
    _seed_card(store, key="a4", project_key="alpha", document_type="unknown_needs_review")
    # beta: 1/5 classified -> 0.2 -> weak_heuristic
    _seed_card(store, key="b0", project_key="beta", document_type="contract")
    for i in range(1, 5):
        _seed_card(store, key=f"b{i}", project_key="beta", document_type="unknown_needs_review")


def _previews(db: str) -> dict[str, sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM construction_document_intelligence_previews"
    ).fetchall()
    return {r["project_key"]: r for r in rows}


def test_project_level_previews(tmp_path: Path) -> None:
    db = str(tmp_path / "prev.sqlite")
    store = ConstructionStore(db)
    _seed(store)

    report = build_document_intelligence_previews(store, apply=True)
    assert report["summary"]["projects"] == 2
    assert report["summary"]["previews"] == 2
    assert store.count_document_intelligence_previews() == 2

    rows = _previews(db)
    assert set(rows) == {"alpha", "beta"}
    for r in rows.values():
        assert r["preview_kind"] == "project_document_intelligence"
        assert r["document_card_id"] is None
        assert r["review_required"] == 1
        for guard in _GUARD_COLS:
            assert r[guard] == 0

    assert rows["alpha"]["confidence_class"] == "high_heuristic"
    assert rows["beta"]["confidence_class"] == "weak_heuristic"

    w = json.loads(rows["alpha"]["warnings_json"])
    assert w["warnings"]
    assert w["source_reference"]["project_key"] == "alpha"
    assert w["source_reference"]["document_count"] == 5
    assert w["source_reference"]["distinct_sources"] == 1
    assert w["review"]["documents_pending_review"] == 5


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "prev.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    report = build_document_intelligence_previews(store, apply=False)
    assert report["mode"] == "dry_run"
    assert report["summary"]["previews"] == 2
    assert store.count_document_intelligence_previews() == 0


def test_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "prev.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    build_document_intelligence_previews(store, apply=True)
    build_document_intelligence_previews(store, apply=True)
    assert store.count_document_intelligence_previews() == 2


def test_no_raw_values_leak_into_preview_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "prev.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    build_document_intelligence_previews(store, apply=True)
    conn = sqlite3.connect(db)
    blob = "\n".join(
        "|".join("" if v is None else str(v) for v in row)
        for row in conn.execute(
            "SELECT * FROM construction_document_intelligence_previews"
        ).fetchall()
    )
    assert "http://" not in blob and "https://" not in blob
    assert "raw_a0" not in blob


def test_guardrails_no_conclusions(tmp_path: Path) -> None:
    db = str(tmp_path / "prev.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    g = build_document_intelligence_previews(store, apply=True)["guardrails"]
    assert g["model_invoked"] is False
    assert g["high_impact_conclusions"] is False
    assert g["external_writeback"] is False
    assert g["card_mutated"] is False
