"""Cross-platform, pure-Python launcher for the HB Assistant Dev and Production
environments.

Two distinct launchers start the current version of their environment's local
processes (backend / frontend / MCP / scheduler), track them in a session file, and
expose a Quit / Run-in-Background close policy. No hard GUI dependency: an optional
pywebview shell is lazy-imported only when installed.
"""

from __future__ import annotations

from hb_assistant.launcher.close_policy import ClosePolicy
from hb_assistant.launcher.models import (
    CloseAction,
    Environment,
    ManagedProcessSpec,
    ProcessRecord,
)
from hb_assistant.launcher.process_manager import ProcessManager
from hb_assistant.launcher.profiles import Profile, resolve_profile, snapshot_source_db
from hb_assistant.launcher.service import LauncherService
from hb_assistant.launcher.session_state import SessionState

__all__ = [
    "ClosePolicy",
    "CloseAction",
    "Environment",
    "LauncherService",
    "ManagedProcessSpec",
    "ProcessManager",
    "ProcessRecord",
    "Profile",
    "SessionState",
    "resolve_profile",
    "snapshot_source_db",
]
