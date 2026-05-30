"""Phase 06A — hardened incremental delta sync (V5 canonical).

Covers nextLink exhaustion + deltaLink capture, initial vs stored-token start,
deleted facet, 410 → requires_rebaseline, sync-state/crawl-run/receipt persistence
(apply) vs dry-run, raw-delta-link redaction (fingerprint only), and the CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.config.models import SourceLocation
from hb_assistant.construction.graph.delta_sync import DeltaSync
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError

runner = CliRunner()

_SID = "sp_2023projects_23_435_01_tropical_sl"
_RAW_DELTA = "https://graph.microsoft.com/v1.0/drives/D1/items/F1/delta?token=SECRETDELTATOKEN999"


def _src() -> SourceLocation:
    return SourceLocation(
        source_key=_SID,
        kind="sharepoint_project_drive_folder",
        display_name="Tropical",
        site_url="https://hedrickbrotherscom.sharepoint.com/sites/2023Projects",
        site_id="S1",
        drive_id="D1",
        folder_item_id="F1",
    )


def _file(i):
    return {"id": f"f{i}", "name": f"f{i}.pdf", "file": {"mimeType": "application/pdf"},
            "parentReference": {"driveId": "D1", "id": "F1"}}


def _deleted(i):
    return {"id": f"d{i}", "name": f"old{i}.pdf", "deleted": {"state": "deleted"},
            "parentReference": {"driveId": "D1", "id": "F1"}}


def _seeded_store(tmp_path: Path) -> ConstructionStore:
    store = ConstructionStore(str(tmp_path / "ds.sqlite"))
    project_registry_to_v5_source_locations(load_source_registry(), store)
    return store


# --- initial / nextLink / deltaLink -------------------------------------------


def test_initial_delta_captures_deltalink_and_redacts() -> None:
    http = MagicMock()
    http.get.return_value = {"value": [_file(1), _deleted(1)], "@odata.deltaLink": _RAW_DELTA}
    r = DeltaSync(http).sync(_src(), dry_run=True)
    assert r.status == "ok" and r.started_from == "initial"
    assert r.items_seen == 2 and r.items_changed == 1 and r.items_deleted == 1
    assert r.delta_link_fingerprint and r.delta_link_fingerprint.startswith("sha256:")
    assert r.endpoint == "/drives/D1/items/F1/delta"
    assert "SECRETDELTATOKEN999" not in json.dumps(r.model_dump())


def test_nextlink_exhaustion_to_deltalink() -> None:
    http = MagicMock()
    http.get.side_effect = [
        {"value": [_file(1)], "@odata.nextLink": "https://graph.microsoft.com/v1.0/drives/D1/items/F1/delta?$skiptoken=p2"},
        {"value": [_file(2)], "@odata.deltaLink": _RAW_DELTA},
    ]
    r = DeltaSync(http).sync(_src(), dry_run=True)
    assert r.pages_seen == 2 and r.items_seen == 2 and r.status == "ok"
    assert r.delta_link_fingerprint is not None


def test_incremental_starts_from_stored_delta(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    store.upsert_source_sync_state(source_id=_SID, drive_id="D1", delta_link=_RAW_DELTA)
    http = MagicMock()
    http.get.return_value = {"value": [_file(1)], "@odata.deltaLink": _RAW_DELTA}
    r = DeltaSync(http, store=store).sync(_src(), dry_run=True)
    assert r.started_from == "stored_delta"
    # The GET used the stored absolute deltaLink as the request path.
    assert http.get.call_args.args[0] == _RAW_DELTA


# --- 410 stale token ----------------------------------------------------------


def test_410_marks_requires_rebaseline(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    store.upsert_source_sync_state(source_id=_SID, drive_id="D1", delta_link=_RAW_DELTA)
    http = MagicMock()
    http.get.side_effect = GraphHttpError("GET", "/drives/D1/items/F1/delta", 410, "Gone")
    r = DeltaSync(http, store=store).sync(_src(), dry_run=False)
    assert r.status == "requires_rebaseline"
    state = store.get_source_sync_state(_SID)
    assert state["sync_status"] == "requires_rebaseline"
    assert state["delta_link"] is None  # stale token cleared
    assert state["error_message_redacted"] == "graph_410_stale_delta_token"
    assert "Gone" not in json.dumps(r.model_dump())


# --- persistence + redaction --------------------------------------------------


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    http = MagicMock()
    http.get.return_value = {"value": [_file(1)], "@odata.deltaLink": _RAW_DELTA}
    DeltaSync(http, store=store).sync(_src(), dry_run=True)
    assert store.get_source_sync_state(_SID) is None
    assert store.list_drive_items(source_id=_SID) == []


def test_apply_persists_state_items_and_receipt(tmp_path: Path) -> None:
    store = _seeded_store(tmp_path)
    http = MagicMock()
    http.get.return_value = {"value": [_file(1), _deleted(1)], "@odata.deltaLink": _RAW_DELTA}
    r = DeltaSync(http, store=store).sync(_src(), dry_run=False)
    assert r.delta_link_recorded is True
    state = store.get_source_sync_state(_SID)
    # Raw delta token lives in SQLite ONLY; fingerprint is the safe render.
    assert state["delta_link"] == _RAW_DELTA
    assert state["delta_link_fingerprint"].startswith("sha256:")
    assert state["sync_status"] == "ok"
    assert len(store.list_drive_items(source_id=_SID)) == 2
    receipts = store.list_processing_receipts(source_id=_SID)
    assert any(x["operation"] == "delta_sync" for x in receipts)
    # The receipt detail (rendered/queryable) must NOT carry the raw token.
    assert "SECRETDELTATOKEN999" not in json.dumps([x for x in receipts])


# --- CLI ----------------------------------------------------------------------


def test_cli_delta_runs_and_redacts(monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    http.get.return_value = {"value": [_file(1)], "@odata.deltaLink": _RAW_DELTA}
    http.close = MagicMock()
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth", lambda scopes: (http, None)
    )
    result = runner.invoke(app, ["files", "delta", "--source", _SID, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files delta"
    assert payload["guardrails"]["delta_token_storage"] == "sqlite_only"
    assert payload["guardrails"]["delta_link_rendered"] == "fingerprint_only"
    assert "SECRETDELTATOKEN999" not in result.output  # no raw token in CLI output


def test_cli_delta_degrades_to_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth",
        lambda scopes: (None, {"status": "auth_required", "scopes": scopes, "detail": "no token"}),
    )
    result = runner.invoke(app, ["files", "delta", "--source", _SID, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "auth_required"
