"""NAS adapter for Mac Obsidian MCP vault tools (bounded subset)."""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from hb_assistant.obsidian_mcp import (
    curation,
    domain,
    fileops,
    frontmatter,
    graph,
    mutations,
    summarize,
    templates,
    tools,
)
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

from .config import NasMcpConfig
from .obsidian_config import apply_obsidian_support_env, obsidian_config_from_nas

_VOLUME1_RE = re.compile(r"/volume1/[^\s\"']+")


NAS_OBSIDIAN_BLOCKED: dict[str, str] = {
    "vault_move_note_apply": "destructive apply blocked; requires separate operator approval for NAS move apply",
    "vault_rename_note_apply": "destructive apply blocked; requires separate operator approval for NAS rename apply",
    "vault_archive_note_apply": "destructive apply blocked; requires separate operator approval for NAS archive apply",
    "vault_curation_apply": "curation apply blocked; requires separate operator approval",
    "vault_email_to_note_apply": "email-to-note apply blocked; requires separate operator approval",
    "rebuild_source_index": "source-intelligence index rebuild blocked on NAS MCP",
    "generate_source_card": "source-intelligence card generation blocked on NAS MCP",
    "refresh_stale_source_notes": "source-intelligence refresh blocked on NAS MCP",
    "summarize_source": "source-intelligence summarize blocked on NAS MCP",
    "search_sources": "source-intelligence search blocked on NAS MCP",
    "search_knowledge": "source-intelligence mixed search blocked on NAS MCP",
    "source_index_status": "source-intelligence status blocked on NAS MCP",
    "vault_semantic_search": "semantic search requires source index; blocked pending approval",
    "llm_chat_ingest": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_classify": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_summarize": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_extract_decisions": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_extract_action_items": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_select_template": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_link_existing_notes": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_to_note_plan": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_to_note_apply": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_update_topic_memory_plan": "LLM chat memory tools blocked on NAS MCP",
    "llm_chat_update_topic_memory_apply": "LLM chat memory tools blocked on NAS MCP",
}


def _normalize(payload: Any) -> Any:
    if isinstance(payload, dict):
        out: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"path", "relative_path", "target_path", "source_path"} and isinstance(value, str):
                rel = value.lstrip("/")
                out[key] = rel
                out.setdefault("path_display", f"vault/{rel}" if rel else "vault")
            else:
                out[key] = _normalize(value)
        out.setdefault("root_key", "vault")
        return out
    if isinstance(payload, list):
        return [_normalize(item) for item in payload]
    if isinstance(payload, str):
        return _VOLUME1_RE.sub("[REDACTED_HOST_PATH]", payload)
    return payload


