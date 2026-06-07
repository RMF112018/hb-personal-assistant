"""Window/session close policy: Quit vs Run-in-Background.

Quit terminates every managed process and writes a clean shutdown receipt.
Run-in-Background terminates only the UI/foreground surfaces, keeps the
``keep_in_background`` services (MCP, scheduler) alive, and marks the session
background-active so it can be inspected and stopped later.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hb_assistant.launcher.models import CloseAction
from hb_assistant.launcher.process_manager import ProcessManager
from hb_assistant.launcher.profiles import Profile
from hb_assistant.source_refresh.orchestrator import _safe_git_sha


class ClosePolicy:
    def __init__(self, profile: Profile, manager: ProcessManager) -> None:
        self.profile = profile
        self.manager = manager

    def apply(self, action: CloseAction) -> dict[str, Any]:
        state = self.manager.load_session()
        current_pids = {r.pid for r in state.processes if r.pid}
        terminated: list[str] = []
        kept: list[str] = []
        terminated_current_session: list[str] = []

        for rec in state.processes:
            if action == "background" and rec.keep_in_background:
                if self.manager.is_alive(rec.pid):
                    kept.append(rec.name)
                continue
            status = self.manager.terminate(rec)
            rec.status = status
            terminated.append(rec.name)
            terminated_current_session.append(rec.name)

        # Quit also sweeps stale launcher-owned processes from prior sessions.
        terminated_stale: list[dict[str, Any]] = []
        skipped_unknown: list[dict[str, Any]] = []
        still_running: list[dict[str, Any]] = []
        if action == "quit":
            terminated_stale, skipped_unknown, still_running = self._sweep_stale(current_pids)

        scheduler_active = False
        if action == "background":
            state.processes = [r for r in state.processes if r.keep_in_background]
            state.background_active = True
            scheduler_active = self.profile.scheduler_enabled and any(
                r.name == "scheduler" for r in state.processes
            )
        else:  # quit
            state.processes = []
            state.background_active = False

        receipt = self._receipt(
            action,
            terminated,
            kept,
            scheduler_active,
            terminated_current_session=terminated_current_session,
            terminated_stale=terminated_stale,
            skipped_unknown=skipped_unknown,
            still_running=still_running,
        )
        state.last_shutdown_receipt = receipt["receipt_path"]
        self.manager.save_session(state)
        return receipt

    def _sweep_stale(
        self, current_pids: set[int]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Terminate stale launcher-owned processes; report skipped unknowns on ports.

        MCP is never swept here (it is only ever a current-session PID) so external
        Claude/Cursor MCP processes are left untouched.
        """
        from hb_assistant.launcher import process_scan

        procs = process_scan.list_system_processes()
        proc_by_pid = {p.pid: p for p in procs}
        terminated_stale: list[dict[str, Any]] = []
        still_running: list[dict[str, Any]] = []
        for op in process_scan.find_stale_launcher_processes(
            self.profile, exclude_pids=current_pids, processes=procs
        ):
            status = self.manager.terminate_pid(op.pid)
            entry: dict[str, Any] = {"pid": op.pid, "role": op.role, "source": op.source}
            if status == "exited":
                terminated_stale.append(entry)
            else:
                entry["status"] = status
                still_running.append(entry)

        skipped_unknown: list[dict[str, Any]] = []
        for port in (self.profile.backend_port, self.profile.frontend_port):
            for owner in process_scan.owner_of_port(
                port, self.profile, tracked_pids=current_pids, proc_by_pid=proc_by_pid
            ):
                if not owner["owned"]:
                    skipped_unknown.append(
                        {"port": port, "pid": owner["pid"], "command": owner["command"]}
                    )
        return terminated_stale, skipped_unknown, still_running

    def _receipt(
        self,
        action: CloseAction,
        terminated: list[str],
        kept: list[str],
        scheduler_active: bool,
        *,
        terminated_current_session: list[str],
        terminated_stale: list[dict[str, Any]],
        skipped_unknown: list[dict[str, Any]],
        still_running: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ts = datetime.now(timezone.utc).isoformat()
        receipt: dict[str, Any] = {
            "command": "launcher close",
            "generated_utc": ts,
            "repo_sha": _safe_git_sha(),
            "environment": self.profile.environment,
            "action": action,
            "terminated": terminated,
            "kept_alive": kept,
            "terminated_current_session": terminated_current_session,
            "terminated_stale": terminated_stale,
            "skipped_unknown": skipped_unknown,
            "still_running": still_running,
            "background_active": action == "background",
            "scheduler_active": scheduler_active,
            "metadata_only": True,
            "status": "ok",
        }
        out_dir = self.profile.evidence_path / "launcher"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"close-{action}-{self.profile.environment}.json"
        import json

        path.write_text(json.dumps(receipt, indent=2, sort_keys=True))
        receipt["receipt_path"] = str(path)
        return receipt
