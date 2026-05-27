"""Tests for the construction-agent Graph delta crawler."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hb_assistant.construction.graph.delta_crawler import ConstructionDeltaCrawler
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
