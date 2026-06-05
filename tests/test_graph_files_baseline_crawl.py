"""Phase 06A — bounded metadata-only baseline crawl.

Covers delta-initial counts, max_pages/max_items/max_seconds truncation, children
diagnostics traversal, crawl-run + receipt persistence (apply) vs dry-run, redacted
errors, no-delta-token, and the CLI surface.
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
from hb_assistant.construction.graph.baseline_crawler import BaselineCrawler
from hb_assistant.construction.source_projection import (
    project_registry_to_v5_source_locations,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpError

runner = CliRunner()


def _folder_source() -> SourceLocation:
    return SourceLocation(
        source_key="sp_2023projects_23_435_01_tropical_sl",
        kind="sharepoint_project_drive_folder",
        display_name="Tropical",
        site_url="https://hedrickbrotherscom.sharepoint.com/sites/2023Projects",
        site_id="S1",
        drive_id="D1",
        folder_item_id="F1",
    )


def _page(items, next_link=None):
    d = {"value": items}
    if next_link:
        d["@odata.nextLink"] = next_link
    return d


def _file(i):
    return {
        "id": f"file{i}",
        "name": f"f{i}.pdf",
        "file": {"mimeType": "application/pdf"},
        "parentReference": {"driveId": "D1", "id": "P"},
    }


# --- counts / scope ------------------------------------------------------------


def test_delta_initial_crawl_counts_in_and_out_of_scope() -> None:
    http = MagicMock()
    http.get.return_value = _page(
        [
            _file(1),
            {
                "id": "del1",
                "name": "old.pdf",
                "deleted": {"state": "deleted"},
                "parentReference": {"driveId": "D1", "id": "P"},
            },
            {"name": "no-id"},  # id-less → out of scope
        ]
    )
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True)
    assert r.status == "ok" and r.traversal == "delta"
    assert r.endpoint == "/drives/D1/items/F1/delta"
    assert r.items_seen == 3 and r.items_in_scope == 1 and r.items_out_of_scope_filtered == 2
    assert r.delta_link_recorded is False


def test_max_pages_truncation() -> None:
    http = MagicMock()
    http.get.side_effect = [
        _page(
            [_file(1)],
            next_link="https://graph.microsoft.com/v1.0/drives/D1/items/F1/delta?$skiptoken=x",
        ),
        _page([_file(2)]),
    ]
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True, max_pages=1)
    assert r.pages_seen == 1 and r.truncated_by == "max_pages" and r.status == "partial"


def test_max_items_truncation() -> None:
    http = MagicMock()
    http.get.return_value = _page([_file(1), _file(2), _file(3)])
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True, max_items=2)
    assert r.items_seen == 2 and r.truncated_by == "max_items"


def test_max_seconds_truncation() -> None:
    http = MagicMock()
    http.get.return_value = _page([_file(1)])
    # Zero budget → stops before fetching any page.
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True, max_seconds=0)
    assert r.truncated_by == "max_seconds"
    http.get.assert_not_called()


def test_children_traversal_uses_children_endpoint() -> None:
    http = MagicMock()
    http.get.return_value = _page([_file(1)])
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True, children=True)
    assert r.traversal == "children"
    assert r.endpoint == "/drives/D1/items/F1/children"
    assert http.get.call_args.args[0] == "/drives/D1/items/F1/children"


# --- persistence ---------------------------------------------------------------


def test_dry_run_persists_nothing(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "bc.sqlite"))
    http = MagicMock()
    http.get.return_value = _page([_file(1)])
    BaselineCrawler(http, store=store).crawl(_folder_source(), dry_run=True)
    assert store.list_source_crawl_runs() == []
    assert store.list_processing_receipts() == []


def test_apply_persists_crawl_run_receipt_and_items(tmp_path: Path) -> None:
    store = ConstructionStore(str(tmp_path / "bc.sqlite"))
    project_registry_to_v5_source_locations(load_source_registry(), store)  # FK target
    http = MagicMock()
    http.get.return_value = _page([_file(1), _file(2)])
    r = BaselineCrawler(http, store=store).crawl(_folder_source(), dry_run=False)
    assert r.items_persisted == 2
    runs = store.list_source_crawl_runs(source_id="sp_2023projects_23_435_01_tropical_sl")
    assert len(runs) == 1 and runs[0]["status"] == "ok" and runs[0]["delta_link_recorded"] == 0
    receipts = store.list_processing_receipts(source_id="sp_2023projects_23_435_01_tropical_sl")
    assert any(x["operation"] == "baseline_crawl" for x in receipts)
    assert len(store.list_drive_items(source_id="sp_2023projects_23_435_01_tropical_sl")) == 2


# --- errors / safety -----------------------------------------------------------


def test_graph_error_is_redacted() -> None:
    http = MagicMock()
    http.get.side_effect = GraphHttpError("GET", "/drives/D1/items/F1/delta", 403, "denied")
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True)
    assert r.status == "error" and r.error_redacted == "graph_403"
    assert "denied" not in json.dumps(r.model_dump())


def test_no_delta_token_or_link_in_output() -> None:
    http = MagicMock()
    http.get.return_value = _page([_file(1)])
    r = BaselineCrawler(http).crawl(_folder_source(), dry_run=True)
    blob = json.dumps(r.model_dump())
    assert r.delta_link_recorded is False
    assert "deltaLink" not in blob and "skiptoken" not in blob.lower()


# --- CLI -----------------------------------------------------------------------


def test_cli_crawl_runs_with_mocked_client(monkeypatch: pytest.MonkeyPatch) -> None:
    http = MagicMock()
    http.get.return_value = _page([_file(1)])
    http.close = MagicMock()
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth", lambda scopes: (http, None)
    )
    result = runner.invoke(
        app, ["files", "crawl", "--source", "sp_2023projects_23_435_01_tropical_sl", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "graph files crawl"
    assert payload["mode"] == "dry_run"
    assert payload["guardrails"]["delta_token_recorded"] is False
    assert payload["guardrails"]["traversal"] == "delta"


def test_cli_crawl_degrades_to_auth_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hb_assistant.cli.graph._files_graph_client_or_auth",
        lambda scopes: (None, {"status": "auth_required", "scopes": scopes, "detail": "no token"}),
    )
    result = runner.invoke(
        app, ["files", "crawl", "--source", "sp_2023projects_23_435_01_tropical_sl", "--json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["status"] == "auth_required"
