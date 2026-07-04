"""Register NAS MCP tools on FastMCP server."""

from __future__ import annotations

import inspect
from typing import Any

from .broker import NasMcpBroker
from .obsidian_adapter import NAS_OBSIDIAN_BLOCKED, list_nas_obsidian_tool_names


def register_nas_mcp_tools(mcp: Any, broker: NasMcpBroker) -> None:
    @mcp.tool()
    def hb_mcp_status() -> dict[str, Any]:
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
        payload = broker.dispatch(
            "hb_db_select",
            {"table_key": table_key, "columns": columns, "filters": filters or {}, "order_by": order_by, "limit": limit},
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_root_list(root_key: str, relative_path: str = ".", max_entries: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch("hb_root_list", {"root_key": root_key, "relative_path": relative_path, "max_entries": max_entries})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_root_stat(root_key: str, relative_path: str) -> dict[str, Any]:
        payload = broker.dispatch("hb_root_stat", {"root_key": root_key, "relative_path": relative_path})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_root_search(root_key: str, query: str, relative_path: str = ".", limit: int = 25) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_root_search", {"root_key": root_key, "query": query, "relative_path": relative_path, "limit": limit}
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_root_read_excerpt(root_key: str, relative_path: str, max_bytes: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_root_read_excerpt", {"root_key": root_key, "relative_path": relative_path, "max_bytes": max_bytes}
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_root_read_file(root_key: str, relative_path: str, max_chars: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_root_read_file", {"root_key": root_key, "relative_path": relative_path, "max_chars": max_chars}
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_output_list(relative_path: str = ".", max_entries: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch("hb_output_list", {"relative_path": relative_path, "max_entries": max_entries})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_output_stat(relative_path: str) -> dict[str, Any]:
        payload = broker.dispatch("hb_output_stat", {"relative_path": relative_path})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_output_read(relative_path: str, max_chars: int | None = None) -> dict[str, Any]:
        payload = broker.dispatch("hb_output_read", {"relative_path": relative_path, "max_chars": max_chars})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_output_write_file(relative_path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
        payload = broker.dispatch(
            "hb_output_write_file", {"relative_path": relative_path, "content": content, "overwrite": overwrite}
        )
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    @mcp.tool()
    def hb_output_create_dir(relative_path: str) -> dict[str, Any]:
        payload = broker.dispatch("hb_output_create_dir", {"relative_path": relative_path})
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    enabled = sorted(set(list_nas_obsidian_tool_names()) - set(NAS_OBSIDIAN_BLOCKED.keys()))

    obsidian_param_names = sorted(
        {
            "allowed_actions",
            "content",
            "create_if_missing",
            "create_parent_dirs",
            "date",
            "depth",
            "dry_run",
            "email_path",
            "end_page",
            "expected_sha256",
            "extensions",
            "extract",
            "extract_action_items",
            "extract_decisions",
            "extract_fields",
            "file_types",
            "filters",
            "frontmatter",
            "include",
            "include_action_items",
            "include_attachments",
            "include_body",
            "include_body_preview",
            "include_content_snippet",
            "include_date",
            "include_decisions",
            "include_entities",
            "include_file_summaries",
            "include_from",
            "include_frontmatter",
            "include_hidden",
            "include_links",
            "include_sections",
            "include_snippets",
            "include_subject",
            "include_tags",
            "include_themes",
            "limit",
            "lookback_days",
            "max_body_chars",
            "max_chars",
            "max_depth",
            "max_files",
            "max_nodes",
            "max_results",
            "max_suggestions",
            "merge_tags",
            "min_confidence",
            "moc_title",
            "new_name",
            "overwrite",
            "path",
            "path_scope",
            "project_aliases",
            "query",
            "recursive",
            "redact",
            "redact_email_addresses",
            "redact_phone_numbers",
            "root_path",
            "section",
            "select",
            "source_path",
            "source_type",
            "start_page",
            "strategy",
            "summary_style",
            "tag_namespace",
            "tags_all",
            "tags_any",
            "target_folder",
            "target_path",
            "target_title",
            "template_path",
            "update_links",
            "updates",
            "variables",
            "where",
        }
    )

    def _make_obsidian_tool(name: str) -> Any:
        def _obsidian_tool(**kwargs: Any) -> dict[str, Any]:
            arguments = {key: value for key, value in kwargs.items() if value is not None}
            payload = broker.dispatch(name, arguments)
            if not payload.get("ok"):
                raise ValueError(str(payload.get("error")))
            return payload["result"]

        params = [
            inspect.Parameter(param, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=Any)
            for param in obsidian_param_names
        ]
        _obsidian_tool.__signature__ = inspect.Signature(params)
        _obsidian_tool.__name__ = name.replace("-", "_")
        return mcp.tool(name=name)(_obsidian_tool)

    for tool_name in enabled:
        _make_obsidian_tool(tool_name)
