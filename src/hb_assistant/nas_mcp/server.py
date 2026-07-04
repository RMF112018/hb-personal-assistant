"""NAS MCP streamable HTTP server (dedicated process — not FastAPI backend)."""

from __future__ import annotations

from typing import Any

from .broker import NasMcpBroker
from .config import NasMcpConfig
from .db_allowlist import list_allowlisted_table_keys
from .guards import (
    NasMcpGuardError,
    assert_no_backend_modules_loaded,
    build_guard_status,
    require_nas_readonly_env,
)
from .tool_registration import register_nas_mcp_tools


class NasMcpUnavailable(RuntimeError):
    """NAS MCP cannot start."""


def build_nas_mcp_asgi_app(config: NasMcpConfig | None = None) -> Any:
    """Build ASGI app: /health + MCP streamable HTTP at /mcp."""
    cfg = config or NasMcpConfig.from_env()
    broker = NasMcpBroker(cfg)

    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]  # noqa: PLC0415
        from starlette.applications import Starlette  # noqa: PLC0415
        from starlette.responses import JSONResponse  # noqa: PLC0415
        from starlette.routing import Mount, Route  # noqa: PLC0415
    except ImportError as exc:
        raise NasMcpUnavailable(
            "MCP SDK not installed. Install with `pip install -e '.[mcp]'`."
        ) from exc

    mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
    register_nas_mcp_tools(mcp, broker)

    async def health(_request: Any) -> JSONResponse:
        body = {
            "status": "ok",
            "surface": "nas_mcp",
            "nas_readonly": True,
            "allowlisted_table_keys": list_allowlisted_table_keys(),
            "configured_roots": {k: v.mode for k, v in cfg.roots.items()},
            "guardrails": build_guard_status(),
        }
        return JSONResponse(body)

    from contextlib import AsyncExitStack, asynccontextmanager  # noqa: PLC0415

    mcp_app = mcp.streamable_http_app()
    inner = getattr(mcp_app, "app", mcp_app)
    mcp_lifespan = getattr(getattr(inner, "router", None), "lifespan_context", None)

    @asynccontextmanager
    async def lifespan(_app: Any):
        async with AsyncExitStack() as stack:
            if callable(mcp_lifespan):
                await stack.enter_async_context(mcp_lifespan(inner))
            yield

    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        lifespan=lifespan,
    )


def serve_nas_readonly_streamable_http(
    *,
    host: str = "0.0.0.0",
    port: int = 8765,
    dry_run: bool = False,
    config: NasMcpConfig | None = None,
) -> dict[str, Any]:
    """Start dedicated NAS MCP HTTP server (not the FastAPI backend)."""
    require_nas_readonly_env()
    assert_no_backend_modules_loaded()
    cfg = config or NasMcpConfig.from_env()
    status = {
        "command": "hb-assistant mcp serve --nas-readonly --streamable-http",
        "transport": "streamable_http",
        "host": host,
        "port": port,
        "served": False,
        "dry_run": dry_run,
        "guardrails": build_guard_status(),
        "configured_roots": sorted(cfg.roots.keys()),
    }
    try:
        app = build_nas_mcp_asgi_app(cfg)
    except NasMcpUnavailable as exc:
        status["error"] = str(exc)
        return status
    except NasMcpGuardError as exc:
        status["error"] = str(exc)
        return status

    if dry_run:
        status["ready"] = True
        return status

    import uvicorn  # noqa: PLC0415

    uvicorn.run(app, host=host, port=port, log_level="info")
    status["served"] = True
    return status
