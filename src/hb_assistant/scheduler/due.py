"""Pure due/catch-up logic. No I/O, no implicit clock — the caller injects ``now``.

Rules:
- Run daily at the local schedule time (default 20:00).
- If the machine was asleep/off/the app wasn't running at the schedule time, run once
  at the next wake/start (when ``catch_up_on_wake``).
- Never double-run the same schedule date (guarded by ``last_successful_schedule_date``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from hb_assistant.scheduler.state import SchedulerState


@dataclass(frozen=True)
class CatchUpDecision:
    should_run: bool
    schedule_date: str  # ISO date of the target schedule occurrence
    reason: str
    now_local: str
    next_expected_run: str


def _parse_hhmm(value: str) -> tuple[int, int]:
    hh, mm = value.split(":", 1)
    return int(hh), int(mm)


def compute_next_run(now: datetime, schedule_time_local: str, timezone: str) -> datetime:
    """The next future occurrence of the local schedule time."""
    zone = ZoneInfo(timezone)
    now_local = now.astimezone(zone)
    hh, mm = _parse_hhmm(schedule_time_local)
    today_run = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now_local >= today_run:
        today_run = today_run + timedelta(days=1)
    return today_run


def _target_schedule_date(now_local: datetime, hh: int, mm: int) -> date:
    """The most recent schedule date whose scheduled time is <= now."""
    today_run = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now_local >= today_run:
        return now_local.date()
    return (now_local - timedelta(days=1)).date()


def is_missed(now: datetime, state: SchedulerState, timezone: str) -> bool:
    zone = ZoneInfo(timezone)
    now_local = now.astimezone(zone)
    hh, mm = _parse_hhmm(state.schedule_time_local)
    target = _target_schedule_date(now_local, hh, mm).isoformat()
    return state.last_successful_schedule_date != target


def decide_catch_up(
    now: datetime,
    state: SchedulerState,
    *,
    schedule_time_local: str,
    timezone: str,
    catch_up_on_wake: bool,
) -> CatchUpDecision:
    zone = ZoneInfo(timezone)
    now_local = now.astimezone(zone)
    hh, mm = _parse_hhmm(schedule_time_local)
    target = _target_schedule_date(now_local, hh, mm)
    target_iso = target.isoformat()
    next_run = compute_next_run(now, schedule_time_local, timezone).isoformat()

    if state.last_successful_schedule_date == target_iso:
        return CatchUpDecision(
            False, target_iso, "already_succeeded_for_date", now_local.isoformat(), next_run
        )

    is_today = target == now_local.date()
    if not is_today and not catch_up_on_wake:
        # A prior day's run was missed and catch-up is disabled — wait for the next 20:00.
        return CatchUpDecision(
            False, target_iso, "catch_up_disabled", now_local.isoformat(), next_run
        )

    reason = "due_on_time" if is_today else "catch_up_missed_schedule"
    return CatchUpDecision(True, target_iso, reason, now_local.isoformat(), next_run)
