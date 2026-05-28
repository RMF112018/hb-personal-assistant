"""Pytest fixtures for config and path tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from hb_assistant.config.models import AppConfig
from hb_assistant.config.path_policy import PathPolicy


@pytest.fixture
def tmp_app_support(tmp_path: Path) -> Path:
    """Temporary Application Support root for isolation."""
    support = tmp_path / "Application Support" / "HB Personal Assistant"
    support.mkdir(parents=True, exist_ok=True)
    return support


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Temporary directory pretending to be a repo root (for PathPolicy fallback)."""
    (tmp_path / "pyproject.toml").touch()
    return tmp_path


@pytest.fixture
def sample_config_dict() -> dict:
    return {
        "project": {"name": "Test HB PA", "slug": "test-hb-pa"},
        "paths": {
            "application_support_root": str(Path("/tmp/fake-support")),  # will be overridden in tests
            "obsidian_vault": "/tmp/fake-vault",
        },
    }


@pytest.fixture
def path_policy(tmp_app_support: Path, monkeypatch: pytest.MonkeyPatch) -> PathPolicy:
    """PathPolicy wired to a temp app support dir (no real FS pollution)."""
    # Force the config to point at our tmp
    cfg = AppConfig()
    cfg.paths.application_support_root = str(tmp_app_support)
    cfg.paths.obsidian_vault = "/tmp/fake-vault-for-tests"

    pp = PathPolicy(config=cfg)
    # Also ensure the tmp dirs
    pp.ensure_dirs(create_sensitive=True)
    return pp


@pytest.fixture(autouse=True)
def isolated_hb_pa_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force all tests to use a writable app-support root inside the test temp dir."""
    cfg_path = tmp_path / "hb-pa-test-config.yml"
    app_support = tmp_path / "app-support"
    vault_root = tmp_path / "vault"
    app_support.mkdir(parents=True, exist_ok=True)
    vault_root.mkdir(parents=True, exist_ok=True)

    cfg = {
        "paths": {
            "application_support_root": str(app_support),
            "obsidian_vault": str(vault_root),
        }
    }
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setenv("HB_PA_CONFIG", str(cfg_path))
