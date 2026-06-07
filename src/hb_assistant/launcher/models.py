"""Value types for the launcher process model. No I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

Environment = Literal["dev", "production"]
CloseAction = Literal["quit", "background"]
ProcessName = Literal["backend", "frontend", "mcp", "scheduler"]
ProcessStatus = Literal["running", "planned", "exited", "unknown", "skipped", "unavailable"]


@dataclass(frozen=True)
class ManagedProcessSpec:
    """A child process the launcher may start for an environment.

    ``argv``/``cwd``/``env`` are profile/config-derived; the defaults in ``service``
    are overridable fallbacks, not hardwired requirements. ``optional`` surfaces
    (frontend/backend) degrade to a skipped status instead of failing the launch.
    """

    name: ProcessName
    argv: list[str]
    cwd: str
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    keep_in_background: bool = False
    optional: bool = True


class ProcessRecord(BaseModel):
    """A spawned (or planned) process, persisted in the session file."""

    name: ProcessName
    pid: int | None = None
    started_at: str
    argv: list[str]
    status: ProcessStatus
    keep_in_background: bool = False
    reason: str | None = None
