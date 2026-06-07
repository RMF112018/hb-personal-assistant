"""SchedulerRunner: drive due/catch-up decisions and execute the daily job.

The runner is invoked by every backend (native OS scheduler or the foreground loop).
It reads the persisted state, asks `due` whether a run is owed for the current target
schedule date, runs the job at most once per schedule date, and persists state +
``next_expected_run``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from hb_assistant.launcher.profiles import Profile
from hb_assistant.scheduler.daily_source_refresh import DailySourceRefreshJob
from hb_assistant.scheduler.due import compute_next_run, decide_catch_up
from hb_assistant.scheduler.models import ScheduledRefreshReceipt
from hb_assistant.scheduler.state import SchedulerState


class SchedulerRunner:
    def __init__(self, profile: Profile) -> None:
        self.profile = profile
        self.job = DailySourceRefreshJob(profile)

    def _load_state(self) -> SchedulerState:
        sc = self.profile.scheduler
        state = SchedulerState.load(
            self.profile.scheduler_state_path, environment=self.profile.environment
        )
        # Keep state's schedule config in sync with the resolved config.
        state.schedule_time_local = sc.schedule_time
        state.timezone = sc.timezone
        state.catch_up_on_wake = sc.catch_up_on_wake
        return state

    def run_once(self, *, schedule_date: date, trigger: str) -> ScheduledRefreshReceipt:
        """Force a run for a specific schedule date (manual `scheduler run --date`)."""
        state = self._load_state()
        state.last_started_at = datetime.now(timezone.utc).isoformat()
        state.last_attempted_schedule_date = schedule_date.isoformat()
        receipt = self.job.execute(schedule_date=schedule_date, trigger=trigger)
        self._record(state, receipt)
        return receipt

    def tick(self, now: datetime) -> dict[str, object]:
        """One scheduler tick: run iff due for the current target schedule date."""
        sc = self.profile.scheduler
        state = self._load_state()
        decision = decide_catch_up(
            now,
            state,
            schedule_time_local=sc.schedule_time,
            timezone=sc.timezone,
            catch_up_on_wake=sc.catch_up_on_wake,
        )
        state.next_expected_run = compute_next_run(now, sc.schedule_time, sc.timezone).isoformat()
        if not decision.should_run:
            state.save(self.profile.scheduler_state_path)
            return {
                "ran": False,
                "reason": decision.reason,
                "schedule_date": decision.schedule_date,
            }

        from datetime import date as _date

        target = _date.fromisoformat(decision.schedule_date)
        state.last_started_at = datetime.now(timezone.utc).isoformat()
        state.last_attempted_schedule_date = decision.schedule_date
        receipt = self.job.execute(schedule_date=target, trigger="scheduler_tick")
        self._record(state, receipt)
        return {
            "ran": True,
            "reason": decision.reason,
            "schedule_date": decision.schedule_date,
            "status": receipt.status,
            "mode": receipt.mode,
        }

    def _record(self, state: SchedulerState, receipt: ScheduledRefreshReceipt) -> None:
        state.last_finished_at = datetime.now(timezone.utc).isoformat()
        state.last_status = receipt.status
        state.last_receipt_path = receipt.receipt_path
        if receipt.status in ("ok", "degraded"):
            state.last_successful_schedule_date = receipt.schedule_date
            state.consecutive_failures = 0
        else:
            state.consecutive_failures += 1
        state.save(self.profile.scheduler_state_path)
