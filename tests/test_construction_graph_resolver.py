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


def test_resolve_unsupported_kind() -> None:
    http = MagicMock()
    resolver = ConstructionGraphResolver(http)
    source = _make_source(kind="onedrive_shared", source_key="shared")
    result = resolver.resolve(source)
    assert result.status == "unsupported"
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
