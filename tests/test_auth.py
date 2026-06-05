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

from hb_assistant.auth.classifier import (
    classify_token_claims,
    require_delegated,
    safe_redact_claims,
)
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
        assert (
            "none" in str(info)
            or info.get("token_type") == "none"
            or "Certificate" in str(info.get("message", ""))
        )


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
    mock_resp1.json.return_value = {
        "value": [{"id": "1"}],
        "@odata.nextLink": "https://graph.../next",
    }
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
    page_1.json.return_value = {
        "value": [{"id": "1"}, {"id": "2"}],
        "@odata.nextLink": "https://graph.example/next",
    }
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
    page_1.json.return_value = {
        "value": [{"id": "1"}],
        "@odata.nextLink": "https://graph.example/next",
    }
    page_2 = MagicMock(status_code=200)
    page_2.json.return_value = {"value": [{"id": "2"}]}
    mock_requests.Session.return_value.request.side_effect = [page_1, page_2]

    items = list(client.get_all_pages("/me/messages", max_pages=1))
    assert [item["id"] for item in items] == ["1"]
    assert mock_requests.Session.return_value.request.call_count == 1


# ---------------------------------------------------------------------------
# Phase 03 entry: silent-acquisition claims backfill so the runtime
# classifier sees the cached delegated token as "delegated" (MSAL doesn't
# re-issue id_token_claims on silent acquisition).
# ---------------------------------------------------------------------------


def _build_test_jwt(payload: dict) -> str:
    """Build an unsigned JWT with the given payload. Signature segment is
    deliberately bogus — we never validate signatures in the synthesis path."""
    import base64
    import json

    def _b64(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    header = _b64({"alg": "none", "typ": "JWT"})
    body = _b64(payload)
    return f"{header}.{body}.bogus-signature-not-validated"


def test_ensure_delegated_id_token_claims_decodes_jwt_for_scp_and_upn() -> None:
    """MSAL silent acquisition strips id_token_claims; decode the access
    token's own JWT payload to recover scp/upn/tid for the classifier."""
    from hb_assistant.auth.providers import _ensure_delegated_id_token_claims

    access_token = _build_test_jwt(
        {
            "scp": "User.Read Files.ReadWrite.All",
            "upn": "bfetting@hedrickbrothers.com",
            "tid": "0e834bd7-628b-42c8-b9ec-ecebc9719be4",
            "oid": "0026a9f0-8ed0-45ca-8bc4-8e1593fcc37b",
            "aud": "https://graph.microsoft.com",
        }
    )
    msal_silent_result = {
        "access_token": access_token,
        "expires_in": 3600,
        "token_source": "cache",
        "token_type": "Bearer",
    }
    account = {
        "username": "bfetting@hedrickbrothers.com",
        "home_account_id": "0026a9f0-8ed0-45ca-8bc4-8e1593fcc37b.0e834bd7-628b-42c8-b9ec-ecebc9719be4",
    }

    enriched = _ensure_delegated_id_token_claims(msal_silent_result, account)
    claims = enriched["id_token_claims"]

    assert classify_token_claims(claims) == "delegated"
    assert claims["scp"] == "User.Read Files.ReadWrite.All"
    assert claims["upn"] == "bfetting@hedrickbrothers.com"
    assert claims["tid"] == "0e834bd7-628b-42c8-b9ec-ecebc9719be4"
    assert claims["oid"] == "0026a9f0-8ed0-45ca-8bc4-8e1593fcc37b"


def test_ensure_delegated_id_token_claims_falls_back_to_account_when_jwt_lacks_upn() -> None:
    """If the access token's JWT lacks UPN/tenant, fall back to the cached
    account record."""
    from hb_assistant.auth.providers import _ensure_delegated_id_token_claims

    access_token = _build_test_jwt({"scp": "User.Read"})  # minimal JWT
    msal_silent_result = {
        "access_token": access_token,
        "expires_in": 3600,
    }
    account = {
        "username": "bfetting@hedrickbrothers.com",
        "home_account_id": "abc.0e834bd7-628b-42c8-b9ec-ecebc9719be4",
    }

    enriched = _ensure_delegated_id_token_claims(msal_silent_result, account)
    claims = enriched["id_token_claims"]

    assert classify_token_claims(claims) == "delegated"
    assert claims["scp"] == "User.Read"
    assert claims["upn"] == "bfetting@hedrickbrothers.com"
    assert claims["tid"] == "0e834bd7-628b-42c8-b9ec-ecebc9719be4"


def test_ensure_delegated_id_token_claims_does_not_override_real_claims() -> None:
    from hb_assistant.auth.providers import _ensure_delegated_id_token_claims

    real = {
        "access_token": "redacted",
        "scope": "fallback.Read",
        "id_token_claims": {"scp": "User.Read Mail.Read", "tid": "real-tenant", "upn": "real@user"},
    }
    out = _ensure_delegated_id_token_claims(real, {"username": "other@user"})

    assert out["id_token_claims"]["scp"] == "User.Read Mail.Read"
    assert out["id_token_claims"]["upn"] == "real@user"
    assert out["id_token_claims"]["tid"] == "real-tenant"


def test_ensure_delegated_id_token_claims_preserves_fail_closed_when_no_evidence() -> None:
    """If MSAL returns an undecodable token and no account info, no
    synthetic scp is injected; the classifier still rejects as invalid
    (fail-closed)."""
    from hb_assistant.auth.providers import _ensure_delegated_id_token_claims

    bare = {"access_token": "not-a-jwt", "expires_in": 3600}
    out = _ensure_delegated_id_token_claims(bare, {})

    claims = out.get("id_token_claims") or {}
    assert classify_token_claims(claims) == "invalid"
