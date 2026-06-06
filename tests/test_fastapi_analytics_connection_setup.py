"""Prompt 04 — optional FastAPI connection setup surfaces."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.construction.analytics.connection_setup import ConnectionSetupService
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "downloadUrl",
    "token=",
    "sig=",
)


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    db = str(tmp_path / "connection-setup.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db)), db


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_procore_url_preview_extracts_project_id_and_saves_locally(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    body = {"url": "https://app.procore.com/projects/2525840/home"}

    preview = client.post("/connections/preview", json=body)
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["status"] == "ready_to_save"
    assert payload["detected_source_type"] == "procore_project"
    assert payload["proposed_source"]["procore_project_id"] == "2525840"
    assert payload["proposed_source"]["project_key"] == "tropical"
    assert payload["first_sync_status"] == "pending_admin_approval"
    assert payload["guardrails"]["no_live_endpoint_calls"] is True

    save = client.post("/connections/save", headers={"X-HB-UI-Role": "operator"}, json=body)
    assert save.status_code == 200
    assert save.json()["ok"] is True
    identity = ConstructionStore(db).get_project_identity("tropical")
    assert identity is not None
    assert identity["procore_project_id"] == "2525840"
    assert identity["project_stage"] == "setup_pending_admin_approval"
    _assert_safe({"preview": payload, "save": save.json()})


def test_sharepoint_folder_preview_and_save_never_starts_sync(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    body = {
        "url": (
            "https://hedrickbrotherscom.sharepoint.com/sites/2025Projects/"
            "Shared%20Documents/25-244-01%20The%20Wellington?token=secret"
        ),
        "project_key": "the-wellington",
        "source_name": "The Wellington Documents",
    }

    preview = client.post("/connections/preview", json=body)
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["detected_source_type"] == "sharepoint_folder"
    assert payload["proposed_source"]["source_scope"] == "sharepoint_project_drive_folder"
    assert payload["proposed_source"]["site_url"].endswith("/sites/2025Projects")

    save = client.post("/connections/save", headers={"X-HB-UI-Role": "admin"}, json=body)
    assert save.status_code == 200
    connection_id = save.json()["connection_id"]
    store = ConstructionStore(db)
    source = store.get_source_location(connection_id)
    sync = store.get_source_sync_state(connection_id)
    assert source is not None
    assert source["read_only"] is True
    assert source["project_key"] == "the-wellington"
    assert sync is not None
    assert sync["sync_status"] == "pending_admin_approval"
    _assert_safe({"preview": payload, "save": save.json(), "source": source, "sync": sync})


def test_onedrive_scope_modes_enforce_explicit_selection(tmp_path: Path) -> None:
    service = ConnectionSetupService(db_path=str(tmp_path / "onedrive.sqlite"))

    blocked = service.preview_connection(
        {"url": "https://tenant-my.sharepoint.com/personal/bobby/Documents", "scope_mode": "selected_folders"}
    )
    assert blocked["status"] == "unavailable"
    assert blocked["reason_code"] == "onedrive_selected_folder_required"

    selected = service.preview_connection(
        {
            "url": "https://tenant-my.sharepoint.com/personal/bobby/Documents",
            "scope_mode": "selected_folders",
            "selected_folder_item_ids": ["folder-1"],
        }
    )
    assert selected["status"] == "ready_to_save"
    assert selected["proposed_source"]["folder_item_id"] == "folder-1"

    all_folders = service.preview_connection(
        {"url": "https://tenant-my.sharepoint.com/personal/bobby", "scope_mode": "all_folders_explicit"}
    )
    assert all_folders["status"] == "ready_to_save"
    assert all_folders["proposed_source"]["folder_policies"]["allow_all_folders"] is True

    excluded = service.preview_connection(
        {"url": "https://tenant-my.sharepoint.com/personal/bobby", "scope_mode": "excluded"}
    )
    assert excluded["status"] == "ready_to_save"
    assert excluded["first_sync_status"] == "excluded"
    assert excluded["proposed_source"]["enabled"] is False
    _assert_safe({"selected": selected, "all": all_folders, "excluded": excluded})


def test_outlook_calendar_options_are_read_only_and_metadata_only(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    body = {"connection_type": "calendar", "include_outlook": True, "include_calendar": True}

    preview = client.post("/connections/preview", json=body)
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["detected_source_type"] == "microsoft365_options"
    assert payload["options"]["outlook"]["mailbox_mutation_allowed"] is False
    assert payload["options"]["outlook"]["full_body_persisted"] is False
    assert payload["options"]["calendar"]["persist_event_body"] is False
    assert payload["options"]["calendar"]["persist_join_url"] is False

    save = client.post("/connections/save", headers={"X-HB-UI-Role": "operator"}, json=body)
    assert save.status_code == 200
    conn = get_connection(db)
    calendar_sync = conn.execute(
        "SELECT sync_status FROM calendar_sync_state WHERE source_id = ?",
        ("m365_microsoft-365-read-only-sources_calendar",),
    ).fetchone()
    assert calendar_sync is not None
    assert calendar_sync[0] == "pending_admin_approval"
    _assert_safe({"preview": payload, "save": save.json(), "calendar_sync": calendar_sync[0]})


def test_connection_setup_role_gates_and_admin_approval(tmp_path: Path) -> None:
    client, db = _client(tmp_path)
    body = {
        "url": "https://hedrickbrotherscom.sharepoint.com/sites/2025Projects/Shared%20Documents/Folder",
        "source_name": "Folder",
    }

    assert client.post("/connections/preview", json=body).status_code == 200
    assert client.post("/connections/save", json=body).status_code == 403
    saved = client.post("/connections/save", headers={"X-HB-UI-Role": "operator"}, json=body)
    assert saved.status_code == 200
    connection_id = saved.json()["connection_id"]

    assert client.post(
        f"/admin/connections/{connection_id}/approve-first-sync",
        headers={"X-HB-UI-Role": "operator"},
    ).status_code == 403
    approved = client.post(
        f"/admin/connections/{connection_id}/approve-first-sync",
        headers={"X-HB-UI-Role": "admin"},
    )
    assert approved.status_code == 200
    assert approved.json()["first_sync_triggered"] is False
    sync = ConstructionStore(db).get_source_sync_state(connection_id)
    assert sync is not None
    assert sync["sync_status"] == "approved_first_sync_not_started"

    schedule = client.post(
        "/admin/projects/missing/sync-schedule",
        headers={"X-HB-UI-Role": "admin"},
        json={"cadence_minutes": 60},
    )
    assert schedule.status_code == 200
    assert schedule.json()["kind"] == "requires_read_model"
    _assert_safe({"saved": saved.json(), "approved": approved.json(), "schedule": schedule.json()})
