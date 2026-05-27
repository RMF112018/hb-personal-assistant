"""Tests for the construction-agent V2 SQLite repositories (Phase 01 Step 4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.fixture
def db_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db = tmp_path / "construction.sqlite"
    return str(db)


def test_store_init_applies_v2_migration(db_path: str) -> None:
    ConstructionStore(db_path)
    assert SQLiteMigrator(db_path).current_version() == 2


def test_upsert_and_get_resolution(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_resolution(
        source_key="tropical-sharepoint",
        kind="sharepoint_site",
        site_id="contoso.sharepoint.com,abc",
        drive_id="b!XYZ",
        web_url="https://contoso.sharepoint.com/sites/Tropical",
        resolution_status="resolved",
    )
    row = store.get_resolution("tropical-sharepoint")
    assert row is not None
    assert row["site_id"] == "contoso.sharepoint.com,abc"
    assert row["drive_id"] == "b!XYZ"
    assert row["resolution_status"] == "resolved"
    assert row["resolved_at"] is not None


def test_upsert_resolution_preserves_non_null_on_partial_update(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_resolution(
        source_key="bobby-onedrive",
        kind="onedrive_personal",
        site_id=None,
        drive_id="drive-1",
        web_url=None,
        resolution_status="resolved",
    )
    store.upsert_resolution(
        source_key="bobby-onedrive",
        kind="onedrive_personal",
        site_id=None,
        drive_id=None,
        web_url="https://onedrive/me",
        resolution_status="resolved",
    )
    row = store.get_resolution("bobby-onedrive")
    assert row["drive_id"] == "drive-1"  # preserved via COALESCE
    assert row["web_url"] == "https://onedrive/me"


def test_delta_token_round_trip(db_path: str) -> None:
    store = ConstructionStore(db_path)
    assert store.get_delta_token("tropical-sharepoint") is None
    store.set_delta_token(
        source_key="tropical-sharepoint",
        drive_id="b!XYZ",
        delta_link="https://graph.microsoft.com/v1.0/drives/b!XYZ/root/delta?token=abc",
        page_count=3,
        last_status="ok",
    )
    tok = store.get_delta_token("tropical-sharepoint")
    assert tok is not None
    assert tok["delta_link"].endswith("token=abc")
    assert tok["page_count"] == 3
    assert tok["last_status"] == "ok"


def test_inventory_upsert_returns_new_then_updated(db_path: str) -> None:
    store = ConstructionStore(db_path)
    outcome1 = store.upsert_inventory_item(
        source_key="tropical-sharepoint",
        drive_id="b!XYZ",
        item_id="item-1",
        name="design.pdf",
        web_url="https://example/item-1",
        parent_path="/drives/x/root:/Project",
        size_bytes=1024,
        is_folder=False,
        last_modified="2026-05-20T10:00:00Z",
        etag="etag-1",
    )
    outcome2 = store.upsert_inventory_item(
        source_key="tropical-sharepoint",
        drive_id="b!XYZ",
        item_id="item-1",
        name="design-v2.pdf",
        web_url="https://example/item-1",
        parent_path="/drives/x/root:/Project",
        size_bytes=2048,
        is_folder=False,
        last_modified="2026-05-21T10:00:00Z",
        etag="etag-2",
    )
    assert outcome1 == "new"
    assert outcome2 == "updated"
    counts = store.count_inventory("tropical-sharepoint")
    assert counts == {"active": 1}


def test_mark_inventory_deleted_is_sticky(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_inventory_item(
        source_key="tropical-sharepoint",
        drive_id="b!XYZ",
        item_id="item-2",
        name="old.txt",
        web_url=None,
        parent_path=None,
        size_bytes=0,
        is_folder=False,
        last_modified=None,
        etag=None,
    )
    matched = store.mark_inventory_deleted(source_key="tropical-sharepoint", item_id="item-2")
    assert matched is True
    counts = store.count_inventory("tropical-sharepoint")
    assert counts == {"deleted": 1}

    # Marking a non-existent item returns False
    assert store.mark_inventory_deleted(source_key="tropical-sharepoint", item_id="nope") is False


def test_insert_and_list_crawl_receipts(db_path: str) -> None:
    store = ConstructionStore(db_path)
    receipt_id = store.insert_crawl_receipt(
        run_id="run-1",
        source_key="tropical-sharepoint",
        mode="apply",
        started_at="2026-05-27T12:00:00+00:00",
        finished_at="2026-05-27T12:00:01+00:00",
        pages_seen=2,
        items_seen=10,
        items_new=7,
        items_updated=2,
        items_deleted=1,
        delta_link_recorded=True,
        status="ok",
    )
    assert receipt_id > 0
    recents = store.list_recent_receipts("tropical-sharepoint")
    assert len(recents) == 1
    assert recents[0]["run_id"] == "run-1"
    assert recents[0]["status"] == "ok"
    assert recents[0]["delta_link_recorded"] == 1


def test_no_body_or_text_columns_in_inventory(db_path: str) -> None:
    """Guardrail: inventory schema must not include body/content/text columns."""
    import sqlite3

    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(construction_drive_item_inventory)")
    columns = {row[1] for row in cur.fetchall()}
    forbidden = {"body", "content", "text", "excerpt", "preview", "full_text"}
    leaks = columns & forbidden
    assert not leaks, f"forbidden columns present: {leaks}"
