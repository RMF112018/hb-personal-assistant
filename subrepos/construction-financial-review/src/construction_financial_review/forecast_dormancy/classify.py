"""Deterministic per-code dormant/closed classification.

``classify(inputs, cfg)`` returns a decision dict (status + suppression flag + evidence + reason + the
audit scalars). Pure and deterministic — a function of the supplied per-code signals only. Statuses:

- ``active_forecastable``           — recent actual cost within the lookback window.
- ``active_with_remaining_evidence``— no recent cost but affirmative remaining-cost evidence exists.
- ``operator_controlled``           — a value-asserting accepted model control provides positive remaining.
- ``closed_do_not_use``             — closure phrase detected, no contrary evidence (suppress).
- ``inactive_no_remaining_evidence``— never incurred cost and no evidence (suppress).
- ``dormant_no_recent_cost``        — idle >= lookback months and no evidence (suppress).

Precedence (contrary evidence overrides closure): value-asserting operator control > recent actual cost >
affirmative remaining evidence > closure phrase > never-active > idle-beyond-lookback.
"""
from __future__ import annotations

import re
from collections import OrderedDict
from decimal import Decimal

from ..common.money import D, dec, money_str

ZERO = Decimal("0")
CENTS = Decimal("0.01")

# ---- statuses ----
S_ACTIVE = "active_forecastable"
S_ACTIVE_EVIDENCE = "active_with_remaining_evidence"
S_OPERATOR = "operator_controlled"
S_CLOSED = "closed_do_not_use"
S_INACTIVE = "inactive_no_remaining_evidence"
S_DORMANT = "dormant_no_recent_cost"
SUPPRESSED_STATUSES = frozenset({S_CLOSED, S_INACTIVE, S_DORMANT})

DEFAULT_STRONG_PATTERNS = ("CLOSED - DO NOT USE", "DO NOT USE", "INACTIVE")
DEFAULT_BARE_TOKEN_FIELDS = ("sub_job_description",)
DEFAULT_LOOKBACK = 18


def _norm(s) -> str:
    return re.sub(r"\s+", " ", (s or "").upper()).strip()


def _mi(ym) -> int | None:
    """Month index for 'YYYY-MM' (or longer date) -> year*12 + month - 1."""
    if not ym or len(ym) < 7 or ym[4] != "-":
        return None
    try:
        return int(ym[:4]) * 12 + int(ym[5:7]) - 1
    except ValueError:
        return None


def detect_closure(sub_desc, bc_desc, cost_desc, cfg) -> tuple:
    """Return (closure_detected, matched_phrase). Strict: bare CLOSED only in status-like fields."""
    strong = [p for p in (cfg.get("closed_description_patterns") or DEFAULT_STRONG_PATTERNS)]
    blob = " ".join(_norm(f) for f in (sub_desc, bc_desc, cost_desc))
    for p in strong:
        if _norm(p) and _norm(p) in blob:
            return True, p
    field_map = {"sub_job_description": _norm(sub_desc), "budget_code_description": _norm(bc_desc),
                 "cost_type_description": _norm(cost_desc)}
    for sf in (cfg.get("closed_bare_token_status_fields") or DEFAULT_BARE_TOKEN_FIELDS):
        v = field_map.get(sf, "")
        if v == "CLOSED" or v.startswith("CLOSED ") or v.startswith("CLOSED-"):
            return True, "CLOSED"
    return False, None


def _last_actual_month(monthly_actuals) -> str | None:
    months = [m.get("month") for m in (monthly_actuals or [])
              if m.get("month") and (D(m.get("amount_decimal_string")) != ZERO)]
    return max(months) if months else None


def _recent_date(period_str, current_month, lookback) -> bool:
    """True if a 'YYYY-MM-DD' activity date is within `lookback` months of the current forecast month."""
    pi, ci = _mi(period_str[:7] if period_str else None), _mi(current_month)
    if pi is None or ci is None:
        return False
    return (ci - pi) <= lookback


