"""Phase 06 (Files) Prompt 06 — rich driveItem normalization + V5 indexing.

Covers item-5 scenarios (file, folder, package, moved/renamed, deleted, missing
optional fields), the downloadUrl-drop proof, the V15 rich-column upsert round-trip
+ idempotency, the indexer (mocked http), and the CLI surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config.models import SourceLocation
from hb_assistant.construction.graph.drive_item_indexer import (
    DriveItemIndexer,
    normalize_drive_item,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()


def _file_item() -> dict:
    return {
        "id": "F1",
        "name": "RFI-001.pdf",
        "webUrl": "https://h/RFI-001.pdf",
        "size": 1234,
        "createdDateTime": "2026-01-01T00:00:00Z",
        "lastModifiedDateTime": "2026-02-01T00:00:00Z",
        "eTag": "etag-1",
        "cTag": "ctag-1",
        "file": {"mimeType": "application/pdf", "hashes": {"quickXorHash": "QXH=="}},
        "parentReference": {"driveId": "D1", "id": "PARENT1", "path": "/drive/root:/07-RFI"},
        "sharepointIds": {"siteId": "S1", "webId": "W1", "listId": "L1", "listItemId": "LI1"},
        "@microsoft.graph.downloadUrl": "https://signed.example/secret-token-blob",
    }


# --- normalization (item 5 scenarios) -----------------------------------------


def test_normalize_file() -> None:
    k = normalize_drive_item("src", "D1", _file_item())
    assert k["is_file"] is True and k["is_folder"] is False and k["is_package"] is False
    assert k["mime_type"] == "application/pdf"
    assert k["file_extension"] == "pdf"
    assert k["quick_xor_hash"] == "QXH=="
    assert json.loads(k["file_hashes_json"]) == {"quickXorHash": "QXH=="}
    assert k["e_tag"] == "etag-1" and k["c_tag"] == "ctag-1"
    assert k["created_datetime"] == "2026-01-01T00:00:00Z"
    assert k["parent_reference_path"] == "/drive/root:/07-RFI"
    assert k["sharepoint_web_id"] == "W1" and k["list_item_id"] == "LI1"


def test_normalize_folder() -> None:
    k = normalize_drive_item(
        "src", "D1", {"id": "FO1", "name": "07-RFI", "folder": {"childCount": 12}}
    )
    assert k["is_folder"] is True and k["is_file"] is False
    assert k["folder_child_count"] == 12


def test_normalize_package() -> None:
    k = normalize_drive_item(
        "src", "D1", {"id": "P1", "name": "Notebook", "package": {"type": "oneNote"}}
    )
    assert k["is_package"] is True
    assert k["is_file"] is False and k["is_folder"] is False
    assert json.loads(k["package_json_redacted"]) == {"type": "oneNote"}


def test_normalize_moved_renamed_captures_new_path_and_etag() -> None:
    raw = _file_item()
    raw["name"] = "RFI-001-renamed.pdf"
    raw["parentReference"]["path"] = "/drive/root:/15-Submittal"
    raw["eTag"] = "etag-2"
    k = normalize_drive_item("src", "D1", raw)
    assert k["name"] == "RFI-001-renamed.pdf"
    assert k["parent_reference_path"] == "/drive/root:/15-Submittal"
    assert k["e_tag"] == "etag-2"


def test_normalize_deleted_facet() -> None:
    k = normalize_drive_item(
        "src", "D1", {"id": "X", "name": "gone.pdf", "deleted": {"state": "deleted"}}
    )
    assert k["deleted"] is True


def test_normalize_missing_optional_fields() -> None:
    k = normalize_drive_item("src", "D1", {"id": "MIN"})
    assert k["drive_item_id"] == "MIN"
    assert k["is_file"] is False and k["is_folder"] is False and k["is_package"] is False
    assert k["mime_type"] is None and k["size_bytes"] is None and k["deleted"] is False


# --- downloadUrl drop ----------------------------------------------------------


def test_download_url_is_never_in_normalized_output() -> None:
    k = normalize_drive_item("src", "D1", _file_item())
    blob = json.dumps(k)
    assert "downloadUrl" not in blob and "downloadurl" not in blob.lower()
    assert "secret-token-blob" not in blob
    assert not any("downloadurl" in str(key).lower() for key in k)


# --- V15 rich-column upsert round-trip + idempotency --------------------------


def test_upsert_persists_rich_columns_and_drops_download_url(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "di.sqlite"))
    k = normalize_drive_item("od_business_bobby_hedrickbrothers", "D1", _file_item())
    # source_id must reference an existing source_location row (FK). Project the seed first.
    from hb_assistant.construction.config import load_source_registry
    from hb_assistant.construction.source_projection import (
        project_registry_to_v5_source_locations,
    )

    project_registry_to_v5_source_locations(load_source_registry(), store)
    store.upsert_drive_item(**k)
    row = store.get_drive_item(source_id="od_business_bobby_hedrickbrothers", drive_item_id="F1")
    assert row is not None
    assert row["is_file"] is True
    assert row["mime_type"] == "application/pdf"
    assert row["e_tag"] == "etag-1"
    assert row["sharepoint_web_id"] == "W1"
    assert row["first_seen_utc"] is not None and row["last_seen_utc"] is not None
    # No column value anywhere contains the signed download URL.
    assert "secret-token-blob" not in json.dumps(row)


def test_upsert_idempotent_preserves_first_seen(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "di.sqlite"))
    from hb_assistant.construction.config import load_source_registry
    from hb_assistant.construction.source_projection import (
        project_registry_to_v5_source_locations,
    )

    project_registry_to_v5_source_locations(load_source_registry(), store)
    k = normalize_drive_item("od_business_bobby_hedrickbrothers", "D1", _file_item())
    store.upsert_drive_item(**k)
    first = store.get_drive_item(source_id="od_business_bobby_hedrickbrothers", drive_item_id="F1")
    store.upsert_drive_item(**k)
    second = store.get_drive_item(source_id="od_business_bobby_hedrickbrothers", drive_item_id="F1")
    assert first["first_seen_utc"] == second["first_seen_utc"]
    assert len(store.list_drive_items(source_id="od_business_bobby_hedrickbrothers")) == 1


# --- indexer (mocked http) -----------------------------------------------------


def _od_source() -> SourceLocation:
    return SourceLocation(
        source_key="od_business_bobby_hedrickbrothers",
        kind="onedrive_business_root",
        display_name="Biz",
    )


def test_indexer_dry_run_writes_nothing(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "di.sqlite"))
    http = MagicMock()
    # resolver /me/drive (http.get), then index /me/drive/root/delta (http.get_all_pages).
    http.get.side_effect = [{"id": "D-BIZ", "webUrl": "https://od", "driveType": "business"}]
    http.get_all_pages.return_value = iter(
        [_file_item(), {"id": "FO1", "name": "07-RFI", "folder": {"childCount": 1}}]
    )
    report = DriveItemIndexer(http, store=store).index(_od_source(), dry_run=True)
    assert report.status == "indexed"
    assert report.items_seen == 2
    assert report.items_persisted == 0
    assert report.download_url_persisted is False
    assert store.list_drive_items(source_id="od_business_bobby_hedrickbrothers") == []


def test_indexer_apply_persists(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "di.sqlite"))
    from hb_assistant.construction.config import load_source_registry
    from hb_assistant.construction.source_projection import (
        project_registry_to_v5_source_locations,
    )

    project_registry_to_v5_source_locations(load_source_registry(), store)
    http = MagicMock()
    http.get.side_effect = [{"id": "D-BIZ", "webUrl": "https://od", "driveType": "business"}]
    http.get_all_pages.return_value = iter([_file_item()])
    report = DriveItemIndexer(http, store=store).index(_od_source(), dry_run=False)
    assert report.items_persisted == 1
    rows = store.list_drive_items(source_id="od_business_bobby_hedrickbrothers")
    assert len(rows) == 1 and rows[0]["drive_item_id"] == "F1"
    # apply also writes a drive_item_index receipt.
    receipts = store.list_processing_receipts(source_id="od_business_bobby_hedrickbrothers")
    assert any(r["operation"] == "drive_item_index" for r in receipts)


# --- CLI -----------------------------------------------------------------------


def test_cli_index_runs_with_mocked_client(monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    http.get.side_effect = [{"id": "D-BIZ", "webUrl": "https://od", "driveType": "business"}]
    http.get_all_pages.return_value = iter([_file_item()])
    http.close = MagicMock()
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth", lambda scopes: (http, None)
    )
    result = runner.invoke(
        app, ["files", "index", "--source", "od_business_bobby_hedrickbrothers", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files index"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["download_url_persisted"] is False


def test_cli_index_degrades_to_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth",
        lambda scopes: (None, {"status": "auth_required", "scopes": scopes, "detail": "no token"}),
    )
    result = runner.invoke(
        app, ["files", "index", "--source", "sp_2023projects_23_435_01_tropical_sl", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "auth_required"
