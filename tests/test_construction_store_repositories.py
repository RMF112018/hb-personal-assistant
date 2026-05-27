"""Tests for the construction-agent V2-V5 SQLite repositories."""

from __future__ import annotations

import sqlite3
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
    # Construction store requires at least V2 (its own tables). Later schema
    # versions stack on top and remain backwards-compatible.
    assert SQLiteMigrator(db_path).current_version() >= 2


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
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(construction_drive_item_inventory)")
    columns = {row[1] for row in cur.fetchall()}
    forbidden = {"body", "content", "text", "excerpt", "preview", "full_text"}
    leaks = columns & forbidden
    assert not leaks, f"forbidden columns present: {leaks}"


# =====================================================================
# V5 canonical alignment tests.
# =====================================================================


CANONICAL_V5_TABLES = [
    "construction_source_locations",
    "construction_source_sync_state",
    "construction_source_crawl_runs",
    "construction_drive_items",
    "construction_project_identity",
    "construction_project_source_matches",
    "construction_document_cards",
    "construction_processing_receipts",
    "construction_sync_errors",
    "construction_email_intelligence_deferred_state",
]


def _existing_tables(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_store_init_applies_v5_migration(db_path: str) -> None:
    ConstructionStore(db_path)
    assert SQLiteMigrator(db_path).current_version() >= 5


def test_v5_migration_creates_all_canonical_tables(db_path: str) -> None:
    ConstructionStore(db_path)
    tables = _existing_tables(db_path)
    missing = set(CANONICAL_V5_TABLES) - tables
    assert not missing, f"V5 canonical tables missing: {sorted(missing)}"


def test_v5_migration_is_additive_v2_v3_v4_intact(db_path: str) -> None:
    ConstructionStore(db_path)
    tables = _existing_tables(db_path)
    legacy = {
        "construction_source_resolutions",
        "construction_delta_tokens",
        "construction_drive_item_inventory",
        "construction_crawl_receipts",
        "construction_review_queue",
        "construction_model_decisions",
    }
    missing = legacy - tables
    assert not missing, f"V2-V4 tables disappeared: {sorted(missing)}"


def test_v5_migration_is_idempotent(db_path: str) -> None:
    m = SQLiteMigrator(db_path)
    assert m.apply() == 5
    assert m.apply() == 5
    assert m.current_version() == 5


def test_no_body_or_text_columns_in_drive_items(db_path: str) -> None:
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.execute("PRAGMA table_info(construction_drive_items)")
    columns = {row[1] for row in cur.fetchall()}
    forbidden = {"body", "content", "text", "excerpt", "preview", "full_text"}
    leaks = columns & forbidden
    assert not leaks, f"forbidden columns present in canonical drive items: {leaks}"


# --- source_locations ---------------------------------------------------


def test_upsert_source_location_roundtrip(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_test_canonical",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Test Canonical",
        project_key="tropical",
        tenant_id="tenant-abc",
        drive_id="drive-1",
        folder_item_id="folder-1",
        folder_path="/Test",
        sync_mode="graph_delta",
        sync_frequency_minutes=30,
        baseline_policy={"mode": "shallow_metadata_first"},
        folder_policies={
            "deep_index_allowed": ["07-RFI"],
            "review_required": ["12-Accounting"],
        },
    )
    record = store.get_source_location("sp_test_canonical")
    assert record is not None
    assert record["source_system"] == "sharepoint"
    assert record["source_scope"] == "sharepoint_project_drive_folder"
    assert record["project_key"] == "tropical"
    assert record["read_only"] is True
    assert record["enabled"] is True
    assert record["baseline_policy"] == {"mode": "shallow_metadata_first"}
    assert "07-RFI" in record["folder_policies"]["deep_index_allowed"]


def test_upsert_source_location_rejects_read_only_false(db_path: str) -> None:
    store = ConstructionStore(db_path)
    with pytest.raises(ValueError, match="read_only must be True"):
        store.upsert_source_location(
            source_id="sp_bad",
            source_system="sharepoint",
            source_scope="sharepoint_project_drive_folder",
            source_name="Bad",
            read_only=False,
        )


def test_source_location_read_only_check_constraint_at_sql_level(db_path: str) -> None:
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO construction_source_locations
                (source_id, source_system, source_scope, source_name, read_only)
            VALUES (?, ?, ?, ?, 0)
            """,
            ("sp_raw_bypass", "sharepoint", "sharepoint_project_drive_folder", "Bypass"),
        )


def test_upsert_source_location_is_idempotent_and_updates_in_place(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_dup",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="V1",
    )
    store.upsert_source_location(
        source_id="sp_dup",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="V2",
    )
    record = store.get_source_location("sp_dup")
    assert record["source_name"] == "V2"


# --- sync_state ---------------------------------------------------------


def test_upsert_source_sync_state_roundtrip(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_sync",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Sync test",
    )
    store.upsert_source_sync_state(
        source_id="sp_sync",
        drive_id="drive-x",
        delta_link="https://graph/delta?t=abc",
        delta_link_fingerprint="sha256:abc12345",
        last_baseline_item_count=100,
        last_change_count=5,
        sync_status="ok",
    )
    record = store.get_source_sync_state("sp_sync")
    assert record["delta_link_fingerprint"] == "sha256:abc12345"
    assert record["last_baseline_item_count"] == 100
    assert record["sync_status"] == "ok"


# --- crawl_runs ---------------------------------------------------------


def test_insert_and_list_source_crawl_runs(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_crawl",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Crawl",
    )
    store.insert_source_crawl_run(
        run_id="run-A",
        source_id="sp_crawl",
        source_scope="sharepoint_project_drive_folder",
        mode="apply",
        started_at="2026-05-27T12:00:00+00:00",
        completed_at="2026-05-27T12:00:05+00:00",
        pages_seen=3,
        items_seen=42,
        items_in_scope=40,
        items_out_of_scope_filtered=2,
        delta_link_recorded=True,
        status="ok",
    )
    runs = store.list_source_crawl_runs(source_id="sp_crawl")
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-A"
    assert runs[0]["delta_link_recorded"] is True
    assert runs[0]["items_in_scope"] == 40


# --- drive_items --------------------------------------------------------


def test_upsert_drive_item_roundtrip_and_soft_delete(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_items",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Items",
    )
    store.upsert_drive_item(
        source_id="sp_items",
        drive_id="drv-1",
        drive_item_id="itm-1",
        name="design.pdf",
        path="/Test/design.pdf",
        is_file=True,
        size_bytes=4096,
        mime_type="application/pdf",
        last_modified_datetime="2026-05-27T10:00:00Z",
        project_number_detected="23-435-01",
        document_type_detected="design",
        indexing_policy="metadata_only",
        classification_status="pending",
    )
    item = store.get_drive_item(source_id="sp_items", drive_item_id="itm-1")
    assert item is not None
    assert item["is_file"] is True
    assert item["deleted"] is False
    assert item["project_number_detected"] == "23-435-01"

    # Soft delete
    store.upsert_drive_item(
        source_id="sp_items",
        drive_id="drv-1",
        drive_item_id="itm-1",
        deleted=True,
    )
    item2 = store.get_drive_item(source_id="sp_items", drive_item_id="itm-1")
    assert item2["deleted"] is True


# --- project_identity ---------------------------------------------------


def test_upsert_project_identity_roundtrip(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_project_identity(
        project_key="tropical",
        hb_project_number="23-435-01",
        project_name_raw="Tropical - S L",
        project_name_normalized="tropical_s_l",
        procore_project_id="2525840",
        match_status="matched",
        match_confidence="high",
    )
    record = store.get_project_identity("tropical")
    assert record["hb_project_number"] == "23-435-01"
    assert record["procore_project_id"] == "2525840"
    assert record["is_active"] is True


# --- project_source_matches --------------------------------------------


def test_upsert_project_source_match_unique_constraint(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_match",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Match",
    )
    store.upsert_project_identity(project_key="tropical")
    id1 = store.upsert_project_source_match(
        project_key="tropical",
        source_id="sp_match",
        match_method="project_number_exact",
        match_confidence="high",
        review_required=False,
    )
    # Upsert with same composite key updates in place; same id returned.
    id2 = store.upsert_project_source_match(
        project_key="tropical",
        source_id="sp_match",
        match_method="project_number_exact",
        match_confidence="medium",
        review_required=True,
    )
    assert id1 == id2
    rows = store.list_project_source_matches(project_key="tropical")
    assert len(rows) == 1
    assert rows[0]["match_confidence"] == "medium"
    assert rows[0]["review_required"] is True


# --- document_cards ----------------------------------------------------


def test_upsert_document_card_roundtrip(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_source_location(
        source_id="sp_card",
        source_system="sharepoint",
        source_scope="sharepoint_project_drive_folder",
        source_name="Card",
    )
    store.upsert_document_card(
        card_id="card-1",
        source_id="sp_card",
        drive_item_id="itm-9",
        project_key="tropical",
        document_type="rfi",
        status="candidate",
        confidence=0.82,
        needs_review=True,
        card_path="Construction/RFIs/card-1.md",
    )
    card = store.get_document_card("card-1")
    assert card["document_type"] == "rfi"
    assert card["confidence"] == 0.82
    assert card["needs_review"] is True


# --- processing_receipts -----------------------------------------------


def test_insert_and_list_processing_receipts(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.insert_processing_receipt(
        receipt_id="proc-1",
        source_id="sp_proc",
        operation="baseline_inventory",
        status="ok",
        detail={"items_scanned": 100, "duration_ms": 4321},
    )
    rows = store.list_processing_receipts(source_id="sp_proc")
    assert len(rows) == 1
    assert rows[0]["operation"] == "baseline_inventory"
    assert rows[0]["detail"] == {"items_scanned": 100, "duration_ms": 4321}


# --- sync_errors -------------------------------------------------------


def test_insert_sync_error_and_resolve(db_path: str) -> None:
    store = ConstructionStore(db_path)
    err_id = store.insert_sync_error(
        source_id="sp_err",
        operation="delta_crawl",
        error_class="GraphAuthRequired",
        error_redacted="No delegated token",
    )
    assert err_id > 0

    unresolved = store.list_sync_errors(source_id="sp_err")
    assert len(unresolved) == 1
    assert unresolved[0]["resolved_utc"] is None

    assert store.resolve_sync_error(err_id) is True
    assert store.list_sync_errors(source_id="sp_err") == []
    all_errors = store.list_sync_errors(source_id="sp_err", include_resolved=True)
    assert len(all_errors) == 1
    assert all_errors[0]["resolved_utc"] is not None


# --- email_intelligence_deferred_state (singleton) ---------------------


def test_email_intelligence_deferred_state_singleton_constraint(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.set_email_intelligence_deferred_state(
        mail_read_all_granted=True,
        mail_readwrite_all_granted=True,
    )
    state = store.get_email_intelligence_deferred_state()
    assert state["id"] == 1
    assert state["mail_read_all_granted"] is True
    assert state["mailbox_writeback_allowed"] is False
    assert state["persist_full_body"] is False

    # Second row with id != 1 rejected by CHECK
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO construction_email_intelligence_deferred_state
                (id, mail_read_all_granted, mail_readwrite_all_granted)
            VALUES (2, 1, 1)
            """,
        )


