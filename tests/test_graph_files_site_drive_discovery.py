"""Phase 06 (Files) Prompt 04 — SharePoint site + drive discovery.

Mirrors the resolver test mocking pattern (MagicMock http client with
``.get.side_effect``). Covers site resolution (pre-seeded fast-path + URL
resolution), drive enumeration + matching precedence, ProjectHome linked-source
candidates (metadata-only), the read-only guard on the enumeration path, receipt
persistence (dry-run vs apply), and the CLI surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config.models import SourceLocation
from hb_assistant.construction.graph.site_drive_discovery import (
    DriveCandidate,
    SiteDriveDiscovery,
    _match_drive,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.files_endpoint_guard import (
    FileMutationBlockedError,
    assert_files_request_allowed,
)

runner = CliRunner()

_HOST = "https://hedrickbrotherscom.sharepoint.com/sites/2023Projects"


def _pre_resolved_folder(**over) -> SourceLocation:
    base = dict(
        source_key="sp_proj",
        kind="sharepoint_project_drive_folder",
        display_name="Proj",
        site_url=_HOST,
        site_id="S1",
        drive_id="D2",
        folder_item_id="F1",
    )
    base.update(over)
    return SourceLocation(**base)


# --- site resolution -----------------------------------------------------------


def test_discover_site_pre_resolved_makes_no_http_call() -> None:
    http = MagicMock()
    disco = SiteDriveDiscovery(http)
    result = disco.discover_site(_pre_resolved_folder())
    assert result.status == "pre_resolved"
    assert result.pre_resolved is True
    assert result.site_id == "S1"
    http.get.assert_not_called()


def test_discover_site_resolves_by_url() -> None:
    http = MagicMock()
    http.get.side_effect = [
        {"id": "SITE9", "webUrl": _HOST, "name": "2023Projects"},  # /sites/{host}:{path}
        {"id": "DRV9", "webUrl": _HOST},  # /sites/{id}/drive
    ]
    src = SourceLocation(
        source_key="sp_site", kind="sharepoint_site", display_name="Site", site_url=_HOST
    )
    result = SiteDriveDiscovery(http).discover_site(src)
    assert result.status == "resolved"
    assert result.site_id == "SITE9"
    assert result.hostname == "hedrickbrotherscom.sharepoint.com"
    assert result.server_relative_path == "/sites/2023Projects"


def test_discover_site_unsupported_for_onedrive() -> None:
    src = SourceLocation(
        source_key="od_x", kind="onedrive_business_root", display_name="OD"
    )
    result = SiteDriveDiscovery(MagicMock()).discover_site(src)
    assert result.status == "unsupported"


# --- drive enumeration + matching ---------------------------------------------


def _drives_payload() -> dict:
    return {
        "value": [
            {"id": "D1", "name": "Documents", "webUrl": f"{_HOST}/Shared%20Documents",
             "driveType": "documentLibrary"},
            {"id": "D2", "name": "Project Files", "webUrl": f"{_HOST}/ProjectFiles",
             "driveType": "documentLibrary"},
        ]
    }


def test_discover_drives_matches_by_drive_id() -> None:
    http = MagicMock()
    http.get.side_effect = [_drives_payload()]  # pre_resolved source → only the drives enum
    result = SiteDriveDiscovery(http).discover_drives(_pre_resolved_folder(drive_id="D2"))
    assert result.status == "matched"
    assert result.matched_drive is not None
    assert result.matched_drive.drive_id == "D2"
    assert result.match_method == "drive_id"
    assert result.match_confidence == "high"
    assert len(result.candidates) == 2


def test_discover_drives_unmatched_when_no_signal() -> None:
    http = MagicMock()
    http.get.side_effect = [_drives_payload()]
    # drive_id D9 not present, no library_name/list_id/webUrl match.
    result = SiteDriveDiscovery(http).discover_drives(_pre_resolved_folder(drive_id="D9"))
    assert result.status == "unmatched"
    assert result.matched_drive is None
    assert result.match_confidence == "none"


def test_discover_drives_site_page_returns_linked_candidates() -> None:
    http = MagicMock()
    http.get.side_effect = [
        {"value": [{"id": "pg1", "name": "ProjectHome.aspx",
                    "webUrl": "https://hedrickbrotherscom.sharepoint.com/sites/HG/SitePages/ProjectHome.aspx"}]},
        {"value": [{"id": "lib1", "name": "Documents", "webUrl": "https://hg/docs",
                    "driveType": "documentLibrary"}]},
    ]
    src = SourceLocation(
        source_key="sp_page",
        kind="sharepoint_site_page",
        display_name="HG",
        site_url="https://hedrickbrotherscom.sharepoint.com/sites/HG",
        site_id="SITEHG",
        page_url="https://hedrickbrotherscom.sharepoint.com/sites/HG/SitePages/ProjectHome.aspx",
    )
    result = SiteDriveDiscovery(http).discover_drives(src)
    assert result.linked_sources
    assert all(c["deep_index_allowed"] is False for c in result.linked_sources)


def test_discover_drives_unsupported_for_onedrive() -> None:
    src = SourceLocation(source_key="od_y", kind="onedrive_personal_root", display_name="OD")
    result = SiteDriveDiscovery(MagicMock()).discover_drives(src)
    assert result.status == "unsupported"


# --- pure matching precedence --------------------------------------------------


def _cands() -> list[DriveCandidate]:
    return [
        DriveCandidate(drive_id="D1", name="Documents", web_url="https://h/docs", list_id="L1"),
        DriveCandidate(drive_id="D2", name="Project Files", web_url="https://h/proj", list_id="L2"),
    ]


def test_match_by_list_id() -> None:
    src = SourceLocation(source_key="s", kind="sharepoint_library", display_name="s", list_id="L2")
    matched, method, conf = _match_drive(src, _cands())
    assert matched.drive_id == "D2" and method == "list_id" and conf == "high"


def test_match_by_library_name() -> None:
    src = SourceLocation(
        source_key="s", kind="sharepoint_library", display_name="s", library_name="project files"
    )
    matched, method, conf = _match_drive(src, _cands())
    assert matched.drive_id == "D2" and method == "library_name" and conf == "medium"


def test_match_by_web_url_prefix() -> None:
    src = SourceLocation(
        source_key="s",
        kind="sharepoint_library",
        display_name="s",
        folder_web_url="https://h/proj/sub/folder",
    )
    matched, method, conf = _match_drive(src, _cands())
    assert matched.drive_id == "D2" and method == "web_url" and conf == "medium"


def test_match_none_when_no_signal() -> None:
    src = SourceLocation(source_key="s", kind="sharepoint_library", display_name="s")
    matched, method, conf = _match_drive(src, _cands())
    assert matched is None and method is None and conf == "none"


# --- read-only guard on the enumeration path -----------------------------------


def test_enumeration_path_is_guard_allowlisted() -> None:
    # GET on the drives-enumeration path is allowed; any mutation verb is refused.
    assert assert_files_request_allowed("GET", "/sites/SITE9/drives") is None
    with pytest.raises(FileMutationBlockedError):
        assert_files_request_allowed("POST", "/sites/SITE9/drives")


# --- receipt persistence (dry-run vs apply) ------------------------------------


def test_dry_run_persists_no_receipt(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "d.sqlite"))
    http = MagicMock()
    http.get.side_effect = [_drives_payload()]
    SiteDriveDiscovery(http, store=store).discover_drives(_pre_resolved_folder(), apply=False)
    assert store.list_processing_receipts(source_id="sp_proj") == []


def test_apply_persists_drive_discovery_receipt(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "d.sqlite"))
    http = MagicMock()
    http.get.side_effect = [_drives_payload()]
    SiteDriveDiscovery(http, store=store).discover_drives(_pre_resolved_folder(), apply=True)
    receipts = store.list_processing_receipts(source_id="sp_proj")
    assert len(receipts) == 1
    assert receipts[0]["operation"] == "drive_discovery"
    # Receipt detail carries metadata only — no token/url secrets.
    blob = json.dumps(receipts[0])
    assert "Bearer" not in blob and "access_token" not in blob


# --- CLI surface ---------------------------------------------------------------


def test_cli_drives_runs_with_mocked_client(monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    http.get.side_effect = [_drives_payload()]
    http.close = MagicMock()
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth", lambda scopes: (http, None)
    )
    result = runner.invoke(
        app, ["files", "drives", "--source", "sp_2023projects_23_435_01_tropical_sl", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files drives"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["content_crawl"] == "none"
    assert payload["guardrails"]["permission_tightening"] == "deferred"


def test_cli_sites_degrades_to_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth",
        lambda scopes: (None, {"status": "auth_required", "scopes": scopes, "detail": "no token"}),
    )
    result = runner.invoke(app, ["files", "sites", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "auth_required"
