"""Forecast-model-control row schema + vocabulary.

A control is one operator decision that configures the forecast model for one canonical budget code: its
forecast window (start/end), model shape, an optional value constraint against a selected reference, and
optional manual total / monthly inputs. The canonical field order mirrors the documented control JSON so
emitted rows are stable and diff-friendly. Money fields are Decimal-strings (2dp) or null;
``manual_monthly_values`` is an ordered ``{YYYY-MM: amount}`` map. ``accepted_at`` is written
deterministically from the package stamp when an accepted control leaves it null, so frozen-stamp runs are
byte-identical.
"""
from __future__ import annotations

from collections import OrderedDict

from ..common.money import money_str

# ---- the single control type ----
CT_MODEL_CONTROL = "forecast_model_control"
CONTROL_TYPES = (CT_MODEL_CONTROL,)

# ---- forecast window policies ----
START_CURRENT_MONTH = "current_month_start"
START_EXPLICIT = "explicit_date"
START_SCHEDULE_ACTIVITY = "schedule_activity_start"
START_EARLIEST_REMAINING = "earliest_remaining_start"
FORECAST_START_POLICIES = (
    START_CURRENT_MONTH, START_EXPLICIT, START_SCHEDULE_ACTIVITY, START_EARLIEST_REMAINING)
DEFAULT_START_POLICY = START_CURRENT_MONTH

END_LATEST_PROJECT_SCHEDULE = "latest_project_schedule_date"
END_EXPLICIT = "explicit_date"
END_SCHEDULE_ACTIVITY_FINISH = "schedule_activity_finish"
END_LATEST_SCHEDULE_FINISH = "latest_schedule_finish"
END_EXISTING_HORIZON = "existing_forecast_horizon"
FORECAST_END_POLICIES = (
    END_LATEST_PROJECT_SCHEDULE, END_EXPLICIT, END_SCHEDULE_ACTIVITY_FINISH,
    END_LATEST_SCHEDULE_FINISH, END_EXISTING_HORIZON)
DEFAULT_END_POLICY = END_LATEST_PROJECT_SCHEDULE

# ---- value-constraint policies ----
VC_NONE = "none"
VC_EQUAL = "equal_to_reference"
VC_NOT_TO_EXCEED = "not_to_exceed_reference"
VC_NOT_LESS_THAN = "not_less_than_reference"
VC_EXPLICIT_FINAL = "explicit_final_value"
VC_EXPLICIT_REMAINING = "explicit_remaining_value"
VALUE_CONSTRAINT_POLICIES = (
    VC_NONE, VC_EQUAL, VC_NOT_TO_EXCEED, VC_NOT_LESS_THAN, VC_EXPLICIT_FINAL, VC_EXPLICIT_REMAINING)
DEFAULT_VALUE_CONSTRAINT = VC_NONE
# Constraints that REQUIRE a reference_source.
REFERENCE_REQUIRED_POLICIES = frozenset({VC_EQUAL, VC_NOT_TO_EXCEED, VC_NOT_LESS_THAN})
# Constraints that REQUIRE explicit_value_amount.
EXPLICIT_AMOUNT_POLICIES = frozenset({VC_EXPLICIT_FINAL, VC_EXPLICIT_REMAINING})

# ---- reference value sources (section 7) ----
RS_EXPLICIT = "explicit_user_amount"
RS_ORIGINAL_BUDGET = "original_budget"
RS_REVISED_BUDGET = "revised_budget"
RS_PROJECTED_BUDGET = "projected_budget"
RS_PROJECTED_COST = "projected_cost"
RS_COMMITTED_COST = "committed_cost"
RS_ACCEPTED_INTEL_FINAL = "accepted_intelligence_final"
RS_PRIOR_COMPREHENSIVE_FINAL = "prior_comprehensive_integrated_final"
REFERENCE_SOURCES = (
    RS_EXPLICIT, RS_ORIGINAL_BUDGET, RS_REVISED_BUDGET, RS_PROJECTED_BUDGET, RS_PROJECTED_COST,
    RS_COMMITTED_COST, RS_ACCEPTED_INTEL_FINAL, RS_PRIOR_COMPREHENSIVE_FINAL)

# ---- model types / monthly shapes ----
MT_EXISTING = "existing_model"
MT_LINEAR = "linear"
MT_LINEAR_ASC = "linear_ascending"
MT_LINEAR_DESC = "linear_descending"
MT_FRONT_S = "front_loaded_s_curve"
MT_BACK_S = "back_loaded_s_curve"
MT_BELL = "bell_curve"
MT_MANUAL_TOTAL = "manual_total"
MT_MANUAL_MONTHLY = "manual_monthly"
MODEL_TYPES = (
    MT_EXISTING, MT_LINEAR, MT_LINEAR_ASC, MT_LINEAR_DESC, MT_FRONT_S, MT_BACK_S, MT_BELL,
    MT_MANUAL_TOTAL, MT_MANUAL_MONTHLY)
