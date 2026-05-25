"""Configuration loader.

Loads YAML (with optional user override) and validates against AppConfig Pydantic model.
Merges with built-in defaults.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .models import AppConfig


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must contain a mapping at top level")
    return data


def load_config(override_path: Optional[Path | str] = None) -> AppConfig:
    """Load and validate configuration.

    Search order (later wins):
      1. Built-in defaults (via Pydantic model defaults)
      2. repo-root/config/config.yml (if present)
      3. explicit override_path (if provided)
      4. env var HB_PA_CONFIG (if set)

    Secrets (tenant/client) are intentionally left in the model defaults or user config;
    production overrides should come from .env or keychain (future).
    """
    # Start with defaults
    config_data: Dict[str, Any] = {}

    # 1. repo level config/config.yml (conventional location after scaffold)
    repo_config = Path(__file__).resolve().parents[3] / "config" / "config.yml"
    if repo_config.exists():
        config_data.update(_load_yaml(repo_config))

    # 2. explicit override or env
    candidate = override_path or os.environ.get("HB_PA_CONFIG")
    if candidate:
        p = Path(candidate).expanduser()
        config_data.update(_load_yaml(p))

    # Validate (Pydantic will apply its own defaults for missing sections)
    return AppConfig.model_validate(config_data)