def test_email_intelligence_deferred_state_rejects_mailbox_writeback_true(
    db_path: str,
) -> None:
    store = ConstructionStore(db_path)
    with pytest.raises(ValueError, match="mailbox_writeback_allowed must be False"):
        store.set_email_intelligence_deferred_state(
            mail_read_all_granted=True,
            mail_readwrite_all_granted=True,
            mailbox_writeback_allowed=True,
        )


def test_email_intelligence_deferred_state_rejects_persist_full_body_true(
    db_path: str,
) -> None:
    store = ConstructionStore(db_path)
    with pytest.raises(ValueError, match="persist_full_body must be False"):
        store.set_email_intelligence_deferred_state(
            mail_read_all_granted=True,
            mail_readwrite_all_granted=True,
            persist_full_body=True,
        )


def test_email_intelligence_deferred_state_sql_level_rejects_mailbox_writeback(
    db_path: str,
) -> None:
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO construction_email_intelligence_deferred_state
                (id, mail_read_all_granted, mail_readwrite_all_granted,
                 mailbox_writeback_allowed)
            VALUES (1, 1, 1, 1)
            """,
        )


def test_email_intelligence_deferred_state_sql_level_rejects_persist_full_body(
    db_path: str,
) -> None:
    ConstructionStore(db_path)
    conn = sqlite3.connect(db_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO construction_email_intelligence_deferred_state
                (id, mail_read_all_granted, mail_readwrite_all_granted,
                 persist_full_body)
            VALUES (1, 1, 1, 1)
            """,
        )
