"""Phase 07C Prompt 04 — document card materializer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.config.models import (
    ProjectIdentity,
    SourceLocation,
    SourceRegistry,
)
from hb_assistant.construction.document import materialize_document_cards
from hb_assistant.construction.policy.document_source_policy import DocumentSourcePolicy
from hb_assistant.construction.store.repositories import ConstructionStore

# Distinctive raw markers that must NEVER appear in any materialized card column.
_RAW_NAME = "Secret RFI 0042.pdf"
_RAW_URL = "https://contoso.sharepoint.com/sites/x/Shared%20Documents/Secret.pdf"
_RAW_PATH = "/Projects/HB-1234/Confidential/RFIs"


def _registry() -> SourceRegistry:
    return SourceRegistry(
        projects=[
            ProjectIdentity(project_key="proj-a", display_name="Proj A", project_number="HB-1234"),
        ],
        sources=[
            SourceLocation(
                source_key="sp_test",
                kind="sharepoint_project_drive_folder",
                display_name="SP",
                project_key="proj-a",
                project_number="HB-1234",
            ),
            SourceLocation(
                source_key="od_test",
                kind="onedrive_business_root",
                display_name="OD",
            ),
        ],
    )


def _seed(store: ConstructionStore) -> None:
    # Compliant SharePoint source: 2 active files, 1 folder, 1 deleted file.
    store.upsert_inventory_item(
        source_key="sp_test",
        drive_id="d1",
        item_id="f1",
        name=_RAW_NAME,
        web_url=_RAW_URL,
        parent_path=_RAW_PATH,
        size_bytes=2048,
        is_folder=False,
        last_modified="2026-05-01T00:00:00Z",
        etag="e1",
    )
    store.upsert_inventory_item(
        source_key="sp_test",
        drive_id="d1",
        item_id="f2",
        name="plan.dwg",
        web_url="https://x/y",
        parent_path="/Projects/HB-1234",
        size_bytes=200_000_000,
        is_folder=False,
        last_modified="2026-05-02T00:00:00Z",
        etag="e2",
    )
    store.upsert_inventory_item(
        source_key="sp_test",
        drive_id="d1",
        item_id="dir1",
        name="RFIs",
        web_url="https://x/dir",
        parent_path="/Projects/HB-1234",
        size_bytes=None,
        is_folder=True,
        last_modified=None,
        etag="e3",
    )
    store.upsert_inventory_item(
        source_key="sp_test",
        drive_id="d1",
        item_id="f3",
        name="old.pdf",
        web_url="https://x/old",
        parent_path="/Projects/HB-1234",
        size_bytes=10,
        is_folder=False,
        last_modified=None,
        etag="e4",
    )
    store.mark_inventory_deleted(source_key="sp_test", item_id="f3")
    # Blocked OneDrive root source: 1 active file (must be skipped).
    store.upsert_inventory_item(
        source_key="od_test",
        drive_id="d2",
        item_id="g1",
        name="onedrive.docx",
        web_url="https://od/x",
        parent_path="/Personal",
        size_bytes=1024,
        is_folder=False,
        last_modified=None,
        etag="e5",
    )


def test_apply_materializes_only_compliant_active_files(tmp_path: Path) -> None:
    db = str(tmp_path / "mat.sqlite")
    store = ConstructionStore(db)
    _seed(store)

    report = materialize_document_cards(
        store, apply=True, registry=_registry(), policy=DocumentSourcePolicy()
    )
    s = report["summary"]
    assert s["inventory_rows"] == 5
    assert s["folders_skipped"] == 1
    assert s["deleted_skipped"] == 1
    assert s["blocked_source_skipped"] == 1
    assert s["unknown_source_skipped"] == 0
    assert s["considered"] == 2
    assert s["cards_written"] == 2
    assert s["review_required"] == 2
    assert report["by_system"] == {"sharepoint": 2}
    assert report["mode"] == "apply"
    assert store.count_document_cards() == 2


def test_apply_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "mat.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    kw = {"registry": _registry(), "policy": DocumentSourcePolicy()}
    materialize_document_cards(store, apply=True, **kw)
    materialize_document_cards(store, apply=True, **kw)  # second apply
    assert store.count_document_cards() == 2


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "mat.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    report = materialize_document_cards(
        store, apply=False, registry=_registry(), policy=DocumentSourcePolicy()
    )
    assert report["mode"] == "dry_run"
    assert report["summary"]["cards_written"] == 2
    assert store.count_document_cards() == 0


def test_cards_are_review_required_candidates_with_guards_zero(tmp_path: Path) -> None:
    db = str(tmp_path / "mat.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    materialize_document_cards(
        store, apply=True, registry=_registry(), policy=DocumentSourcePolicy()
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM construction_document_cards").fetchall()
    assert len(rows) == 2
    for row in rows:
        assert row["document_type"] == "unknown"
        assert row["confidence_class"] == "unknown"
        assert row["extraction_eligibility"] == "not_evaluated"
        assert row["review_status"] == "pending"
        assert row["review_required"] == 1
        assert row["needs_review"] == 1
        assert row["project_key"] == "proj-a"
        assert row["document_card_id"] and row["document_card_id"] == row["card_id"]
        assert row["title_hash"] and row["drive_item_id_hash"] and row["project_number_hash"]
        for guard in (
            "raw_document_text_persisted",
            "raw_payload_persisted",
            "signed_url_persisted",
            "download_url_persisted",
            "source_file_copied_to_vault",
            "external_writeback_performed",
        ):
            assert row[guard] == 0


def test_no_raw_values_leak_into_card_columns(tmp_path: Path) -> None:
    db = str(tmp_path / "mat.sqlite")
    store = ConstructionStore(db)
    _seed(store)
    materialize_document_cards(
        store, apply=True, registry=_registry(), policy=DocumentSourcePolicy()
    )
    conn = sqlite3.connect(db)
    blob = "\n".join(
        "|".join("" if v is None else str(v) for v in row)
        for row in conn.execute("SELECT * FROM construction_document_cards").fetchall()
    )
    for raw in (_RAW_NAME, _RAW_URL, _RAW_PATH, "contoso", "Confidential", "Secret"):
        assert raw not in blob, f"raw value leaked into a card column: {raw!r}"
    # No URL scheme persisted anywhere in the cards.
    assert "http://" not in blob and "https://" not in blob
