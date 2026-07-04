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

    mcp = FastMCP("hb-nas-mcp-readonly", json_response=True, stateless_http=True)

    @mcp.tool()
    def hb_mcp_status() -> dict[str, Any]:
        """Return NAS readonly MCP posture (metadata only)."""
        payload = broker.dispatch("hb_mcp_status", {})
        return payload.get("result", payload)

    @mcp.tool()
    def hb_db_select(
        table_key: str,
        columns: list[str],
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Structured allowlisted DB read (no raw SQL)."""
        payload = broker.dispatch(
            "hb_db_select",
            {
                "table_key": table_key,
                "columns": columns,
                "filters": filters or {},
                "order_by": order_by,
                "limit": limit,
            },
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_secure_list(root_key: str, relative_path: str = ".", max_entries: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_secure_list",
            {"root_key": root_key, "relative_path": relative_path, "max_entries": max_entries},
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_secure_stat(root_key: str, relative_path: str) -> dict[str, Any]:
        payload = broker.dispatch("hb_secure_stat", {"root_key": root_key, "relative_path": relative_path})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_secure_read_excerpt(root_key: str, relative_path: str, max_bytes: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_secure_read_excerpt",
            {"root_key": root_key, "relative_path": relative_path, "max_bytes": max_bytes},
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_vault_search(query: str, relative_path: str = ".", limit: int = 25) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_vault_search",
            {"query": query, "relative_path": relative_path, "limit": limit},
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_vault_read_excerpt(relative_path: str, max_bytes: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch("hb_vault_read_excerpt", {"relative_path": relative_path, "max_bytes": max_bytes})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_source_root_search(
        query: str, root_key: str = "syn-work", relative_path: str = ".", limit: int = 25
    ) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_source_root_search",
            {"query": query, "root_key": root_key, "relative_path": relative_path, "limit": limit},
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_source_root_read_excerpt(
        relative_path: str, root_key: str = "syn-work", max_bytes: int | None = None
    ) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_source_root_read_excerpt",
            {"relative_path": relative_path, "root_key": root_key, "max_bytes": max_bytes},
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    async def health(_request: Any) -> JSONResponse:
        body = {
            "status": "ok",
            "surface": "nas_mcp.readonly",
            "nas_readonly": True,
            "allowlisted_table_keys": list_allowlisted_table_keys(),
            "configured_roots": sorted(cfg.roots.keys()),
            "guardrails": build_guard_status(),
        }
        return JSONResponse(body)

    mcp_app = mcp.streamable_http_app()
    return Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Mount("/mcp", app=mcp_app),
        ]
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
