"""Tests for the construction-agent Graph source resolver."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from hb_assistant.construction.config import SourceLocation
from hb_assistant.construction.graph.resolver import (
    ConstructionGraphResolver,
    _parse_sharepoint_url,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError


def _make_source(
    *,
    kind: str = "sharepoint_site",
    site_url: str | None = None,
    source_key: str = "tropical-sharepoint",
) -> SourceLocation:
    return SourceLocation(
        source_key=source_key,
        kind=kind,  # type: ignore[arg-type]
        display_name="Test",
        site_url=site_url,
    )


def test_parse_sharepoint_url_basic() -> None:
    host, path = _parse_sharepoint_url("https://contoso.sharepoint.com/sites/Tropical")
    assert host == "contoso.sharepoint.com"
    assert path == "/sites/Tropical"


def test_parse_sharepoint_url_url_encoded() -> None:
    host, path = _parse_sharepoint_url(
        "https://contoso.sharepoint.com/sites/Tropical%20Pointe/"
    )
    assert host == "contoso.sharepoint.com"
    assert path == "/sites/Tropical Pointe"


def test_parse_sharepoint_url_missing_path_raises() -> None:
    with pytest.raises(ValueError):
        _parse_sharepoint_url("https://contoso.sharepoint.com")


def test_resolve_sharepoint_site_happy_path() -> None:
    http = MagicMock()
    http.get.side_effect = [
        {"id": "contoso.sharepoint.com,site-guid", "webUrl": "https://contoso.sharepoint.com/sites/Tropical"},
        {"id": "b!drive-guid", "webUrl": "https://contoso.sharepoint.com/sites/Tropical/Documents"},
    ]
    resolver = ConstructionGraphResolver(http)
    source = _make_source(site_url="https://contoso.sharepoint.com/sites/Tropical")
    result = resolver.resolve(source)

    assert result.status == "resolved"
    assert result.site_id == "contoso.sharepoint.com,site-guid"
    assert result.drive_id == "b!drive-guid"
    assert result.web_url == "https://contoso.sharepoint.com/sites/Tropical"

    # Verify request shape: /sites/{host}:{path} then /sites/{id}/drive
    first_call = http.get.call_args_list[0]
    assert first_call.args[0] == "/sites/contoso.sharepoint.com:/sites/Tropical"
    second_call = http.get.call_args_list[1]
    assert second_call.args[0] == "/sites/contoso.sharepoint.com,site-guid/drive"


def test_resolve_sharepoint_site_pending_when_no_site_url() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    result = resolver.resolve(_make_source(site_url=None))
    assert result.status == "pending"
    http.get.assert_not_called()


def test_resolve_sharepoint_site_graph_error_is_sanitized() -> None:
    http = MagicMock()
    http.get.side_effect = GraphHttpError("GET", "/sites/x", 404, "site not found")
    resolver = ConstructionGraphResolver(http)
    result = resolver.resolve(_make_source(site_url="https://x.sharepoint.com/sites/Missing"))
    assert result.status == "error"
    assert result.error_redacted is not None
    assert "graph_404" in result.error_redacted


def test_resolve_onedrive_personal_happy_path() -> None:
    http = MagicMock()
    http.get.return_value = {"id": "drive-bobby", "webUrl": "https://onedrive.live.com/?id=root"}
    resolver = ConstructionGraphResolver(http)
    source = _make_source(kind="onedrive_personal", source_key="bobby-onedrive")
    result = resolver.resolve(source)
    assert result.status == "resolved"
    assert result.drive_id == "drive-bobby"
    http.get.assert_called_once()
    assert http.get.call_args.args[0] == "/me/drive"


def test_legacy_onedrive_shared_now_dispatches_to_shared_library_handler() -> None:
    # Pre Phase 02, kind="onedrive_shared" returned status="unsupported".
    # Phase 02 routes it through the shared-library handler: without a
    # pre-populated drive_id it returns status="pending" with the
    # documented note and no Graph HTTP call.
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    source = _make_source(kind="onedrive_shared", source_key="shared")
    result = resolver.resolve(source)
    assert result.status == "pending"
    assert result.note == "drive_id_resolution_requires_share_url_or_remote_item_lookup"
    http.get.assert_not_called()


def test_resolve_apply_persists_to_store(tmp_path: Path) -> None:
    http = MagicMock()
    http.get.return_value = {"id": "drive-bobby", "webUrl": "https://x"}
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    resolver = ConstructionGraphResolver(http, store=store)
    source = _make_source(kind="onedrive_personal", source_key="bobby-onedrive")
    resolver.resolve(source, apply=True)

    row = store.get_resolution("bobby-onedrive")
    assert row is not None
    assert row["drive_id"] == "drive-bobby"
    assert row["resolution_status"] == "resolved"


def test_resolve_dry_run_does_not_persist(tmp_path: Path) -> None:
    http = MagicMock()
    http.get.return_value = {"id": "drive-bobby", "webUrl": "https://x"}
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    resolver = ConstructionGraphResolver(http, store=store)
    source = _make_source(kind="onedrive_personal", source_key="bobby-onedrive")
    resolver.resolve(source, apply=False)

    assert store.get_resolution("bobby-onedrive") is None


# =====================================================================
# Phase 02 scope-aware dispatcher tests.
# =====================================================================


def _make_canonical_project_drive_folder(**overrides) -> SourceLocation:
    defaults = dict(
        source_key="sp_2023projects_23_435_01_tropical_sl",
        kind="sharepoint_project_drive_folder",
        display_name="23-435-01 Tropical - S L",
        site_url="https://hedrickbrotherscom.sharepoint.com/sites/2023Projects",
        site_id="b1abbdda-da3b-4fd1-a038-c4aeb13ba951",
        drive_id="b!2r2rsTva0U-gOMSusTupUT0Ecgn6KG9CrTXQO7ex9-wjlyM1iYsETbs3ktNIMr0B",
        folder_item_id="01KUIR4CV3RKZL4MURNRKY6DWASR3B7EGM",
        folder_path="/23-435-01Tropical -S L",
        folder_web_url="https://hedrickbrotherscom.sharepoint.com/sites/2023Projects/Shared%20Documents/23-435-01Tropical%20-S%20L",
    )
    defaults.update(overrides)
    return SourceLocation(**defaults)  # type: ignore[arg-type]


def test_resolve_project_drive_folder_pre_resolved() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    source = _make_canonical_project_drive_folder()
    result = resolver.resolve(source)

    assert result.status == "pre_resolved"
    assert result.pre_resolved is True
    assert result.scope == "sharepoint_project_drive_folder"
    assert result.site_id == source.site_id
    assert result.drive_id == source.drive_id
    assert result.folder_item_id == source.folder_item_id
    http.get.assert_not_called()


def test_resolve_project_drive_folder_resolves_folder_item_id_when_missing() -> None:
    http = MagicMock()
    http.get.side_effect = [
        {"id": "drv-resolved", "webUrl": "https://example/drive"},
        {"id": "folder-resolved", "webUrl": "https://example/folder", "name": "Folder"},
    ]
    resolver = ConstructionGraphResolver(http)
    source = _make_canonical_project_drive_folder(
        site_id="site-pre",
        drive_id=None,
        folder_item_id=None,
        folder_path="/Folder",
    )
    result = resolver.resolve(source)

    assert result.status == "resolved"
    assert result.site_id == "site-pre"
    assert result.drive_id == "drv-resolved"
    assert result.folder_item_id == "folder-resolved"
    assert result.scope == "sharepoint_project_drive_folder"
    # Two HTTP calls: /sites/.../drive then /drives/<id>/root:/Folder
    assert http.get.call_count == 2


def test_resolve_project_drive_folder_pending_when_site_url_missing() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    source = SourceLocation(
        source_key="sp_no_url",
        kind="sharepoint_project_drive_folder",  # type: ignore[arg-type]
        display_name="No URL",
    )
    result = resolver.resolve(source)
    assert result.status == "pending"
    assert "site_url" in (result.error_redacted or "")
    http.get.assert_not_called()


def test_resolve_site_page_resolves_site_id_only() -> None:
    http = MagicMock()
    http.get.return_value = {"id": "site-hilltop", "webUrl": "https://example/site"}
    resolver = ConstructionGraphResolver(http)
    source = SourceLocation(
        source_key="sp_hilltop_gardens_projecthome",
        kind="sharepoint_site_page",  # type: ignore[arg-type]
        display_name="Hilltop Gardens ProjectHome",
        site_url="https://hedrickbrotherscom.sharepoint.com/sites/HilltopGardens",
        page_url="https://hedrickbrotherscom.sharepoint.com/sites/HilltopGardens/SitePages/ProjectHome.aspx",
    )
    result = resolver.resolve(source)
    assert result.status == "pending"
    assert result.site_id == "site-hilltop"
    assert result.note == "page_id_resolution_deferred_to_page_crawler"
    assert result.scope == "sharepoint_site_page"


def test_resolve_onedrive_business_root_records_drive_type() -> None:
    http = MagicMock()
    http.get.return_value = {
        "id": "drive-biz",
        "webUrl": "https://onedrive/biz",
        "driveType": "business",
    }
    resolver = ConstructionGraphResolver(http)
    source = SourceLocation(
        source_key="od_business_bobby",
        kind="onedrive_business_root",  # type: ignore[arg-type]
        display_name="Bobby business",
    )
    result = resolver.resolve(source)
    assert result.status == "resolved"
    assert result.drive_id == "drive-biz"
    assert "drive_type='business'" in (result.note or "")
    http.get.assert_called_once_with(
        "/me/drive",
        params={"$select": "id,webUrl,driveType"},
        scopes=resolver._http.get.call_args.kwargs["scopes"],
    )


def test_resolve_onedrive_personal_root_records_drive_type() -> None:
    http = MagicMock()
    http.get.return_value = {
        "id": "drive-personal",
        "webUrl": "https://onedrive/personal",
        "driveType": "personal",
    }
    resolver = ConstructionGraphResolver(http)
    source = SourceLocation(
        source_key="od_personal_bobby",
        kind="onedrive_personal_root",  # type: ignore[arg-type]
        display_name="Bobby personal",
    )
    result = resolver.resolve(source)
    assert result.status == "resolved"
    assert result.drive_id == "drive-personal"
    assert "drive_type='personal'" in (result.note or "")


def test_resolve_onedrive_shared_library_pre_resolved_when_drive_id_present() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    source = SourceLocation(
        source_key="od_shared_cloudtemp",
        kind="onedrive_shared_library",  # type: ignore[arg-type]
        display_name="CloudTemp",
        drive_id="drv-cloudtemp",
    )
    result = resolver.resolve(source)
    assert result.status == "pre_resolved"
    assert result.pre_resolved is True
    assert result.drive_id == "drv-cloudtemp"
    http.get.assert_not_called()


def test_resolve_onedrive_shared_library_pending_when_drive_id_missing() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    source = SourceLocation(
        source_key="od_shared_unknown",
        kind="onedrive_shared_library",  # type: ignore[arg-type]
        display_name="Unknown shared",
    )
    result = resolver.resolve(source)
    assert result.status == "pending"
    assert result.note == "drive_id_resolution_requires_share_url_or_remote_item_lookup"
    http.get.assert_not_called()


def test_resolver_dispatcher_covers_all_canonical_kinds() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    expected = {
        "sharepoint_site",
        "sharepoint_library",
        "sharepoint_project_drive_folder",
        "sharepoint_site_page",
        "onedrive_personal",
        "onedrive_personal_root",
        "onedrive_business_root",
        "onedrive_shared",
        "onedrive_shared_library",
    }
    assert expected.issubset(resolver.supported_kinds())


def test_pre_resolved_status_normalizes_to_resolved_in_store(tmp_path: Path) -> None:
    http = MagicMock()
    db = str(tmp_path / "c.sqlite")
    store = ConstructionStore(db)
    resolver = ConstructionGraphResolver(http, store=store)
    source = _make_canonical_project_drive_folder()
    result = resolver.resolve(source, apply=True)
    assert result.status == "pre_resolved"
    # Persisted row uses the legacy "resolved" label so the V2 schema's
    # resolution_status enum stays unchanged.
    row = store.get_resolution(source.source_key)
    assert row is not None
    assert row["resolution_status"] == "resolved"
    assert row["site_id"] == source.site_id
    assert row["drive_id"] == source.drive_id
    http.get.assert_not_called()
