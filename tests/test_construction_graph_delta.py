"""Tests for the construction-agent Graph delta crawler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.delta_crawler import (
    ConstructionDeltaCrawler,
    _select_delta_endpoint,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError


@pytest.fixture
def store(tmp_path: Path) -> ConstructionStore:
    db = str(tmp_path / "c.sqlite")
    s = ConstructionStore(db)
    s.upsert_resolution(
        source_key="tropical-sharepoint",
        kind="sharepoint_site",
        site_id="site-1",
        drive_id="drive-1",
        web_url="https://x",
        resolution_status="resolved",
    )
    return s


def _page(
    items: list[dict],
    *,
    next_link: str | None = None,
    delta_link: str | None = None,
) -> dict:
    page: dict = {"value": items}
    if next_link:
        page["@odata.nextLink"] = next_link
    if delta_link:
        page["@odata.deltaLink"] = delta_link
    return page


def _item(item_id: str, **overrides) -> dict:
    base = {
        "id": item_id,
        "name": f"file-{item_id}.txt",
        "size": 100,
        "webUrl": f"https://x/{item_id}",
        "lastModifiedDateTime": "2026-05-20T10:00:00Z",
        "eTag": f'"etag-{item_id}"',
        "parentReference": {"path": "/drives/drive-1/root:/Folder"},
        "file": {"mimeType": "text/plain"},
    }
    base.update(overrides)
    return base


def test_dry_run_does_not_write_to_store(store: ConstructionStore) -> None:
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a"), _item("b")],
        delta_link="https://graph/drives/drive-1/root/delta?token=tok-1",
    )
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=True)

    assert receipt.status == "ok"
    assert receipt.pages_seen == 1
    assert receipt.items_seen == 2
    assert receipt.items_new == 0  # never tallied in dry run
    assert receipt.delta_link_recorded is False
    assert len(receipt.sample_items) == 2

    # No persistence
    assert store.count_inventory("tropical-sharepoint") == {}
    assert store.get_delta_token("tropical-sharepoint") is None
    assert store.list_recent_receipts("tropical-sharepoint") == []


def test_apply_persists_inventory_token_and_receipt(store: ConstructionStore) -> None:
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a"), _item("b", folder={"childCount": 0})],
        delta_link="https://graph/drives/drive-1/root/delta?token=tok-1",
    )
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=False)

    assert receipt.status == "ok"
    assert receipt.items_new == 2
    assert receipt.delta_link_recorded is True
    assert store.count_inventory("tropical-sharepoint") == {"active": 2}
    tok = store.get_delta_token("tropical-sharepoint")
    assert tok is not None
    assert tok["delta_link"].endswith("token=tok-1")
    receipts = store.list_recent_receipts("tropical-sharepoint")
    assert len(receipts) == 1
    assert receipts[0]["status"] == "ok"


def test_multi_page_iterates_nextlink_and_records_final_deltalink(store: ConstructionStore) -> None:
    http = MagicMock()
    http.get.side_effect = [
        _page([_item("a")], next_link="/drives/drive-1/root/delta?$skiptoken=2"),
        _page([_item("b")], next_link="/drives/drive-1/root/delta?$skiptoken=3"),
        _page([_item("c")], delta_link="https://graph/drives/drive-1/root/delta?token=final"),
    ]
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=False)

    assert receipt.pages_seen == 3
    assert receipt.items_seen == 3
    assert receipt.items_new == 3
    tok = store.get_delta_token("tropical-sharepoint")
    assert tok["delta_link"].endswith("token=final")

    # Second + third calls follow the nextLink path verbatim
    assert http.get.call_args_list[1].args[0] == "/drives/drive-1/root/delta?$skiptoken=2"
    assert http.get.call_args_list[2].args[0] == "/drives/drive-1/root/delta?$skiptoken=3"


def test_max_pages_cap_is_enforced(store: ConstructionStore) -> None:
    http = MagicMock()
    http.get.side_effect = [
        _page([_item("a")], next_link="/p2"),
        _page([_item("b")], next_link="/p3"),
        _page([_item("c")], next_link="/p4"),
    ]
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=True, max_pages=2)
    assert receipt.pages_seen == 2
    assert receipt.items_seen == 2


def test_incremental_uses_stored_deltalink(store: ConstructionStore) -> None:
    store.set_delta_token(
        source_key="tropical-sharepoint",
        drive_id="drive-1",
        delta_link="https://graph/drives/drive-1/root/delta?token=prior",
        page_count=1,
        last_status="ok",
    )
    http = MagicMock()
    http.get.return_value = _page(
        [_item("z")],
        delta_link="https://graph/drives/drive-1/root/delta?token=new",
    )
    crawler = ConstructionDeltaCrawler(http, store)
    crawler.crawl(source_key="tropical-sharepoint", dry_run=False)
    # First call should hit the prior deltaLink URL
    assert http.get.call_args_list[0].args[0] == "https://graph/drives/drive-1/root/delta?token=prior"
    tok = store.get_delta_token("tropical-sharepoint")
    assert tok["delta_link"].endswith("token=new")


def test_deleted_item_marks_inventory_deleted(store: ConstructionStore) -> None:
    # Seed an active item
    store.upsert_inventory_item(
        source_key="tropical-sharepoint",
        drive_id="drive-1",
        item_id="a",
        name="file-a.txt",
        web_url=None,
        parent_path=None,
        size_bytes=10,
        is_folder=False,
        last_modified=None,
        etag=None,
    )
    http = MagicMock()
    http.get.return_value = _page(
        [{"id": "a", "deleted": {"state": "deleted"}}],
        delta_link="https://graph/drives/drive-1/root/delta?token=t",
    )
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=False)
    assert receipt.items_deleted == 1
    counts = store.count_inventory("tropical-sharepoint")
    assert counts == {"deleted": 1}


def test_unresolved_source_returns_unresolved_receipt(store: ConstructionStore) -> None:
    http = MagicMock()
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="hilltop-sharepoint", dry_run=True)
    assert receipt.status == "unresolved"
    assert receipt.drive_id is None
    http.get.assert_not_called()


def test_graph_error_yields_failed_receipt_with_sanitized_error(store: ConstructionStore) -> None:
    http = MagicMock()
    http.get.side_effect = GraphHttpError("GET", "/drives/drive-1/root/delta", 503, "service unavailable")
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=False)
    assert receipt.status == "failed"
    assert receipt.error_redacted is not None
    assert "graph_503" in receipt.error_redacted
    # Receipt is persisted even on failure (apply mode)
    receipts = store.list_recent_receipts("tropical-sharepoint")
    assert len(receipts) == 1
    assert receipts[0]["status"] == "failed"


def test_sample_items_carry_only_metadata(store: ConstructionStore) -> None:
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a", content="SECRET BODY", body="full text")],
        delta_link="https://graph/drives/drive-1/root/delta?token=t",
    )
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=True)
    sample = receipt.sample_items[0]
    forbidden = {"content", "body", "text", "excerpt"}
    leaks = forbidden & set(sample.keys())
    assert not leaks, f"sample leaked forbidden fields: {leaks}"


# =====================================================================
# Phase 02 scope-aware endpoint selection tests.
# =====================================================================


def _src(**overrides) -> SourceLocation:
    defaults = dict(
        source_key="sp_test",
        kind="sharepoint_project_drive_folder",
        display_name="Test",
    )
    defaults.update(overrides)
    return SourceLocation(**defaults)  # type: ignore[arg-type]


def test_select_endpoint_folder_scoped_for_project_drive_folder() -> None:
    src = _src(
        source_key="sp_2023projects_23_435_01_tropical_sl",
        kind="sharepoint_project_drive_folder",
        drive_id="drv-1",
        folder_item_id="folder-1",
    )
    endpoint, kind, drive, folder = _select_delta_endpoint(src)
    assert endpoint == "/drives/drv-1/items/folder-1/delta"
    assert kind == "folder_scoped"
    assert drive == "drv-1"
    assert folder == "folder-1"


def test_select_endpoint_drive_root_fallback_when_folder_item_id_missing() -> None:
    src = _src(
        source_key="sp_no_folder",
        kind="sharepoint_project_drive_folder",
        drive_id="drv-1",
    )
    endpoint, kind, drive, folder = _select_delta_endpoint(src)
    assert endpoint == "/drives/drv-1/root/delta"
    assert kind == "drive_root_fallback"
    assert folder is None


def test_select_endpoint_me_drive_for_onedrive_personal_root() -> None:
    src = _src(source_key="od_p", kind="onedrive_personal_root")
    endpoint, kind, drive, folder = _select_delta_endpoint(src)
    assert endpoint == "/me/drive/root/delta"
    assert kind == "me_drive_delta"


def test_select_endpoint_me_drive_for_onedrive_business_root() -> None:
    src = _src(source_key="od_b", kind="onedrive_business_root")
    endpoint, kind, drive, folder = _select_delta_endpoint(src)
    assert endpoint == "/me/drive/root/delta"
    assert kind == "me_drive_delta"


def test_select_endpoint_drive_root_for_shared_library_with_drive_id() -> None:
    src = _src(
        source_key="od_shared",
        kind="onedrive_shared_library",
        drive_id="drv-shared",
    )
    endpoint, kind, drive, folder = _select_delta_endpoint(src)
    assert endpoint == "/drives/drv-shared/root/delta"
    assert kind == "drive_root"


def test_select_endpoint_site_page_returns_none_with_unsupported_kind() -> None:
    src = _src(
        source_key="sp_page",
        kind="sharepoint_site_page",
        site_url="https://example.sharepoint.com/sites/Home",
    )
    endpoint, kind, drive, folder = _select_delta_endpoint(src)
    assert endpoint is None
    assert kind == "site_page_unsupported"


def test_site_page_scope_emits_skipped_receipt(tmp_path: Path) -> None:
    """When the registry has a site_page source, crawl returns a clean skipped receipt."""
    import tempfile
    import yaml as _yaml

    # Construct a temp registry override containing a site_page source the
    # registry loader will pick up via HB_CONSTRUCTION_SOURCES.
    tmp_yaml = tmp_path / "registry.yml"
    tmp_yaml.write_text(
        _yaml.safe_dump(
            {
                "projects": [{"project_key": "hilltop-gardens", "display_name": "HG"}],
                "sources": [
                    {
                        "source_key": "sp_hilltop_gardens_projecthome",
                        "project_key": "hilltop-gardens",
                        "kind": "sharepoint_site_page",
                        "display_name": "Hilltop Gardens ProjectHome",
                        "site_url": "https://example.sharepoint.com/sites/HilltopGardens",
                    }
                ],
            }
        )
    )

    import os
    prior = os.environ.get("HB_CONSTRUCTION_SOURCES")
    os.environ["HB_CONSTRUCTION_SOURCES"] = str(tmp_yaml)
    try:
        db = str(tmp_path / "c.sqlite")
        s = ConstructionStore(db)
        http = MagicMock()
        crawler = ConstructionDeltaCrawler(http, s)
        receipt = crawler.crawl(
            source_key="sp_hilltop_gardens_projecthome", dry_run=True
        )
    finally:
        if prior is None:
            del os.environ["HB_CONSTRUCTION_SOURCES"]
        else:
            os.environ["HB_CONSTRUCTION_SOURCES"] = prior

    assert receipt.status == "skipped_unsupported_scope"
    assert receipt.scope == "sharepoint_site_page"
    assert receipt.endpoint_kind == "site_page_unsupported"
    assert receipt.drive_id is None
    assert receipt.error_redacted is not None
    assert "page crawler" in receipt.error_redacted
    http.get.assert_not_called()


def test_receipt_carries_scope_and_endpoint_kind(
    tmp_path: Path, store: ConstructionStore
) -> None:
    """A successful crawl populates scope + endpoint_kind on the receipt."""
    import os
    import tempfile
    import yaml as _yaml

    tmp_yaml = tmp_path / "registry.yml"
    tmp_yaml.write_text(
        _yaml.safe_dump(
            {
                "projects": [{"project_key": "tropical", "display_name": "Tropical"}],
                "sources": [
                    {
                        "source_key": "tropical-sharepoint",
                        "project_key": "tropical",
                        "kind": "sharepoint_site",
                        "display_name": "Tropical site",
                    }
                ],
            }
        )
    )

    prior = os.environ.get("HB_CONSTRUCTION_SOURCES")
    os.environ["HB_CONSTRUCTION_SOURCES"] = str(tmp_yaml)
    try:
        http = MagicMock()
        http.get.return_value = _page(
            [_item("a")], delta_link="https://graph/drives/drive-1/root/delta?t=x"
        )
        crawler = ConstructionDeltaCrawler(http, store)
        receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=True)
    finally:
        if prior is None:
            del os.environ["HB_CONSTRUCTION_SOURCES"]
        else:
            os.environ["HB_CONSTRUCTION_SOURCES"] = prior

    assert receipt.status == "ok"
    assert receipt.scope == "sharepoint_site"
    assert receipt.endpoint_kind == "drive_root"
    assert receipt.drive_id == "drive-1"


# =====================================================================
# Baseline comparison integration tests (Phase 02 Prompt 04).
# =====================================================================


def _tropical_canonical_registry_yaml(tmp_path: Path):
    """Write a registry override carrying the canonical Tropical source."""
    import yaml as _yaml

    yaml_path = tmp_path / "registry.yml"
    yaml_path.write_text(
        _yaml.safe_dump(
            {
                "projects": [
                    {"project_key": "tropical", "display_name": "Tropical"}
                ],
                "sources": [
                    {
                        "source_key": "sp_2023projects_23_435_01_tropical_sl",
                        "project_key": "tropical",
                        "kind": "sharepoint_project_drive_folder",
                        "display_name": "Tropical canonical",
                        "site_id": "site-1",
                        "drive_id": "drive-1",
                        "folder_item_id": "folder-1",
                        "baseline": {
                            "baseline_status": "complete",
                            "baseline_unique_item_count": 8921,
                            "baseline_file_count": 7208,
                            "baseline_folder_count": 1713,
                            "baseline_file_size_gb": 39.78,
                        },
                    }
                ],
            }
        )
    )
    return yaml_path


def _with_canonical_registry(tmp_path: Path):
    """Context-manager helper: set HB_CONSTRUCTION_SOURCES to a temp registry."""
    import contextlib
    import os

    @contextlib.contextmanager
    def _ctx():
        yaml_path = _tropical_canonical_registry_yaml(tmp_path)
        prior = os.environ.get("HB_CONSTRUCTION_SOURCES")
        os.environ["HB_CONSTRUCTION_SOURCES"] = str(yaml_path)
        try:
            yield
        finally:
            if prior is None:
                del os.environ["HB_CONSTRUCTION_SOURCES"]
            else:
                os.environ["HB_CONSTRUCTION_SOURCES"] = prior

    return _ctx()


def test_crawl_dry_run_populates_baseline_comparison_when_source_has_baseline(
    tmp_path: Path,
) -> None:
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a")],
        delta_link="https://graph/drives/drive-1/items/folder-1/delta?token=t",
    )
    with _with_canonical_registry(tmp_path):
        crawler = ConstructionDeltaCrawler(http, store)
        receipt = crawler.crawl(
            source_key="sp_2023projects_23_435_01_tropical_sl", dry_run=True
        )

    assert receipt.status == "ok"
    assert receipt.endpoint_kind == "folder_scoped"
    assert receipt.baseline_comparison is not None
    # Dry-run never persists inventory, so the comparison reads an empty
    # store and classifies as "never_crawled" — historic counts are still
    # surfaced verbatim from the registry seed for operator visibility.
    assert receipt.baseline_comparison.status == "never_crawled"
    assert receipt.baseline_comparison.historic["unique_item_count"] == 8921
    # Dry-run also does not persist the comparison receipt.
    assert store.list_processing_receipts(
        source_id="sp_2023projects_23_435_01_tropical_sl"
    ) == []


def test_crawl_apply_persists_baseline_processing_receipt(tmp_path: Path) -> None:
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a")],
        delta_link="https://graph/drives/drive-1/items/folder-1/delta?token=t",
    )
    with _with_canonical_registry(tmp_path):
        crawler = ConstructionDeltaCrawler(http, store)
        receipt = crawler.crawl(
            source_key="sp_2023projects_23_435_01_tropical_sl", dry_run=False
        )

    assert receipt.status == "ok"
    assert receipt.baseline_comparison is not None

    rows = store.list_processing_receipts(
        source_id="sp_2023projects_23_435_01_tropical_sl"
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["operation"] == "baseline_comparison"
    assert row["status"] == receipt.baseline_comparison.status
    assert row["receipt_id"] == f"{receipt.run_id}:baseline_comparison"
    assert row["detail"]["historic"]["unique_item_count"] == 8921


def test_crawl_without_baseline_does_not_populate_comparison(
    store: ConstructionStore,
) -> None:
    """Legacy tropical-sharepoint has no baseline block; comparison stays None."""
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a")],
        delta_link="https://graph/drives/drive-1/root/delta?token=t",
    )
    crawler = ConstructionDeltaCrawler(http, store)
    receipt = crawler.crawl(source_key="tropical-sharepoint", dry_run=True)
    assert receipt.status == "ok"
    assert receipt.baseline_comparison is None


def test_failed_crawl_does_not_populate_baseline_comparison(tmp_path: Path) -> None:
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    http = MagicMock()
    http.get.side_effect = GraphHttpError(
        "GET", "/drives/drive-1/items/folder-1/delta", 503, "service unavailable"
    )
    with _with_canonical_registry(tmp_path):
        crawler = ConstructionDeltaCrawler(http, store)
        receipt = crawler.crawl(
            source_key="sp_2023projects_23_435_01_tropical_sl", dry_run=False
        )

    assert receipt.status == "failed"
    assert receipt.baseline_comparison is None
    assert store.list_processing_receipts(
        source_id="sp_2023projects_23_435_01_tropical_sl"
    ) == []


# =====================================================================
# Phase 02 Prompt 06 — OneDrive inventory-first crawl-side guardrails.
# =====================================================================


def _onedrive_canonical_registry_yaml(tmp_path: Path):
    import yaml as _yaml

    yaml_path = tmp_path / "onedrive_registry.yml"
    yaml_path.write_text(
        _yaml.safe_dump(
            {
                "projects": [],
                "sources": [
                    {
                        "source_key": "od_business_bobby_hedrickbrothers",
                        "kind": "onedrive_business_root",
                        "display_name": "Bobby - Hedrick Brothers OneDrive",
                        "drive_id": "drv-business",
                        "baseline_policy": {
                            "mode": "inventory_first",
                            "classify_project_matches": True,
                            "graph_delta_required": True,
                            "local_folder_watcher": "secondary_signal_only",
                            "require_review_for_sensitive": True,
                        },
                    },
                    {
                        "source_key": "od_personal_bobby",
                        "kind": "onedrive_personal_root",
                        "display_name": "Bobby - Personal OneDrive",
                        "drive_id": "drv-personal",
                        "baseline_policy": {
                            "mode": "inventory_first",
                            "classify_project_matches": False,
                            "require_review_for_sensitive": True,
                        },
                    },
                    {
                        "source_key": "od_shared_libraries_cloudtemp",
                        "kind": "onedrive_shared_library",
                        "display_name": "CloudTemp shared library",
                        "drive_id": "drv-shared",
                        "baseline_policy": {
                            "mode": "inventory_first",
                            "classify_project_matches": True,
                            "require_review_for_sensitive": True,
                        },
                    },
                ],
            }
        )
    )
    return yaml_path


def _with_onedrive_registry(tmp_path: Path):
    import contextlib
    import os

    @contextlib.contextmanager
    def _ctx():
        yaml_path = _onedrive_canonical_registry_yaml(tmp_path)
        prior = os.environ.get("HB_CONSTRUCTION_SOURCES")
        os.environ["HB_CONSTRUCTION_SOURCES"] = str(yaml_path)
        try:
            yield
        finally:
            if prior is None:
                del os.environ["HB_CONSTRUCTION_SOURCES"]
            else:
                os.environ["HB_CONSTRUCTION_SOURCES"] = prior

    return _ctx()


ONEDRIVE_SOURCE_KEYS = (
    "od_business_bobby_hedrickbrothers",
    "od_personal_bobby",
    "od_shared_libraries_cloudtemp",
)


def test_onedrive_crawl_receipt_carries_no_forbidden_keys(tmp_path: Path) -> None:
    from hb_assistant.construction.policy import assert_no_full_text_extraction

    for source_key in ONEDRIVE_SOURCE_KEYS:
        db = str(tmp_path / f"{source_key}.sqlite")
        store = ConstructionStore(db)
        http = MagicMock()
        http.get.return_value = _page(
            [_item("a")],
            delta_link=f"https://graph/drives/.../delta?token={source_key}",
        )
        with _with_onedrive_registry(tmp_path):
            crawler = ConstructionDeltaCrawler(http, store)
            receipt = crawler.crawl(source_key=source_key, dry_run=True)

        assert receipt.status == "ok", f"{source_key}: {receipt.error_redacted}"
        # Defense-in-depth: sample_items must not carry any forbidden body/text key.
        assert_no_full_text_extraction(receipt.sample_items)


def test_onedrive_crawl_does_not_produce_document_cards(tmp_path: Path) -> None:
    import sqlite3

    for source_key in ONEDRIVE_SOURCE_KEYS:
        db = str(tmp_path / f"{source_key}_cards.sqlite")
        store = ConstructionStore(db)
        http = MagicMock()
        http.get.return_value = _page(
            [_item("a"), _item("b")],
            delta_link=f"https://graph/drives/.../delta?t={source_key}",
        )
        with _with_onedrive_registry(tmp_path):
            crawler = ConstructionDeltaCrawler(http, store)
            crawler.crawl(source_key=source_key, dry_run=False)

        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT card_id FROM construction_document_cards"
        ).fetchall()
        assert rows == [], (
            f"OneDrive crawl for {source_key} unexpectedly created document cards: {rows}"
        )


def test_onedrive_crawl_records_metadata_only_per_inventory_first_policy(
    tmp_path: Path,
) -> None:
    """Apply-mode crawl writes only metadata columns — no body/text/excerpt fields."""
    import sqlite3

    source_key = "od_business_bobby_hedrickbrothers"
    db = str(tmp_path / "od_metadata.sqlite")
    store = ConstructionStore(db)
    http = MagicMock()
    http.get.return_value = _page(
        [_item("a"), _item("b", folder={"childCount": 0})],
        delta_link="https://graph/drives/.../delta?t=metadata-only",
    )
    with _with_onedrive_registry(tmp_path):
        crawler = ConstructionDeltaCrawler(http, store)
        receipt = crawler.crawl(source_key=source_key, dry_run=False)

    assert receipt.status == "ok"
    assert receipt.items_new == 2

    # Inspect the actual inventory schema columns; no body/text/excerpt etc.
    conn = sqlite3.connect(db)
    cur = conn.execute("PRAGMA table_info(construction_drive_item_inventory)")
    columns = {row[1] for row in cur.fetchall()}
    forbidden = {"body", "content", "text", "excerpt", "preview", "full_text", "text_excerpt"}
    leaks = columns & forbidden
    assert not leaks, f"OneDrive inventory schema leaks: {leaks}"


# ---------------------------------------------------------------------------
# Phase 03 entry: per-source-kind delegated scope selection.
# ---------------------------------------------------------------------------


def test_scopes_for_source_kind_drive_folder_excludes_sites_read_all() -> None:
    """Drive/folder sources should NOT request Sites.Read.All — that scope is
    needed only for SharePoint site-page resolution. Including it would block
    MSAL silent token acquisition in tenants that haven't admin-consented it.
    """
    from hb_assistant.construction.graph import (
        GRAPH_SCOPES_DRIVE,
        scopes_for_source_kind,
    )

    for kind in (
        "sharepoint_project_drive_folder",
        "sharepoint_site",
        "sharepoint_library",
        "onedrive_business_root",
        "onedrive_personal_root",
        "onedrive_shared_library",
        "onedrive_personal",
        "onedrive_shared",
    ):
        scopes = scopes_for_source_kind(kind)
        assert "Sites.Read.All" not in scopes, (
            f"kind={kind!r}: drive-/folder-scoped delta endpoints don't need "
            f"Sites.Read.All; including it blocks login in tenants that haven't "
            f"admin-consented it. Got scopes: {scopes!r}"
        )
        assert "Files.ReadWrite.All" in scopes
        assert "User.Read" in scopes
        assert scopes == list(GRAPH_SCOPES_DRIVE)


def test_scopes_for_source_kind_site_page_includes_sites_read_all() -> None:
    """Site-page sources (Hilltop Gardens ProjectHome) DO need Sites.Read.All
    to enumerate the page and discover linked libraries.
    """
    from hb_assistant.construction.graph import (
        GRAPH_SCOPES_SITE_PAGE,
        scopes_for_source_kind,
    )

    scopes = scopes_for_source_kind("sharepoint_site_page")
    assert "Sites.Read.All" in scopes
    assert "Files.ReadWrite.All" in scopes
    assert "User.Read" in scopes
    assert scopes == list(GRAPH_SCOPES_SITE_PAGE)
