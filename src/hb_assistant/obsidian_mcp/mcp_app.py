"""Optional MCP SDK adapter for the UI-managed Obsidian MCP server."""

# NOTE: deliberately no ``from __future__ import annotations`` — the MCP SDK
# evaluates tool type hints via ``get_type_hints``, and the ``Context`` param is
# bound in a local scope, so annotations must stay real objects (not strings).

from typing import Any

from . import oauth_store, pathsafe
from .config import ObsidianMcpConfig
from .service import ObsidianMcpService
from .tools import ObsidianMcpToolError

# Per-tool OAuth scope requirements. Read tools need ``obsidian.read``; write
# tools need ``obsidian.write``. Enforcement is additive — write tools still run
# the full vault write policy in ``mutations.py`` regardless of scope.
_TOOL_SCOPES = {
    "list_directory": "obsidian.read",
    "search_vault": "obsidian.read",
    "read_file": "obsidian.read",
    "create_note": "obsidian.write",
    "patch_note": "obsidian.write",
    "vault_map": "obsidian.read",
    "vault_summarize_note": "obsidian.read",
    "vault_summarize_folder": "obsidian.read",
    "vault_curation_plan": "obsidian.read",
    "vault_curation_apply": "obsidian.write",
}

_BEARER_PREFIX = "Bearer "


def _auth_required(config: ObsidianMcpConfig) -> bool:
    return bool(config.token_configured or getattr(config, "oauth_enabled", False))


def is_authorized(authorization: str | None, config: ObsidianMcpConfig) -> bool:
    """Authentication check used by the middleware: is this a known principal?"""
    auth = authorization or ""
    if config.token_configured and auth == f"Bearer {config.bearer_token}":
        return True
    if getattr(config, "oauth_enabled", False) and auth.startswith(_BEARER_PREFIX):
        return oauth_store.validate_access_token(auth[len(_BEARER_PREFIX):]) is not None
    return False


def resolve_granted_scopes(authorization: str | None, config: ObsidianMcpConfig) -> tuple[str, ...] | None:
    """Return ``None`` for unrestricted access, else the granted OAuth scopes.

    Unrestricted means the static bearer token (full access, unchanged behavior)
    or a server where no auth is configured at all (local trusted use).
    """
    if not _auth_required(config):
        return None
    auth = authorization or ""
    if config.token_configured and auth == f"Bearer {config.bearer_token}":
        return None
    if auth.startswith(_BEARER_PREFIX):
        info = oauth_store.validate_access_token(auth[len(_BEARER_PREFIX):])
        if info is not None:
            return tuple(info.scopes)
    return ()


def enforce_tool_scope(tool_name: str, authorization: str | None, config: ObsidianMcpConfig) -> None:
    """Raise ``insufficient_scope`` when an OAuth principal lacks the tool's scope."""
    granted = resolve_granted_scopes(authorization, config)
    if granted is None:
        return
    required = _TOOL_SCOPES[tool_name]
    if required not in granted:
        raise ObsidianMcpToolError("insufficient_scope", f"missing required scope: {required}")


class BearerTokenMiddleware:
    """Authenticates mounted MCP HTTP requests (static bearer or OAuth token)."""

    def __init__(self, app: Any, service: ObsidianMcpService | None = None) -> None:
        self.app = app
        self.service = service or ObsidianMcpService()

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") == "http":
            config = self.service.get_config()
            if _auth_required(config):
                headers = {k.decode("latin1").lower(): v.decode("latin1") for k, v in scope.get("headers", [])}
                if not is_authorized(headers.get("authorization"), config):
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


def _request_authorization(ctx: Any) -> tuple[bool, str | None]:
    """Extract (is_http, Authorization header) from a FastMCP tool context.

    Returns ``(False, None)`` for non-HTTP transports (e.g. stdio), where scope
    enforcement is skipped and the local caller is trusted.
    """
    try:
        request = getattr(ctx.request_context, "request", None)
    except Exception:
        return (False, None)
    if request is None:
        return (False, None)
    try:
        return (True, request.headers.get("authorization"))
    except Exception:
        return (True, None)


