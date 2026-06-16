"""BudgetDetails budget-code-key parsing.

Canonical key format: ``sub_job.cost_code.category`` (e.g. ``1000.15-16-110.SUB``).
BudgetDetails is the master budget-code universe — keys are never invented.
"""
from __future__ import annotations

from typing import Optional, Tuple

VALID_CATEGORIES = ("SUB", "MAT", "LAB", "LBN", "OVH")


def parse_budget_key(key) -> Optional[Tuple[str, str, str]]:
    """Split ``sub_job.cost_code.category`` -> (sub_job, cost_code, category) or None.

    The cost_code itself contains dashes, so we split on exactly three dotted segments.
    """
    if not isinstance(key, str):
        return None
    parts = key.split(".")
    if len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def cost_code_family(cost_code) -> Optional[str]:
    """First two dash-segments, e.g. ``15-16-110`` -> ``15-16`` ; ``15-01-XXX`` -> ``15-01``."""
    if not isinstance(cost_code, str):
        return None
    segs = cost_code.split("-")
    if len(segs) >= 2 and segs[0] and segs[1]:
        return f"{segs[0]}-{segs[1]}"
    return None


def build_budget_key(sub_job: str, cost_code: str, category: str) -> str:
    return f"{sub_job}.{cost_code}.{category}"


def is_valid_category(category) -> bool:
    return category in VALID_CATEGORIES
