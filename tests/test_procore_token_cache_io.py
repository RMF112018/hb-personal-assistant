"""Phase 04 Prompt 02 OAuth acquisition — token cache writer / clearer tests."""

from __future__ import annotations

import json
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hb_assistant.procore.oauth import TokenSet
from hb_assistant.procore.token_provider import (
    AUTH_TOKEN_FILE_NAME,
    LocalOAuthCacheTokenProvider,
    clear_token_cache,
    read_token_cache_payload,
    write_token_cache,
)

SYNTHETIC_TOKEN = "synthetic-cache-write-token"


def _patch_auth_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "hb_assistant.procore.token_provider.PathPolicy",
        lambda: type("X", (), {"get_auth_dir": lambda self: tmp_path / "auth"})(),
    )


def _make_token_set(*, expires_in_seconds: int = 7200) -> TokenSet:
    now = datetime.now(timezone.utc)
    return TokenSet(
        access_token=SYNTHETIC_TOKEN,
        refresh_token="synthetic-refresh-x",
        expires_at=now + timedelta(seconds=expires_in_seconds),
        obtained_at=now,
    )


def test_write_creates_file_with_0o600_and_parent_dir_0o700(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    cache_path = write_token_cache(_make_token_set())

    assert cache_path == tmp_path / "auth" / AUTH_TOKEN_FILE_NAME
    assert cache_path.exists()
    file_mode = stat.S_IMODE(cache_path.stat().st_mode)
    parent_mode = stat.S_IMODE(cache_path.parent.stat().st_mode)
    assert file_mode == 0o600, f"cache file perms must be 0o600, got {oct(file_mode)}"
    assert parent_mode == 0o700, f"auth dir perms must be 0o700, got {oct(parent_mode)}"


def test_write_then_read_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    write_token_cache(_make_token_set())
    payload = read_token_cache_payload()
    assert payload is not None
    assert payload["access_token"] == SYNTHETIC_TOKEN
    assert payload["refresh_token"] == "synthetic-refresh-x"
    assert isinstance(payload["expires_at"], str)
    assert isinstance(payload["obtained_at"], str)


def test_provider_reads_token_written_by_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    write_token_cache(_make_token_set())
    provider = LocalOAuthCacheTokenProvider()
    assert provider.get_access_token() == SYNTHETIC_TOKEN


def test_write_replaces_existing_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    write_token_cache(_make_token_set())
    first_payload = read_token_cache_payload()

    second = TokenSet(
        access_token="synthetic-rotated-token",
        refresh_token="synthetic-rotated-refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=600),
        obtained_at=datetime.now(timezone.utc),
    )
    write_token_cache(second)
    second_payload = read_token_cache_payload()

    assert first_payload is not None and second_payload is not None
    assert first_payload["access_token"] != second_payload["access_token"]
    assert second_payload["access_token"] == "synthetic-rotated-token"
    # No tempfile leftovers in the auth dir.
    auth_dir = tmp_path / "auth"
    leftovers = [p.name for p in auth_dir.iterdir() if p.name.startswith(".procore_token_")]
    assert leftovers == []


def test_clear_token_cache_removes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    write_token_cache(_make_token_set())
    assert clear_token_cache() is True
    assert clear_token_cache() is False
    assert not (tmp_path / "auth" / AUTH_TOKEN_FILE_NAME).exists()


def test_read_returns_none_when_permissions_unsafe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    cache_path = write_token_cache(_make_token_set())
    cache_path.chmod(0o644)
    if cache_path.stat().st_mode & 0o077 == 0:
        pytest.skip("filesystem does not honour group/other mode bits")
    assert read_token_cache_payload() is None


def test_explicit_path_argument_overrides_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_auth_dir(monkeypatch, tmp_path)
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_file = other_dir / "custom_token.json"
    write_token_cache(_make_token_set(), path=other_file)
    assert other_file.exists()
    assert json.loads(other_file.read_text())["access_token"] == SYNTHETIC_TOKEN
