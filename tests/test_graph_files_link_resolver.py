"""Phase 06A — user-provided link → ID resolution (Graph Shares API).

Covers encoding, malformed-before-Graph, redaction/fingerprinting (no raw URL),
/shares folder+file+package success, OneDrive-business-root fallback, source-registry
fallback, unauthorized, apply-writes-SQLite vs dry-run, the no-raw-URL CHECK, the
no-redeemSharingLink guarantee, and the CLI surface.
"""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.graph import app
from hb_assistant.construction.graph.link_resolver import (
    LinkResolver,
    encode_sharing_url,
    fingerprint_url,
    redact_graph_link_url,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError

runner = CliRunner()

_SP_FOLDER_URL = (
    "https://hedrickbrotherscom.sharepoint.com/sites/2023Projects/Shared%20Documents"
    "/Forms/AllItems.aspx?id=%2Fsites%2F2023Projects%2FShared%20Documents%2F23-435-01Tropical"
    "&e=SECRETTOKEN123"
)


def _folder_item() -> dict:
    return {
        "id": "01FOLDERID",
        "name": "23-435-01Tropical",
        "webUrl": "https://hedrickbrotherscom.sharepoint.com/sites/2023Projects/Shared%20Documents/23-435-01Tropical",
        "folder": {"childCount": 9},
        "parentReference": {"driveId": "b!drive1", "id": "PARENT1"},
        "sharepointIds": {"siteId": "site-1", "webId": "web-1", "listId": "list-1", "listItemId": "7"},
    }


def _file_item() -> dict:
    return {
        "id": "01FILEID",
        "name": "RFI-001.pdf",
        "webUrl": "https://h/RFI-001.pdf",
        "file": {"mimeType": "application/pdf"},
        "parentReference": {"driveId": "b!drive1", "id": "PARENT1"},
        "sharepointIds": {"siteId": "site-1", "listId": "list-1", "listItemId": "42"},
    }


# --- pure helpers --------------------------------------------------------------


def test_encode_sharing_url_is_u_prefixed_unpadded_base64url() -> None:
    url = "https://contoso.sharepoint.com/sites/X/Shared Documents/RFI"
    enc = encode_sharing_url(url)
    assert enc.startswith("u!")
    assert "=" not in enc and "/" not in enc[2:] and "+" not in enc[2:]
    b = enc[2:].replace("_", "/").replace("-", "+")
    b += "=" * (-len(b) % 4)
    assert base64.b64decode(b).decode("utf-8") == url


def test_redact_and_fingerprint_drop_tokens() -> None:
    red = redact_graph_link_url(_SP_FOLDER_URL)
    assert red is not None
    assert "SECRETTOKEN123" not in red  # query dropped
    assert "?" not in red and "&" not in red
    fp = fingerprint_url(_SP_FOLDER_URL)
    assert fp.startswith("sha256:") and "SECRETTOKEN123" not in fp


def test_redact_returns_none_for_malformed() -> None:
    assert redact_graph_link_url("not a url") is None


# --- malformed-before-Graph ----------------------------------------------------


def test_malformed_url_fails_before_graph_call() -> None:
    http = MagicMock()
    r = LinkResolver(http_client=http).resolve_link("nonsense", dry_run=True)
    assert r.status == "malformed"
    http.get.assert_not_called()  # never touched Graph


# --- /shares success -----------------------------------------------------------


def test_shares_api_folder_success() -> None:
    http = MagicMock()
    http.get.side_effect = [_folder_item()]
    r = LinkResolver(http_client=http).resolve_link(_SP_FOLDER_URL, dry_run=True)
    assert r.status == "resolved" and r.resolution_method == "shares_api"
    assert r.item_kind == "folder"
    assert r.drive_item_id == "01FOLDERID" and r.folder_item_id == "01FOLDERID"
    assert r.drive_id == "b!drive1" and r.site_id == "site-1" and r.list_item_id == "7"
    # The GET went to the encoded /shares path with only $select params (no headers).
    call = http.get.call_args
    assert call.args[0].startswith("/shares/u!")
    assert "headers" not in call.kwargs  # no redeemSharingLink header possible
    assert "redeemSharingLink" not in json.dumps({"args": list(call.args), "kwargs": {k: str(v) for k, v in call.kwargs.items()}})


def test_shares_api_file_success() -> None:
    http = MagicMock()
    http.get.side_effect = [_file_item()]
    r = LinkResolver(http_client=http).resolve_link("https://h/x?e=tok", dry_run=True)
    assert r.status == "resolved" and r.item_kind == "file"
    assert r.drive_item_id == "01FILEID" and r.folder_item_id is None


def test_shares_api_package_success() -> None:
    http = MagicMock()
    http.get.side_effect = [{"id": "01PKG", "name": "Notebook", "package": {"type": "oneNote"}}]
    r = LinkResolver(http_client=http).resolve_link("https://h/n", dry_run=True)
    assert r.item_kind == "package" and r.folder_item_id == "01PKG"


def test_tokenized_url_is_redacted_not_raw() -> None:
    http = MagicMock()
    http.get.side_effect = [_folder_item()]
    r = LinkResolver(http_client=http).resolve_link(_SP_FOLDER_URL, dry_run=True)
    blob = json.dumps(r.model_dump())
    assert "SECRETTOKEN123" not in blob
    assert r.url_fingerprint and r.url_fingerprint.startswith("sha256:")
    assert r.share_token_fingerprint and r.share_token_fingerprint.startswith("sha256:")


# --- fallbacks -----------------------------------------------------------------


def test_onedrive_business_root_fallback() -> None:
    http = MagicMock()
    # /shares 404 → fall through; then /me/drive resolves the root.
    http.get.side_effect = [
        GraphHttpError("GET", "/shares/x/driveItem", 404, "not found"),
        {"id": "b!bizdrive", "webUrl": "https://h-my.sharepoint.com/personal/bfetting/Documents", "driveType": "business"},
    ]
    url = "https://hedrickbrotherscom-my.sharepoint.com/personal/bfetting/Documents/Forms/All.aspx"
    r = LinkResolver(http_client=http).resolve_link(url, dry_run=True)
    assert r.resolution_method == "me_drive_root" and r.item_kind == "root_candidate"
    assert r.drive_id == "b!bizdrive"


def test_source_registry_fallback_without_graph() -> None:
    # No http client → Shares API skipped; host/path matches the seed Tropical source.
    r = LinkResolver(http_client=None).resolve_link(_SP_FOLDER_URL, dry_run=True)
    assert r.resolution_method == "source_registry_match"
    assert r.source_id == "sp_2023projects_23_435_01_tropical_sl"
    assert r.drive_id is not None  # pre-resolved drive id from the registry


def test_unauthorized_link_produces_redacted_error() -> None:
    http = MagicMock()
    http.get.side_effect = [GraphHttpError("GET", "/shares/x/driveItem", 403, "denied")]
    r = LinkResolver(http_client=http).resolve_link("https://h/x", dry_run=True)
    assert r.status == "unauthorized" and r.error_redacted == "graph_403"
    assert "denied" not in json.dumps(r.model_dump())  # message not leaked beyond status


# --- persistence ---------------------------------------------------------------


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "lr.sqlite"))
    http = MagicMock()
    http.get.side_effect = [_folder_item()]
    LinkResolver(http_client=http, store=store).resolve_link(_SP_FOLDER_URL, dry_run=True)
    assert store.list_link_resolutions() == []


