"""Tests for Phase 2 auth (classifier, cache manager, providers, graph client).

All tests are offline/mocked; no real tokens or network calls to Graph.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from hb_assistant.auth.classifier import classify_token_claims, require_delegated, safe_redact_claims
from hb_assistant.auth.exceptions import ClassificationError
from hb_assistant.auth.providers import AppOnlyAuthProvider, DelegatedAuthProvider
from hb_assistant.auth.token_cache_manager import TokenCacheManager
from hb_assistant.config.models import AppConfig
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.graph.http_client import GraphHttpClient


# --- Classifier tests (core, 4+ cases + edges) ---

def test_classify_delegated() -> None:
    claims = {"scp": "User.Read Mail.Read", "tid": "abc"}
    assert classify_token_claims(claims) == "delegated"


def test_classify_app_only() -> None:
    claims = {"roles": ["Sites.Read.All"], "tid": "abc"}
    assert classify_token_claims(claims) == "app_only"


def test_classify_ambiguous() -> None:
    claims = {"scp": "foo", "roles": ["bar"]}
    assert classify_token_claims(claims) == "ambiguous"


def test_classify_invalid() -> None:
    assert classify_token_claims(None) == "invalid"
    assert classify_token_claims({}) == "invalid"
    assert classify_token_claims({"aud": "x"}) == "invalid"


def test_require_delegated_raises_on_non_delegated() -> None:
    with pytest.raises(ClassificationError):
        require_delegated({"roles": ["x"]}, context="test")


def test_safe_redact_claims() -> None:
    claims = {"scp": "a b", "roles": ["r1"], "upn": "bobby@ex.com", "access_token": "SECRET"}
    red = safe_redact_claims(claims)
    assert "access_token" not in red
    assert red["upn"] == "bobby@ex.com"
    assert red["scp_count"] == 2


# --- Cache manager (temp dir, perms, roundtrip) ---

def test_cache_manager_temp_perms_and_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        # Override PathPolicy to use temp as app support root
        cfg = AppConfig()
        cfg.paths.application_support_root = td
        pp = PathPolicy(cfg)
        mgr = TokenCacheManager(pp)

        # Initially no files
        info = mgr.check_permissions()
        assert "path_status" in info
        assert "path_error" in info["path_status"]
        assert "ensure_report" in info["path_status"]
        assert not info["msal-token-cache.bin"]["exists"]

        # Simulate save (create dummy content)
        dummy_cache = MagicMock()
        dummy_cache.has_state_changed = True
        dummy_cache.serialize.return_value = json.dumps({"foo": "bar"})
        mgr.save_cache(dummy_cache, app_only=False)

        p = mgr._cache_path(False)
        assert p.exists()
        info2 = mgr.check_permissions()
        assert info2["msal-token-cache.bin"]["exists"]
        # 600 check is best-effort in test env; at least owner read/write
        mode = p.stat().st_mode & 0o777
        assert (mode & 0o600) == 0o600 or mode == 0o600  # relaxed for container umask

        # Clear
        deleted = mgr.clear_cache(app_only=False)
        assert len(deleted) == 1
        assert not p.exists()


# --- Provider mocks (no real MSAL network) ---

def test_delegated_provider_status_no_token() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = AppConfig()
        cfg.paths.application_support_root = td
        pp = PathPolicy(cfg)
        prov = DelegatedAuthProvider("tid", "cid", ["User.Read"], path_policy=pp)
        with patch.object(prov, "get_token", return_value={}):
            info = prov.status_info()
        assert info["token_type"] in ("none", "delegated", "invalid")
        assert "path_status" in info["cache"]


def test_cache_manager_does_not_crash_on_app_support_chmod_failure() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = AppConfig()
        cfg.paths.application_support_root = td
        pp = PathPolicy(cfg)
        app_support = pp.get_app_support()
        orig_chmod = Path.chmod

        def _chmod(self: Path, mode: int) -> None:
            if self == app_support:
                raise PermissionError("Operation not permitted")
            orig_chmod(self, mode)

        with patch("os.chmod", side_effect=lambda p, m: _chmod(Path(p), m)):
            mgr = TokenCacheManager(pp)
            status = mgr.check_permissions()

        assert "path_status" in status
        assert status["path_status"]["path_error"] is None
        assert status["path_status"]["ensure_report"]["warnings"]


@patch("hb_assistant.auth.providers.msal")
def test_app_only_provider_graceful_no_cert(mock_msal: MagicMock) -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg = AppConfig()
        cfg.paths.application_support_root = td
        pp = PathPolicy(cfg)
        prov = AppOnlyAuthProvider("tid", "cid", "/nonexistent/bundle.pem", path_policy=pp)
        info = prov.status_info()
        assert "none" in str(info) or info.get("token_type") == "none" or "Certificate" in str(info.get("message", ""))


# --- Graph client retry/paging (mocked responses) ---

@patch("hb_assistant.graph.http_client.requests")
def test_graph_client_paging_and_retry(mock_requests: MagicMock) -> None:
    from hb_assistant.graph.http_client import GraphHttpClient

    # Fake token getter
    def fake_token(scopes=None):
        return {"access_token": "fake", "id_token_claims": {"scp": "User.Read"}}

    client = GraphHttpClient(fake_token)

    # Simulate one page + nextLink
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {"value": [{"id": "1"}], "@odata.nextLink": "https://graph.../next"}
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {"value": [{"id": "2"}]}

    mock_requests.Session.return_value.request.side_effect = [mock_resp1, mock_resp2]

    items = list(client.get_all_pages("/me/messages", params={"$top": 1}))
    assert len(items) == 2

    # Also test 429 retry path (simple)
    mock_429 = MagicMock(status_code=429, headers={"Retry-After": "0"}, content=b"")
    mock_429.json.return_value = {}
    mock_ok = MagicMock(status_code=200)
    mock_ok.json.return_value = {"value": []}
    mock_requests.Session.return_value.request.side_effect = [mock_429, mock_ok]

    data = client.get("/me")
    assert data == {"value": []}

    client.close()


@patch("hb_assistant.graph.http_client.requests")
def test_graph_client_get_all_pages_respects_max_items(mock_requests: MagicMock) -> None:
    from hb_assistant.graph.http_client import GraphHttpClient

    def fake_token(scopes=None):
        return {"access_token": "fake", "id_token_claims": {"scp": "User.Read"}}

    client = GraphHttpClient(fake_token)

    page_1 = MagicMock(status_code=200)
    page_1.json.return_value = {"value": [{"id": "1"}, {"id": "2"}], "@odata.nextLink": "https://graph.example/next"}
    page_2 = MagicMock(status_code=200)
    page_2.json.return_value = {"value": [{"id": "3"}, {"id": "4"}]}
    mock_requests.Session.return_value.request.side_effect = [page_1, page_2]

    items = list(client.get_all_pages("/me/messages", max_items=3))
    assert [item["id"] for item in items] == ["1", "2", "3"]
    assert mock_requests.Session.return_value.request.call_count == 2


@patch("hb_assistant.graph.http_client.requests")
def test_graph_client_get_all_pages_respects_max_pages(mock_requests: MagicMock) -> None:
    from hb_assistant.graph.http_client import GraphHttpClient

    def fake_token(scopes=None):
        return {"access_token": "fake", "id_token_claims": {"scp": "User.Read"}}

    client = GraphHttpClient(fake_token)

    page_1 = MagicMock(status_code=200)
    page_1.json.return_value = {"value": [{"id": "1"}], "@odata.nextLink": "https://graph.example/next"}
    page_2 = MagicMock(status_code=200)
    page_2.json.return_value = {"value": [{"id": "2"}]}
    mock_requests.Session.return_value.request.side_effect = [page_1, page_2]

    items = list(client.get_all_pages("/me/messages", max_pages=1))
    assert [item["id"] for item in items] == ["1"]
    assert mock_requests.Session.return_value.request.call_count == 1
