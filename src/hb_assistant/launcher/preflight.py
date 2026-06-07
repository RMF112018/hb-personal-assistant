"""Pre-start reconciliation: reuse a healthy session, stop a stale one, free ports.

Before a new Dev/Production session spawns, this inspects the tracked session and
live OS state. It will reuse a healthy prior session, stop an unhealthy one, free
required ports held by launcher-owned stale processes, and fail closed (``ok=False``)
when a required port is held by an unknown process — never starting a conflicting
duplicate. OS scanning lives in ``process_scan`` (monkeypatchable for tests).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from hb_assistant.launcher import process_scan
from hb_assistant.launcher.process_manager import ProcessManager
from hb_assistant.launcher.profiles import Profile

# Surfaces that bind a port and must be live for a session to count as "healthy".
_KEY_SURFACES = {"backend", "frontend"}


@dataclass
class PreflightResult:
    ok: bool = True
    reused: bool = False
    stopped_prior: list[str] = field(default_factory=list)
    freed_ports: list[dict[str, object]] = field(default_factory=list)
    conflicts: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "reused": self.reused,
            "stopped_prior": self.stopped_prior,
            "freed_ports": self.freed_ports,
            "conflicts": self.conflicts,
            "warnings": self.warnings,
        }


def run_preflight(
    profile: Profile,
    manager: ProcessManager,
    *,
    force_restart: bool,
    required_ports: list[tuple[str, int]],
) -> PreflightResult:
    """Reconcile prior session + required ports before a new spawn."""
    result = PreflightResult()
    state = manager.reconcile(manager.load_session())
    live = [r for r in state.processes if manager.is_alive(r.pid)]
    live_names = {r.name for r in live}

    if live and _KEY_SURFACES.issubset(live_names) and not force_restart:
        result.reused = True
        result.warnings.append("reusing healthy prior session (use --force-restart to replace)")
        return result

    # Stop an unhealthy / partial prior session (or any session under --force-restart).
    if live:
        for rec in live:
            manager.terminate(rec)
            result.stopped_prior.append(rec.name)
        state.processes = []
        state.background_active = False
        manager.save_session(state)

    # Free / detect conflicts on required ports.
    procs = process_scan.list_system_processes()
    proc_by_pid = {p.pid: p for p in procs}
    for name, port in required_ports:
        if not process_scan.port_in_use(port):
            continue
        owners = process_scan.owner_of_port(
            port, profile, tracked_pids=set(), proc_by_pid=proc_by_pid
        )
        if not owners:
            # Port is occupied but the listener can't be identified — fail closed.
            result.conflicts.append(
                {
                    "surface": name,
                    "port": port,
                    "pid": None,
                    "command": "",
                    "reason": "unidentified",
                }
            )
            result.ok = False
            continue
        for owner in owners:
            if owner["owned"]:
                status = manager.terminate_pid(cast("int | None", owner["pid"]))
                result.freed_ports.append(
                    {
                        "surface": name,
                        "port": port,
                        "pid": owner["pid"],
                        "role": owner["role"],
                        "source": owner["source"],
                        "terminate_status": status,
                    }
                )
            else:
                result.conflicts.append(
                    {
                        "surface": name,
                        "port": port,
                        "pid": owner["pid"],
                        "command": owner["command"],
                        "reason": "unknown_owner",
                    }
                )
                result.ok = False

    if result.conflicts:
        result.warnings.append(
            "required port(s) held by unknown process(es); refusing to start a conflicting session"
        )
    return result


def cleanup(profile: Profile, manager: ProcessManager, *, apply: bool) -> dict[str, object]:
    """Identify (and with ``apply`` terminate) stale launcher-owned processes.

    Candidates are the live tracked-session PIDs (any role, including MCP) plus
    signature-matched stale processes (never MCP). Unknown processes holding the
    required ports are reported under ``skipped_unknown`` and never terminated.
    """
    state = manager.reconcile(manager.load_session())
    tracked = [r for r in state.processes if r.pid and manager.is_alive(r.pid)]
    tracked_pids = {r.pid for r in tracked if r.pid}
    stale = process_scan.find_stale_launcher_processes(profile, exclude_pids=tracked_pids)

    candidates: list[dict[str, object]] = [
        {"pid": r.pid, "role": r.name, "source": "tracked"} for r in tracked
    ]
    candidates += [{"pid": op.pid, "role": op.role, "source": op.source} for op in stale]

    procs = process_scan.list_system_processes()
    proc_by_pid = {p.pid: p for p in procs}
    skipped_unknown: list[dict[str, object]] = []
    for port in (profile.backend_port, profile.frontend_port):
        for owner in process_scan.owner_of_port(
            port, profile, tracked_pids=tracked_pids, proc_by_pid=proc_by_pid
        ):
            if not owner["owned"]:
                skipped_unknown.append(
                    {"port": port, "pid": owner["pid"], "command": owner["command"]}
                )

    out: dict[str, object] = {
        "command": "launcher cleanup",
        "environment": profile.environment,
        "applied": apply,
        "candidates": candidates,
        "skipped_unknown": skipped_unknown,
        "status": "ok",
    }
    if apply:
        terminated: list[dict[str, object]] = []
        still_running: list[dict[str, object]] = []
        for cand in candidates:
            status = manager.terminate_pid(cast("int | None", cand["pid"]))
            entry = {**cand, "terminate_status": status}
            (terminated if status == "exited" else still_running).append(entry)
        state.processes = []
        state.background_active = False
        manager.save_session(state)
        out["terminated"] = terminated
        out["still_running"] = still_running
    return out
