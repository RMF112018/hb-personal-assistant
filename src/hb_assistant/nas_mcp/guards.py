"""Startup guards for NAS read-only MCP mode."""

from __future__ import annotations

import os
from typing import Any

BACKEND_FORBIDDEN_IMPORTS = (
    "hb_assistant.construction.analytics.api",
)


class NasMcpGuardError(RuntimeError):
    """NAS MCP refused to start (fail-closed)."""


def require_nas_readonly_env() -> None:
    if os.environ.get("HB_MCP_NAS_READONLY", "").strip() != "1":
        raise NasMcpGuardError("HB_MCP_NAS_READONLY=1 is required for NAS MCP serve")
    if os.environ.get("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "").strip() != "1":
        raise NasMcpGuardError(
            "HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1 is required for NAS MCP serve"
        )


def assert_no_backend_modules_loaded() -> None:
    import sys

    for name in BACKEND_FORBIDDEN_IMPORTS:
        if name in sys.modules:
            raise NasMcpGuardError(f"forbidden module already loaded: {name}")


def build_guard_status() -> dict[str, Any]:
    return {
        "nas_readonly": os.environ.get("HB_MCP_NAS_READONLY") == "1",
        "background_workers_disabled": os.environ.get("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS") == "1",
        "db_readonly_env": os.environ.get("HB_ASSISTANT_DB_READONLY") == "1",
        "nas_runtime": os.environ.get("HB_NAS_RUNTIME") == "1",
        "forbidden_backend_imports": list(BACKEND_FORBIDDEN_IMPORTS),
    }
