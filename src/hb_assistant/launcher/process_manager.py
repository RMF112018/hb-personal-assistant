"""Spawn, track, and terminate launcher child processes across CLI invocations.

PIDs persist in the per-environment session JSON so an independent later CLI call
(`status`/`stop`/`close`) can manage processes a prior `launcher dev/production` started.
Cross-platform: POSIX uses process groups + SIGTERM→SIGKILL; Windows uses
CREATE_NEW_PROCESS_GROUP + taskkill.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

from hb_assistant.launcher.models import ManagedProcessSpec, ProcessRecord, ProcessStatus
from hb_assistant.launcher.profiles import Profile
from hb_assistant.launcher.session_state import SessionState

_IS_WINDOWS = sys.platform.startswith("win")


class ProcessManager:
    """Owns the lifecycle of the managed processes for one Profile."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    # -- session ------------------------------------------------------------------

    def load_session(self) -> SessionState:
        return SessionState.load(
            self.profile.launcher_session_path, environment=self.profile.environment
        )

    def save_session(self, state: SessionState) -> None:
        state.save(self.profile.launcher_session_path)

    # -- spawn --------------------------------------------------------------------

    def spawn(self, spec: ManagedProcessSpec) -> ProcessRecord:
        """Start a managed process. Returns a ProcessRecord (status running/unavailable)."""
        now = datetime.now(timezone.utc).isoformat()
        env = {**os.environ, **spec.env}
        kwargs: dict[str, object] = {"cwd": spec.cwd, "env": env}
        if _IS_WINDOWS:
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["start_new_session"] = True
        try:
            proc = subprocess.Popen(spec.argv, **kwargs)  # type: ignore[call-overload]  # noqa: S603
        except (FileNotFoundError, OSError) as exc:
            return ProcessRecord(
                name=spec.name,
                pid=None,
                started_at=now,
                argv=spec.argv,
                status="unavailable",
                keep_in_background=spec.keep_in_background,
                reason=f"{type(exc).__name__}: {str(exc)[:120]}",
            )
        return ProcessRecord(
            name=spec.name,
            pid=proc.pid,
            started_at=now,
            argv=spec.argv,
            status="running",
            keep_in_background=spec.keep_in_background,
        )

    @staticmethod
    def planned(spec: ManagedProcessSpec, *, reason: str = "plan_only") -> ProcessRecord:
        return ProcessRecord(
            name=spec.name,
            pid=None,
            started_at=datetime.now(timezone.utc).isoformat(),
            argv=spec.argv,
            status="planned",
            keep_in_background=spec.keep_in_background,
            reason=reason,
        )

    # -- liveness / termination ---------------------------------------------------

    def is_alive(self, pid: int | None) -> bool:
        if not pid:
            return False
        if _IS_WINDOWS:  # pragma: no cover - exercised on Windows only
            try:
                import ctypes

                handle = ctypes.windll.kernel32.OpenProcess(0x100000, False, pid)  # type: ignore[attr-defined]
                if handle:
                    ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                    return True
                return False
            except Exception:
                return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def terminate(self, record: ProcessRecord, *, timeout: float = 8.0) -> ProcessStatus:
        """Terminate a managed process. Returns the resulting status."""
        pid = record.pid
        if not pid or not self.is_alive(pid):
            return "exited"
        try:
            if _IS_WINDOWS:  # pragma: no cover
                subprocess.run(  # noqa: S603,S607
                    ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False
                )
            else:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    os.kill(pid, signal.SIGTERM)
                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    if not self.is_alive(pid):
                        return "exited"
                    time.sleep(0.1)
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            return "unknown"
        return "exited" if not self.is_alive(pid) else "unknown"

    def reconcile(self, state: SessionState) -> SessionState:
        """Refresh each record's status against current liveness."""
        for rec in state.processes:
            if rec.status in ("running", "unknown"):
                rec.status = "running" if self.is_alive(rec.pid) else "exited"
        return state
