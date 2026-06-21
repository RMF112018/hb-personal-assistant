"""Load budget column role metadata from the semantic catalog."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "forecasting"
    / "semantic-catalog"
    / "budget_column_roles.yml"
)


@lru_cache(maxsize=1)
def load_budget_column_roles() -> dict[str, Any]:
    """Return parsed budget_column_roles.yml (empty dict if missing)."""
    if not _CATALOG_PATH.exists():
        return {}
    data = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def overlap_checks() -> list[dict[str, Any]]:
    catalog = load_budget_column_roles()
    checks = catalog.get("overlap_checks", [])
    return checks if isinstance(checks, list) else []