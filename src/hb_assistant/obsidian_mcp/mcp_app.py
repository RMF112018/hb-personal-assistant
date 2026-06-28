"""Optional MCP SDK adapter for the UI-managed Obsidian MCP server."""

from __future__ import annotations

from typing import Any

from .service import ObsidianMcpService


class BearerTokenMiddleware:
    """Tiny ASGI bearer-token wrapper for a mounted MCP app."""

    def __init__(self, app: Any, service: ObsidianMcpService | None = None) -> None:
        self.app = app
        self.service = service or ObsidianMcpService()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        config = self.service.get_config()
        if scope.get("type") == "http" and config.token_configured:
            headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
            expected = f"Bearer {config.bearer_token}"
            if headers.get("authorization") != expected:
                await send(
                    {
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": b'{"detail":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def build_streamable_http_app(service: ObsidianMcpService | None = None) -> Any:
    """Build the official MCP SDK Streamable HTTP ASGI app.

    The SDK is optional and imported only when the FastAPI backend is created with it installed.
    """
    from mcp.server.fastmcp import FastMCP  # type: ignore[import-not-found]  # noqa: PLC0415

    svc = service or ObsidianMcpService()
    mcp = FastMCP("hb-obsidian-mcp")

    @mcp.tool()
    def list_directory(
        path: str = "",
        recursive: bool = False,
        extensions: list[str] | None = None,
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        return svc.list_directory(
            {
                "path": path,
                "recursive": recursive,
                "extensions": extensions,
                "max_depth": max_depth,
            }
        )

    @mcp.tool()
    def search_vault(
        query: str,
        path_scope: str | None = None,
        file_types: list[str] | None = None,
        limit: int | None = None,
        include_content_snippet: bool = True,
    ) -> dict[str, Any]:
        return svc.search_vault(
            {
                "query": query,
                "path_scope": path_scope,
                "file_types": file_types,
                "limit": limit,
                "include_content_snippet": include_content_snippet,
            }
        )

    @mcp.tool()
    def read_file(
        path: str,
        start_page: int | None = None,
        end_page: int | None = None,
        section: str | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        return svc.read_file(
            {
                "path": path,
                "start_page": start_page,
                "end_page": end_page,
                "section": section,
                "max_chars": max_chars,
            }
        )

    @mcp.tool()
    def create_note(
        path: str,
        content: str,
        overwrite: bool = False,
        create_parent_dirs: bool = True,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Create a Markdown note under the configured autonomous vault policy."""
        return svc.create_note(
            {
                "path": path,
                "content": content,
                "overwrite": overwrite,
                "create_parent_dirs": create_parent_dirs,
                "expected_sha256": expected_sha256,
                "caller_surface": "mcp",
            }
        )

    @mcp.tool()
    def patch_note(path: str, content: str, expected_sha256: str) -> dict[str, Any]:
        """Replace an existing Markdown note as a whole-file replacement when SHA-256 matches."""
        return svc.patch_note(
            {
                "path": path,
                "content": content,
                "expected_sha256": expected_sha256,
                "caller_surface": "mcp",
            }
        )

    app = mcp.streamable_http_app()
    return BearerTokenMiddleware(app, service=svc)
