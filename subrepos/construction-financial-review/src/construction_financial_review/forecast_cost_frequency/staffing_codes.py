"""Configured weekly internal-staffing codes + future staff-change-event placeholder.

The configured override is authoritative: a code in ``weekly_internal_staffing_budget_code_keys`` is
ALWAYS treated as weekly-incurred internal staffing/labor-burden, regardless of what cadence the raw
entry counts would otherwise suggest. Staff-change events are a future-ready schema only — none are
ever fabricated; the list defaults empty until a schedule-staffing source provides them.
"""
from __future__ import annotations

from collections import OrderedDict

# Future schema (read from config; never synthesized): when a person/role leaves or joins a code.
STAFF_CHANGE_EVENT_FIELDS = ("effective_date", "budget_code_key", "action", "note")


def staffing_keys(cfg_fcf: dict) -> set:
    return set((cfg_fcf or {}).get("weekly_internal_staffing_budget_code_keys") or [])


def is_internal_staffing_code(budget_code_key, cfg_fcf: dict) -> bool:
    return budget_code_key in staffing_keys(cfg_fcf)


def staff_change_events(cfg_fcf: dict) -> list:
    """Return configured staff-change events (effective-dated). Empty by default — never fabricated."""
    out = []
    for e in (cfg_fcf or {}).get("staff_change_events") or []:
        out.append(OrderedDict([(f, e.get(f)) for f in STAFF_CHANGE_EVENT_FIELDS]))
    return out


def policy_audit(cfg_fcf: dict, canonical_keys: set, project_key: str) -> OrderedDict:
    """Census of configured staffing codes vs the canonical universe (found / missing)."""
    keys = sorted(staffing_keys(cfg_fcf))
    found = [k for k in keys if k in canonical_keys]
    missing = [k for k in keys if k not in canonical_keys]
    return OrderedDict([
        ("project_key", project_key),
        ("configured_staffing_code_count", len(keys)),
        ("configured_staffing_codes", keys),
        ("found_in_canonical_budget_details", found),
        ("missing_from_canonical_budget_details", missing),
        ("all_configured_present", not missing),
        ("staff_change_events_configured", len(staff_change_events(cfg_fcf))),
        ("staff_change_events_note",
         "future-ready placeholder; no staff-change events are fabricated by this slice"),
    ])
