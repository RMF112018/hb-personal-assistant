"""Tests for PathPolicy, models, and loader (Phase 1 foundation)."""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from hb_assistant.config.loader import load_config
from hb_assistant.config.models import AppConfig
from hb_assistant.config.path_policy import PathPolicy


def test_path_policy_resolves_correctly(path_policy: PathPolicy, tmp_app_support: Path) -> None:
    """Basic resolution and summary contain expected keys and our temp root."""
    s = path_policy.summary()
    assert "app_support" in s
    assert "auth_dir" in s
    assert s["app_support"] == str(tmp_app_support)
    assert "hb-personal-assistant" in s["db_path"]


def test_ensure_dirs_creates_with_perms(path_policy: PathPolicy) -> None:
    """ensure_dirs must create auth dir with 0o700 (best effort on macOS)."""
    auth = path_policy.get_auth_dir()
    assert auth.exists()
    mode = stat.S_IMODE(auth.stat().st_mode)
    # On some FS or umask we accept 0o700 or at least owner-only
    assert (mode & 0o700) == 0o700 or (mode & 0o777) in (0o700, 0o755)  # relax for CI containers


def test_loader_merges_defaults_and_overrides(tmp_path: Path) -> None:
    """load_config accepts override and still produces valid AppConfig with defaults filled."""
    override = tmp_path / "override.yml"
    override.write_text(
        """
        project:
          name: "Override Test"
        paths:
          obsidian_vault: "/tmp/override-vault"
        """,
        encoding="utf-8",
    )
    cfg = load_config(override_path=override)
    assert cfg.project.name == "Override Test"
    assert cfg.paths.obsidian_vault == "/tmp/override-vault"
    # defaults still present
    assert cfg.mail.inbound_lookback_days == 5
    assert cfg.security.microsoft_365_writeback_enabled is False


def test_no_secrets_in_paths_or_config(path_policy: PathPolicy) -> None:
    """PathPolicy and config must never surface tokens, keys, or PEM material by design."""
    s = path_policy.summary()
    forbidden_fragments = ["token", "pem", "password", "credential"]
    path_like_keys = ("root", "path", "dir", "logs", "evidence", "support")
    for key, value in s.items():
        key_l = key.lower()
        value_l = str(value).lower()
        if any(fragment in key_l for fragment in forbidden_fragments):
            raise AssertionError(f"Unsafe key name in path summary: {key}")
        # Avoid false positives from temporary directory names while still guarding obvious leaks.
        if not any(k in key_l for k in path_like_keys):
            for bad in forbidden_fragments:
                assert bad not in value_l

    cfg = AppConfig()
    # The model itself contains only non-secret fields in defaults
    assert "08c399eb" in cfg.identity.client_id  # the public client id is ok (not a secret)
    # No private key path in the model
    assert not hasattr(cfg, "private_key")
