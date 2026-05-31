"""Phase 07C Prompt 05 — document type classifier (deterministic-first)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.document import classify_document_cards
from hb_assistant.construction.policy.document_classification import (
    load_document_review_rules,
    load_document_type_classification_policy,
)
from hb_assistant.construction.store.repositories import ConstructionStore

_RAW_CONTRACT_NAME = "Master Services Agreement SECRET.pdf"


def _seed_card(store: ConstructionStore, *, key: str, ext: str, name: str, path: str) -> None:
    store.upsert_inventory_item(
        source_key="sp", drive_id="d", item_id=key, name=name, web_url="https://x/" + key,
        parent_path=path, size_bytes=1024, is_folder=False, last_modified=None, etag="e",
    )
    store.upsert_document_card(
        card_id=key, document_card_id=key, source_id="sp", drive_item_id=key,
        file_extension=ext, project_key=None, document_type="unknown",
    )


def _seed(store: ConstructionStore) -> None:
    _seed_card(store, key="c_dwg", ext="dwg", name="site.dwg", path="/General")
    _seed_card(store, key="c_rfi_folder", ext="pdf", name="doc.pdf", path="/Project/RFIs")
    _seed_card(store, key="c_rfi_record", ext="pdf", name="RFI 042 Response.pdf", path="/General")
    _seed_card(store, key="c_contract", ext="pdf", name=_RAW_CONTRACT_NAME, path="/Project/Contracts")
    _seed_card(store, key="c_unknown", ext="pdf", name="summary.pdf", path="/General")


def _by_card(db: str) -> dict[str, sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM construction_document_classification_candidates"
    ).fetchall()
    return {r["document_card_id"]: r for r in rows}


def test_deterministic_classification_and_review_routing(tmp_path: Path) -> None:
    db = str(tmp_path / "clf.sqlite")
    store = ConstructionStore(db)
    _seed(store)

    report = classify_document_cards(store, apply=True)
    assert report["summary"]["cards_total"] == 5
    assert store.count_document_classification_candidates() == 5

    cards = _by_card(db)
    assert cards["c_dwg"]["document_type"] == "drawings"
    assert cards["c_dwg"]["signal_class"] == "deterministic"
    assert cards["c_dwg"]["review_required"] == 0  # not a review-required type

    assert cards["c_rfi_folder"]["document_type"] == "rfi"
    assert cards["c_rfi_folder"]["signal_class"] == "deterministic"

    assert cards["c_rfi_record"]["document_type"] == "rfi"
    assert json.loads(cards["c_rfi_record"]["signals_json"])["winning_signal"] == "record_number"

    # Contract -> review-required + sensitive, never auto-promoted.
    assert cards["c_contract"]["document_type"] == "contract"
    assert cards["c_contract"]["review_required"] == 1
    assert cards["c_contract"]["promotion_status"] == "candidate"

    # Ambiguous -> unknown_needs_review + review-required.
    assert cards["c_unknown"]["document_type"] == "unknown_needs_review"
    assert cards["c_unknown"]["review_required"] == 1

    # Every candidate: guard columns 0, candidate promotion status.
    for r in cards.values():
        assert r["promotion_status"] == "candidate"
        for guard in (
            "raw_document_text_persisted", "raw_prompt_persisted",
            "raw_response_persisted", "external_writeback_performed",
        ):
            assert r[guard] == 0


def test_cards_are_not_mutated_candidates_only(tmp_path: Path) -> None:
    db = str(tmp_path / "clf.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    classify_document_cards(store, apply=True)
    for card in store.list_document_cards():
        assert card["document_type"] == "unknown"  # cards left unchanged


def test_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "clf.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    classify_document_cards(store, apply=True)
    classify_document_cards(store, apply=True)
    assert store.count_document_classification_candidates() == 5


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "clf.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    report = classify_document_cards(store, apply=False)
    assert report["mode"] == "dry_run"
    assert report["summary"]["classified"] == 5
    assert store.count_document_classification_candidates() == 0


def test_no_raw_values_leak_into_candidate_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "clf.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    classify_document_cards(store, apply=True)
    conn = sqlite3.connect(db)
    blob = "\n".join(
        "|".join("" if v is None else str(v) for v in row)
        for row in conn.execute(
            "SELECT * FROM construction_document_classification_candidates"
        ).fetchall()
    )
    for raw in (_RAW_CONTRACT_NAME, "SECRET", "Master Services", "summary.pdf", "site.dwg"):
        assert raw not in blob, f"raw value leaked into a classification candidate: {raw!r}"
    assert "http://" not in blob and "https://" not in blob


def test_policy_loaders() -> None:
    pol = load_document_type_classification_policy()
    assert pol.version == "phase07c-document-type-classification-policy-v1"
    assert "rfi" in pol.document_types
    rules = load_document_review_rules()
    assert "contract" in rules.review_required_when.document_type
    assert rules.rules.no_auto_promotion_for_sensitive is True
