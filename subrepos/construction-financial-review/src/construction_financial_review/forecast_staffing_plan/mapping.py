"""Resolve source staffing cost codes to canonical budget-code keys (fail-closed).

Operator decision (binding): staffing dollars are LAB-only. For each source ``cost_code``:
1. Gather the canonical keys carrying that cost code and the role/description family they belong to.
2. The numeric target is the single canonical ``.LAB`` key for that cost code. The whole family
   (``.LAB`` / ``.LBN`` / ``.MAT``) are date-context targets only.
3. Unique resolution requires exactly ONE role-family stem AND exactly ONE ``.LAB`` key. Otherwise the
   cost code is ``ambiguous`` and applies numerically to nothing.
4. An operator mapping-override row is the acceptance signal. A code applies numerically only when the
   resolver proves a unique ``.LAB`` AND an ``accepted`` override row targets that exact ``.LAB`` key.
   An override targeting a non-canonical key is ``invented``; one disagreeing with the resolver is a
   ``mismatch``. Both fail closed.

Nothing is fabricated; no split across LAB/LBN/MAT is ever invented.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict

from ..common.budget_keys import parse_budget_key
from . import staffing_schema as ss


def build_canonical_family_index(canonical_rows) -> dict:
    """Return {cost_code: {"keys": [...], "lab_keys": [...], "roles": set(), "by_key_role": {key: role}}}."""
    idx = defaultdict(lambda: {"keys": [], "lab_keys": [], "roles": set(), "by_key_role": {}})
    for r in canonical_rows:
        key = r.get("budget_code_key")
        parsed = parse_budget_key(key)
        if not parsed:
            continue
        _sub, cc, cat = parsed
        role = ss.role_stem(r.get("budget_code_description"))
        e = idx[cc]
        e["keys"].append(key)
        if cat == "LAB":
            e["lab_keys"].append(key)
        if role:
            e["roles"].add(role)
        e["by_key_role"][key] = role
    for cc in idx:
        idx[cc]["keys"].sort()
        idx[cc]["lab_keys"].sort()
    return dict(idx)


def _accepted_override(cc: str, overrides_by_cc: dict):
    """Return the single accepted override row for a cost code, or None."""
    for r in overrides_by_cc.get(cc, []):
        if r.get("acceptance_status") == "accepted":
            return r
    return None


def _pending_override(cc: str, overrides_by_cc: dict) -> bool:
    return any(r.get("acceptance_status") == "pending" for r in overrides_by_cc.get(cc, []))


def resolve_cost_code(cost_code: str, fam_index: dict, canonical_keys, overrides_by_cc: dict,
                      require_acceptance: bool) -> "OrderedDict":
    """Resolve one source cost code into a mapping result row (does not mutate inputs)."""
    fam = fam_index.get(cost_code)
    accepted = _accepted_override(cost_code, overrides_by_cc)
    has_pending = _pending_override(cost_code, overrides_by_cc)

    numeric_key = None
    date_context = []
    role = None
    status = None
    detail = None
    allocation = "0.0000"

    if not fam or not fam["keys"]:
        status = ss.M_UNMAPPED
        detail = f"cost_code '{cost_code}' matches no canonical budget-code key"
    else:
        date_context = list(fam["keys"])
        roles = sorted(fam["roles"])
        lab_keys = fam["lab_keys"]
        role = roles[0] if len(roles) == 1 else None
        unique = (len(roles) == 1 and len(lab_keys) == 1)
        if not unique:
            status = ss.M_AMBIGUOUS
            detail = (f"cost_code '{cost_code}' resolves to roles={roles} and lab_keys={lab_keys}; "
                      "a unique role family with exactly one .LAB is required")
        else:
            resolved_lab = lab_keys[0]
            if accepted is not None:
                target = accepted.get("target_budget_code_key")
                if target not in canonical_keys:
                    status = ss.M_INVENTED
                    detail = f"accepted override target '{target}' is not a canonical budget-code key"
                elif target != resolved_lab:
                    status = ss.M_MISMATCH
                    detail = (f"accepted override target '{target}' disagrees with the resolved .LAB "
                              f"'{resolved_lab}'")
                else:
                    numeric_key = resolved_lab
                    status = ss.M_OP_APPROVED
                    allocation = accepted.get("allocation_share") or "1.0000"
                    detail = "unique .LAB family resolution confirmed by an accepted operator override"
            else:
                status = ss.M_RESOLVED_PENDING
                detail = ("unique .LAB family resolves deterministically but no accepted operator "
                          "override exists" + (" (pending override present)" if has_pending else ""))
                if not require_acceptance:
                    numeric_key = resolved_lab
                    allocation = "1.0000"

    applied = status in ss.APPLIED_STATUSES or (status == ss.M_RESOLVED_PENDING and not require_acceptance)
    return OrderedDict([
        ("source_cost_code", cost_code),
        ("resolved_role_family", role),
        ("numeric_target_budget_code_key", numeric_key),
        ("date_context_target_budget_code_keys", date_context),
        ("candidate_budget_code_keys", date_context),
        ("mapping_status", status),
        ("applied_numeric", bool(applied and numeric_key)),
        ("allocation_share", allocation if (applied and numeric_key) else "0.0000"),
        ("override_acceptance_status",
         (accepted or {}).get("acceptance_status") if accepted else ("pending" if has_pending else None)),
        ("detail", detail),
    ])
