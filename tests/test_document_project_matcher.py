"""Phase 07C Prompt 06 — document project matcher (deterministic-first)."""

from __future__ import annotations

import json
import sqlite3
import types
from pathlib import Path

from hb_assistant.construction.document import match_document_projects
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

_RAW_PROJECT_NUMBER = "PN-100-SECRET"
_RAW_WRONG_NUMBER = "PN-999-WRONG"


def _registry() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        projects=[
            types.SimpleNamespace(project_key="alpha", project_number=_RAW_PROJECT_NUMBER),
            types.SimpleNamespace(project_key="beta", project_number="PN-200"),
            types.SimpleNamespace(project_key="gamma", project_number=None),
        ]
    )


def _seed_card(
    store: ConstructionStore,
    *,
    key: str,
    project_key: str | None,
    project_number_hash: str | None,
) -> None:
    store.upsert_inventory_item(
        source_key="sp",
        drive_id="d",
        item_id=key,
        name="raw_" + key + ".pdf",
        web_url="https://x/" + key,
        parent_path="/General",
        size_bytes=1024,
        is_folder=False,
        last_modified=None,
        etag="e",
    )
    store.upsert_document_card(
        card_id=key,
        document_card_id=key,
        source_id="sp",
        drive_item_id=key,
        file_extension="pdf",
        project_key=project_key,
        project_number_hash=project_number_hash,
    )


def _seed(store: ConstructionStore) -> None:
    # Full match: source key + corroborating registry project-number hash.
    _seed_card(
        store, key="c_det", project_key="alpha", project_number_hash=hash_value(_RAW_PROJECT_NUMBER)
    )
    # Source binding only (no project_number_hash on the card).
    _seed_card(store, key="c_src_only", project_key="beta", project_number_hash=None)
    # Conflict: card hash disagrees with the registry hash.
    _seed_card(
        store,
        key="c_conflict",
        project_key="alpha",
        project_number_hash=hash_value(_RAW_WRONG_NUMBER),
    )
    # Unmatchable: no project_key -> skipped (cannot write a candidate).
    _seed_card(store, key="c_noproj", project_key=None, project_number_hash=None)


def _by_card(db: str) -> dict[str, sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM construction_document_project_match_candidates").fetchall()
    return {r["document_card_id"]: r for r in rows}


def test_deterministic_match_conflict_and_skip(tmp_path: Path) -> None:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    _seed(store)

    report = match_document_projects(store, apply=True, registry=_registry())
    summary = report["summary"]
    assert summary["cards_total"] == 4
    assert summary["matched"] == 3
    assert summary["unmatched_skipped"] == 1
    assert summary["deterministic"] == 2
    assert summary["conflict"] == 1
    assert summary["review_required"] == 1
    assert summary["by_candidate_type"] == {"conflict": 1, "deterministic": 2}
    assert store.count_document_project_match_candidates() == 3

    cards = _by_card(db)
    assert "c_noproj" not in cards  # skipped, never written

    assert cards["c_det"]["candidate_type"] == "deterministic"
    assert cards["c_det"]["confidence_class"] == "deterministic"
    assert cards["c_det"]["deterministic"] == 1
    assert cards["c_det"]["review_required"] == 0
    assert "full_project_number_hash" in json.loads(cards["c_det"]["signals_json"])["signals"]

    assert cards["c_src_only"]["candidate_type"] == "deterministic"
    assert cards["c_src_only"]["review_required"] == 0

    # Conflict -> review-required, weak, never auto-promoted.
    assert cards["c_conflict"]["candidate_type"] == "conflict"
    assert cards["c_conflict"]["confidence_class"] == "weak_heuristic"
    assert cards["c_conflict"]["review_required"] == 1
    assert cards["c_conflict"]["deterministic"] == 0

    # Every candidate: guard columns 0, candidate promotion status.
    for r in cards.values():
        assert r["promotion_status"] == "candidate"
        assert r["model_proposed"] == 0
        for guard in ("raw_document_text_persisted", "external_writeback_performed"):
            assert r[guard] == 0


def test_cards_are_not_mutated_candidates_only(tmp_path: Path) -> None:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    match_document_projects(store, apply=True, registry=_registry())
    for card in store.list_document_cards():
        # project_key/document_type on the card are untouched by matching.
        assert card["document_type"] in (None, "candidate", "unknown")


def test_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    match_document_projects(store, apply=True, registry=_registry())
    match_document_projects(store, apply=True, registry=_registry())
    assert store.count_document_project_match_candidates() == 3


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    report = match_document_projects(store, apply=False, registry=_registry())
    assert report["mode"] == "dry_run"
    assert report["summary"]["matched"] == 3
    assert store.count_document_project_match_candidates() == 0


def test_no_raw_values_leak_into_candidate_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    match_document_projects(store, apply=True, registry=_registry())
    conn = sqlite3.connect(db)
    blob = "\n".join(
        "|".join("" if v is None else str(v) for v in row)
        for row in conn.execute(
            "SELECT * FROM construction_document_project_match_candidates"
        ).fetchall()
    )
    for raw in (_RAW_PROJECT_NUMBER, _RAW_WRONG_NUMBER, "SECRET", "WRONG", "raw_c_det.pdf"):
        assert raw not in blob, f"raw value leaked into a match candidate: {raw!r}"
    assert "http://" not in blob and "https://" not in blob


def test_guardrails_advisory_only(tmp_path: Path) -> None:
    db = str(tmp_path / "match.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    report = match_document_projects(store, apply=True, registry=_registry())
    g = report["guardrails"]
    assert g["model_invoked"] is False
    assert g["auto_promotion"] is False
    assert g["card_mutated"] is False
    assert g["external_systems"] == "read_only"
    assert g["graph_calls"] == "none"
