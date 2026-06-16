"""Resolve a control's forecast window (start/end) per canonical budget code.

Start/end policies map to dates from the control, the per-code schedule evidence, or the project
schedule manifest, then are intersected with the project forecast calendar to produce the active months.

End resolution order (default ``latest_project_schedule_date``):
  1. explicit ``forecast_end_date`` -> use it (basis ``explicit_date``);
  2. a code-specific schedule-end policy AND a usable mapped code schedule date -> use it
     (basis ``code_mapped_schedule_date``);
  3. else the latest date anywhere in the project schedule (basis ``project_schedule_final_date``);
  4. only if the ENTIRE schedule dataset is missing/unparseable -> existing forecast horizon
     (basis ``existing_forecast_horizon_fallback``); ``window_degraded`` is set ONLY in this case.

A code being unmapped to schedule activities never degrades the window — it simply falls through to the
project schedule final date. ``impossible_window`` is set when the resolved window does not intersect the
project calendar at all (caller fails closed).
"""
from __future__ import annotations

from collections import OrderedDict

from ..common.dates import normalize_date
from . import control_schema as cs

# end-policy -> the code-specific schedule field it prefers
_CODE_END_FIELD = {
    cs.END_SCHEDULE_ACTIVITY_FINISH: "latest_remaining_finish",
    cs.END_LATEST_SCHEDULE_FINISH: "latest_schedule_finish",
}
_CODE_START_FIELD = {
    cs.START_SCHEDULE_ACTIVITY: "earliest_activity_start",
    cs.START_EARLIEST_REMAINING: "earliest_remaining_start",
}


def _month(date_str):
    d = normalize_date(date_str)
    return d[:7] if d else None


def resolve_window(control: dict, key_schedule: dict | None, project_schedule: dict,
                   calendar_months: list) -> "OrderedDict":
    """Resolve the active forecast window for one control. Pure + deterministic."""
    key_schedule = key_schedule or {}
    cal_first = calendar_months[0] if calendar_months else None
    cal_last = calendar_months[-1] if calendar_months else None
    schedule_present = bool(project_schedule.get("schedule_present"))
    project_final = normalize_date(project_schedule.get("latest_project_schedule_date"))

    start_policy = cs.effective_start_policy(control)
    end_policy = cs.effective_end_policy(control)

    # ---- start ----
    start_basis = start_policy
    if start_policy == cs.START_EXPLICIT:
        start_date = normalize_date(control.get("forecast_start_date"))
    elif start_policy in _CODE_START_FIELD:
        start_date = normalize_date(key_schedule.get(_CODE_START_FIELD[start_policy]))
    else:  # current_month_start
        start_date = None
    start_month = _month(start_date)
    if start_month is None:
        start_month, start_basis = cal_first, "current_month_start"

    # ---- end ----
    window_degraded = False
    degraded_reason = None
    if end_policy == cs.END_EXPLICIT:
        end_date = normalize_date(control.get("forecast_end_date"))
        end_basis = "explicit_date"
    elif end_policy == cs.END_EXISTING_HORIZON:
        end_date, end_basis = None, "existing_forecast_horizon_fallback"
    elif end_policy in _CODE_END_FIELD:
        code_end = normalize_date(key_schedule.get(_CODE_END_FIELD[end_policy]))
        if code_end:
            end_date, end_basis = code_end, "code_mapped_schedule_date"
        elif project_final:
            end_date, end_basis = project_final, "project_schedule_final_date"
        else:
            end_date, end_basis = None, "existing_forecast_horizon_fallback"
    else:  # latest_project_schedule_date (default)
        if project_final:
            end_date, end_basis = project_final, "project_schedule_final_date"
        else:
            end_date, end_basis = None, "existing_forecast_horizon_fallback"

    end_month = _month(end_date)
    if end_month is None:
        end_month = cal_last
        if end_basis == "existing_forecast_horizon_fallback" and not schedule_present:
            window_degraded = True
            degraded_reason = "entire project schedule dataset missing or unparseable"

    # ---- intersect with the project calendar ----
    active = [m for m in calendar_months if (start_month is None or m >= start_month)
              and (end_month is None or m <= end_month)]
    impossible = not active

    return OrderedDict([
        ("forecast_start_policy", start_policy), ("forecast_end_policy", end_policy),
        ("resolved_start_date", start_date if start_policy != cs.START_CURRENT_MONTH else None),
        ("resolved_end_date", end_date),
        ("start_month", start_month), ("end_month", end_month),
        ("schedule_start_basis", start_basis), ("schedule_end_basis", end_basis),
        ("active_months", active), ("active_month_count", len(active)),
        ("calendar_first_month", cal_first), ("calendar_last_month", cal_last),
        ("window_degraded", window_degraded), ("window_degraded_reason", degraded_reason),
        ("impossible_window", impossible),
    ])
