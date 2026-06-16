"""Map operator controls to canonical BudgetDetails budget_code_keys.

Rules (fail closed):
- An explicit `budget_code_key` must exist in the canonical universe — never invent a key.
- A `cost_code`-only control resolves ONLY when exactly one canonical key carries that cost code;
  otherwise it is ambiguous (fail when `fail_on_ambiguous_cost_code`).
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict

from ..common.budget_keys import parse_budget_key

# mapping status values
M_EXPLICIT = "mapped_explicit"
M_RESOLVED = "mapped_resolved_from_cost_code"
M_AMBIGUOUS = "ambiguous_cost_code"
M_INVENTED = "invented_budget_code_key"
M_UNMAPPED = "unmapped_no_match"
M_MISSING = "no_budget_code_or_cost_code"

MAPPED_STATUSES = frozenset({M_EXPLICIT, M_RESOLVED})


def cost_code_to_keys(canonical_keys) -> dict:
    """Build {cost_code: [budget_code_key,...]} from the canonical key universe."""
    out = defaultdict(list)
    for k in sorted(canonical_keys):
        parsed = parse_budget_key(k)
        if parsed:
            out[parsed[1]].append(k)
    return {cc: sorted(ks) for cc, ks in out.items()}


def map_control(control: dict, canonical_keys, cc_index: dict) -> "OrderedDict":
    """Return a mapping result row for one control (does not mutate the control)."""
    bck = control.get("budget_code_key")
    cc = control.get("cost_code")
    mapped_key, status, candidates, detail = None, None, [], None

    if bck:
        if bck in canonical_keys:
            mapped_key, status = bck, M_EXPLICIT
            detail = "explicit budget_code_key present in canonical universe"
        else:
            status = M_INVENTED
            detail = f"budget_code_key '{bck}' not in canonical BudgetDetails universe"
    elif cc:
        candidates = cc_index.get(cc, [])
        if len(candidates) == 1:
            mapped_key, status = candidates[0], M_RESOLVED
            detail = f"cost_code '{cc}' resolved to single canonical key"
        elif len(candidates) > 1:
            status = M_AMBIGUOUS
            detail = f"cost_code '{cc}' maps to {len(candidates)} canonical keys; budget_code_key required"
        else:
            status = M_UNMAPPED
            detail = f"cost_code '{cc}' matches no canonical key"
    else:
        status = M_MISSING
        detail = "control carries neither budget_code_key nor cost_code"

    return OrderedDict([
        ("control_id", control.get("control_id")),
        ("control_type", control.get("control_type")),
        ("requested_budget_code_key", bck),
        ("requested_cost_code", cc),
        ("mapped_budget_code_key", mapped_key),
        ("mapping_status", status),
        ("candidate_budget_code_keys", candidates),
        ("detail", detail),
    ])
