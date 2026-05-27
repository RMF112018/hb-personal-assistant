"""Synthetic Graph /delta response fixtures.

Every payload is metadata-only: name + parent path + drive-item identifiers
only — no ``content``, ``body``, or any text-extraction field. IDs are
obviously fake (``fake-item-NNNN``, ``fake-drive-NNNN``) so they cannot be
confused with real tenant data.

Fixtures are dicts mirroring the Microsoft Graph drive-item delta
envelope. They support testing the crawler's pagination + tombstone
handling without contacting Graph.
"""

from __future__ import annotations

from typing import Any

_FAKE_DRIVE = "fake-drive-0001"


def _item(item_id: str, name: str, parent_path: str, *, deleted: bool = False) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": item_id,
        "name": name,
        "parentReference": {
            "driveId": _FAKE_DRIVE,
            "path": parent_path,
        },
        "size": 1024,
        "lastModifiedDateTime": "2026-04-01T12:00:00Z",
        "eTag": f'"{item_id}-etag"',
    }
    if deleted:
        row["deleted"] = {"state": "deleted"}
    else:
        row["file"] = {"mimeType": "application/pdf"}
    return row


SINGLE_PAGE: dict[str, Any] = {
    "value": [
        _item("fake-item-0001", "Daily Log 2026-04-01.pdf",
              "/drives/fake-drive-0001/root:/Tropical/Daily Logs"),
        _item("fake-item-0002", "RFI 0042 - Roof Detail.pdf",
              "/drives/fake-drive-0001/root:/Tropical/RFIs"),
    ],
    "@odata.deltaLink": (
        "https://graph.microsoft.com/v1.0/drives/fake-drive-0001/root/delta"
        "?token=FAKE-DELTA-TOKEN-001"
    ),
}


PAGINATED_PAGE_1: dict[str, Any] = {
    "value": [
        _item("fake-item-0010", "Submittal 0011.pdf",
              "/drives/fake-drive-0001/root:/Tropical/Submittals"),
        _item("fake-item-0011", "Drawing A-100.pdf",
              "/drives/fake-drive-0001/root:/Tropical/Drawings"),
    ],
    "@odata.nextLink": (
        "https://graph.microsoft.com/v1.0/drives/fake-drive-0001/root/delta"
        "?token=FAKE-NEXT-PAGE-002"
    ),
}

PAGINATED_PAGE_2: dict[str, Any] = {
    "value": [
        _item("fake-item-0012", "Punch List 04-15.pdf",
              "/drives/fake-drive-0001/root:/Tropical/Punch"),
    ],
    "@odata.deltaLink": (
        "https://graph.microsoft.com/v1.0/drives/fake-drive-0001/root/delta"
        "?token=FAKE-DELTA-TOKEN-002"
    ),
}


WITH_DELETIONS: dict[str, Any] = {
    "value": [
        _item("fake-item-0020", "Site Photos 2026-04-12.zip",
              "/drives/fake-drive-0001/root:/Tropical/General"),
        _item("fake-item-0021", "Removed File.pdf",
              "/drives/fake-drive-0001/root:/Tropical/General",
              deleted=True),
        _item("fake-item-0022", "Active File.pdf",
              "/drives/fake-drive-0001/root:/Tropical/General"),
    ],
    "@odata.deltaLink": (
        "https://graph.microsoft.com/v1.0/drives/fake-drive-0001/root/delta"
        "?token=FAKE-DELTA-TOKEN-003"
    ),
}


# name -> payload
GRAPH_DELTA_FIXTURES: dict[str, dict[str, Any]] = {
    "single_page": SINGLE_PAGE,
    "paginated_page_1": PAGINATED_PAGE_1,
    "paginated_page_2": PAGINATED_PAGE_2,
    "with_deletions": WITH_DELETIONS,
}
