"""Phase 06 (Files) Prompt 05 — OneDrive discovery + shared-library posture.

Mirrors the resolver mock pattern. Covers business/personal `/me/drive` resolution
+ `/me/drives` enumeration, the `unavailable` (404) state, shared-library
pre_resolved vs requires_share_url, receipt persistence, and the CLI surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config.models import SourceLocation
from hb_assistant.construction.graph.site_drive_discovery import SiteDriveDiscovery
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError

runner = CliRunner()


def _me_drive(drive_id: str = "D-BIZ", dtype: str = "business") -> dict:
    return {"id": drive_id, "webUrl": "https://od/biz", "driveType": dtype}


def _me_drives(drive_id: str = "D-BIZ", dtype: str = "business") -> dict:
    return {"value": [{"id": drive_id, "name": "OneDrive", "driveType": dtype, "webUrl": "https://od/biz"}]}


def _business() -> SourceLocation:
    return SourceLocation(
        source_key="od_biz",
        kind="onedrive_business_root",
        display_name="Biz OneDrive",
        local_sync_path="/x",
        resolution_status="pending_drive_resolution",
    )


# --- root resolution -----------------------------------------------------------


def test_business_root_resolves_and_enumerates() -> None:
    http = MagicMock()
    http.get.side_effect = [_me_drive(), _me_drives()]
    result = SiteDriveDiscovery(http).discover_onedrive(_business())
    assert result.status == "resolved"
    assert result.drive_id == "D-BIZ"
    assert result.drive_type == "business"  # derived from /me/drives enumeration
    assert len(result.available_drives) == 1
    assert result.resolution_status == "pending_drive_resolution"


def test_personal_root_unavailable_on_404() -> None:
    http = MagicMock()
    http.get.side_effect = [
        GraphHttpError("GET", "/me/drive", 404, "not found"),
        GraphHttpError("GET", "/me/drives", 404, "not found"),
    ]
    src = SourceLocation(
        source_key="od_personal", kind="onedrive_personal_root", display_name="Personal"
    )
    result = SiteDriveDiscovery(http).discover_onedrive(src)
    assert result.status == "unavailable"
    assert result.available_drives == []


# --- shared libraries ----------------------------------------------------------


def test_shared_library_pre_resolved_with_drive_id() -> None:
    http = MagicMock()
    src = SourceLocation(
        source_key="od_shared",
        kind="onedrive_shared_library",
        display_name="Shared",
        drive_id="D-SH",
        resolution_status="pending_source_resolution",
    )
    result = SiteDriveDiscovery(http).discover_onedrive(src)
    assert result.status == "pre_resolved"
    assert result.drive_id == "D-SH"
    http.get.assert_not_called()


def test_shared_library_requires_share_url_without_drive_id() -> None:
    http = MagicMock()
    src = SourceLocation(
        source_key="od_shared2",
        kind="onedrive_shared_library",
        display_name="Shared2",
        resolution_status="pending_source_resolution",
    )
    result = SiteDriveDiscovery(http).discover_onedrive(src)
    assert result.status == "requires_share_url"
    assert result.drive_id is None
    assert result.resolution_status == "pending_source_resolution"
    http.get.assert_not_called()


def test_unsupported_for_sharepoint_kind() -> None:
    src = SourceLocation(
        source_key="sp", kind="sharepoint_project_drive_folder", display_name="SP"
    )
    result = SiteDriveDiscovery(MagicMock()).discover_onedrive(src)
    assert result.status == "unsupported"


# --- receipts ------------------------------------------------------------------


def test_dry_run_persists_no_receipt(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "od.sqlite"))
    http = MagicMock()
    http.get.side_effect = [_me_drive(), _me_drives()]
    SiteDriveDiscovery(http, store=store).discover_onedrive(_business(), apply=False)
    assert store.list_processing_receipts(source_id="od_biz") == []


def test_apply_persists_onedrive_receipt(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "od.sqlite"))
    http = MagicMock()
    http.get.side_effect = [_me_drive(), _me_drives()]
    SiteDriveDiscovery(http, store=store).discover_onedrive(_business(), apply=True)
    receipts = store.list_processing_receipts(source_id="od_biz")
    assert len(receipts) == 1
    assert receipts[0]["operation"] == "onedrive_discovery"
    blob = json.dumps(receipts[0])
    assert "Bearer" not in blob and "access_token" not in blob


# --- CLI -----------------------------------------------------------------------


def test_cli_onedrive_runs_with_mocked_client(monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    http.get.side_effect = [_me_drive(), _me_drives()]
    http.close = MagicMock()
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth", lambda scopes: (http, None)
    )
    result = runner.invoke(
        app, ["files", "onedrive", "--source", "od_business_bobby_hedrickbrothers", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files onedrive"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["permission_tightening"] == "deferred"


def test_cli_onedrive_degrades_to_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth",
        lambda scopes: (None, {"status": "auth_required", "scopes": scopes, "detail": "no token"}),
    )
    result = runner.invoke(app, ["files", "onedrive", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "auth_required"
