"""Phase 07C Prompt 07 — controlled extraction eligibility (deterministic-first)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.document import evaluate_extraction_eligibility
from hb_assistant.construction.store.repositories import ConstructionStore

_GUARD_COLS = (
    "raw_document_text_persisted",
    "raw_payload_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "source_file_copied_to_vault",
    "external_writeback_performed",
)


def _seed_card(
    store: ConstructionStore,
    *,
    key: str,
    ext: str | None,
    size_class: str = "small",
    review_required: bool = True,
    review_status: str = "pending",
    document_type: str = "unknown",
    project_key: str | None = "alpha",
    project_number_hash: str | None = "ph_alpha",
) -> None:
    store.upsert_inventory_item(
        source_key="sp",
        drive_id="d",
        item_id=key,
        name="raw_" + key,
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
        file_extension=ext,
        size_class=size_class,
        review_required=review_required,
        review_status=review_status,
        document_type=document_type,
        project_key=project_key,
        project_number_hash=project_number_hash,
    )


def _seed(store: ConstructionStore) -> None:
    # blocked: dangerous extension; blocked: oversize; metadata_only: non-text kind.
    _seed_card(store, key="c_blocked_ext", ext="exe")
    _seed_card(store, key="c_oversize", ext="pdf", size_class="oversize")
    _seed_card(store, key="c_meta_dwg", ext="dwg")
    # review-required text-parseable -> manual approval (cannot extract).
    _seed_card(store, key="c_review_pdf", ext="pdf", review_required=True)
    # cleared review, unparseable extension -> metadata_only.
    _seed_card(
        store,
        key="c_unparseable",
        ext="xyz",
        review_required=False,
        review_status="approved",
        document_type="rfi",
    )
    # cleared review, parseable, but no deterministic project binding -> manual approval.
    _seed_card(
        store,
        key="c_lowproj",
        ext="pdf",
        review_required=False,
        review_status="approved",
        document_type="rfi",
        project_number_hash=None,
    )
    # cleared review, parseable, deterministically bound -> eligible.
    _seed_card(
        store,
        key="c_eligible",
        ext="pdf",
        review_required=False,
        review_status="approved",
        document_type="rfi",
        project_key="alpha",
        project_number_hash="ph_alpha",
    )
    # no extension -> skipped.
    _seed_card(store, key="c_noext", ext=None)


def _cards(db: str) -> dict[str, sqlite3.Row]:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM construction_document_cards").fetchall()
    return {r["card_id"]: r for r in rows}


def test_each_disposition_path(tmp_path: Path) -> None:
    db = str(tmp_path / "elig.sqlite")
    store = ConstructionStore(db)
    _seed(store)

    report = evaluate_extraction_eligibility(store, apply=True)
    assert report["summary"]["cards_total"] == 8
    assert report["summary"]["eligible"] == 1

    cards = _cards(db)
    assert cards["c_blocked_ext"]["extraction_eligibility"] == "blocked"
    assert cards["c_oversize"]["extraction_eligibility"] == "blocked"
    assert cards["c_meta_dwg"]["extraction_eligibility"] == "metadata_only"
    assert cards["c_review_pdf"]["extraction_eligibility"] == "manual_approval_required"
    assert cards["c_unparseable"]["extraction_eligibility"] == "metadata_only"
    assert cards["c_lowproj"]["extraction_eligibility"] == "manual_approval_required"
    assert cards["c_eligible"]["extraction_eligibility"] == "eligible"
    assert cards["c_noext"]["extraction_eligibility"] == "skipped"

    # No review-required card is ever marked eligible.
    for r in cards.values():
        if r["review_required"] == 1:
            assert r["extraction_eligibility"] != "eligible"
        for guard in _GUARD_COLS:
            assert r[guard] == 0


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "elig.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    report = evaluate_extraction_eligibility(store, apply=False)
    assert report["mode"] == "dry_run"
    assert report["summary"]["evaluated"] == 8
    assert report["guardrails"]["card_eligibility_updated"] is False
    assert report["guardrails"]["card_columns_mutated"] == []
    for r in _cards(db).values():
        assert r["extraction_eligibility"] == "not_evaluated"


def test_idempotent_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "elig.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    first = evaluate_extraction_eligibility(store, apply=True)["summary"]["by_eligibility"]
    after_one = {k: v["extraction_eligibility"] for k, v in _cards(db).items()}
    second = evaluate_extraction_eligibility(store, apply=True)["summary"]["by_eligibility"]
    after_two = {k: v["extraction_eligibility"] for k, v in _cards(db).items()}
    assert first == second
    assert after_one == after_two


def test_only_eligibility_column_mutated(tmp_path: Path) -> None:
    db = str(tmp_path / "elig.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    before = {k: dict(v) for k, v in _cards(db).items()}
    evaluate_extraction_eligibility(store, apply=True)
    after = {k: dict(v) for k, v in _cards(db).items()}
    for key in before:
        for col in before[key]:
            if col in ("extraction_eligibility", "updated_utc"):
                continue
            assert before[key][col] == after[key][col], f"{key}.{col} changed unexpectedly"


def test_no_raw_values_leak_into_card_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "elig.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    evaluate_extraction_eligibility(store, apply=True)
    conn = sqlite3.connect(db)
    blob = "\n".join(
        "|".join("" if v is None else str(v) for v in row)
        for row in conn.execute("SELECT * FROM construction_document_cards").fetchall()
    )
    assert "http://" not in blob and "https://" not in blob
    assert "raw_c_eligible" not in blob


def test_guardrails_no_download_no_parse(tmp_path: Path) -> None:
    db = str(tmp_path / "elig.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    g = evaluate_extraction_eligibility(store, apply=True)["guardrails"]
    assert g["download_performed"] is False
    assert g["parse_performed"] is False
    assert g["model_invoked"] is False
    assert g["auto_promotion"] is False
    assert g["raw_document_text_persisted"] is False
    assert g["card_eligibility_updated"] is True
    assert g["card_columns_mutated"] == ["extraction_eligibility"]
