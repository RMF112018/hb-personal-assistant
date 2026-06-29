"""Optional MCP SDK adapter for the UI-managed Obsidian MCP server."""

# NOTE: deliberately no ``from __future__ import annotations`` — the MCP SDK
# evaluates tool type hints via ``get_type_hints``, and the ``Context`` param is
# bound in a local scope, so annotations must stay real objects (not strings).

import logging
import time
from collections.abc import Callable
from typing import Any

import anyio

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
    "vault_read_eml": "obsidian.read",
    "vault_email_inventory": "obsidian.read",
    "vault_parse_email": "obsidian.read",
    "vault_read_frontmatter": "obsidian.read",
    "vault_update_frontmatter": "obsidian.write",
    "vault_search_by_properties": "obsidian.read",
    "vault_dataview_query": "obsidian.read",
    "vault_get_backlinks": "obsidian.read",
    "vault_get_unlinked_mentions": "obsidian.read",
    "vault_get_note_graph": "obsidian.read",
    "vault_create_note_from_template": "obsidian.write",
    "vault_append_to_daily_note": "obsidian.write",
    "vault_move_note_plan": "obsidian.read",
    "vault_move_note_apply": "obsidian.write",
    "vault_rename_note_plan": "obsidian.read",
    "vault_rename_note_apply": "obsidian.write",
    "vault_archive_note_plan": "obsidian.read",
    "vault_archive_note_apply": "obsidian.write",
    "vault_delete_note_plan": "obsidian.read",
    "vault_semantic_search": "obsidian.read",
    "vault_extract_action_items": "obsidian.read",
    "vault_project_status_summary": "obsidian.read",
    "vault_extract_project_mentions": "obsidian.read",
    "vault_curation_plan": "obsidian.read",
    "vault_curation_apply": "obsidian.write",
    "vault_create_moc_plan": "obsidian.read",
    "vault_auto_link_plan": "obsidian.read",
    "vault_bulk_tagging_plan": "obsidian.read",
    "vault_email_to_note_plan": "obsidian.read",
    "vault_email_to_note_apply": "obsidian.write",
    "search_sources": "obsidian.read",
    "search_knowledge": "obsidian.read",
    "source_index_status": "obsidian.read",
    "rebuild_source_index": "obsidian.write",
    "generate_source_card": "obsidian.write",
    "refresh_stale_source_notes": "obsidian.write",
    "summarize_source": "obsidian.write",
    "llm_chat_classify": "obsidian.read",
    "llm_chat_ingest": "obsidian.read",
    "llm_chat_summarize": "obsidian.read",
    "llm_chat_extract_decisions": "obsidian.read",
    "llm_chat_extract_action_items": "obsidian.read",
    "llm_chat_select_template": "obsidian.read",
    "llm_chat_link_existing_notes": "obsidian.read",
    "llm_chat_to_note_plan": "obsidian.read",
    "llm_chat_to_note_apply": "obsidian.write",
    "llm_chat_update_topic_memory_plan": "obsidian.read",
    "llm_chat_update_topic_memory_apply": "obsidian.write",
}

_BEARER_PREFIX = "Bearer "


_logger = logging.getLogger("hb_assistant.obsidian_mcp.mcp")

_DEFAULT_TOOL_TIMEOUT_SECONDS = 30.0

# Allow-list of argument keys that are safe to log verbatim. Vault-relative paths
# are already constrained by pathsafe; the rest are structural scalars/enums/ints/
# bools. Free-text and payload keys (content, updates, query, titles, names, dict/
# list bodies) are never logged verbatim: ``content``/``updates`` become a char
# count, and any key not on this allow-list is dropped entirely.
_SAFE_LOG_KEYS = frozenset(
    {
        "path", "path_scope", "root_path", "target_path", "source_path", "email_path",
        "template_path", "target_folder", "file_types", "extract", "extract_fields",
        "include", "limit", "max_files", "max_depth", "max_results", "max_nodes",
        "max_updates", "max_suggestions", "max_chars", "max_body_chars", "depth",
        "lookback_days", "recursive", "include_hidden", "include_snippets", "dry_run",
        "overwrite", "create_parent_dirs", "merge_tags", "backup_before_replace",
        "update_links", "allow_overwrite", "require_expected_sha256", "mode",
        "summary_style", "strategy", "source_type", "date", "section",
        "min_confidence", "operator_mode", "principal_kind", "project_key",
        "source_id",
    }
)
_LEN_ONLY_LOG_KEYS = frozenset({"content", "updates"})


def _tool_timeout_seconds(config: ObsidianMcpConfig) -> float:
    """Per-tool execution budget (seconds); falls back to the default if unset/invalid."""
    try:
        value = float(getattr(config, "tool_timeout_seconds", _DEFAULT_TOOL_TIMEOUT_SECONDS))
    except (TypeError, ValueError):
        return _DEFAULT_TOOL_TIMEOUT_SECONDS
    return value if value > 0 else _DEFAULT_TOOL_TIMEOUT_SECONDS


def _safe_descriptors(args: dict[str, Any]) -> dict[str, Any]:
    """Redacted, allow-listed view of tool args for diagnostics.

    Never returns secrets, note content, raw bodies, or free-text query/title values.
    """
    safe: dict[str, Any] = {}
    for key, value in args.items():
        if key in _LEN_ONLY_LOG_KEYS:
            try:
                safe[f"{key}_chars"] = len(value) if value is not None else 0
            except TypeError:
                safe[f"{key}_chars"] = None
            continue
        if key not in _SAFE_LOG_KEYS:
            continue
        if isinstance(value, str) and len(value) > 256:
            value = value[:256]
        safe[key] = value
    return safe


