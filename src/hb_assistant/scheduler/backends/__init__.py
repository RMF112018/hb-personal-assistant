"""Cross-platform scheduler backends.

Every backend installs a native artifact (or, for the foreground fallback, none) that
fires ONLY the repo runner `hb-assistant scheduler run daily-source-refresh
--environment <env> --if-due`. App-level state (`due` + `SchedulerState`) decides
whether a run is owed and prevents double-running a schedule date.
"""

from __future__ import annotations

from typing import Protocol

from hb_assistant.launcher.profiles import Profile
from hb_assistant.launcher.service import _hb_executable
from hb_assistant.scheduler.models import Backend, InstallPlan


class SchedulerBackend(Protocol):
    def preview(self) -> dict: ...
    def install(self, *, dry_run: bool) -> dict: ...
    def uninstall(self, *, dry_run: bool) -> dict: ...
    def status(self) -> dict: ...


def make_install_plan(profile: Profile) -> InstallPlan:
    sc = profile.scheduler
    exe = _hb_executable()
    runner_argv = [
        exe,
        "scheduler",
        "run",
        "daily-source-refresh",
        "--environment",
        profile.environment,
        "--if-due",
    ]
    if profile.environment == "dev":
        runner_argv.append("--mock-data")
    return InstallPlan(
        environment=profile.environment,
        job_id="daily-source-refresh",
        schedule_time_local=sc.schedule_time,
        timezone=sc.timezone,
        catch_up_on_wake=sc.catch_up_on_wake,
        mock_data=profile.environment == "dev",
        executable=exe,
        working_directory=str(profile.path_policy.resolve_repo_root()),
        label=f"com.hb.personal-assistant.scheduler.{profile.environment}",
        runner_argv=runner_argv,
    )


def get_backend(name: Backend, profile: Profile) -> SchedulerBackend:
    plan = make_install_plan(profile)
    log_path = profile.log_path
    if name == "launchd":
        from hb_assistant.scheduler.backends.launchd import LaunchdSchedulerBackend

        return LaunchdSchedulerBackend(plan, log_path=log_path)
    if name == "windows":
        from hb_assistant.scheduler.backends.windows_task_scheduler import WindowsTaskBackend

        return WindowsTaskBackend(plan, state_dir=profile.app_support_root / "scheduler-state")
    if name == "systemd":
        from hb_assistant.scheduler.backends.systemd import SystemdBackend

        return SystemdBackend(plan)
    from hb_assistant.scheduler.backends.foreground_loop import ForegroundLoopBackend

    return ForegroundLoopBackend(plan)


def default_backend_name() -> Backend:
    import sys

    if sys.platform == "darwin":
        return "launchd"
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "systemd"
    return "foreground"
