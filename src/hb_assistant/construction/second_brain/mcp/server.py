"""Phase 08D local stdio MCP server entrypoint (Prompt 03 — foundation only).

``serve_stdio`` runs the fail-closed startup checks and then **refuses to serve**: the
tool broker and workflow wrappers do not exist until Prompt 04, and the MCP-specific
guard proofs land in Prompts 13/14. It never opens a socket, never starts a loop, and
never imports the ``mcp`` SDK unless serving is actually enabled (it is not, here).

The ``mcp`` SDK is an optional extra (``pip install -e .[mcp]``); ``_import_mcp`` lazily
imports it only when a future prompt enables the real stdio loop.
"""

from __future__ import annotations

from typing import Any

from .policy import build_mcp_status


class MCPUnavailable(RuntimeError):
    """Raised when the MCP stdio server cannot start (SDK missing or fail-closed)."""


def _import_mcp() -> Any:  # pragma: no cover - reached only once serving is enabled (Prompt 04+)
    try:
        import mcp  # noqa: PLC0415  (lazy by design — optional extra)
    except ImportError as exc:
        raise MCPUnavailable(
            "MCP SDK not installed. Install with `pip install -e .[mcp]` to enable the "
            "local stdio server (serving also requires the Prompt 04 tool broker)."
        ) from exc
    return mcp


def serve_stdio(*, db_path: str | None = None) -> dict[str, Any]:
    """Attempt to start the stdio MCP server; fail-closed at the foundation stage.

    Returns a metadata-only status envelope with ``served=False`` and the blocking
    reasons. Never opens a network listener or a serve loop.
    """
    status = build_mcp_status(db_path=db_path, persist=False)
    reasons = list(status["serve_blockers"])
    if not status["foundation_ok"]:
        reasons.append("foundation_checks_failed")

    # Foundation stage: serving is always refused (no tool broker, no guard proofs yet).
    return {
        "command": "second-brain mcp serve",
        "phase": "08D",
        "transport": "stdio",
        "served": False,
        "ready_to_serve": status["ready_to_serve"],
        "foundation_ok": status["foundation_ok"],
        "mcp_sdk_available": status["mcp_sdk_available"],
        "reasons": reasons,
        "note": (
            "Server foundation only — stdio serving is fail-closed until the Prompt 04 "
            "tool broker and the Prompt 13/14 guard proofs are wired."
        ),
        "guardrails": status["guardrails"],
    }
