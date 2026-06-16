"""Operator forecast-control row schema + control-type vocabulary.

A control is one operator decision for one budget code. The canonical field order mirrors the documented
control JSON exactly so emitted rows are stable and diff-friendly. Money fields are Decimal-strings
(2dp) or null. `created_at` / `accepted_at` are written deterministically from the package stamp when
left null, so frozen-stamp runs are byte-identical.
"""
from __future__ import annotations

from collections import OrderedDict

from ..common.money import money_str

# ---- control types ----
CT_CLOSEOUT_STOP = "closeout_stop_date"
CT_FORECAST_STOP = "forecast_stop_date"
CT_REMAINING_ALLOWANCE = "remaining_cost_allowance"
CT_FINAL_OVERRIDE = "accepted_final_cost_override"
CT_MONTHLY_DIST = "monthly_distribution_override"
CT_INACTIVE_AFTER = "inactive_after_date"
CT_WATCH_ONLY = "watch_only"

CONTROL_TYPES = (
    CT_CLOSEOUT_STOP, CT_FORECAST_STOP, CT_REMAINING_ALLOWANCE, CT_FINAL_OVERRIDE,
    CT_MONTHLY_DIST, CT_INACTIVE_AFTER, CT_WATCH_ONLY,
)

# Stop-date / closeout-window controls: they reshape monthly timing and zero post-stop months.
STOP_DATE_TYPES = frozenset({CT_CLOSEOUT_STOP, CT_FORECAST_STOP, CT_INACTIVE_AFTER})
# Dollar controls: they change the integrated remaining / final cost.
DOLLAR_TYPES = frozenset({CT_REMAINING_ALLOWANCE, CT_FINAL_OVERRIDE})

ACCEPTANCE_STATUSES = frozenset({"pending", "accepted", "rejected"})

# Required human-acceptance fields — a control missing any of these fails closed.
REQUIRED_ACCEPTANCE_FIELDS = (
    "requires_human_acceptance", "acceptance_status", "accepted_by", "accepted_at", "acceptance_notes",
)
# Minimum identity fields every control must carry.
REQUIRED_IDENTITY_FIELDS = ("project_key", "control_id", "control_type")

# Canonical field order for emitted control rows.
CONTROL_FIELD_ORDER = (
    "project_key", "control_id", "budget_code_key", "cost_code", "description", "control_type",
    "effective_month", "forecast_stop_date", "post_stop_monthly_forecast", "remaining_cost_policy",
    "accepted_remaining_cost", "accepted_final_cost", "monthly_distribution_policy", "reason", "source",
    "requires_human_acceptance", "acceptance_status", "accepted_by", "accepted_at", "acceptance_notes",
    "created_by", "created_at", "expires_after_package", "notes",
)


def is_stop_date_type(control_type) -> bool:
    return control_type in STOP_DATE_TYPES


def is_dollar_type(control_type) -> bool:
    return control_type in DOLLAR_TYPES


def is_posture_changing(control_type) -> bool:
    """A control that changes forecast posture (zeroes months or changes dollars) — requires acceptance."""
    return control_type in STOP_DATE_TYPES or control_type in DOLLAR_TYPES


def stop_month_for(control: dict) -> str | None:
    """Month-level stop month (YYYY-MM) for a stop-date control, derived from forecast_stop_date."""
    if not is_stop_date_type(control.get("control_type")):
        return None
    d = control.get("forecast_stop_date")
    if isinstance(d, str) and len(d) >= 7:
        return d[:7]
    return None


def normalize_control(raw: dict, stamp_iso: str | None = None) -> "OrderedDict":
    """Return a control row in canonical field order; stamp null created_at/accepted_at deterministically.

    Money fields are normalized to canonical 2dp strings (or kept null). Unknown extra keys are preserved
    after the canonical block so nothing operator-entered is silently dropped.
    """
    row = OrderedDict()
    for f in CONTROL_FIELD_ORDER:
        row[f] = raw.get(f)
    # canonical money strings (null preserved)
    for mf in ("post_stop_monthly_forecast", "accepted_remaining_cost", "accepted_final_cost"):
        row[mf] = money_str(row[mf]) if row[mf] is not None else None
    if row.get("created_at") is None:
        row["created_at"] = stamp_iso
    if row.get("acceptance_status") == "accepted" and row.get("accepted_at") is None:
        row["accepted_at"] = stamp_iso
    # preserve any extra operator keys deterministically
    for k in sorted(raw.keys()):
        if k not in row:
            row[k] = raw[k]
    return row
