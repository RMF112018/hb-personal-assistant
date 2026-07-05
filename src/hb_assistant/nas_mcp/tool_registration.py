"""Register NAS MCP tools on FastMCP server."""

from __future__ import annotations

import inspect
from typing import Any

from .broker import NasMcpBroker
from .obsidian_adapter import NAS_OBSIDIAN_BLOCKED, list_nas_obsidian_tool_names
from .profile import (
    ai_outputs_write_enabled,
    assistant_nav_enabled,
    blocked_write_tools,
    scratch_output_write_enabled,
)


def register_nas_mcp_tools(mcp: Any, broker: NasMcpBroker) -> None:
    @mcp.tool()
    def hb_mcp_status() -> dict[str, Any]:
        payload = broker.dispatch("hb_mcp_status", {})
        return payload.get("result", payload)

    # Tier-0 read-only status/freshness tools — always available (incl. safe mode),
    # require origin auth like every other tool, never expose row content/paths.
    @mcp.tool()
    def hb_data_freshness() -> dict[str, Any]:
        payload = broker.dispatch("hb_data_freshness", {})
        return payload.get("result", payload)

    @mcp.tool()
    def hb_queue_status() -> dict[str, Any]:
        payload = broker.dispatch("hb_queue_status", {})
        return payload.get("result", payload)

    @mcp.tool()
    def hb_recent_failures(limit: int = 10) -> dict[str, Any]:
        payload = broker.dispatch("hb_recent_failures", {"limit": limit})
        return payload.get("result", payload)

    @mcp.tool()
    def hb_last_successful_runs() -> dict[str, Any]:
        payload = broker.dispatch("hb_last_successful_runs", {})
        return payload.get("result", payload)

    @mcp.tool()
    def hb_capability_mode() -> dict[str, Any]:
        payload = broker.dispatch("hb_capability_mode", {})
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

    # N8C-3 read-only source/card/note navigation (assistant_*). Reads only; enabled by default
    # (operator-authorized full-content navigation). Origin auth still applies. Each forwards to the
    # broker, which serves them from a read-only DB snapshot (query_only) with no live-DB fallback.
    def _assistant_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = broker.dispatch(name, arguments)
        if not payload.get("ok"):
            raise ValueError(str(payload.get("error")))
        return payload["result"]

    if assistant_nav_enabled():

        @mcp.tool()
        def assistant_search_sources(query: str, limit: int = 25, project_key: str | None = None) -> dict[str, Any]:
            return _assistant_result("assistant_search_sources", {"query": query, "limit": limit, "project_key": project_key})

        @mcp.tool()
        def assistant_get_source(source_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_source", {"source_id": source_id})

        @mcp.tool()
        def assistant_get_card_for_source(source_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_card_for_source", {"source_id": source_id})

        @mcp.tool()
        def assistant_get_source_for_card(note_rel_path: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_source_for_card", {"note_rel_path": note_rel_path})

        @mcp.tool()
        def assistant_search_cards(query: str, limit: int = 25, path_prefix: str | None = None) -> dict[str, Any]:
            return _assistant_result("assistant_search_cards", {"query": query, "limit": limit, "path_prefix": path_prefix})

        @mcp.tool()
        def assistant_get_card_state(source_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_card_state", {"source_id": source_id})

        @mcp.tool()
        def assistant_list_stale_cards(limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_stale_cards", {"limit": limit})

        @mcp.tool()
        def assistant_list_duplicate_cards(limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_duplicate_cards", {"limit": limit})

        @mcp.tool()
        def assistant_list_ambiguous_card_links(limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_ambiguous_card_links", {"limit": limit})

        @mcp.tool()
        def assistant_recent_changes(limit: int = 25, event_types: list[str] | None = None) -> dict[str, Any]:
            return _assistant_result("assistant_recent_changes", {"limit": limit, "event_types": event_types})

        @mcp.tool()
        def assistant_get_related_sources(source_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_related_sources", {"source_id": source_id})

        @mcp.tool()
        def assistant_get_vault_note(note_rel_path: str, max_chars: int | None = None) -> dict[str, Any]:
            return _assistant_result("assistant_get_vault_note", {"note_rel_path": note_rel_path, "max_chars": max_chars})

    # Local-scratch output writers — registered only when the scratch gate is on
    # (always off in the remote_cloudflare profile).
    if scratch_output_write_enabled():

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

    # The single sanctioned remote write (tier 3): AI Outputs card create/update/append.
    if ai_outputs_write_enabled():

        @mcp.tool()
        def ai_outputs_card_upsert(
            title: str,
            body_markdown: str,
            tags: list[str] | None = None,
            source_client: str = "unknown",
            expected_sha: str | None = None,
            mode: str = "create",
            domain: str = "unknown",
        ) -> dict[str, Any]:
            payload = broker.dispatch(
                "ai_outputs_card_upsert",
                {
                    "title": title,
                    "body_markdown": body_markdown,
                    "tags": tags or [],
                    "source_client": source_client,
                    "expected_sha": expected_sha,
                    "mode": mode,
                    "domain": domain,
                },
            )
            if not payload.get("ok"):
                raise ValueError(str(payload.get("error")))
            return payload["result"]

    enabled = sorted(
        (set(list_nas_obsidian_tool_names()) - set(NAS_OBSIDIAN_BLOCKED.keys())) - blocked_write_tools()
    )

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
