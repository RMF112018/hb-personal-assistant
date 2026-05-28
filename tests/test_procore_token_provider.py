"""Phase 04 Prompt 02 — token-provider boundary tests.

Covers the protocol, each concrete provider, the composed default chain, and
the invariant that no provider ever stringifies a token value.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from hb_assistant.procore.token_provider import (
    AUTH_TOKEN_FILE_NAME,
    EnvOrKeychainTokenProvider,
    LocalOAuthCacheTokenProvider,
    MissingTokenProvider,
    ProcoreTokenProvider,
    StaticTokenProvider,
    _ChainedTokenProvider,
    adapt_token_source,
    default_procore_token_provider,
)

SYNTHETIC_TOKEN = "synthetic-procore-token-x"


# --- Protocol surface --------------------------------------------------------


def test_missing_provider_returns_none() -> None:
    p = MissingTokenProvider()
    assert p.get_access_token() is None
    assert p.kind == "missing"
    assert isinstance(p, ProcoreTokenProvider)


def test_static_provider_returns_value_verbatim() -> None:
    p = StaticTokenProvider(SYNTHETIC_TOKEN)
    assert p.get_access_token() == SYNTHETIC_TOKEN
    assert p.kind == "static"


def test_static_provider_returns_none_when_token_is_none() -> None:
    assert StaticTokenProvider(None).get_access_token() is None


# --- Env / Keychain ----------------------------------------------------------


def test_env_keychain_provider_returns_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", SYNTHETIC_TOKEN)
    # Force Keychain miss to isolate the env path.
    with patch(
        "hb_assistant.procore.config.get_macos_keychain_secret",
        return_value=None,
    ):
        assert EnvOrKeychainTokenProvider().get_access_token() == SYNTHETIC_TOKEN


def test_env_keychain_provider_returns_none_when_both_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROCORE_ACCESS_TOKEN", raising=False)
    with patch(
        "hb_assistant.procore.config.get_macos_keychain_secret",
        return_value=None,
    ):
        assert EnvOrKeychainTokenProvider().get_access_token() is None


# --- Local OAuth cache (read-only shell) -------------------------------------


def _write_cache(tmp_path: Path, payload: object) -> Path:
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir(parents=True)
    auth_dir.chmod(0o700)
    cache_file = auth_dir / AUTH_TOKEN_FILE_NAME
    if isinstance(payload, (dict, list)):
        cache_file.write_text(json.dumps(payload), encoding="utf-8")
    else:
        cache_file.write_text(str(payload), encoding="utf-8")
    cache_file.chmod(0o600)
    return cache_file


def _patch_auth_dir(tmp_path: Path) -> Any:
    return patch(
        "hb_assistant.procore.token_provider.PathPolicy",
        return_value=type("X", (), {"get_auth_dir": lambda self: tmp_path / "auth"})(),
    )


def test_cache_provider_returns_none_when_file_missing(tmp_path: Path) -> None:
    (tmp_path / "auth").mkdir()
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() is None


def test_cache_provider_returns_none_on_malformed_json(tmp_path: Path) -> None:
    _write_cache(tmp_path, "this is not json {")
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() is None


def test_cache_provider_returns_none_when_access_token_missing(tmp_path: Path) -> None:
    _write_cache(tmp_path, {"expires_at": "2099-01-01T00:00:00+00:00"})
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() is None


def test_cache_provider_returns_none_when_expired(tmp_path: Path) -> None:
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    _write_cache(tmp_path, {"access_token": SYNTHETIC_TOKEN, "expires_at": past})
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() is None


def test_cache_provider_returns_token_when_valid_and_unexpired(tmp_path: Path) -> None:
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    _write_cache(tmp_path, {"access_token": SYNTHETIC_TOKEN, "expires_at": future})
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() == SYNTHETIC_TOKEN


def test_cache_provider_returns_token_when_no_expires_field(tmp_path: Path) -> None:
    """Absence of ``expires_at`` is treated as no expiry assertion (caller must
    interpret freshness externally). Required for fresh-cache scenarios where
    the writer has not populated the field yet.
    """
    _write_cache(tmp_path, {"access_token": SYNTHETIC_TOKEN})
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() == SYNTHETIC_TOKEN


def test_cache_provider_returns_none_when_permissions_unsafe(tmp_path: Path) -> None:
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    cache_file = _write_cache(
        tmp_path, {"access_token": SYNTHETIC_TOKEN, "expires_at": future}
    )
    cache_file.chmod(0o644)  # group/other readable — unsafe
    if cache_file.stat().st_mode & 0o077 == 0:
        pytest.skip("filesystem does not honour group/other mode bits")
    with _patch_auth_dir(tmp_path):
        assert LocalOAuthCacheTokenProvider().get_access_token() is None


# --- Composed default chain --------------------------------------------------


def test_default_chain_shape() -> None:
    chain = default_procore_token_provider()
    assert isinstance(chain, _ChainedTokenProvider)
    kinds = [p.kind for p in chain.providers]
    assert kinds == ["env_or_keychain", "oauth_cache", "missing"]


def test_default_chain_returns_none_when_all_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PROCORE_ACCESS_TOKEN", raising=False)
    (tmp_path / "auth").mkdir()
    with patch(
        "hb_assistant.procore.config.get_macos_keychain_secret",
        return_value=None,
    ), _patch_auth_dir(tmp_path):
        assert default_procore_token_provider().get_access_token() is None


def test_default_chain_env_wins_over_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_token = "env-only-token"
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", env_token)
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    _write_cache(tmp_path, {"access_token": "cache-token", "expires_at": future})
    with patch(
        "hb_assistant.procore.config.get_macos_keychain_secret",
        return_value=None,
    ), _patch_auth_dir(tmp_path):
        assert default_procore_token_provider().get_access_token() == env_token


# --- adapter -----------------------------------------------------------------


def test_adapter_accepts_callable() -> None:
    adapted = adapt_token_source(lambda: SYNTHETIC_TOKEN)
    assert adapted.get_access_token() == SYNTHETIC_TOKEN


def test_adapter_returns_provider_unchanged() -> None:
    p = StaticTokenProvider(SYNTHETIC_TOKEN)
    assert adapt_token_source(p) is p


def test_adapter_returns_default_chain_for_none() -> None:
    assert isinstance(adapt_token_source(None), _ChainedTokenProvider)


def test_adapter_rejects_garbage_input() -> None:
    with pytest.raises(TypeError):
        adapt_token_source(42)


# --- redaction invariants ----------------------------------------------------


def test_provider_repr_never_includes_token_value() -> None:
    providers = [
        MissingTokenProvider(),
        StaticTokenProvider(SYNTHETIC_TOKEN),
        EnvOrKeychainTokenProvider(),
        LocalOAuthCacheTokenProvider(),
        default_procore_token_provider(),
    ]
    for p in providers:
        assert SYNTHETIC_TOKEN not in repr(p)
        assert SYNTHETIC_TOKEN not in str(p)