def _tool_start_message(tool: str) -> str:
    return f"obsidian_mcp.tool_start tool={tool}"


def _tool_end_message(tool: str, elapsed_ms: float) -> str:
    return f"obsidian_mcp.tool_end tool={tool} elapsed_ms={elapsed_ms}"


def _tool_error_message(tool: str, error_code: str, elapsed_ms: float) -> str:
    return f"obsidian_mcp.tool_error tool={tool} error_code={error_code} elapsed_ms={elapsed_ms}"


def _auth_required(config: ObsidianMcpConfig) -> bool:
    return bool(config.token_configured or getattr(config, "oauth_enabled", False))


def is_authorized(authorization: str | None, config: ObsidianMcpConfig) -> bool:
    """Authentication check used by the middleware: is this a known principal?"""
    auth = authorization or ""
    if config.token_configured and auth == f"Bearer {config.bearer_token}":
        return True
    if getattr(config, "oauth_enabled", False) and auth.startswith(_BEARER_PREFIX):
        if not config.public_base_url:
            return False
        return oauth_store.validate_access_token(
            auth[len(_BEARER_PREFIX):],
            resource=oauth_store.mcp_resource(config.public_base_url),
        ) is not None
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
        if not config.public_base_url:
            return ()
        info = oauth_store.validate_access_token(
            auth[len(_BEARER_PREFIX):],
            resource=oauth_store.mcp_resource(config.public_base_url),
        )
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
                    response_headers = [(b"content-type", b"application/json")]
                    if config.public_base_url:
                        response_headers.append(
                            (
                                b"www-authenticate",
                                oauth_store.www_authenticate_header(config.public_base_url).encode("latin1"),
                            )
                        )
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 401,
                            "headers": response_headers,
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