def _dispatch_obsidian(config: NasMcpConfig, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if tool_name in NAS_OBSIDIAN_BLOCKED:
        raise ObsidianMcpToolError("blocked_on_nas", NAS_OBSIDIAN_BLOCKED[tool_name])
    if config.obsidian is None:
        raise ObsidianMcpToolError("obsidian_not_configured", "obsidian block missing from MCP config")
    apply_obsidian_support_env(config)
    ob = obsidian_config_from_nas(config)
    args = dict(arguments)

    handlers: dict[str, Callable[..., Any]] = {
        "list_directory": lambda: tools.list_directory(ob, path=args.get("path", ""), recursive=bool(args.get("recursive", False)), extensions=args.get("extensions"), max_depth=args.get("max_depth")),
        "search_vault": lambda: tools.search_vault(ob, query=str(args["query"]), path_scope=args.get("path_scope"), file_types=args.get("file_types"), limit=int(args.get("limit", 25)), include_content_snippet=bool(args.get("include_content_snippet", False))),
        "read_file": lambda: tools.read_file(ob, path=str(args["path"]), start_page=args.get("start_page"), end_page=args.get("end_page"), section=args.get("section"), max_chars=args.get("max_chars")),
        "create_note": lambda: mutations.create_note(ob, path=str(args["path"]), content=str(args["content"]), overwrite=bool(args.get("overwrite", False)), create_parent_dirs=bool(args.get("create_parent_dirs", True)), expected_sha256=args.get("expected_sha256"), caller_surface="nas_mcp"),
        "patch_note": lambda: mutations.patch_note(ob, path=str(args["path"]), content=str(args["content"]), expected_sha256=str(args["expected_sha256"]), caller_surface="nas_mcp"),
        "vault_map": lambda: curation.vault_map(ob, root_path=str(args.get("root_path", "")), recursive=bool(args.get("recursive", False)), max_depth=args.get("max_depth"), file_types=args.get("file_types"), include_hidden=bool(args.get("include_hidden", False)), include_frontmatter=bool(args.get("include_frontmatter", False)), include_links=bool(args.get("include_links", False)), include_tags=bool(args.get("include_tags", False)), max_files=args.get("max_files")),
        "vault_summarize_note": lambda: summarize.summarize_note(ob, path=str(args["path"]), max_chars=args.get("max_chars"), summary_style=str(args.get("summary_style", "executive")), include_action_items=bool(args.get("include_action_items", True)), include_decisions=bool(args.get("include_decisions", True)), include_entities=bool(args.get("include_entities", True)), backend=None),
        "vault_summarize_folder": lambda: summarize.summarize_folder(ob, root_path=str(args.get("root_path", "")), recursive=bool(args.get("recursive", False)), max_depth=args.get("max_depth"), max_files=args.get("max_files"), summary_style=str(args.get("summary_style", "executive")), include_file_summaries=bool(args.get("include_file_summaries", True)), include_themes=bool(args.get("include_themes", True)), include_action_items=bool(args.get("include_action_items", True)), backend=None),
        "vault_read_frontmatter": lambda: frontmatter.read_frontmatter(ob, path=str(args["path"])),
        "vault_update_frontmatter": lambda: frontmatter.update_frontmatter(ob, path=str(args["path"]), updates=dict(args.get("updates") or {}), merge_tags=bool(args.get("merge_tags", True)), expected_sha256=str(args["expected_sha256"]), backup_before_replace=bool(args.get("backup_before_replace", True)), caller_surface="nas_mcp"),
        "vault_search_by_properties": lambda: frontmatter.search_by_properties(ob, root_path=str(args.get("root_path", "")), filters=dict(args.get("filters") or {}), tags_any=args.get("tags_any"), tags_all=args.get("tags_all"), limit=int(args.get("limit", 25))),
        "vault_dataview_query": lambda: frontmatter.dataview_query(ob, root_path=str(args.get("root_path", "")), where=args.get("where"), select=args.get("select"), limit=int(args.get("limit", 25))),
        "vault_get_backlinks": lambda: graph.get_backlinks(ob, target_path=str(args["target_path"]), root_path=str(args.get("root_path", "")), max_results=int(args.get("max_results", 25))),
        "vault_get_unlinked_mentions": lambda: graph.get_unlinked_mentions(ob, target_title=str(args["target_title"]), root_path=str(args.get("root_path", "")), max_results=int(args.get("max_results", 25)), include_snippets=bool(args.get("include_snippets", False))),
        "vault_get_note_graph": lambda: graph.get_note_graph(ob, root_path=str(args.get("root_path", "")), target_path=args.get("target_path"), depth=int(args.get("depth", 1)), max_nodes=int(args.get("max_nodes", 50))),
        "vault_create_note_from_template": lambda: templates.create_note_from_template(ob, template_path=str(args["template_path"]), target_path=str(args["target_path"]), variables=dict(args.get("variables") or {}), frontmatter=dict(args.get("frontmatter") or {}), overwrite=bool(args.get("overwrite", False)), create_parent_dirs=bool(args.get("create_parent_dirs", True)), caller_surface="nas_mcp"),
        "vault_append_to_daily_note": lambda: templates.append_to_daily_note(ob, date=str(args.get("date", "")), section=str(args.get("section", "")), content=str(args["content"]), create_if_missing=bool(args.get("create_if_missing", True)), template_path=args.get("template_path"), caller_surface="nas_mcp"),
        "vault_move_note_plan": lambda: fileops.move_note_plan(ob, source_path=str(args["source_path"]), target_path=str(args["target_path"]), update_links=bool(args.get("update_links", True))),
        "vault_rename_note_plan": lambda: fileops.rename_note_plan(ob, source_path=str(args["source_path"]), new_name=str(args["new_name"]), update_links=bool(args.get("update_links", True))),
        "vault_archive_note_plan": lambda: fileops.archive_note_plan(ob, source_path=str(args["source_path"]), update_links=bool(args.get("update_links", True))),
        "vault_delete_note_plan": lambda: fileops.delete_note_plan(ob, source_path=str(args["source_path"]), update_links=bool(args.get("update_links", True))),
        "vault_curation_plan": lambda: curation.build_curation_plan(ob, root_path=str(args.get("root_path", "")), strategy=str(args.get("strategy", "balanced")), max_depth=args.get("max_depth"), max_files=args.get("max_files"), allowed_actions=args.get("allowed_actions"), dry_run=bool(args.get("dry_run", True))),
        "vault_create_moc_plan": lambda: curation.build_moc_plan(ob, root_path=str(args.get("root_path", "")), moc_title=str(args.get("moc_title", "")), target_path=str(args.get("target_path", "")), max_files=args.get("max_files"), include_sections=bool(args.get("include_sections", True))),
        "vault_auto_link_plan": lambda: curation.build_auto_link_plan(ob, root_path=str(args.get("root_path", "")), max_files=args.get("max_files"), min_confidence=float(args.get("min_confidence", 0.5)), max_suggestions=int(args.get("max_suggestions", 10))),
        "vault_bulk_tagging_plan": lambda: curation.build_bulk_tagging_plan(ob, root_path=str(args.get("root_path", "")), tag_namespace=str(args.get("tag_namespace", "")), max_files=args.get("max_files"), max_suggestions=int(args.get("max_suggestions", 10))),
        "vault_email_to_note_plan": lambda: curation.build_email_to_note_plan(ob, email_path=str(args["email_path"]), target_folder=str(args.get("target_folder", "")), template_path=args.get("template_path"), link_projects=bool(args.get("link_projects", True)), extract_action_items=bool(args.get("extract_action_items", True)), extract_decisions=bool(args.get("extract_decisions", True)), redact=bool(args.get("redact", True))),
        "vault_read_eml": lambda: __import__("hb_assistant.obsidian_mcp.eml", fromlist=["read_eml"]).read_eml(ob, path=str(args["path"]), include_body=bool(args.get("include_body", True)), include_attachments=bool(args.get("include_attachments", False)), max_body_chars=args.get("max_body_chars"), redact_email_addresses=bool(args.get("redact_email_addresses", True)), redact_phone_numbers=bool(args.get("redact_phone_numbers", True))),
        "vault_email_inventory": lambda: __import__("hb_assistant.obsidian_mcp.eml", fromlist=["email_inventory"]).email_inventory(ob, root_path=str(args.get("root_path", "")), recursive=bool(args.get("recursive", False)), max_depth=args.get("max_depth"), max_files=args.get("max_files"), include_subject=bool(args.get("include_subject", True)), include_from=bool(args.get("include_from", True)), include_date=bool(args.get("include_date", True)), include_body_preview=bool(args.get("include_body_preview", False))),
        "vault_parse_email": lambda: __import__("hb_assistant.obsidian_mcp.eml", fromlist=["parse_email"]).parse_email(ob, path=str(args["path"]), extract=args.get("extract"), max_body_chars=args.get("max_body_chars"), redact_email_addresses=bool(args.get("redact_email_addresses", True)), redact_phone_numbers=bool(args.get("redact_phone_numbers", True))),
        "vault_extract_action_items": lambda: domain.extract_action_items(ob, path=str(args["path"]), source_type=str(args.get("source_type", "note")), extract_fields=args.get("extract_fields"), max_chars=args.get("max_chars")),
        "vault_project_status_summary": lambda: domain.project_status_summary(ob, root_path=str(args.get("root_path", "")), lookback_days=int(args.get("lookback_days", 30)), include=args.get("include"), max_files=args.get("max_files")),
        "vault_extract_project_mentions": lambda: domain.extract_project_mentions(ob, root_path=str(args.get("root_path", "")), project_aliases=args.get("project_aliases"), max_files=args.get("max_files"), include_snippets=bool(args.get("include_snippets", False))),
    }

    handler = handlers.get(tool_name)
    if handler is None:
        raise ObsidianMcpToolError("tool_not_registered", f"obsidian tool not enabled on NAS: {tool_name}")
    result = handler()
    normalized = _normalize(result)
    blob = json.dumps(normalized)
    if "/volume1/" in blob:
        raise ObsidianMcpToolError("host_path_leak", "tool response contained host path")
    return normalized


def dispatch_obsidian_tool(config: NasMcpConfig, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return _dispatch_obsidian(config, tool_name, arguments)
    except ObsidianMcpToolError as exc:
        raise ValueError(str(exc.code if hasattr(exc, "code") else exc)) from exc


def list_nas_obsidian_tool_names() -> list[str]:
    from hb_assistant.obsidian_mcp.tools import tool_registry

    names = [t["name"] for t in tool_registry()]
    return sorted(names)