DEFAULT_MODEL_TYPE = MT_EXISTING
MODEL_TYPE_ALIASES = {"belle": MT_BELL}
# Shapes usable as a distribution policy for manual_total (deterministic monthly vectors).
SHAPE_MODEL_TYPES = frozenset({MT_LINEAR, MT_LINEAR_ASC, MT_LINEAR_DESC, MT_FRONT_S, MT_BACK_S, MT_BELL})
MANUAL_TOTAL_DISTRIBUTION_POLICIES = tuple(sorted(SHAPE_MODEL_TYPES))
DEFAULT_MANUAL_TOTAL_DISTRIBUTION = MT_LINEAR

ACCEPTANCE_STATUSES = frozenset({"pending", "accepted", "rejected"})

# Required human-acceptance fields — a control missing any of these fails closed.
REQUIRED_ACCEPTANCE_FIELDS = (
    "requires_human_acceptance", "acceptance_status", "accepted_by", "accepted_at", "reason")
# Minimum identity fields every control must carry.
REQUIRED_IDENTITY_FIELDS = ("project_key", "control_id", "control_type", "effective_month")

# Canonical field order for emitted control rows.
CONTROL_FIELD_ORDER = (
    "project_key", "control_id", "budget_code_key", "cost_code", "control_type", "effective_month",
    "forecast_start_policy", "forecast_start_date", "forecast_end_policy", "forecast_end_date",
    "value_constraint_policy", "reference_source", "reference_field", "explicit_value_amount",
    "model_type", "manual_total_distribution_policy", "manual_final_cost", "manual_remaining_cost",
    "manual_monthly_values",
    "acceptance_status", "requires_human_acceptance", "accepted_by", "accepted_at", "reason", "notes")

_MONEY_FIELDS = ("explicit_value_amount", "manual_final_cost", "manual_remaining_cost")


def normalize_model_type(model_type):
    """Normalize documented aliases (e.g. ``belle`` -> ``bell_curve``)."""
    if model_type is None:
        return None
    return MODEL_TYPE_ALIASES.get(model_type, model_type)


def is_value_changing_policy(policy) -> bool:
    """A value-constraint policy that can change the deterministic final cost (not ``none``)."""
    return policy in (VC_EQUAL, VC_NOT_TO_EXCEED, VC_NOT_LESS_THAN, VC_EXPLICIT_FINAL, VC_EXPLICIT_REMAINING)


def effective_start_policy(control: dict) -> str:
    return control.get("forecast_start_policy") or DEFAULT_START_POLICY


def effective_end_policy(control: dict) -> str:
    return control.get("forecast_end_policy") or DEFAULT_END_POLICY


def effective_value_constraint(control: dict) -> str:
    return control.get("value_constraint_policy") or DEFAULT_VALUE_CONSTRAINT


def effective_model_type(control: dict) -> str:
    return normalize_model_type(control.get("model_type")) or DEFAULT_MODEL_TYPE


def effective_manual_distribution(control: dict) -> str:
    return (normalize_model_type(control.get("manual_total_distribution_policy"))
            or DEFAULT_MANUAL_TOTAL_DISTRIBUTION)


def normalize_control(raw: dict, stamp_iso: str | None = None) -> "OrderedDict":
    """Return a control row in canonical field order; normalize money + aliases; stamp accepted_at.

    Unknown extra keys are preserved after the canonical block so nothing operator-entered is dropped.
    Defaults for policy/model fields are applied at resolution time (not here), so the stored row stays
    faithful to what the operator wrote.
    """
    row = OrderedDict()
    for f in CONTROL_FIELD_ORDER:
        row[f] = raw.get(f)
    for mf in _MONEY_FIELDS:
        row[mf] = money_str(row[mf]) if row[mf] is not None else None
    row["model_type"] = normalize_model_type(row["model_type"])
    row["manual_total_distribution_policy"] = normalize_model_type(row["manual_total_distribution_policy"])
    mmv = row.get("manual_monthly_values")
    if isinstance(mmv, dict):
        row["manual_monthly_values"] = OrderedDict(
            (m, money_str(mmv[m]) if mmv[m] is not None else None) for m in sorted(mmv.keys()))
    if row.get("acceptance_status") == "accepted" and row.get("accepted_at") is None:
        row["accepted_at"] = stamp_iso
    for k in sorted(raw.keys()):
        if k not in row:
            row[k] = raw[k]
    return row