def build_streamable_http_app(
    service: ObsidianMcpService | None = None, *, db_path: str | None = None
) -> Any:
    """Build the official MCP SDK Streamable HTTP ASGI app.

    The SDK is optional and imported only when the FastAPI backend is created with it installed.
    ``db_path`` is threaded into the service so source-intelligence tools hit the same SQLite as
    the app (tests pass a temp DB; production resolves PathPolicy().get_db_path()).
    """
    from mcp.server.fastmcp import (  # type: ignore[import-not-found]  # noqa: PLC0415
        Context,
        FastMCP,
    )
    from mcp.server.transport_security import (  # type: ignore[import-not-found]  # noqa: PLC0415
        TransportSecuritySettings,
    )
    from mcp.types import ToolAnnotations  # type: ignore[import-not-found]  # noqa: PLC0415

    svc = service or ObsidianMcpService(db_path=db_path)
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

    def _tool_options(tool_name: str, *, read_only: bool, destructive: bool = False) -> dict[str, Any]:
        scope = _TOOL_SCOPES[tool_name]
        security_scheme = {"type": "oauth2", "scopes": [scope]}
        return {
            "annotations": ToolAnnotations(readOnlyHint=read_only, destructiveHint=destructive),
            "meta": {
                "securitySchemes": [security_scheme],
                "openai/toolInvocation/invoking": f"Running {tool_name}",
                "openai/toolInvocation/invoked": f"Completed {tool_name}",
            },
        }

    async def _run_tool(
        tool: str,
        ctx: Context,
        call: Callable[[], dict[str, Any]],
        args: dict[str, Any],
    ) -> dict[str, Any]:
        """Run a blocking service call off the event loop, bounded by a timeout.

        ``call`` is a zero-arg callable closing over already-resolved args; it must
        not touch ``ctx`` (the request contextvar is not valid in a worker thread).
        All ctx/scope/principal resolution happens on the loop before this point.
        """
        is_http, authorization = _request_authorization(ctx)
        diag = {
            "caller_surface": "mcp",
            "authorization_present": bool(authorization),
            "principal_kind": _principal_kind(ctx) if is_http else pathsafe.PRINCIPAL_LOCAL,
            **_safe_descriptors(args),
        }
        _logger.info(
            _tool_start_message(tool),
            extra={"obsidian_mcp": {"tool": tool, "status": "start", **diag}},
        )
        started = time.monotonic()
        try:
            with anyio.fail_after(_tool_timeout_seconds(svc.get_config())):
                # abandon_on_cancel=True is required: on timeout the worker thread is
                # abandoned and the loop is freed immediately, so a truly stuck I/O
                # call surfaces as a fast structured error instead of hanging forever.
                result = await anyio.to_thread.run_sync(call, abandon_on_cancel=True)
        except TimeoutError:
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            _logger.warning(
                _tool_error_message(tool, "tool_timeout", elapsed_ms),
                extra={
                    "obsidian_mcp": {
                        "tool": tool,
                        "status": "tool_timeout",
                        "error_code": "tool_timeout",
                        "elapsed_ms": elapsed_ms,
                        **diag,
                    }
                },
            )
            raise ObsidianMcpToolError("tool_timeout") from None
        except ObsidianMcpToolError as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            _logger.warning(
                _tool_error_message(tool, exc.code, elapsed_ms),
                extra={
                    "obsidian_mcp": {
                        "tool": tool,
                        "status": "error",
                        "error_code": exc.code,
                        "elapsed_ms": elapsed_ms,
                        **diag,
                    }
                },
            )
            raise
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            _logger.warning(
                _tool_error_message(tool, "internal_error", elapsed_ms),
                extra={
                    "obsidian_mcp": {
                        "tool": tool,
                        "status": "error",
                        "error_code": "internal_error",
                        "elapsed_ms": elapsed_ms,
                        **diag,
                    }
                },
            )
            raise ObsidianMcpToolError("internal_error") from exc
        elapsed_ms = round((time.monotonic() - started) * 1000, 1)
        _logger.info(
            _tool_end_message(tool, elapsed_ms),
            extra={"obsidian_mcp": {"tool": tool, "status": "ok", "elapsed_ms": elapsed_ms, **diag}},
        )
        return result

    @mcp.tool(**_tool_options("list_directory", read_only=True))
    async def list_directory(
        ctx: Context,
        path: str = "",
        recursive: bool = False,
        extensions: list[str] | None = None,
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        _enforce("list_directory", ctx)
        args = {
            "path": path,
            "recursive": recursive,
            "extensions": extensions,
            "max_depth": max_depth,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("list_directory", ctx, lambda: svc.list_directory(args), args)

    @mcp.tool(**_tool_options("search_vault", read_only=True))
    async def search_vault(
        ctx: Context,
        query: str,
        path_scope: str | None = None,
        file_types: list[str] | None = None,
        limit: int | None = None,
        include_content_snippet: bool = True,
    ) -> dict[str, Any]:
        _enforce("search_vault", ctx)
        args = {
            "query": query,
            "path_scope": path_scope,
            "file_types": file_types,
            "limit": limit,
            "include_content_snippet": include_content_snippet,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("search_vault", ctx, lambda: svc.search_vault(args), args)

    @mcp.tool(**_tool_options("read_file", read_only=True))
    async def read_file(
        ctx: Context,
        path: str,
        start_page: int | None = None,
        end_page: int | None = None,
        section: str | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        _enforce("read_file", ctx)
        args = {
            "path": path,
            "start_page": start_page,
            "end_page": end_page,
            "section": section,
            "max_chars": max_chars,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("read_file", ctx, lambda: svc.read_file(args), args)

    @mcp.tool(**_tool_options("create_note", read_only=False))
    async def create_note(
        ctx: Context,
        path: str,
        content: str,
        overwrite: bool = False,
        create_parent_dirs: bool = True,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Create a Markdown note under the configured autonomous vault policy."""
        _enforce("create_note", ctx)
        args = {
            "path": path,
            "content": content,
            "overwrite": overwrite,
            "create_parent_dirs": create_parent_dirs,
            "expected_sha256": expected_sha256,
            "caller_surface": "mcp",
            "tool_name": "create_note",
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("create_note", ctx, lambda: svc.create_note(args), args)

    @mcp.tool(**_tool_options("patch_note", read_only=False, destructive=True))
    async def patch_note(ctx: Context, path: str, content: str, expected_sha256: str) -> dict[str, Any]:
        """Replace an existing Markdown note as a whole-file replacement when SHA-256 matches."""
        _enforce("patch_note", ctx)
        args = {
            "path": path,
            "content": content,
            "expected_sha256": expected_sha256,
            "caller_surface": "mcp",
            "tool_name": "patch_note",
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("patch_note", ctx, lambda: svc.patch_note(args), args)

    @mcp.tool()
    async def vault_map(
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
        args = {
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
        return await _run_tool("vault_map", ctx, lambda: svc.vault_map(args), args)

    @mcp.tool()
    async def vault_summarize_note(
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
        args = {
            "path": path,
            "max_chars": max_chars,
            "summary_style": summary_style,
            "include_action_items": include_action_items,
            "include_decisions": include_decisions,
            "include_entities": include_entities,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_summarize_note", ctx, lambda: svc.vault_summarize_note(args), args)

    @mcp.tool()
    async def vault_summarize_folder(
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
        args = {
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
        return await _run_tool("vault_summarize_folder", ctx, lambda: svc.vault_summarize_folder(args), args)

    @mcp.tool()
    async def vault_read_eml(
        ctx: Context,
        path: str,
        include_body: bool = True,
        include_attachments: bool = False,
        max_body_chars: int = 12000,
        redact_email_addresses: bool = False,
        redact_phone_numbers: bool = False,
    ) -> dict[str, Any]:
        """Parse one .eml email: headers, body, attachment metadata, detected entities."""
        _enforce("vault_read_eml", ctx)
        args = {
            "path": path,
            "include_body": include_body,
            "include_attachments": include_attachments,
            "max_body_chars": max_body_chars,
            "redact_email_addresses": redact_email_addresses,
            "redact_phone_numbers": redact_phone_numbers,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_read_eml", ctx, lambda: svc.vault_read_eml(args), args)

    @mcp.tool()
    async def vault_email_inventory(
        ctx: Context,
        root_path: str = "",
        recursive: bool = True,
        max_depth: int | None = 3,
        max_files: int = 500,
        include_subject: bool = True,
        include_from: bool = True,
        include_date: bool = True,
        include_body_preview: bool = False,
    ) -> dict[str, Any]:
        """Inventory .eml files in a folder without reading full bodies by default."""
        _enforce("vault_email_inventory", ctx)
        args = {
            "root_path": root_path,
            "recursive": recursive,
            "max_depth": max_depth,
            "max_files": max_files,
            "include_subject": include_subject,
            "include_from": include_from,
            "include_date": include_date,
            "include_body_preview": include_body_preview,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_email_inventory", ctx, lambda: svc.vault_email_inventory(args), args)

    @mcp.tool()
    async def vault_parse_email(
        ctx: Context,
        path: str,
        extract: list[str] | None = None,
        max_body_chars: int = 12000,
        redact_email_addresses: bool = False,
        redact_phone_numbers: bool = False,
    ) -> dict[str, Any]:
        """Parse one .eml into construction/PM extraction categories."""
        _enforce("vault_parse_email", ctx)
        args = {
            "path": path,
            "extract": extract,
            "max_body_chars": max_body_chars,
            "redact_email_addresses": redact_email_addresses,
            "redact_phone_numbers": redact_phone_numbers,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_parse_email", ctx, lambda: svc.vault_parse_email(args), args)

    @mcp.tool()
    async def vault_read_frontmatter(ctx: Context, path: str) -> dict[str, Any]:
        """Read YAML frontmatter/properties plus body and file SHA-256 from a note."""
        _enforce("vault_read_frontmatter", ctx)
        args = {"path": path, "operator_mode": _operator_mode(ctx)}
        return await _run_tool("vault_read_frontmatter", ctx, lambda: svc.vault_read_frontmatter(args), args)

    @mcp.tool()
    async def vault_update_frontmatter(
        ctx: Context,
        path: str,
        updates: dict[str, Any],
        expected_sha256: str,
        merge_tags: bool = True,
        backup_before_replace: bool = True,
    ) -> dict[str, Any]:
        """Update frontmatter properties safely (SHA-gated, body-preserving, backup + receipt)."""
        _enforce("vault_update_frontmatter", ctx)
        args = {
            "path": path,
            "updates": updates,
            "expected_sha256": expected_sha256,
            "merge_tags": merge_tags,
            "backup_before_replace": backup_before_replace,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_update_frontmatter", ctx, lambda: svc.vault_update_frontmatter(args), args)

    @mcp.tool()
    async def vault_search_by_properties(
        ctx: Context,
        root_path: str = "",
        filters: dict[str, Any] | None = None,
        tags_any: list[str] | None = None,
        tags_all: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Find notes by frontmatter property filters and tag any/all matching."""
        _enforce("vault_search_by_properties", ctx)
        args = {
            "root_path": root_path,
            "filters": filters,
            "tags_any": tags_any,
            "tags_all": tags_all,
            "limit": limit,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_search_by_properties", ctx, lambda: svc.vault_search_by_properties(args), args)

    @mcp.tool()
    async def vault_dataview_query(
        ctx: Context,
        root_path: str = "",
        where: list[dict[str, Any]] | None = None,
        select: list[str] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Constrained structured query over note properties (no arbitrary Dataview execution)."""
        _enforce("vault_dataview_query", ctx)
        args = {
            "root_path": root_path,
            "where": where,
            "select": select,
            "limit": limit,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_dataview_query", ctx, lambda: svc.vault_dataview_query(args), args)

    @mcp.tool()
    async def vault_get_backlinks(
        ctx: Context,
        target_path: str,
        root_path: str = "",
        max_results: int = 100,
    ) -> dict[str, Any]:
        """Find notes that link to a target note (wikilinks and Markdown links)."""
        _enforce("vault_get_backlinks", ctx)
        args = {
            "target_path": target_path,
            "root_path": root_path,
            "max_results": max_results,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_get_backlinks", ctx, lambda: svc.vault_get_backlinks(args), args)

    @mcp.tool()
    async def vault_get_unlinked_mentions(
        ctx: Context,
        target_title: str,
        root_path: str = "",
        max_results: int = 100,
        include_snippets: bool = True,
    ) -> dict[str, Any]:
        """Find notes that mention a title/entity but do not link to it."""
        _enforce("vault_get_unlinked_mentions", ctx)
        args = {
            "target_title": target_title,
            "root_path": root_path,
            "max_results": max_results,
            "include_snippets": include_snippets,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_get_unlinked_mentions", ctx, lambda: svc.vault_get_unlinked_mentions(args), args)

    @mcp.tool()
    async def vault_get_note_graph(
        ctx: Context,
        root_path: str = "",
        target_path: str | None = None,
        depth: int = 2,
        max_nodes: int = 100,
    ) -> dict[str, Any]:
        """Return local graph data (nodes, edges, orphans, high-degree notes)."""
        _enforce("vault_get_note_graph", ctx)
        args = {
            "root_path": root_path,
            "target_path": target_path,
            "depth": depth,
            "max_nodes": max_nodes,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_get_note_graph", ctx, lambda: svc.vault_get_note_graph(args), args)

    @mcp.tool()
    async def vault_create_note_from_template(
        ctx: Context,
        template_path: str,
        target_path: str,
        variables: dict[str, Any] | None = None,
        frontmatter: dict[str, Any] | None = None,
        overwrite: bool = False,
        create_parent_dirs: bool = True,
    ) -> dict[str, Any]:
        """Create a note from a vault template with variable substitution and frontmatter."""
        _enforce("vault_create_note_from_template", ctx)
        args = {
            "template_path": template_path,
            "target_path": target_path,
            "variables": variables,
            "frontmatter": frontmatter,
            "overwrite": overwrite,
            "create_parent_dirs": create_parent_dirs,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_create_note_from_template", ctx, lambda: svc.vault_create_note_from_template(args), args)

    @mcp.tool()
    async def vault_append_to_daily_note(
        ctx: Context,
        content: str,
        date: str = "today",
        section: str | None = None,
        create_if_missing: bool = True,
        template_path: str | None = None,
    ) -> dict[str, Any]:
        """Append structured content to a daily note (section-aware, create-if-missing)."""
        _enforce("vault_append_to_daily_note", ctx)
        args = {
            "content": content,
            "date": date,
            "section": section,
            "create_if_missing": create_if_missing,
            "template_path": template_path,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_append_to_daily_note", ctx, lambda: svc.vault_append_to_daily_note(args), args)

    @mcp.tool()
    async def vault_semantic_search(
        ctx: Context,
        query: str,
        path_scope: str | None = None,
        file_types: list[str] | None = None,
        limit: int = 20,
        mode: str = "hybrid",
        include_snippets: bool = True,
    ) -> dict[str, Any]:
        """Semantic/hybrid search (falls back to lexical with a warning when no index exists)."""
        _enforce("vault_semantic_search", ctx)
        args = {
            "query": query,
            "path_scope": path_scope,
            "file_types": file_types,
            "limit": limit,
            "mode": mode,
            "include_snippets": include_snippets,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_semantic_search", ctx, lambda: svc.vault_semantic_search(args), args)

    @mcp.tool()
    async def vault_move_note_plan(
        ctx: Context, source_path: str, target_path: str, update_links: bool = True
    ) -> dict[str, Any]:
        """Plan a note move with a backlink-impact preview (read-only)."""
        _enforce("vault_move_note_plan", ctx)
        args = {
            "source_path": source_path,
            "target_path": target_path,
            "update_links": update_links,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_move_note_plan", ctx, lambda: svc.vault_move_note_plan(args), args)

    @mcp.tool()
    async def vault_move_note_apply(
        ctx: Context,
        plan_id: str,
        update_links: bool = True,
        max_updates: int = 25,
        allow_overwrite: bool = False,
    ) -> dict[str, Any]:
        """Apply an approved move plan_id (backup, sha-gated link rewrite, receipts)."""
        _enforce("vault_move_note_apply", ctx)
        args = {
            "plan_id": plan_id,
            "update_links": update_links,
            "max_updates": max_updates,
            "allow_overwrite": allow_overwrite,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_move_note_apply", ctx, lambda: svc.vault_move_note_apply(args), args)

    @mcp.tool()
    async def vault_rename_note_plan(
        ctx: Context, source_path: str, new_name: str, update_links: bool = True
    ) -> dict[str, Any]:
        """Plan a note rename with a backlink-impact preview (read-only)."""
        _enforce("vault_rename_note_plan", ctx)
        args = {
            "source_path": source_path,
            "new_name": new_name,
            "update_links": update_links,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_rename_note_plan", ctx, lambda: svc.vault_rename_note_plan(args), args)

    @mcp.tool()
    async def vault_rename_note_apply(
        ctx: Context,
        plan_id: str,
        update_links: bool = True,
        max_updates: int = 25,
        allow_overwrite: bool = False,
    ) -> dict[str, Any]:
        """Apply an approved rename plan_id (backup, sha-gated link rewrite, receipts)."""
        _enforce("vault_rename_note_apply", ctx)
        args = {
            "plan_id": plan_id,
            "update_links": update_links,
            "max_updates": max_updates,
            "allow_overwrite": allow_overwrite,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_rename_note_apply", ctx, lambda: svc.vault_rename_note_apply(args), args)

    @mcp.tool()
    async def vault_archive_note_plan(ctx: Context, source_path: str, update_links: bool = True) -> dict[str, Any]:
        """Plan moving a note to the archive folder with a backlink-impact preview (read-only)."""
        _enforce("vault_archive_note_plan", ctx)
        args = {
            "source_path": source_path,
            "update_links": update_links,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_archive_note_plan", ctx, lambda: svc.vault_archive_note_plan(args), args)

    @mcp.tool()
    async def vault_archive_note_apply(
        ctx: Context,
        plan_id: str,
        update_links: bool = True,
        max_updates: int = 25,
        allow_overwrite: bool = False,
    ) -> dict[str, Any]:
        """Apply an approved archive plan_id (backup, sha-gated link rewrite, receipts)."""
        _enforce("vault_archive_note_apply", ctx)
        args = {
            "plan_id": plan_id,
            "update_links": update_links,
            "max_updates": max_updates,
            "allow_overwrite": allow_overwrite,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_archive_note_apply", ctx, lambda: svc.vault_archive_note_apply(args), args)

    @mcp.tool()
    async def vault_delete_note_plan(ctx: Context, source_path: str, update_links: bool = True) -> dict[str, Any]:
        """Refuses permanent deletion; returns an archive plan as the safe substitute."""
        _enforce("vault_delete_note_plan", ctx)
        args = {
            "source_path": source_path,
            "update_links": update_links,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_delete_note_plan", ctx, lambda: svc.vault_delete_note_plan(args), args)

    @mcp.tool()
    async def vault_extract_action_items(
        ctx: Context,
        path: str,
        source_type: str = "note",
        extract_fields: list[str] | None = None,
        max_chars: int = 12000,
    ) -> dict[str, Any]:
        """Extract action items, decisions, risks, owners, and dates from a note, email, or folder."""
        _enforce("vault_extract_action_items", ctx)
        args = {
            "path": path,
            "source_type": source_type,
            "extract_fields": extract_fields,
            "max_chars": max_chars,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_extract_action_items", ctx, lambda: svc.vault_extract_action_items(args), args)

    @mcp.tool()
    async def vault_project_status_summary(
        ctx: Context,
        root_path: str = "",
        lookback_days: int = 30,
        include: list[str] | None = None,
        max_files: int = 100,
    ) -> dict[str, Any]:
        """Summarize project notes/emails into a PM-facing status summary."""
        _enforce("vault_project_status_summary", ctx)
        args = {
            "root_path": root_path,
            "lookback_days": lookback_days,
            "include": include,
            "max_files": max_files,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_project_status_summary", ctx, lambda: svc.vault_project_status_summary(args), args)

    @mcp.tool()
    async def vault_extract_project_mentions(
        ctx: Context,
        root_path: str = "",
        project_aliases: list[str] | None = None,
        max_files: int = 200,
        include_snippets: bool = False,
    ) -> dict[str, Any]:
        """Detect project references (HB numbers and aliases) across notes and emails."""
        _enforce("vault_extract_project_mentions", ctx)
        args = {
            "root_path": root_path,
            "project_aliases": project_aliases,
            "max_files": max_files,
            "include_snippets": include_snippets,
            "operator_mode": _operator_mode(ctx),
            "principal_kind": _principal_kind(ctx),
        }
        return await _run_tool("vault_extract_project_mentions", ctx, lambda: svc.vault_extract_project_mentions(args), args)

    @mcp.tool()
    async def vault_curation_plan(
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
        args = {
            "root_path": root_path,
            "strategy": strategy,
            "max_depth": max_depth,
            "max_files": max_files,
            "allowed_actions": allowed_actions,
            "dry_run": dry_run,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_curation_plan", ctx, lambda: svc.vault_curation_plan(args), args)

    @mcp.tool()
    async def vault_curation_apply(
        ctx: Context,
        plan_id: str,
        approved_actions: list[str] | None = None,
        require_expected_sha256: bool = True,
        backup_before_replace: bool = True,
        max_updates: int = 25,
    ) -> dict[str, Any]:
        """Apply approved actions from a server-generated curation plan_id only."""
        _enforce("vault_curation_apply", ctx)
        args = {
            "plan_id": plan_id,
            "approved_actions": approved_actions,
            "require_expected_sha256": require_expected_sha256,
            "backup_before_replace": backup_before_replace,
            "max_updates": max_updates,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_curation_apply", ctx, lambda: svc.vault_curation_apply(args), args)

    @mcp.tool()
    async def vault_create_moc_plan(
        ctx: Context,
        root_path: str = "",
        moc_title: str | None = None,
        target_path: str | None = None,
        max_files: int = 100,
        include_sections: list[str] | None = None,
    ) -> dict[str, Any]:
        """Plan creation of a Map of Content note (applied via vault_curation_apply)."""
        _enforce("vault_create_moc_plan", ctx)
        args = {
            "root_path": root_path,
            "moc_title": moc_title,
            "target_path": target_path,
            "max_files": max_files,
            "include_sections": include_sections,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_create_moc_plan", ctx, lambda: svc.vault_create_moc_plan(args), args)

    @mcp.tool()
    async def vault_auto_link_plan(
        ctx: Context,
        root_path: str = "",
        max_files: int = 200,
        min_confidence: float = 0.75,
        max_suggestions: int = 100,
    ) -> dict[str, Any]:
        """Plan suggested links between notes by title/entity overlap."""
        _enforce("vault_auto_link_plan", ctx)
        args = {
            "root_path": root_path,
            "max_files": max_files,
            "min_confidence": min_confidence,
            "max_suggestions": max_suggestions,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_auto_link_plan", ctx, lambda: svc.vault_auto_link_plan(args), args)

    @mcp.tool()
    async def vault_bulk_tagging_plan(
        ctx: Context,
        root_path: str = "",
        tag_namespace: str | None = None,
        max_files: int = 200,
        max_suggestions: int = 100,
    ) -> dict[str, Any]:
        """Plan normalized tag suggestions for notes."""
        _enforce("vault_bulk_tagging_plan", ctx)
        args = {
            "root_path": root_path,
            "tag_namespace": tag_namespace,
            "max_files": max_files,
            "max_suggestions": max_suggestions,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_bulk_tagging_plan", ctx, lambda: svc.vault_bulk_tagging_plan(args), args)

    @mcp.tool()
    async def vault_email_to_note_plan(
        ctx: Context,
        email_path: str,
        target_folder: str,
        template_path: str | None = None,
        link_projects: bool = True,
        extract_action_items: bool = True,
        extract_decisions: bool = True,
        redact: bool = False,
    ) -> dict[str, Any]:
        """Plan conversion of one .eml into a structured note (applied via vault_email_to_note_apply)."""
        _enforce("vault_email_to_note_plan", ctx)
        args = {
            "email_path": email_path,
            "target_folder": target_folder,
            "template_path": template_path,
            "link_projects": link_projects,
            "extract_action_items": extract_action_items,
            "extract_decisions": extract_decisions,
            "redact": redact,
            "operator_mode": _operator_mode(ctx),
        }
        return await _run_tool("vault_email_to_note_plan", ctx, lambda: svc.vault_email_to_note_plan(args), args)

    @mcp.tool()
    async def vault_email_to_note_apply(ctx: Context, plan_id: str, max_updates: int = 25) -> dict[str, Any]:
        """Create the structured note from an approved email-to-note plan_id."""
        _enforce("vault_email_to_note_apply", ctx)
        args = {"plan_id": plan_id, "max_updates": max_updates, "operator_mode": _operator_mode(ctx)}
        return await _run_tool("vault_email_to_note_apply", ctx, lambda: svc.vault_email_to_note_apply(args), args)

    @mcp.tool()
    async def search_sources(
        ctx: Context, query: str, project_key: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Search the durable external-source intelligence index (FTS over metadata + extracted
        text). Never live-scans directories; returns index-status when the index is unavailable."""
        _enforce("search_sources", ctx)
        args = {"query": query, "project_key": project_key, "limit": limit,
                "operator_mode": _operator_mode(ctx)}
        return await _run_tool("search_sources", ctx, lambda: svc.search_sources(args), args)

    @mcp.tool()
    async def search_knowledge(
        ctx: Context, query: str, path_scope: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        """Search across both Obsidian notes and external source intelligence (mixed result
        types) via the index. Never live-scans the vault."""
        _enforce("search_knowledge", ctx)
        args = {"query": query, "path_scope": path_scope, "limit": limit,
                "operator_mode": _operator_mode(ctx)}
        return await _run_tool("search_knowledge", ctx, lambda: svc.search_knowledge(args), args)

    @mcp.tool()
    async def source_index_status(ctx: Context) -> dict[str, Any]:
        """Report source-intelligence index + watcher status (counts, queue, freshness)."""
        _enforce("source_index_status", ctx)
        args: dict[str, Any] = {"operator_mode": _operator_mode(ctx)}
        return await _run_tool("source_index_status", ctx, lambda: svc.source_index_status({}), args)

    @mcp.tool()
    async def rebuild_source_index(ctx: Context) -> dict[str, Any]:
        """Operator action: enqueue a bounded rebuild of configured source roots + the vault note
        index. Never scans inside the request; the watcher/worker drains the queue."""
        _enforce("rebuild_source_index", ctx)
        args: dict[str, Any] = {"operator_mode": _operator_mode(ctx)}
        return await _run_tool("rebuild_source_index", ctx, lambda: svc.rebuild_source_index({}), args)

    @mcp.tool()
    async def generate_source_card(ctx: Context, source_id: str, overwrite: bool = False) -> dict[str, Any]:
        """Generate a deterministic curated source card (Markdown note) for one indexed source_id.
        Describes + links the source; no model summary, no raw file/email-body dump. Write-scoped."""
        _enforce("generate_source_card", ctx)
        args = {"source_id": source_id, "overwrite": overwrite,
                "principal_kind": _principal_kind(ctx), "operator_mode": _operator_mode(ctx)}
        return await _run_tool(
            "generate_source_card", ctx,
            lambda: svc.generate_source_card(
                {"source_id": source_id, "overwrite": overwrite, "principal_kind": args["principal_kind"]}
            ),
            args,
        )

    @mcp.tool()
    async def refresh_stale_source_notes(ctx: Context, max_updates: int = 25) -> dict[str, Any]:
        """Refresh source cards whose underlying source changed (status=stale), up to max_updates.
        SHA-gated whole-file replacement via the write guardrails. Write-scoped."""
        _enforce("refresh_stale_source_notes", ctx)
        args = {"max_updates": max_updates, "principal_kind": _principal_kind(ctx),
                "operator_mode": _operator_mode(ctx)}
        return await _run_tool(
            "refresh_stale_source_notes", ctx,
            lambda: svc.refresh_stale_source_notes(
                {"max_updates": max_updates, "principal_kind": args["principal_kind"]}
            ),
            args,
        )

    @mcp.tool()
    async def summarize_source(ctx: Context, source_id: str) -> dict[str, Any]:
        """Model-assisted (Ollama) ADVISORY enrichment of a source card: generates the
        deterministic base if missing, then adds a bounded, clearly-labelled advisory summary
        section in place. Falls back to summarized:false when the model is unavailable; never
        runs in the search path. Write-scoped."""
        _enforce("summarize_source", ctx)
        args = {"source_id": source_id, "principal_kind": _principal_kind(ctx),
                "operator_mode": _operator_mode(ctx)}
        return await _run_tool(
            "summarize_source", ctx,
            lambda: svc.summarize_source(
                {"source_id": source_id, "principal_kind": args["principal_kind"]}
            ),
            args,
        )

    @mcp.tool()
    def llm_chat_ingest(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
    ) -> dict[str, Any]:
        """Load, redact, and truncate LLM transcript text without persisting raw content."""
        _enforce("llm_chat_ingest", ctx)
        return svc.llm_chat_ingest(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_classify(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
    ) -> dict[str, Any]:
        """Classify an LLM chat session by domain, knowledge type, and sensitivity."""
        _enforce("llm_chat_classify", ctx)
        return svc.llm_chat_classify(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_summarize(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
    ) -> dict[str, Any]:
        """Produce a bounded summary from an LLM chat transcript."""
        _enforce("llm_chat_summarize", ctx)
        return svc.llm_chat_summarize(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_extract_decisions(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
    ) -> dict[str, Any]:
        """Extract decision lines from an LLM chat transcript."""
        _enforce("llm_chat_extract_decisions", ctx)
        return svc.llm_chat_extract_decisions(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_extract_action_items(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
    ) -> dict[str, Any]:
        """Extract action items from an LLM chat transcript."""
        _enforce("llm_chat_extract_action_items", ctx)
        return svc.llm_chat_extract_action_items(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_select_template(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        template_mode: str = "auto",
        target_folder: str | None = None,
        topic_domain: str | None = None,
        routing_hint: str | None = None,
    ) -> dict[str, Any]:
        """Select a vault LLM session template based on classification."""
        _enforce("llm_chat_select_template", ctx)
        return svc.llm_chat_select_template(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "template_mode": template_mode,
                "target_folder": target_folder,
                "topic_domain": topic_domain,
                "routing_hint": routing_hint,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_link_existing_notes(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Suggest related existing vault notes for an LLM chat session."""
        _enforce("llm_chat_link_existing_notes", ctx)
        return svc.llm_chat_link_existing_notes(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "limit": limit,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_to_note_plan(
        ctx: Context,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
        conversation_title: str | None = None,
        conversation_date: str | None = None,
        source_platform: str = "unknown",
        source_model: str = "unknown",
        topic_domain: str | None = None,
        knowledge_type: str | None = None,
        sensitivity: str | None = None,
        target_folder: str | None = None,
        template_mode: str = "auto",
        include_raw_transcript: bool = False,
        include_domain_specific_sections: bool | None = None,
        routing_hint: str | None = None,
        project_hint: str | None = None,
        workstream_hint: str | None = None,
        topic_hint: str | None = None,
        people_hint: str | None = None,
        location_hint: str | None = None,
        source_context_hint: str | None = None,
        related_notes: list[str] | None = None,
        link_existing_notes: bool = False,
    ) -> dict[str, Any]:
        """Create a durable plan to convert an LLM chat into an Obsidian session note."""
        _enforce("llm_chat_to_note_plan", ctx)
        return svc.llm_chat_to_note_plan(
            {
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "conversation_title": conversation_title,
                "conversation_date": conversation_date,
                "source_platform": source_platform,
                "source_model": source_model,
                "topic_domain": topic_domain,
                "knowledge_type": knowledge_type,
                "sensitivity": sensitivity,
                "target_folder": target_folder,
                "template_mode": template_mode,
                "include_raw_transcript": include_raw_transcript,
                "include_domain_specific_sections": include_domain_specific_sections,
                "routing_hint": routing_hint,
                "project_hint": project_hint,
                "workstream_hint": workstream_hint,
                "topic_hint": topic_hint,
                "people_hint": people_hint,
                "location_hint": location_hint,
                "source_context_hint": source_context_hint,
                "related_notes": related_notes,
                "link_existing_notes": link_existing_notes,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_to_note_apply(
        ctx: Context,
        plan_id: str,
        approved_action_ids: list[str] | None = None,
        approved_actions: list[str] | None = None,
        max_updates: int | None = None,
    ) -> dict[str, Any]:
        """Apply approved actions from a server-generated LLM chat plan_id only."""
        _enforce("llm_chat_to_note_apply", ctx)
        return svc.llm_chat_to_note_apply(
            {
                "plan_id": plan_id,
                "approved_action_ids": approved_action_ids,
                "approved_actions": approved_actions,
                "max_updates": max_updates,
                "tool_name": "llm_chat_to_note_apply",
                "principal_kind": _principal_kind(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_update_topic_memory_plan(
        ctx: Context,
        target_path: str,
        transcript: str | None = None,
        transcript_text: str | None = None,
        transcript_path: str | None = None,
        max_chars: int | None = None,
        redact: bool | None = None,
    ) -> dict[str, Any]:
        """Plan an append-only update to a durable topic memory note."""
        _enforce("llm_chat_update_topic_memory_plan", ctx)
        return svc.llm_chat_update_topic_memory_plan(
            {
                "target_path": target_path,
                "transcript": transcript,
                "transcript_text": transcript_text,
                "transcript_path": transcript_path,
                "max_chars": max_chars,
                "redact": redact,
                "operator_mode": _operator_mode(ctx),
            }
        )

    @mcp.tool()
    def llm_chat_update_topic_memory_apply(
        ctx: Context,
        plan_id: str,
        approved_action_ids: list[str] | None = None,
        approved_actions: list[str] | None = None,
        max_updates: int | None = None,
    ) -> dict[str, Any]:
        """Apply approved topic-memory updates from a server-generated plan_id only."""
        _enforce("llm_chat_update_topic_memory_apply", ctx)
        return svc.llm_chat_update_topic_memory_apply(
            {
                "plan_id": plan_id,
                "approved_action_ids": approved_action_ids,
                "approved_actions": approved_actions,
                "max_updates": max_updates,
                "tool_name": "llm_chat_update_topic_memory_apply",
                "principal_kind": _principal_kind(ctx),
            }
        )

    app = mcp.streamable_http_app()
    return BearerTokenMiddleware(app, service=svc)
