"""Repo-owned, cross-platform daily source-refresh scheduler.

App-level state owns catch-up: the native OS backends (launchd / Windows Task
Scheduler / systemd) and the foreground loop only fire the repo runner; the
`due` logic + persisted `SchedulerState` decide whether a run is actually due and
prevent double-running the same schedule date.
"""

from __future__ import annotations

from hb_assistant.scheduler.daily_source_refresh import DailySourceRefreshJob
from hb_assistant.scheduler.due import CatchUpDecision, compute_next_run, decide_catch_up, is_missed
from hb_assistant.scheduler.models import InstallPlan, ScheduledRefreshReceipt
from hb_assistant.scheduler.runner import SchedulerRunner
from hb_assistant.scheduler.state import SchedulerState

__all__ = [
    "CatchUpDecision",
    "DailySourceRefreshJob",
    "InstallPlan",
    "ScheduledRefreshReceipt",
    "SchedulerRunner",
    "SchedulerState",
    "compute_next_run",
    "decide_catch_up",
    "is_missed",
]
