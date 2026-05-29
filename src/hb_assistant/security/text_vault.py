"""Encryption-at-rest vault for full free-text bodies (Phase 04B).

Procore meeting minutes / topic descriptions are high-value but sensitive. The
default enrichment posture stores only a hash + length + redacted excerpt +
extracted tokens. This vault provides the *optional* safe full-text mechanism:
the plaintext is encrypted with Fernet (AES-128-CBC + HMAC) and written to a
file outside the repo, returning a deterministic reference stored in
``procore_text_intelligence.encrypted_full_text_ref``.

Key management mirrors the OAuth token-cache pattern: a Fernet key lives in a
``0o600`` key file under the Application Support root (resolved by
:class:`PathPolicy`), generated on first use, or is supplied via the
``HB_TEXT_VAULT_KEY`` environment variable for headless / test contexts.
Ciphertext blobs are ``0o600`` and live under Application Support — never in the
repo, and never as plaintext.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from hb_assistant.config.path_policy import PathPolicy

_ENV_KEY = "HB_TEXT_VAULT_KEY"
_SECURITY_SUBDIR = "security"
_VAULT_SUBDIR = "text-vault"
_KEY_FILENAME = "text-vault.key"


def _security_dir() -> Path:
    d = PathPolicy().get_app_support() / _SECURITY_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(d, 0o700)
    return d


def _vault_dir() -> Path:
    d = _security_dir() / _VAULT_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(d, 0o700)
    return d


def _key() -> bytes:
    env = os.environ.get(_ENV_KEY)
    if env:
        return env.encode("utf-8") if isinstance(env, str) else env
    key_path = _security_dir() / _KEY_FILENAME
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    with contextlib.suppress(OSError):
        os.chmod(key_path, 0o600)
    return key


def _fernet() -> Fernet:
    return Fernet(_key())


def encrypt_text(plaintext: object) -> Optional[str]:
    """Encrypt ``plaintext`` to a ``0o600`` blob under the vault; return its ref.

    The ref is ``sha256(plaintext)[:32]`` so the same text maps to the same blob
    (idempotent). Returns ``None`` for empty input.
    """
    if plaintext is None:
        return None
    text = plaintext if isinstance(plaintext, str) else str(plaintext)
    if not text:
        return None
    ref = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
    blob = _fernet().encrypt(text.encode("utf-8"))
    path = _vault_dir() / f"{ref}.enc"
    path.write_bytes(blob)
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return ref


def decrypt_text(ref: Optional[str]) -> Optional[str]:
    """Return the plaintext for a vault ref, or ``None`` if missing/undecryptable."""
    if not ref:
        return None
    path = _vault_dir() / f"{ref}.enc"
    if not path.exists():
        return None
    try:
        return _fernet().decrypt(path.read_bytes()).decode("utf-8")
    except (InvalidToken, OSError):
        return None


__all__ = ["encrypt_text", "decrypt_text"]