def classify(inputs: dict, cfg: dict) -> "OrderedDict":
    """Classify one budget code. Pure + deterministic."""
    lookback = int(cfg.get("lookback_months_without_actual_cost") or DEFAULT_LOOKBACK)
    key = inputs.get("budget_code_key")
    current_month = inputs.get("current_forecast_month")
    actual = D(inputs.get("actual_cost_to_date"))

    closure_detected, phrase = detect_closure(
        inputs.get("sub_job_description"), inputs.get("budget_code_description"),
        inputs.get("cost_type_description"), cfg)

    last_actual = _last_actual_month(inputs.get("monthly_actuals"))
    ci, li = _mi(current_month), _mi(last_actual)
    months_since = (ci - li) if (ci is not None and li is not None) else None
    trailing_zero = months_since if months_since is not None else None

    # ---- affirmative remaining-cost evidence ----
    committed = dec(inputs.get("committed_costs"))
    invoiced = dec(inputs.get("commitment_invoiced"))
    open_commitment = None
    if committed is not None:
        open_commitment = committed - (invoiced if invoiced is not None else ZERO)
    has_open_commitment = open_commitment is not None and open_commitment > CENTS

    owner_recent = _recent_date(inputs.get("owner_latest_period_to"), current_month, lookback)
    sub_recent = _recent_date(inputs.get("procore_latest_period_end"), current_month, lookback)

    sched_status = inputs.get("schedule_remaining_work_status")
    open_acts = int(inputs.get("schedule_open_activity_count") or 0)
    sched_finish_future = (_mi(inputs.get("schedule_latest_finish")) is not None
                           and ci is not None and _mi(inputs.get("schedule_latest_finish")) >= ci)
    schedule_evidence = sched_status == "material_remaining_work" or (open_acts > 0 and sched_finish_future)

    recent_cost = (last_actual is not None and months_since is not None and months_since < lookback)

    evidence = []
    if has_open_commitment:
        evidence.append(f"open_commitment_remaining={money_str(open_commitment)}")
    if owner_recent:
        evidence.append("owner_pay_app_recent_activity")
    if sub_recent:
        evidence.append("subcontractor_pay_app_recent_activity")
    if schedule_evidence:
        evidence.append("schedule_remaining_work")

    # ---- value-asserting operator control override ----
    mdec = inputs.get("model_control")
    op_value_assert = bool(mdec and mdec.get("changes_deterministic_final")
                           and D(mdec.get("controlled_remaining")) > ZERO)

    # ---- precedence ----
    if op_value_assert:
        status, suppress = S_OPERATOR, False
        reason = (f"accepted value-asserting operator model control '{mdec.get('control_id')}' "
                  f"(controlled_remaining={money_str(D(mdec.get('controlled_remaining')))}) overrides dormancy")
    elif recent_cost:
        status, suppress = S_ACTIVE, False
        reason = f"recent actual cost (last {last_actual}, {months_since} months ago < {lookback})"
    elif evidence:
        status, suppress = S_ACTIVE_EVIDENCE, False
        reason = "no recent actual cost but affirmative remaining evidence: " + ", ".join(evidence)
    elif closure_detected:
        status, suppress = S_CLOSED, True
        reason = (f"closure phrase '{phrase}' detected and no recent actual cost "
                  f"(last {last_actual or 'never'}, {months_since if months_since is not None else 'n/a'} "
                  f"months idle); no affirmative remaining evidence")
    elif last_actual is None and actual == ZERO:
        status, suppress = S_INACTIVE, True
        reason = "never incurred cost and no affirmative remaining evidence"
    elif months_since is not None and months_since >= lookback:
        status, suppress = S_DORMANT, True
        reason = (f"no actual cost for {months_since} months (>= {lookback}); "
                  f"no affirmative remaining evidence (last actual {last_actual})")
    else:
        status, suppress = S_ACTIVE, False
        reason = "active"

    return OrderedDict([
        ("budget_code_key", key), ("cost_code", inputs.get("cost_code")),
        ("category", inputs.get("category")),
        ("description", inputs.get("budget_code_description") or inputs.get("sub_job_description")),
        ("dormant_status", status), ("suppression_applied", bool(suppress)),
        ("closure_phrase_detected", bool(closure_detected)), ("closure_phrase", phrase),
        ("last_actual_month", last_actual), ("months_since_last_actual", months_since),
        ("trailing_zero_months", trailing_zero),
        ("actual_cost_to_date", money_str(actual)),
        ("current_budget", money_str(dec(inputs.get("revised_budget"))) if inputs.get("revised_budget") is not None else None),
        ("projected_cost", money_str(dec(inputs.get("projected_costs"))) if inputs.get("projected_costs") is not None else None),
        ("committed_cost", money_str(committed) if committed is not None else None),
        ("open_commitment_remaining", money_str(open_commitment) if open_commitment is not None else None),
        ("owner_pay_app_recent_activity", bool(owner_recent)),
        ("subcontractor_pay_app_recent_activity", bool(sub_recent)),
        ("schedule_remaining_evidence", bool(schedule_evidence)),
        ("operator_control_override", bool(op_value_assert)),
        ("operator_control_id", (mdec or {}).get("control_id") if op_value_assert else None),
        ("remaining_evidence", evidence),
        ("suppression_reason", reason),
    ])