def build_streamable_http_app(service: ObsidianMcpService | None = None) -> Any:
    """Build the official MCP SDK Streamable HTTP ASGI app.

    The SDK is optional and imported only when the FastAPI backend is created with it installed.
    """
    from mcp.server.fastmcp import (  # type: ignore[import-not-found]  # noqa: PLC0415
        Context,
        FastMCP,
    )
    from mcp.server.transport_security import (  # type: ignore[import-not-found]  # noqa: PLC0415
        TransportSecuritySettings,
    )

    svc = service or ObsidianMcpService()
    mcp = FastMCP(
        "hb-obsidian-mcp",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[
                "127.0.0.1",
                "127.0.0.1:8000",
                "127.0.0.1:3010",
                "localhost",
                "localhost:8000",
                "localhost:3010",
                "mcp.bobby-fetting.me",
                "mcp.bobby-fetting.me:443",
            ],
            allowed_origins=[
                "https://mcp.bobby-fetting.me",
                "https://grok.com",
                "https://x.ai",
            ],
        ),
    )

    def _enforce(tool_name: str, ctx: Context) -> None:
        is_http, authorization = _request_authorization(ctx)
        if is_http:
            enforce_tool_scope(tool_name, authorization, svc.get_config())

    def _operator_mode(ctx: Context) -> bool:
        """True for unrestricted principals (static bearer / no-auth / stdio).

        OAuth principals are never operators, so they can never broaden the
        hidden/protected-path inspection performed by read/curation tools.
        """
        is_http, authorization = _request_authorization(ctx)
        if not is_http:
            return True
        return resolve_granted_scopes(authorization, svc.get_config()) is None

    def _principal_kind(ctx: Context) -> str:
        """Classify the caller for receipts: oauth | static_bearer | local."""
        is_http, authorization = _request_authorization(ctx)
        if not is_http:
            return pathsafe.PRINCIPAL_LOCAL
        config = svc.get_config()
        if config.token_configured and (authorization or "") == f"Bearer {config.bearer_token}":
            return pathsafe.PRINCIPAL_STATIC_BEARER
        if resolve_granted_scopes(authorization, config) is None:
            return pathsafe.PRINCIPAL_LOCAL
        return pathsafe.PRINCIPAL_OAUTH

    @mcp.tool()
    def list_directory(
        ctx: Context,
        path: str = "",
        recursive: bool = False,
        extensions: list[str] | None = None,
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        _enforce("list_directory", ctx)
        return svc.list_directory(
            {
                "path": path,
                "recursive": recursive,
                "extensions": extensions,
                "max_depth": max_depth,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def search_vault(
        ctx: Context,
        query: str,
        path_scope: str | None = None,
        file_types: list[str] | None = None,
        limit: int | None = None,
        include_content_snippet: bool = True,
    ) -> dict[str, Any]:
        _enforce("search_vault", ctx)
        return svc.search_vault(
            {
                "query": query,
                "path_scope": path_scope,
                "file_types": file_types,
                "limit": limit,
                "include_content_snippet": include_content_snippet,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def read_file(
        ctx: Context,
        path: str,
        start_page: int | None = None,
        end_page: int | None = None,
        section: str | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        _enforce("read_file", ctx)
        return svc.read_file(
            {
                "path": path,
                "start_page": start_page,
                "end_page": end_page,
                "section": section,
                "max_chars": max_chars,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def create_note(
        ctx: Context,
        path: str,
        content: str,
        overwrite: bool = False,
        create_parent_dirs: bool = True,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Create a Markdown note under the configured autonomous vault policy."""
        _enforce("create_note", ctx)
        return svc.create_note(
            {
                "path": path,
                "content": content,
                "overwrite": overwrite,
                "create_parent_dirs": create_parent_dirs,
                "expected_sha256": expected_sha256,
                "caller_surface": "mcp",
                "tool_name": "create_note",
                "principal_kind": _principal_kind(ctx),
            }
        )

    @mcp.tool()
    def patch_note(ctx: Context, path: str, content: str, expected_sha256: str) -> dict[str, Any]:
        """Replace an existing Markdown note as a whole-file replacement when SHA-256 matches."""
        _enforce("patch_note", ctx)
        return svc.patch_note(
            {
                "path": path,
                "content": content,
                "expected_sha256": expected_sha256,
                "caller_surface": "mcp",
                "tool_name": "patch_note",
                "principal_kind": _principal_kind(ctx),
            }
        )

    @mcp.tool()
    def vault_map(
        ctx: Context,
        root_path: str = "",
        recursive: bool = True,
        max_depth: int | None = 4,
        file_types: list[str] | None = None,
        include_hidden: bool = False,
        include_frontmatter: bool = True,
        include_links: bool = True,
        include_tags: bool = True,
        max_files: int = 500,
    ) -> dict[str, Any]:
        """Read-only crawl of the vault returning a folder/file inventory."""
        _enforce("vault_map", ctx)
        return svc.vault_map(
            {
                "root_path": root_path,
                "recursive": recursive,
                "max_depth": max_depth,
                "file_types": file_types,
                "include_hidden": include_hidden,
                "include_frontmatter": include_frontmatter,
                "include_links": include_links,
                "include_tags": include_tags,
                "max_files": max_files,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def vault_summarize_note(
        ctx: Context,
        path: str,
        max_chars: int | None = None,
        summary_style: str = "executive",
        include_action_items: bool = True,
        include_decisions: bool = True,
        include_entities: bool = True,
    ) -> dict[str, Any]:
        """Summarize one note (md/txt/pdf/docx) with action items, decisions, and entities."""
        _enforce("vault_summarize_note", ctx)
        return svc.vault_summarize_note(
            {
                "path": path,
                "max_chars": max_chars,
                "summary_style": summary_style,
                "include_action_items": include_action_items,
                "include_decisions": include_decisions,
                "include_entities": include_entities,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def vault_summarize_folder(
        ctx: Context,
        root_path: str = "",
        recursive: bool = True,
        max_depth: int | None = 3,
        max_files: int = 100,
        summary_style: str = "project_brief",
        include_file_summaries: bool = True,
        include_themes: bool = True,
        include_action_items: bool = True,
    ) -> dict[str, Any]:
        """Summarize a folder/subtree into themes, per-file summaries, and aggregated actions."""
        _enforce("vault_summarize_folder", ctx)
        return svc.vault_summarize_folder(
            {
                "root_path": root_path,
                "recursive": recursive,
                "max_depth": max_depth,
                "max_files": max_files,
                "summary_style": summary_style,
                "include_file_summaries": include_file_summaries,
                "include_themes": include_themes,
                "include_action_items": include_action_items,
                "operator_mode": _operator_mode(ctx),
                "principal_kind": _principal_kind(ctx),
            }
        )

    @mcp.tool()
    def vault_curation_plan(
        ctx: Context,
        root_path: str = "",
        strategy: str = "second_brain",
        max_depth: int | None = 5,
        max_files: int = 300,
        allowed_actions: list[str] | None = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """Read-only second-brain analysis returning a durable plan_id and proposed actions."""
        _enforce("vault_curation_plan", ctx)
        return svc.vault_curation_plan(
            {
                "root_path": root_path,
                "strategy": strategy,
                "max_depth": max_depth,
                "max_files": max_files,
                "allowed_actions": allowed_actions,
                "dry_run": dry_run,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def vault_curation_apply(
        ctx: Context,
        plan_id: str,
        approved_actions: list[str] | None = None,
        require_expected_sha256: bool = True,
        backup_before_replace: bool = True,
        max_updates: int = 25,
    ) -> dict[str, Any]:
        """Apply approved actions from a server-generated curation plan_id only."""
        _enforce("vault_curation_apply", ctx)
        return svc.vault_curation_apply(
            {
                "plan_id": plan_id,
                "approved_actions": approved_actions,
                "require_expected_sha256": require_expected_sha256,
                "backup_before_replace": backup_before_replace,
                "max_updates": max_updates,
                "operator_mode": _operator_mode(ctx),
            }
        )

    app = mcp.streamable_http_app()
    return BearerTokenMiddleware(app, service=svc)
