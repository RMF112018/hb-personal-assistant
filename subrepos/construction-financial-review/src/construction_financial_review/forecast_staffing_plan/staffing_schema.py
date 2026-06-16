"""Schema + vocabulary for the staffing-plan slice.

Two normalized row shapes are defined here:
- the operator mapping-override row (cost_code -> canonical .LAB target, with acceptance metadata), and
- the staffing-plan monthly/bridge row field order helpers.

Money is Decimal-string (2dp) or null; allocation shares are 4dp Decimal strings. ``accepted_at`` /
``created_at`` are stamped deterministically from the package stamp when left null so frozen-stamp runs
are byte-identical.
"""
from __future__ import annotations

from collections import OrderedDict

from ..common.money import money_str

# ---- mapping status vocabulary (resolver output) ----
M_OP_APPROVED = "mapped_operator_approved_lab"          # unique .LAB resolution AND accepted override
M_RESOLVED_PENDING = "resolved_unique_lab_pending_acceptance"  # unique .LAB but no accepted override
M_AMBIGUOUS = "ambiguous_multiple_lab_or_family"        # >1 role family or >1 .LAB for the cost code
M_INVENTED = "override_target_not_canonical"            # override points at a non-canonical key
M_MISMATCH = "override_target_disagrees_with_resolver"  # accepted override target != resolved .LAB
M_UNMAPPED = "unmapped_no_canonical_match"              # cost code matches no canonical key

# Statuses whose numeric staffing dollars are APPLIED to the .LAB code.
APPLIED_STATUSES = frozenset({M_OP_APPROVED})

# Mapping-override acceptance vocabulary.
ACCEPTANCE_STATUSES = frozenset({"pending", "accepted", "rejected"})

# Canonical field order for an operator mapping-override row.
MAPPING_FIELD_ORDER = (
    "project_key", "source_cost_code", "target_budget_code_key", "mapping_type", "allocation_share",
    "effective_start", "effective_end", "reason", "acceptance_status", "accepted_by", "accepted_at",
    "notes",
)

# Required identity fields a mapping-override row must carry.
REQUIRED_MAPPING_FIELDS = ("project_key", "source_cost_code", "target_budget_code_key", "acceptance_status")


def normalize_mapping(raw: dict, stamp_iso: str | None = None) -> "OrderedDict":
    """Return a mapping-override row in canonical field order; stamp null accepted_at deterministically."""
    row = OrderedDict()
    for f in MAPPING_FIELD_ORDER:
        row[f] = raw.get(f)
    # allocation share normalized to a 4dp decimal string (default 1.0000 when present-but-blank)
    share = row.get("allocation_share")
    row["allocation_share"] = _share_str(share) if share is not None else "1.0000"
    if row.get("acceptance_status") == "accepted" and row.get("accepted_at") is None:
        row["accepted_at"] = stamp_iso
    for k in sorted(raw.keys()):
        if k not in row:
            row[k] = raw[k]
    return row


def _share_str(v) -> str:
    from decimal import Decimal, InvalidOperation
    try:
        return str(Decimal(str(v)).quantize(Decimal("0.0001")))
    except (InvalidOperation, ValueError):
        return "0.0000"


def role_stem(description) -> str | None:
    """Extract the canonical staffing-family role from a BudgetDetails description.

    Descriptions look like ``TROPICAL WORLD NURSERY-CONSTR.SUPERINTENDENT 2.Labor`` — the role is the
    middle dotted segment(s) between the project/phase prefix and the category suffix
    (``Labor`` / ``Labor Burden`` / ``Materials``). Returns the role, or the whole string if it does
    not split into the expected three-part shape.
    """
    if not isinstance(description, str) or not description:
        return None
    parts = description.split(".")
    if len(parts) >= 3:
        return ".".join(parts[1:-1]).strip()
    return description.strip()


def money_or_none(v):
    return money_str(v) if v is not None else None
