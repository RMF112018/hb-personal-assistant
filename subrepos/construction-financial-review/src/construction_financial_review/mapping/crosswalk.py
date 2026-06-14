"""Authoritative owner SOV scope crosswalk loader + deterministic expander.

The crosswalk is AUTHORITATIVE — consumed verbatim, never inferred/fuzzy-matched/overridden. The
EXPLICIT ``covered_budget_code_keys`` / ``covered_procore_wbs_flat_codes`` lists are the source of
truth (any ``*_patterns`` / ``*_exclusion_patterns`` fields are human-readable provenance only).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from ..common.io import read_jsonl

REQUIRED_FIELDS = (
    "crosswalk_id", "owner_sov_code", "scope_relationship", "comparison_level",
    "coverage_type", "covered_budget_code_keys",
)


def load_crosswalk(path: str | Path) -> list:
    """Load all crosswalk rows from JSONL."""
    return list(read_jsonl(path))


def expanded_budget_keys(row: dict, canonical_keys: Optional[set] = None) -> list:
    """Explicit covered budget keys (optionally intersected with the canonical universe)."""
    keys = list(row.get("covered_budget_code_keys") or [])
    if canonical_keys is not None:
        keys = [k for k in keys if k in canonical_keys]
    return sorted(set(keys))


def expanded_procore_wbs(row: dict, wbs_universe: Optional[set] = None) -> list:
    wbs = list(row.get("covered_procore_wbs_flat_codes") or [])
    if wbs_universe is not None:
        wbs = [w for w in wbs if w in wbs_universe]
    return sorted(set(wbs))


def build_budget_assignment(rows: list, canonical_keys: Optional[set] = None):
    """Return (assign: key->row, duplicates: list[key]) from explicit coverage lists."""
    assign = {}
    duplicates = []
    for r in rows:
        for k in expanded_budget_keys(r, canonical_keys):
            if k in assign:
                duplicates.append(k)
            assign[k] = r
    return assign, duplicates


def build_procore_assignment(rows: list, wbs_universe: Optional[set] = None):
    assign = defaultdict(list)
    for r in rows:
        for w in expanded_procore_wbs(r, wbs_universe):
            assign[w].append(r)
    return assign


def covers(rows: list, owner_sov_code: str, budget_code_key: str) -> bool:
    """True if the named owner SOV row explicitly covers the budget code key."""
    for r in rows:
        if r.get("owner_sov_code") == owner_sov_code and budget_code_key in (r.get("covered_budget_code_keys") or []):
            return True
    return False