def test_apply_persists_redacted_row(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "lr.sqlite"))
    http = MagicMock()
    http.get.side_effect = [_folder_item()]
    LinkResolver(http_client=http, store=store).resolve_link(
        _SP_FOLDER_URL, dry_run=False, source_id="sp_x"
    )
    rows = store.list_link_resolutions()
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "resolved" and row["drive_item_id"] == "01FOLDERID"
    assert row["raw_tokenized_url_persisted"] == 0
    assert "SECRETTOKEN123" not in json.dumps(row)  # no raw tokenized URL stored


def test_raw_tokenized_url_persisted_check_is_enforced(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "lr.sqlite"))
    # The CHECK(raw_tokenized_url_persisted = 0) rejects any attempt to set it to 1.
    import hb_assistant.store.connection as conn_mod

    conn = conn_mod.get_connection(str(tmp_path / "lr.sqlite"))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO construction_graph_link_resolution "
            "(resolution_id, status, raw_tokenized_url_persisted) VALUES ('x','resolved',1)"
        )


# --- CLI -----------------------------------------------------------------------


def test_cli_link_resolve_with_mocked_client(monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    http.get.side_effect = [_folder_item()]
    http.close = MagicMock()
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth", lambda scopes: (http, None)
    )
    result = runner.invoke(app, ["files", "link", "resolve", "--url", _SP_FOLDER_URL, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files link resolve"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["sharing_link_redemption"] == "none"
    assert payload["guardrails"]["raw_tokenized_url_persisted"] is False
    assert "SECRETTOKEN123" not in result.output


def test_cli_link_resolve_offline_registry_match(monkeypatch: pytest.MonkeyPatch) -> None:
    # No token → client None; resolver still does the registry fallback offline.
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth",
        lambda scopes: (None, {"status": "auth_required", "scopes": scopes, "detail": "no token"}),
    )
    result = runner.invoke(app, ["files", "link", "resolve", "--url", _SP_FOLDER_URL, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["graph_available"] is False
    assert payload["result"]["resolution_method"] == "source_registry_match"
