"""Discover launcher-owned OS processes and port occupancy (pure helpers).

No ``psutil`` dependency — process enumeration shells out to ``ps``, port-listener
lookup to ``lsof``, and port-occupancy to a stdlib ``socket`` probe. All OS calls
are best-effort and degrade to empty results so callers never crash; they are
module-level functions so tests can monkeypatch them.

Env-attribution rules (deliberately conservative):
- ``scheduler`` / ``frontend`` / ``backend`` are matched only by unambiguous,
  environment-scoped command signatures.
- ``mcp`` is **never** signature-matched — ``second-brain mcp serve --stdio`` is
  also what Claude/Cursor launch, so a launcher MCP is only ever terminated via a
  recorded session PID, never by this scanner.
"""

from __future__ import annotations

import re
import socket
import subprocess
from dataclasses import dataclass

from hb_assistant.launcher.profiles import Profile


@dataclass(frozen=True)
class ProcInfo:
    pid: int
    command: str


@dataclass(frozen=True)
class OwnedProc:
    pid: int
    role: str
    command: str
    source: str  # "tracked" | "signature"


def list_system_processes() -> list[ProcInfo]:
    """Enumerate processes as ``(pid, command)`` via ``ps`` (POSIX). ``[]`` on failure."""
    try:
        out = subprocess.run(  # noqa: S603,S607 — fixed argv, no shell
            ["ps", "-axww", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    procs: list[ProcInfo] = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_str, _, command = line.partition(" ")
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        procs.append(ProcInfo(pid=pid, command=command.strip()))
    return procs


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """True if a TCP listener accepts a connection on ``host:port`` (local probe)."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def port_listener_pids(port: int) -> list[int]:
    """PIDs listening on ``port`` via ``lsof`` (best-effort; ``[]`` if unavailable)."""
    try:
        out = subprocess.run(  # noqa: S603,S607 — fixed argv, no shell
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for tok in out.stdout.split():
        try:
            pids.append(int(tok))
        except ValueError:
            continue
    return pids


def _has_port_token(command: str, port: int) -> bool:
    return re.search(rf"(?<!\d){port}(?!\d)", command) is not None


def classify(proc: ProcInfo, profile: Profile) -> str | None:
    """Return a launcher role for an env-attributable signature, else ``None``.

    Never returns ``"mcp"`` — the MCP stdio signature is shared with external IDE
    launches and must not be killed by signature.
    """
    cmd = proc.command
    env = profile.environment

    if "daily-source-refresh" in cmd and f"--environment {env}" in cmd:
        return "scheduler"

    if (
        ("vite" in cmd or "http.server" in cmd)
        and "/frontend" in cmd
        and _has_port_token(cmd, profile.frontend_port)
    ):
        return "frontend"

    if "hb_assistant.construction.analytics.api" in cmd and _has_port_token(
        cmd, profile.backend_port
    ):
        return "backend"

    return None


def find_stale_launcher_processes(
    profile: Profile,
    *,
    exclude_pids: set[int],
    processes: list[ProcInfo] | None = None,
) -> list[OwnedProc]:
    """Signature-matched launcher processes for ``profile`` not in ``exclude_pids``.

    MCP is never returned (see ``classify``). ``processes`` may be injected for tests.
    """
    procs = processes if processes is not None else list_system_processes()
    owned: list[OwnedProc] = []
    for p in procs:
        if p.pid in exclude_pids:
            continue
        role = classify(p, profile)
        if role is not None:
            owned.append(OwnedProc(pid=p.pid, role=role, command=p.command, source="signature"))
    return owned


def owner_of_port(
    port: int,
    profile: Profile,
    *,
    tracked_pids: set[int],
    proc_by_pid: dict[int, ProcInfo],
) -> list[dict[str, object]]:
    """Classify each listener on ``port`` as launcher-owned or unknown.

    Returns one entry per listener PID: ``{pid, command, owned, role, source}``.
    """
    result: list[dict[str, object]] = []
    for pid in port_listener_pids(port):
        proc = proc_by_pid.get(pid)
        command = proc.command if proc else ""
        if pid in tracked_pids:
            result.append(
                {"pid": pid, "command": command, "owned": True, "role": None, "source": "tracked"}
            )
            continue
        role = classify(proc, profile) if proc else None
        result.append(
            {
                "pid": pid,
                "command": command,
                "owned": role is not None,
                "role": role,
                "source": "signature" if role is not None else "unknown",
            }
        )
    return result
