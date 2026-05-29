"""Encryption-at-rest vault round-trip + permissions."""

from __future__ import annotations

import stat

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.security.text_vault import decrypt_text, encrypt_text

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_SAMPLE_TEXT = "Owner threatened a delay claim. Contact carl@example.test re: RFI 123."


def test_encrypt_decrypt_round_trip() -> None:
    ref = encrypt_text(_SAMPLE_TEXT)
    assert ref is not None
    assert decrypt_text(ref) == _SAMPLE_TEXT


def test_ref_is_deterministic() -> None:
    assert encrypt_text(_SAMPLE_TEXT) == encrypt_text(_SAMPLE_TEXT)
    assert encrypt_text("other") != encrypt_text(_SAMPLE_TEXT)


def test_ciphertext_is_not_plaintext_and_blob_is_0600() -> None:
    ref = encrypt_text(_SAMPLE_TEXT)
    blob = PathPolicy().get_app_support() / "security" / "text-vault" / f"{ref}.enc"
    raw = blob.read_bytes()
    assert _SAMPLE_TEXT.encode("utf-8") not in raw
    assert b"carl@example.test" not in raw
    assert (stat.S_IMODE(blob.stat().st_mode)) == 0o600


def test_key_file_is_0600() -> None:
    encrypt_text(_SAMPLE_TEXT)
    key_path = PathPolicy().get_app_support() / "security" / "text-vault.key"
    assert key_path.exists()
    assert (stat.S_IMODE(key_path.stat().st_mode)) == 0o600


def test_empty_text_returns_none() -> None:
    assert encrypt_text("") is None
    assert encrypt_text(None) is None
    assert decrypt_text(None) is None
    assert decrypt_text("does-not-exist") is None
