"""Phase 07C Prompt 08 — document->record relationship candidates (Procore arm)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.document import build_document_relationship_candidates
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    upsert_procore_live_record,
)

_GUARD_COLS = (
    "raw_document_text_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "external_writeback_performed",
)


def _seed_card(
    store: ConstructionStore,
    db: str,
    *,
    key: str,
    document_type: str,
    project_key: str | None = "alpha",
) -> None:
    store.upsert_inventory_item(
        source_key="sp", drive_id="d", item_id=key, name="raw_" + key, web_url="https://x/" + key,
        parent_path="/General", size_bytes=1024, is_folder=False, last_modified=None, etag="e",
    )
    store.upsert_document_card(
        card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
        file_extension="pdf", project_key=project_key, document_type="unknown",
    )
    store.upsert_document_classification_candidate(
        candidate_id="clf_" + key, document_card_id=key, document_type=document_type,
        classifier_name="deterministic_v1", signal_class="deterministic", confidence=0.9,
        confidence_class="deterministic",
    )


def _seed_procore(db: str, *, project_key: str, endpoint_id: str, record_id: str) -> None:
    run_id = "run_" + endpoint_id
    record_sync_run_start(
        sync_run_id=run_id, endpoint_id=endpoint_id, command_endpoint=endpoint_id,
        legacy_endpoint_alias=None, project_key=project_key, procore_project_id="pp1",
        company_id="co1", mode="history", started_at_utc="2026-01-01T00:00:00Z", db_path=Path(db),
    )
    upsert_procore_live_record(
        project_key=project_key, procore_project_id="pp1", endpoint_id=endpoint_id,
        procore_record_id=record_id, parent_procore_id=None,
        normalized_fields={"number": record_id}, review_required=False, sensitive_reason=None,
        source_url_redacted=None, last_sync_run_id=run_id, now_utc="2026-01-01T00:00:00Z",
        db_path=Path(db),
    )


def _seed(store: ConstructionStore, db: str) -> None:
    _seed_card(store, db, key="c_rfi", document_type="rfi")
    _seed_card(store, db, key="c_change_order", document_type="change_order")
    _seed_card(store, db, key="c_no_procore", document_type="submittal")  # aligned, but no procore
    _seed_card(store, db, key="c_drawings", document_type="drawings")  # unaligned
    _seed_card(store, db, key="c_noproj", document_type="rfi", project_key=None)
    # Procore data exists only for rfis + prime-change-orders (not submittals).
    _seed_procore(db, project_key="alpha", endpoint_id="rfis", record_id="101")
    _seed_procore(db, project_key="alpha", endpoint_id="prime-change-orders", record_id="201")


def _by_card(db: str) -> dict[str, sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM construction_document_relationship_candidates"
    ).fetchall()
    return {r["document_card_id"]: r for r in rows}


def test_procore_type_alignment_candidates(tmp_path: Path) -> None:
    db = str(tmp_path / "rel.sqlite")
    store = ConstructionStore(db)
    _seed(store, db)

    report = build_document_relationship_candidates(store, apply=True)
    summary = report["summary"]
    assert summary["cards_total"] == 5
    assert summary["candidates"] == 2
    assert summary["unmatched_skipped"] == 3  # no_procore + drawings + noproj
    assert summary["by_target_record_type"] == {"change_order": 1, "rfi": 1}
    assert summary["by_target_system"] == {"procore": 2}
    assert store.count_document_relationship_candidates() == 2

    cards = _by_card(db)
    assert set(cards) == {"c_rfi", "c_change_order"}
    assert cards["c_rfi"]["target_system"] == "procore"
    assert cards["c_rfi"]["target_record_type"] == "rfi"
    assert cards["c_rfi"]["candidate_type"] == "heuristic"
    assert cards["c_rfi"]["relationship_type"] == "project_document_type_alignment"
    assert cards["c_change_order"]["target_record_type"] == "change_order"
    for r in cards.values():
        assert r["review_required"] == 1
        assert r["promotion_status"] == "candidate"
        for guard in _GUARD_COLS:
            assert r[guard] == 0


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "rel.sqlite")
    store = ConstructionStore(db)
    _seed(store, db)
    report = build_document_relationship_candidates(store, apply=False)
    assert report["mode"] == "dry_run"
    assert report["summary"]["candidates"] == 2
    assert store.count_document_relationship_candidates() == 0


def test_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "rel.sqlite")
    store = ConstructionStore(db)
    _seed(store, db)
    build_document_relationship_candidates(store, apply=True)
    build_document_relationship_candidates(store, apply=True)
    assert store.count_document_relationship_candidates() == 2


def test_no_raw_values_leak_into_candidate_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "rel.sqlite")
    store = ConstructionStore(db)
    _seed(store, db)
    build_document_relationship_candidates(store, apply=True)
    conn = sqlite3.connect(db)
    blob = "\n".join(
        "|".join("" if v is None else str(v) for v in row)
        for row in conn.execute(
            "SELECT * FROM construction_document_relationship_candidates"
        ).fetchall()
    )
    assert "http://" not in blob and "https://" not in blob
    assert "raw_c_rfi" not in blob


def test_guardrails_candidates_only(tmp_path: Path) -> None:
    db = str(tmp_path / "rel.sqlite")
    store = ConstructionStore(db)
    _seed(store, db)
    g = build_document_relationship_candidates(store, apply=True)["guardrails"]
    assert g["model_invoked"] is False
    assert g["auto_promotion"] is False
    assert g["card_mutated"] is False
    assert g["external_writeback"] is False
    assert g["deferred_target_systems"] == ["email", "calendar"]
