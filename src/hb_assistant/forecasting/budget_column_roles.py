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


# Procore Standard Budget View display labels -> local budget_detail_rows column keys.
_PROCORE_LABEL_TO_ROLE_KEY: dict[str, str] = {
    "original budget amount": "original_budget_amount",
    "approved cos": "approved_budget_changes",
    "approved budget changes": "approved_budget_changes",
    "budget modifications": "budget_modifications",
    "revised budget": "revised_budget",
    "pending budget changes": "pending_budget_changes",
    "projected budget": "projected_budget",
    "committed costs": "committed_costs",
    "direct costs": "direct_costs",
    "job to date costs": "job_to_date_costs",
    "erp job to date costs": "erp_job_to_date_costs",
    "erp direct costs": "erp_direct_costs",
    "pending cost changes": "pending_cost_changes",
    "projected costs": "projected_costs",
    "forecast to complete": "forecast_to_complete",
    "estimated cost at completion": "estimated_cost_at_completion",
    "projected over/under": "projected_over_under",
    "actual cost": "actual_cost",
    "commitment invoiced": "commitment_invoiced",
}


def procore_label_to_role_key(label: str) -> str | None:
    """Map a Procore budget column label/key to a budget_column_roles.yml role key."""
    normalized = " ".join((label or "").strip().lower().split())
    if not normalized:
        return None
    return _PROCORE_LABEL_TO_ROLE_KEY.get(normalized)


_DYNAMIC_CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "forecasting"
    / "semantic-catalog"
    / "budget_dynamic_columns.yml"
)


@lru_cache(maxsize=1)
def load_budget_dynamic_columns() -> dict[str, Any]:
    """Return parsed budget_dynamic_columns.yml (empty dict if missing)."""
    if not _DYNAMIC_CATALOG_PATH.exists():
        return {}
    data = yaml.safe_load(_DYNAMIC_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def dynamic_column_classifications() -> list[dict[str, Any]]:
    catalog = load_budget_dynamic_columns()
    entries = catalog.get("column_classifications", [])
    return entries if isinstance(entries, list) else []