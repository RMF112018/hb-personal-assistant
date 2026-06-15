"""Map historical (cost-code-only) rows to the canonical BudgetDetails universe.

The canonical 127-code universe is the SOLE mapping authority (reuses ``build_canonical_index``). A
historical ``cost_code`` is resolved deterministically; a code that spans multiple canonical categories
is NEVER force-mapped to one category — it becomes an explicit rollup signal. No fuzzy/description
matching creates a mapped key. Duplicate same-sheet cost codes (distinct descriptions) and absent codes
are surfaced, never silently aggregated.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict

from ..common.budget_keys import cost_code_family

# mapping_status
MAP_UNIQUE = "cost_code_unique_budget_match"
MAP_MULTI = "cost_code_multi_category_rollup"
MAP_FAMILY = "cost_code_family_rollup"
MAP_UNMAPPED = "unmapped_absent_from_budget_details"

# deterministic confidence per status (4dp strings emitted at the row builder)
CONFIDENCE = {
    MAP_UNIQUE: 1.0,
    MAP_MULTI: 0.5,
    MAP_FAMILY: 0.3,
    MAP_UNMAPPED: 0.0,
}

GR_DESC = "GENERAL REQUIREMENTS"


def group_history_by_cost_code(history_rows: list) -> "OrderedDict[str, list]":
    """Group normalized historical rows by bare cost_code (deterministic order)."""
    groups: dict = defaultdict(list)
    for r in history_rows:
        cc = r.get("cost_code")
        if cc:
            groups[cc].append(r)
    return OrderedDict((cc, groups[cc]) for cc in sorted(groups))


def _duplicate_descriptions(rows: list) -> list:
    """Distinct (sheet,row,description) lineage where the same cost code carries >1 description."""
    descs = {(r.get("description") or "").strip() for r in rows if r.get("description")}
    if len(descs) <= 1:
        return []
    lineage = sorted({(r.get("source_sheet"), r.get("source_row"), (r.get("description") or "").strip())
                      for r in rows})
    return [OrderedDict([("source_sheet", s), ("source_row", row), ("description", d)])
            for (s, row, d) in lineage]


def _is_description_sensitive(cost_code: str, rows: list) -> bool:
    """10-XX General-Requirements codes are description-sensitive (GR vs non-GR disjoint)."""
    if not cost_code or not cost_code.startswith("10-"):
        return False
    descs = {(r.get("description") or "").strip().upper() for r in rows}
    has_gr = any(d == GR_DESC for d in descs)
    has_non_gr = any(d and d != GR_DESC for d in descs)
    return has_gr and has_non_gr


def map_cost_code(cost_code: str, rows: list, index: dict) -> OrderedDict:
    """Resolve one historical cost_code against the canonical index."""
    by_cc = index["by_cost_code"].get(cost_code, [])
    fam = cost_code_family(cost_code)
    by_fam = index["by_family"].get(fam, []) if fam else []
    if len(by_cc) == 1:
        status, keys = MAP_UNIQUE, by_cc
    elif len(by_cc) > 1:
        status, keys = MAP_MULTI, by_cc
    elif by_fam:
        status, keys = MAP_FAMILY, by_fam
    else:
        status, keys = MAP_UNMAPPED, []
    single_key = keys[0] if status == MAP_UNIQUE else None
    dup = _duplicate_descriptions(rows)
    return OrderedDict([
        ("cost_code", cost_code),
        ("mapping_status", status),
        ("mapping_method", status),
        ("mapping_confidence", CONFIDENCE[status]),
        ("budget_code_key", single_key),
        ("candidate_budget_code_keys", keys),
        ("cost_code_family", fam),
        ("source_row_count", len(rows)),
        ("source_packages", sorted({r["history_source_package"] for r in rows})),
        ("distinct_descriptions", sorted({(r.get("description") or "").strip()
                                          for r in rows if r.get("description")})),
        ("duplicate_cost_code_warning", bool(dup)),
        ("duplicate_lineage", dup),
        ("description_sensitive_review", _is_description_sensitive(cost_code, rows)),
    ])


def build_mapping(history_rows: list, index: dict) -> "OrderedDict[str, OrderedDict]":
    """{cost_code: mapping_decision} over all historical cost codes."""
    groups = group_history_by_cost_code(history_rows)
    return OrderedDict((cc, map_cost_code(cc, rows, index)) for cc, rows in groups.items())


def check_code_presence(cost_code: str, history_rows: list, index: dict, current_keys: set) -> OrderedDict:
    """Explicit cross-source presence report (e.g. 15-16-100) — which sources actually contain it."""
    in_cashflow = any(r["cost_code"] == cost_code and r["history_source_package"] == "cash_flow"
                      for r in history_rows)
    in_gcgr = any(r["cost_code"] == cost_code and r["history_source_package"] == "gcgr"
                  for r in history_rows)
    in_canonical = cost_code in index["by_cost_code"]
    canonical_keys = index["by_cost_code"].get(cost_code, [])
    in_current = any(k in current_keys for k in canonical_keys)
    return OrderedDict([
        ("cost_code", cost_code),
        ("present_in_cash_flow_history", in_cashflow),
        ("present_in_gcgr_history", in_gcgr),
        ("present_in_canonical_budget_details", in_canonical),
        ("present_in_current_forecast_packages", in_current),
        ("canonical_budget_code_keys", canonical_keys),
        ("sources_checked", ["cash_flow_history", "gcgr_history",
                             "canonical_budget_details", "current_forecast_packages"]),
        ("absent_everywhere", not (in_cashflow or in_gcgr or in_canonical or in_current)),
    ])
