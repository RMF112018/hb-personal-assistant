"""Phase 08D local stdio MCP server entrypoint.

``serve_stdio`` runs the fail-closed startup checks, then either refuses to serve
(fail-closed) or — once the optional ``mcp`` SDK is installed and every foundation check
passes — drives the real low-level stdio MCP loop via :mod:`.sdk_server`. The local stdio
transport is the package's explicitly allowed transport; no network listener is ever
opened.

Serving stays fail-closed unless ``ready_to_serve`` is true (schema at the expected
version, all registries present, the fail-closed permission policy, stdio-only transport,
and the Prompt 13/14 no-raw / no-writeback guard proofs all pass) **and** the SDK is
present. ``dry_run=True`` reports readiness without entering the loop (diagnostics/tests).

The ``mcp`` SDK is an optional extra (``pip install -e .[mcp]``); it is imported lazily —
only when serving is actually enabled — so the base install and full test suite run with
the SDK absent.
"""

from __future__ import annotations

from typing import Any

from .policy import build_mcp_status


class MCPUnavailable(RuntimeError):
    """Raised when the MCP stdio server cannot start (SDK missing or fail-closed)."""


def _import_mcp() -> Any:  # pragma: no cover - thin availability probe
    try:
        import mcp  # noqa: PLC0415  (lazy by design — optional extra)
    except ImportError as exc:
        raise MCPUnavailable(
            "MCP SDK not installed. Install with `pip install -e .[mcp]` to enable the "
            "local stdio server."
        ) from exc
    return mcp


def serve_stdio(*, db_path: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    """Start the local stdio MCP server, or fail-closed with the blocking reasons.

    Returns a metadata-only status envelope. When ``ready_to_serve`` is false (a
    foundation check failed or the SDK is absent) the server refuses and ``served`` is
    ``False``. When ready and ``dry_run`` is false this **blocks**, driving the real stdio
    JSON-RPC loop until the client disconnects, then returns with ``served=True``.
    ``dry_run`` true reports readiness without entering the loop. stdout is the JSON-RPC
    channel — this function writes nothing to it.
    """
    status = build_mcp_status(db_path=db_path, persist=False)
    foundation_ok = bool(status["foundation_ok"])
    sdk_available = bool(status["mcp_sdk_available"])
    ready_to_serve = bool(status["ready_to_serve"])

    def _envelope(*, served: bool, reasons: list[str], note: str) -> dict[str, Any]:
        return {
            "command": "second-brain mcp serve",
            "phase": "08D",
            "transport": "stdio",
            "served": served,
            "ready_to_serve": ready_to_serve,
            "foundation_ok": foundation_ok,
            "mcp_sdk_available": sdk_available,
            "reasons": reasons,
            "note": note,
            "guardrails": status["guardrails"],
        }

    # Fail-closed: a failing foundation check or a missing SDK refuses to serve.
    if not ready_to_serve or not sdk_available or not foundation_ok:
        reasons = list(status["serve_blockers"])
        if not foundation_ok:
            reasons.append("foundation_checks_failed")
        return _envelope(
            served=False,
            reasons=reasons,
            note="Serving refused — fail-closed (foundation check failed or MCP SDK absent).",
        )

    if dry_run:
        return _envelope(
            served=False,
            reasons=[],
            note="Ready to serve — dry run (no stdio loop entered).",
        )

    # Ready: drive the real local stdio MCP loop (blocking until the client disconnects).
    from functools import partial  # noqa: PLC0415

    import anyio  # noqa: PLC0415 - mcp SDK dependency, present only when serving

    from .sdk_server import serve_stdio_loop  # noqa: PLC0415 - lazy (imports the mcp SDK)

    anyio.run(partial(serve_stdio_loop, db_path=db_path))
    return _envelope(
        served=True,
        reasons=[],
        note="Served a local stdio MCP session; client disconnected.",
    )
