"""Register NAS MCP tools on FastMCP server."""

from __future__ import annotations

import inspect
from typing import Any

from mcp.types import ToolAnnotations

from .broker import (
    ALL_ASSISTANT_TOOLS,
    ASSISTANT_TOOL_GROUPS,
    DENIED_TOOL_NAMES,
    GATEWAY_ALLOWLIST,
    NasMcpBroker,
    assistant_client_exposure_status,
)
from .client_output_tools import ALL_PA_OUTPUT_TOOLS
from .obsidian_adapter import NAS_OBSIDIAN_BLOCKED, list_nas_obsidian_tool_names
from .profile import (
    ai_outputs_write_enabled,
    artifact_author_enabled,
    artifact_workspace_enabled,
    assistant_action_stages_enabled,
    assistant_answer_drafts_enabled,
    assistant_context_packs_enabled,
    assistant_decision_memory_enabled,
    assistant_feedback_enabled,
    assistant_intelligence_enabled,
    assistant_memory_enabled,
    assistant_nav_enabled,
    assistant_quality_enabled,
    assistant_research_packets_enabled,
    assistant_review_enabled,
    assistant_source_connector_enabled,
    assistant_source_structure_enabled,
    assistant_workflows_enabled,
    blocked_write_tools,
    client_output_write_enabled,
    client_tool_manifest_enabled,
    prompt_preflight_enabled,
    scratch_output_write_enabled,
)

# N8C-22 client-exposure bridge helper tools. NOT part of the canonical 78 assistant tools — they are
# read-only meta/gateway helpers named ``hb_assistant_*`` (never ``assistant_*``) so they stay outside
# the exact-78 inventory invariant and the ``assistant_``-prefixed finality guard. Names carry no
# finality/write verb (catalog / tool_help / tool_query).
CLIENT_BRIDGE_HELPER_TOOLS = (
    "hb_assistant_catalog",
    "hb_assistant_tool_help",
    "hb_assistant_tool_query",
)

# Reverse map: canonical assistant tool name -> its group label (built once from the canonical registry).
_TOOL_TO_GROUP = {tool: group for group, tools in ASSISTANT_TOOL_GROUPS.items() for tool in tools}

# Gateway bound caps: reject unbounded numeric limit-like args before dispatch (defense in depth on top
# of the per-handler bounds). A request over the cap fails closed rather than being silently clamped.
_GATEWAY_LIMIT_CAPS = {
    "limit": 500,
    "max_results": 500,
    "max_files": 500,
    "max_nodes": 500,
    "max_suggestions": 500,
    "depth": 100,
    "max_depth": 100,
    "lookback_days": 3650,
    "max_chars": 20000,
    "max_body_chars": 20000,
}


def _extract_client_tool_index(mcp: Any) -> dict[str, dict[str, Any]]:
    """Best-effort snapshot of the LIVE client-facing tool manifest {name: {description, input_schema}}.

    Reads the FastMCP tool manager (the same registry FastMCP's ``tools/list`` serves to clients), so the
    catalog/help helpers describe what a connected client can actually call. Degrades to ``{}`` on any
    non-FastMCP object (e.g. a test fake) or introspection error — never raises.
    """
    mgr = getattr(mcp, "_tool_manager", None)
    lister = getattr(mgr, "list_tools", None) if mgr is not None else None
    if not callable(lister):
        return {}
    try:
        tools = lister()
    except Exception:
        return {}
    index: dict[str, dict[str, Any]] = {}
    for tool in tools or []:
        name = getattr(tool, "name", None)
        if not name:
            continue
        index[name] = {
            "description": getattr(tool, "description", "") or "",
            "input_schema": getattr(tool, "parameters", None) or {},
        }
    return index


# Live client-facing tool-schema index, captured once at registration (see register_nas_mcp_tools).
# Lets the persisted tool manifest (built in the handler context, which has no `mcp` object) carry the
# same purpose/args/limits the catalog derives from the live FastMCP schemas. Best-effort: empty until
# registration runs; the manifest checksum ignores these fields so an empty snapshot never churns it.
_LIVE_TOOL_SCHEMA_INDEX: dict[str, dict[str, Any]] = {}


def live_tool_schema_index() -> dict[str, dict[str, Any]]:
    """The live client-facing tool-schema index captured at registration ({} before registration)."""
    return _LIVE_TOOL_SCHEMA_INDEX


def schema_index_frozen() -> bool:
    """True when ``register_nas_mcp_tools`` has captured the FastMCP tool-schema index."""
    return bool(_LIVE_TOOL_SCHEMA_INDEX)


def freeze_registered_schema_index(mcp: Any) -> dict[str, dict[str, Any]]:
    """Capture the live FastMCP tool schemas once registration is complete.

    Manifest builds must read required_args / optional_args / purpose from this frozen index
    only — never from speculative ToolSpec fallbacks.
    """
    global _LIVE_TOOL_SCHEMA_INDEX
    _LIVE_TOOL_SCHEMA_INDEX = _extract_client_tool_index(mcp)
    return _LIVE_TOOL_SCHEMA_INDEX


def seed_frozen_schema_index(index: dict[str, dict[str, Any]]) -> None:
    """Test hook: inject a frozen schema index without full MCP registration."""
    global _LIVE_TOOL_SCHEMA_INDEX
    _LIVE_TOOL_SCHEMA_INDEX = dict(index)


def ensure_schema_index_frozen(config: Any) -> None:
    """Capture the live FastMCP tool-schema index when broker-only dispatch has not registered tools.

    Operator ``docker exec`` refresh paths construct a fresh ``NasMcpBroker`` without running
    ``register_nas_mcp_tools``; manifest refresh must still read args/purpose from the frozen index.
    """
    if schema_index_frozen():
        return
    from mcp.server.fastmcp import FastMCP  # noqa: PLC0415

    from .broker import NasMcpBroker  # noqa: PLC0415

    mcp = FastMCP("hb-nas-mcp-schema-freeze", json_response=True, stateless_http=True)
    register_nas_mcp_tools(mcp, NasMcpBroker(config))


def derive_tool_arg_meta(name: str, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Purpose + required/optional args + result limits for one tool, derived from its live schema."""
    entry = index.get(name) or {}
    schema = entry.get("input_schema") or {}
    props = schema.get("properties") or {}
    required = list(schema.get("required") or [])
    optional = sorted(p for p in props if p not in required)
    desc = (entry.get("description") or "").strip()
    purpose = next((line.strip() for line in desc.splitlines() if line.strip()), "")
    from hb_assistant.obsidian_mcp.canonical_tool_specs import (  # noqa: PLC0415
        resolve_tool_spec,
    )

    spec = resolve_tool_spec(name, _TOOL_TO_GROUP.get(name))
    if spec.purpose:
        purpose = spec.purpose
    limits = {
        key: props[key].get("default")
        for key in ("limit", "max_chars", "max_results", "max_files", "max_nodes", "max_body_chars")
        if key in props
    }
    return {"purpose": purpose, "required_args": required, "optional_args": optional, "limits": limits}


def _assistant_tool_meta(name: str, index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Bounded, secret-free metadata for one canonical assistant tool, derived from its live schema."""
    arg_meta = derive_tool_arg_meta(name, index)
    # Classify from the single source of truth (mirrors broker._access_mode) instead of hardcoding a
    # blanket "read_only_advisory" — that label mislabelled every gateway-reachable staged/canonical
    # write (pa_session_capture_stage, pa_output_stage, …) as a safe read.
    from hb_assistant.obsidian_mcp.client_tool_manifest import classify_tool  # noqa: PLC0415

    tool_class, safety_class, read_write_class = classify_tool(name, _TOOL_TO_GROUP.get(name))
    from hb_assistant.obsidian_mcp.canonical_tool_specs import resolve_tool_spec  # noqa: PLC0415

    spec = resolve_tool_spec(name, _TOOL_TO_GROUP.get(name))
    examples = list(spec.examples)
    if not examples and spec.use_when:
        examples = [spec.use_when]
    return {
        "tool_name": name,
        "group": _TOOL_TO_GROUP.get(name),
        "purpose": arg_meta["purpose"],
        "required_args": arg_meta["required_args"],
        "optional_args": arg_meta["optional_args"],
        "result_limits": arg_meta["limits"],
        "tool_class": tool_class,
        "read_write_class": read_write_class,
        "safety_class": safety_class,
        "direct_exposure_available": name in index,
        "use_when": spec.use_when,
        "do_not_use_when": spec.do_not_use_when,
        "examples": examples,
        "common_failure_modes": list(spec.common_failure_modes),
    }


def _gateway_arg_validation_error(arguments: dict[str, Any]) -> str | None:
    """Return a bounded reason if any limit-like arg exceeds its cap."""
    for key, cap in _GATEWAY_LIMIT_CAPS.items():
        if key not in arguments:
            continue
        val = arguments[key]
        if isinstance(val, bool):
            continue
        if isinstance(val, int) and val > cap:
            return f"limit_exceeds_max:{key}:{val}>{cap}"
    return None


def _gateway_failure(
    gateway_tool: str,
    reason: str,
    *,
    subject_tool: str | None = None,
) -> dict[str, Any]:
    from .broker import runtime_commit  # noqa: PLC0415
    from .failure_envelope import gateway_plugin_failure  # noqa: PLC0415

    return gateway_plugin_failure(
        tool=subject_tool or gateway_tool,
        reason=reason,
        gateway_tool=gateway_tool,
        runtime_commit=runtime_commit(),
    )


# Gateway proxy that can route to a canonical write tool. The broker classifies its own access mode
# as "read" (it holds no write verb), but for connector safety-annotation purposes it is treated as
# write-capable so a client's safety layer does not present it as an unconditionally-safe read. Any
# write actually routed through it still passes the full broker gate chain regardless of this hint.
_GATEWAY_PROXY_WRITE_TOOLS: frozenset[str] = frozenset({"hb_assistant_tool_query"})


def _is_write_tool(tool_name: str) -> bool:
    """Read/write classification for MCP tool annotations. Mirrors ``broker._access_mode`` (the single
    source of truth for what counts as a write) plus the gateway proxy, so annotations never drift from
    the gate chain."""
    if NasMcpBroker._access_mode(tool_name) == "write":
        return True
    return tool_name in _GATEWAY_PROXY_WRITE_TOOLS


def _stamp_tool_annotations(mcp: Any) -> None:
    """Stamp MCP ``ToolAnnotations`` (readOnlyHint / destructiveHint) on every registered tool so a
    connected client's safety layer can tell safe reads from writes.

    Additive metadata only: the broker gate chain, safe mode, scope enforcement, and the gateway remain
    the real controls — a tool's annotation never widens or narrows what the broker allows. The read/write
    split reuses ``_is_write_tool`` (which mirrors ``broker._access_mode``). Called once, after all
    conditional tool registration, over the live FastMCP tool objects (FastMCP ``list_tools`` serializes
    ``annotations``/``meta`` straight into the ``tools/list`` response).

    No-op on stubs that do not expose a FastMCP tool manager (test doubles register tools without one)."""
    manager = getattr(mcp, "_tool_manager", None)
    if manager is None or not hasattr(manager, "list_tools"):
        return
    for tool in manager.list_tools():
        write = _is_write_tool(tool.name)
        tool.annotations = ToolAnnotations(readOnlyHint=not write, destructiveHint=write)
        meta = dict(tool.meta or {})
        meta.setdefault("openai/toolInvocation/invoking", f"Running {tool.name}")
        meta.setdefault("openai/toolInvocation/invoked", f"Completed {tool.name}")
        tool.meta = meta


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
        def assistant_get_source(source_id: str, max_excerpt_chars: int | None = None) -> dict[str, Any]:
            """DB detail for an indexed source + its card linkage. The echoed ``text_excerpt`` is bounded
            to a least-exposure default (4000 chars); pass ``max_excerpt_chars`` to widen it (a truncated
            excerpt is flagged with ``text_excerpt_truncated``). Prefer metadata first, then a bounded
            read via assistant_source_file_read for full file content."""
            return _assistant_result("assistant_get_source",
                                     {"source_id": source_id, "max_excerpt_chars": max_excerpt_chars})

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

    # N8C-6 read-only enrichment-review + context-pack tools. Reads only; enabled by default. The pack
    # BUILD/apply path is CLI-only and is NEVER exposed remotely (no write tool is registered here).
    # Served from the same read-only DB snapshot via the broker.
    if assistant_context_packs_enabled():

        @mcp.tool()
        def assistant_list_context_packs(pack_type: str | None = None, status: str | None = None,
                                         limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_context_packs",
                                     {"pack_type": pack_type, "status": status, "limit": limit})

        @mcp.tool()
        def assistant_get_context_pack(pack_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_context_pack", {"pack_id": pack_id})

        @mcp.tool()
        def assistant_get_context_pack_items(pack_id: str, limit: int = 200) -> dict[str, Any]:
            return _assistant_result("assistant_get_context_pack_items",
                                     {"pack_id": pack_id, "limit": limit})

        @mcp.tool()
        def assistant_list_enrichment_review_items(limit: int = 25, job_type: str | None = None,
                                                   review_tier: str | None = None) -> dict[str, Any]:
            return _assistant_result("assistant_list_enrichment_review_items",
                                     {"limit": limit, "job_type": job_type, "review_tier": review_tier})

    # N8C-7 read-only memory-compiler tools. Reads only; enabled by default. The compile/apply path
    # is CLI-only and is NEVER exposed remotely (no write tool is registered here). Served from the
    # same read-only DB snapshot via the broker.
    if assistant_memory_enabled():

        @mcp.tool()
        def assistant_list_memory_nodes(node_type: str | None = None, status: str | None = None,
                                        domain: str | None = None, limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_memory_nodes",
                                     {"node_type": node_type, "status": status, "domain": domain,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_memory_node(node_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_memory_node", {"node_id": node_id})

        @mcp.tool()
        def assistant_get_memory_mentions(node_id: str, limit: int = 200) -> dict[str, Any]:
            return _assistant_result("assistant_get_memory_mentions",
                                     {"node_id": node_id, "limit": limit})

        @mcp.tool()
        def assistant_get_memory_compilations(node_id: str, limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_get_memory_compilations",
                                     {"node_id": node_id, "limit": limit})

    # N8C-8 read-only decision/preference/open-loop tools. Reads only; enabled by default. The
    # extract/apply path is CLI-only and is NEVER exposed remotely (no write/extract/action tool is
    # registered here). Served from the same read-only DB snapshot via the broker.
    if assistant_decision_memory_enabled():

        @mcp.tool()
        def assistant_list_decisions(decision_type: str | None = None, status: str | None = None,
                                     query: str | None = None, limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_decisions",
                                     {"decision_type": decision_type, "status": status,
                                      "query": query, "limit": limit})

        @mcp.tool()
        def assistant_get_decision(decision_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_decision", {"decision_id": decision_id})

        @mcp.tool()
        def assistant_list_preferences(preference_type: str | None = None, status: str | None = None,
                                       query: str | None = None, limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_preferences",
                                     {"preference_type": preference_type, "status": status,
                                      "query": query, "limit": limit})

        @mcp.tool()
        def assistant_get_preference(preference_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_preference", {"preference_id": preference_id})

        @mcp.tool()
        def assistant_list_open_loops(open_loop_type: str | None = None, status: str | None = None,
                                      query: str | None = None, limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_open_loops",
                                     {"open_loop_type": open_loop_type, "status": status,
                                      "query": query, "limit": limit})

        @mcp.tool()
        def assistant_get_open_loop(open_loop_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_open_loop", {"open_loop_id": open_loop_id})

    # N8C-9 read-only review-overlay tools. Reads only; enabled by default. The build/apply and
    # disposition/apply writers are CLI-only and are NEVER exposed remotely (no build/apply/disposition/
    # action tool is registered here). Served from the same read-only DB snapshot via the broker.
    if assistant_review_enabled():

        @mcp.tool()
        def assistant_list_review_items(target_kind: str | None = None, review_type: str | None = None,
                                        review_state: str | None = None,
                                        effective_state: str | None = None,
                                        include_superseded: bool = False,
                                        limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_review_items",
                                     {"target_kind": target_kind, "review_type": review_type,
                                      "review_state": review_state, "effective_state": effective_state,
                                      "include_superseded": include_superseded, "limit": limit})

        @mcp.tool()
        def assistant_get_review_item(review_item_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_review_item", {"review_item_id": review_item_id})

        @mcp.tool()
        def assistant_get_review_dispositions(review_item_id: str, limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_get_review_dispositions",
                                     {"review_item_id": review_item_id, "limit": limit})

        @mcp.tool()
        def assistant_get_effective_review_state(target_kind: str, target_id: str,
                                                 limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_get_effective_review_state",
                                     {"target_kind": target_kind, "target_id": target_id,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_review_summary() -> dict[str, Any]:
            return _assistant_result("assistant_get_review_summary", {})

    # N8C-10 read-only review-aware intelligence-projection tools. Reads only; enabled by default. The
    # build/apply writer is CLI-only and is NEVER exposed remotely (no build/apply/action tool is
    # registered here). Served from the same read-only DB snapshot via the broker.
    if assistant_intelligence_enabled():

        @mcp.tool()
        def assistant_list_intelligence_projections(projection_type: str | None = None,
                                                    status: str | None = None,
                                                    limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_intelligence_projections",
                                     {"projection_type": projection_type, "status": status,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_intelligence_projection(projection_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_intelligence_projection",
                                     {"projection_id": projection_id})

        @mcp.tool()
        def assistant_get_intelligence_projection_items(projection_id: str,
                                                       inclusion_state: str | None = None,
                                                       included_only: bool = False,
                                                       limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_get_intelligence_projection_items",
                                     {"projection_id": projection_id, "inclusion_state": inclusion_state,
                                      "included_only": included_only, "limit": limit})

        @mcp.tool()
        def assistant_get_intelligence_projection_export(projection_id: str, included_only: bool = True,
                                                        limit: int = 200) -> dict[str, Any]:
            return _assistant_result("assistant_get_intelligence_projection_export",
                                     {"projection_id": projection_id, "included_only": included_only,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_intelligence_summary() -> dict[str, Any]:
            return _assistant_result("assistant_get_intelligence_summary", {})

    # N8C-11 read-only review-aware research-packet + citation tools. Reads only; enabled by default. The
    # build/apply writer is CLI-only and is NEVER exposed remotely (no build/apply/answer/action tool is
    # registered here). Served from the same read-only DB snapshot via the broker.
    if assistant_research_packets_enabled():

        @mcp.tool()
        def assistant_list_research_packets(packet_type: str | None = None, status: str | None = None,
                                            limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_list_research_packets",
                                     {"packet_type": packet_type, "status": status, "limit": limit})

        @mcp.tool()
        def assistant_get_research_packet(packet_id: str) -> dict[str, Any]:
            return _assistant_result("assistant_get_research_packet", {"packet_id": packet_id})

        @mcp.tool()
        def assistant_get_research_packet_items(packet_id: str, answer_role: str | None = None,
                                                included_only: bool = False,
                                                limit: int = 25) -> dict[str, Any]:
            return _assistant_result("assistant_get_research_packet_items",
                                     {"packet_id": packet_id, "answer_role": answer_role,
                                      "included_only": included_only, "limit": limit})

        @mcp.tool()
        def assistant_get_research_packet_citations(packet_id: str, packet_item_id: str | None = None,
                                                    limit: int = 200) -> dict[str, Any]:
            return _assistant_result("assistant_get_research_packet_citations",
                                     {"packet_id": packet_id, "packet_item_id": packet_item_id,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_research_packet_export(packet_id: str, included_only: bool = True,
                                                 limit: int = 200) -> dict[str, Any]:
            return _assistant_result("assistant_get_research_packet_export",
                                     {"packet_id": packet_id, "included_only": included_only,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_research_packet_summary() -> dict[str, Any]:
            return _assistant_result("assistant_get_research_packet_summary", {})

    # N8C-12 read-only NAS source-root file connector. Reads only; enabled by default. These tools search /
    # list / inspect / bounded-READ indexed original SOURCE FILES (PDFs, contracts, invoices, drawings,
    # proposals, spreadsheets) under configured NAS source roots — distinct from vault notes and generated
    # source cards. No scan/reindex, card-generation, answer, or action tool is registered. Served from the
    # same read-only DB snapshot via the broker; the bounded read opens exactly one configured file.
    if assistant_source_connector_enabled():

        @mcp.tool()
        def assistant_source_status() -> dict[str, Any]:
            """NAS source-index status + configured source-root summary (indexed source FILES, not vault
            notes). Use to see how many source files are indexed and which source roots exist."""
            return _assistant_result("assistant_source_status", {})

        @mcp.tool()
        def assistant_source_roots_list() -> dict[str, Any]:
            """List configured NAS source roots (source_root_key + indexed file counts). Use to show the
            structure/top level of the user's source FILE folders before searching or listing files — these
            are NAS source files, not Obsidian vault notes or generated source cards."""
            return _assistant_result("assistant_source_roots_list", {})

        @mcp.tool()
        def assistant_source_files_list(source_root_key: str, prefix: str | None = None,
                                        limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
            """List indexed NAS source FILES under a source_root_key (optional rel_path prefix/folder),
            with cursor paging. Use to browse original files in a NAS project/source folder — not vault
            notes. ``limit`` defaults to 25 and is clamped to 100 per page; pass ``cursor`` for the next
            page. An unknown ``source_root_key`` or a ``..``/absolute ``prefix`` fails closed."""
            return _assistant_result("assistant_source_files_list",
                                     {"source_root_key": source_root_key, "prefix": prefix,
                                      "limit": limit, "cursor": cursor})

        @mcp.tool()
        def assistant_source_file_search(query: str, source_root_key: str | None = None,
                                         file_ext: str | None = None, limit: int = 25,
                                         cursor: str | None = None) -> dict[str, Any]:
            """Full-text search indexed NAS source FILE contents. Use when the user asks to find files in
            NAS source folders / project folders / documents — PDFs, contracts, invoices, drawings,
            proposals, spreadsheets. Hyphenated/dotted project numbers (e.g. ``23-435-01``) are matched
            literally — no quoting needed. Results carry source_root_key + source_ref for follow-up.
            Filter by ``source_root_key``/``file_ext`` (an unknown root fails closed); ``limit`` defaults
            to 25 and is clamped to 100 per page; page with ``cursor``. NOT for Obsidian vault notes."""
            return _assistant_result("assistant_source_file_search",
                                     {"query": query, "source_root_key": source_root_key,
                                      "file_ext": file_ext, "limit": limit, "cursor": cursor})

        @mcp.tool()
        def assistant_source_file_metadata(source_id: str | None = None,
                                           source_ref: str | None = None) -> dict[str, Any]:
            """Metadata for one NAS source FILE by source_id/source_ref: root/rel_path/extension/size +
            whether a generated source card exists (supplemental). Use after a search/list result. The
            original source file is the primary object; the generated card is only supplemental."""
            return _assistant_result("assistant_source_file_metadata",
                                     {"source_id": source_id, "source_ref": source_ref})

        @mcp.tool()
        def assistant_source_file_read(source_id: str | None = None, source_ref: str | None = None,
                                       max_chars: int = 4000,
                                       prefer_live: bool = True) -> dict[str, Any]:
            """Bounded, extension-gated read of one NAS source FILE by source_id/source_ref. Returns a
            live bounded extract when permitted, else the indexed excerpt (labelled
            ``indexed_excerpt_fallback``). Use to read an original source file's content — not a vault
            note or source card. Never returns a full raw file or an absolute path."""
            return _assistant_result("assistant_source_file_read",
                                     {"source_id": source_id, "source_ref": source_ref,
                                      "max_chars": max_chars, "prefer_live": prefer_live})

        @mcp.tool()
        def assistant_source_index_health() -> dict[str, Any]:
            """Per-root source index health (file index + folder map layers): freshness, counts,
            skipped/unsupported, whether safe for client answering. No absolute paths. Use before
            trusting broad NAS answers."""
            return _assistant_result("assistant_source_index_health", {})

        @mcp.tool()
        def assistant_source_query_plan(prompt: str, query: str | None = None) -> dict[str, Any]:
            """Deterministic planner for NAS source prompts: classifies intent (map vs search vs health
            vs unsupported), normalizes project numbers, and recommends a tool sequence. Does not search
            or read files. Prefer this before generic file search for map/folder/project questions."""
            return _assistant_result("assistant_source_query_plan",
                                     {"prompt": prompt or query or "", "query": query})

    # NAS Source-Structure Layered Index (V115) read-only map/route tools. DEFAULT-ON
    # (kill-switch ``HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0``). They return bounded,
    # root-relative maps / routing hints / quality findings from the precomputed source-structure index
    # (built out-of-band by ``hb-assistant source-structure``) — never a live scan, model call, mutation,
    # or absolute path. Names use map/summary/route/explain/quality verbs (no finality/action substring).
    if assistant_source_structure_enabled():

        @mcp.tool()
        def assistant_source_root_map(query_family: str | None = None,
                                      limit: int = 25) -> dict[str, Any]:
            """Map the NAS source ROOTS and where to search first. Returns each root's class
            (construction_work / work / personal / backup_mirror / generated_output / vault), trust tier,
            index policy, counts, and a rationale. Pass ``query_family`` (e.g. ``construction_project``) to
            rank the roots for that intent. Use this before drilling into folders — no absolute paths."""
            return _assistant_result("assistant_source_root_map",
                                     {"query_family": query_family, "limit": limit})

        @mcp.tool()
        def assistant_source_folder_map(root_key: str | None = None,
                                        parent_folder_id: str | None = None, depth: int | None = None,
                                        folder_class: str | None = None, doc_family: str | None = None,
                                        project_number: str | None = None, include_noise: bool = False,
                                        limit: int = 50, cursor: str | None = None) -> dict[str, Any]:
            """Browse a bounded, root-relative folder map. Filter by ``root_key`` / ``parent_folder_id`` /
            ``depth`` / ``folder_class`` / ``doc_family`` / ``project_number``; page with ``cursor``. Noise
            folders (``@eaDir`` etc.) are hidden unless ``include_noise=true``. Each folder carries an
            opaque ``folder_id`` + ``rel_path`` — never an absolute path."""
            return _assistant_result("assistant_source_folder_map",
                                     {"root_key": root_key, "parent_folder_id": parent_folder_id,
                                      "depth": depth, "folder_class": folder_class,
                                      "doc_family": doc_family, "project_number": project_number,
                                      "include_noise": include_noise, "limit": limit, "cursor": cursor})

        @mcp.tool()
        def assistant_source_folder_summary(folder_id: str) -> dict[str, Any]:
            """Summarize one known folder by ``folder_id``: classification, doc-family, a bounded summary,
            child class counts, routing hints, and quality warnings (backup/generated/noise/sensitive).
            Use after a folder-map result to understand what a folder holds before searching it."""
            return _assistant_result("assistant_source_folder_summary", {"folder_id": folder_id})

        @mcp.tool()
        def assistant_source_search_route(query: str | None = None, query_family: str | None = None,
                                          project_number: str | None = None,
                                          doc_family: str | None = None,
                                          limit: int = 10) -> dict[str, Any]:
            """Tell the client WHERE to search first for a file/folder question. Returns preferred roots +
            folders, avoided roots (backups/generated), a rationale, and a confidence. Pass any of
            ``query`` / ``query_family`` / ``project_number`` / ``doc_family``. It routes only — it does
            not execute a search or read any file."""
            return _assistant_result("assistant_source_search_route",
                                     {"query": query, "query_family": query_family,
                                      "project_number": project_number, "doc_family": doc_family,
                                      "limit": limit})

        @mcp.tool()
        def assistant_source_scope_explain(root_key: str | None = None,
                                           folder_id: str | None = None) -> dict[str, Any]:
            """Explain why a root or folder is preferred, downranked, or excluded: its policy,
            classification, reason, and allowed usage. Pass ``root_key`` or ``folder_id``. Use to justify a
            routing choice or to check whether a backup/generated/sensitive folder should be searched."""
            return _assistant_result("assistant_source_scope_explain",
                                     {"root_key": root_key, "folder_id": folder_id})

        @mcp.tool()
        def assistant_source_project_map(project_number: str, limit: int = 50) -> dict[str, Any]:
            """Show candidate folders for a project number (e.g. ``21-801-01``): each folder's relationship
            (primary / supporting / backup / generated), confidence, and the document-family coverage
            (submittals / rfis / pay_app …). Use to locate all of a project's folders across roots."""
            return _assistant_result("assistant_source_project_map",
                                     {"project_number": project_number, "limit": limit})

        @mcp.tool()
        def assistant_source_quality(severity: str | None = None, finding_type: str | None = None,
                                     status: str | None = "open", limit: int = 50,
                                     cursor: str | None = None) -> dict[str, Any]:
            """List advisory source-structure quality findings (stale/noisy/ambiguous/duplicate/
            misclassified folders, and any absolute-path-exposure error). Filter by ``severity`` /
            ``finding_type`` / ``status``; page with ``cursor``. Read-only advisory — it repairs nothing."""
            return _assistant_result("assistant_source_quality",
                                     {"severity": severity, "finding_type": finding_type,
                                      "status": status, "limit": limit, "cursor": cursor})

    # N8C-14 read-only citation-safe answer drafts. Reads only; enabled by default. These tools RETRIEVE
    # bounded, citation-safe DRAFT artifacts built from N8C-11 research packets — cited sections that preserve
    # review labels + source provenance + excluded-content rules + a no-execution policy. They do NOT
    # generate a final/authoritative answer and do NOT execute actions: no build/apply, answer-generation,
    # send, or action tool is registered. Served from the same read-only DB snapshot via the broker.
    if assistant_answer_drafts_enabled():

        @mcp.tool()
        def assistant_list_drafts(draft_type: str | None = None, status: str | None = None,
                                  packet_id: str | None = None, limit: int = 25) -> dict[str, Any]:
            """List persisted citation-safe answer DRAFTS (read-only). Drafts are guidance artifacts, not
            final answers; this retrieves draft artifacts only — it never builds a draft or generates an
            answer."""
            return _assistant_result("assistant_list_drafts",
                                     {"draft_type": draft_type, "status": status, "packet_id": packet_id,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_draft(draft_id: str) -> dict[str, Any]:
            """Get one citation-safe answer DRAFT header (read-only). A draft is guidance, never a final or
            operator-approved answer."""
            return _assistant_result("assistant_get_draft", {"draft_id": draft_id})

        @mcp.tool()
        def assistant_get_draft_sections(draft_id: str, section_type: str | None = None,
                                         limit: int = 100) -> dict[str, Any]:
            """List a draft's bounded, cited DRAFT sections (read-only). Section bodies are bounded
            restatements with review labels — not final authoritative answer prose."""
            return _assistant_result("assistant_get_draft_sections",
                                     {"draft_id": draft_id, "section_type": section_type, "limit": limit})

        @mcp.tool()
        def assistant_get_draft_citations(draft_id: str, draft_section_id: str | None = None,
                                          limit: int = 200) -> dict[str, Any]:
            """List a draft's provenance-anchored citations (read-only). Retrieves citation metadata only;
            performs no live source file read."""
            return _assistant_result("assistant_get_draft_citations",
                                     {"draft_id": draft_id, "draft_section_id": draft_section_id,
                                      "limit": limit})

        @mcp.tool()
        def assistant_get_draft_export(draft_id: str, limit: int = 200) -> dict[str, Any]:
            """Bounded JSON export of a persisted DRAFT (read-only; header + bounded sections + bounded
            citations). Returns a citation-safe draft artifact only — no final answer, no answer prose, no
            action."""
            return _assistant_result("assistant_get_draft_export",
                                     {"draft_id": draft_id, "limit": limit})

        @mcp.tool()
        def assistant_get_draft_summary() -> dict[str, Any]:
            """Bounded aggregate over persisted answer drafts (read-only counts by type/status)."""
            return _assistant_result("assistant_get_draft_summary", {})

    # N8C-16 read-only LIVE workflow consumption. Reads only; enabled by default. These tools expose the
    # N8C-15 deterministic workflow ROUTER to MCP clients: they retrieve bounded workflow routing/context
    # artifacts over EXISTING N8C read surfaces. They do NOT generate final answers and do NOT execute
    # actions — no build, apply, persist, send, schedule, remind, scan, reindex, or live source read is
    # reachable. Served from the same read-only DB snapshot via the broker.
    if assistant_workflows_enabled():

        @mcp.tool()
        def assistant_list_workflows() -> dict[str, Any]:
            """List the workflow catalog (read-only): canonical workflow types, routing targets, and
            deferred-capability markers. Retrieves routing metadata only — it does not generate a final
            answer and does not execute an action."""
            return _assistant_result("assistant_list_workflows", {})

        @mcp.tool()
        def assistant_route_workflow(
            workflow_type: str | None = None, query: str | None = None, objective: str | None = None,
            domain: str | None = None, project_key: str | None = None, source_root_key: str | None = None,
            draft_id: str | None = None, packet_id: str | None = None, projection_id: str | None = None,
            context_pack_id: str | None = None, review_item_id: str | None = None,
            memory_node_id: str | None = None, decision_id: str | None = None,
            preference_id: str | None = None, open_loop_id: str | None = None,
        ) -> dict[str, Any]:
            """Route a bounded workflow request via the N8C-15 router and return the normalized routing
            envelope (read-only). This is selection/routing metadata over EXISTING N8C artifacts only — it
            does not generate a final answer, build/apply/persist anything, execute an action, or read a live
            source file. All inputs are clamped."""
            return _assistant_result("assistant_route_workflow", {
                "workflow_type": workflow_type, "query": query, "objective": objective, "domain": domain,
                "project_key": project_key, "source_root_key": source_root_key, "draft_id": draft_id,
                "packet_id": packet_id, "projection_id": projection_id, "context_pack_id": context_pack_id,
                "review_item_id": review_item_id, "memory_node_id": memory_node_id,
                "decision_id": decision_id, "preference_id": preference_id, "open_loop_id": open_loop_id})

        @mcp.tool()
        def assistant_get_workflow_context(
            workflow_type: str | None = None, query: str | None = None, objective: str | None = None,
            domain: str | None = None, project_key: str | None = None, source_root_key: str | None = None,
            draft_id: str | None = None, packet_id: str | None = None, projection_id: str | None = None,
            context_pack_id: str | None = None, review_item_id: str | None = None,
            memory_node_id: str | None = None, decision_id: str | None = None,
            preference_id: str | None = None, open_loop_id: str | None = None,
        ) -> dict[str, Any]:
            """Return bounded workflow CONTEXT for a request (read-only): selected artifact references,
            citations, source refs, review labels, open questions, and policy. Whitelisted metadata only —
            no full upstream payloads, raw prompts, raw bodies, or live source reads. It does not generate a
            final answer and does not execute an action."""
            return _assistant_result("assistant_get_workflow_context", {
                "workflow_type": workflow_type, "query": query, "objective": objective, "domain": domain,
                "project_key": project_key, "source_root_key": source_root_key, "draft_id": draft_id,
                "packet_id": packet_id, "projection_id": projection_id, "context_pack_id": context_pack_id,
                "review_item_id": review_item_id, "memory_node_id": memory_node_id,
                "decision_id": decision_id, "preference_id": preference_id, "open_loop_id": open_loop_id})

        @mcp.tool()
        def assistant_get_workflow_artifacts(
            workflow_type: str | None = None, query: str | None = None, objective: str | None = None,
            domain: str | None = None, project_key: str | None = None, source_root_key: str | None = None,
            draft_id: str | None = None, packet_id: str | None = None, projection_id: str | None = None,
            context_pack_id: str | None = None, review_item_id: str | None = None,
            memory_node_id: str | None = None, decision_id: str | None = None,
            preference_id: str | None = None, open_loop_id: str | None = None,
        ) -> dict[str, Any]:
            """Return the selected artifact REFERENCES from a workflow routing result (read-only): ids,
            kinds, statuses, bounded title/summary, citation ids, source refs, review labels, counts, and
            warnings. Never full packet/draft/context-pack exports or raw payloads. It does not generate a
            final answer and does not execute an action."""
            return _assistant_result("assistant_get_workflow_artifacts", {
                "workflow_type": workflow_type, "query": query, "objective": objective, "domain": domain,
                "project_key": project_key, "source_root_key": source_root_key, "draft_id": draft_id,
                "packet_id": packet_id, "projection_id": projection_id, "context_pack_id": context_pack_id,
                "review_item_id": review_item_id, "memory_node_id": memory_node_id,
                "decision_id": decision_id, "preference_id": preference_id, "open_loop_id": open_loop_id})

        @mcp.tool()
        def assistant_get_workflow_policy(
            workflow_type: str | None = None, query: str | None = None, objective: str | None = None,
            domain: str | None = None, project_key: str | None = None, source_root_key: str | None = None,
            draft_id: str | None = None, packet_id: str | None = None, projection_id: str | None = None,
            context_pack_id: str | None = None, review_item_id: str | None = None,
            memory_node_id: str | None = None, decision_id: str | None = None,
            preference_id: str | None = None, open_loop_id: str | None = None,
        ) -> dict[str, Any]:
            """Return the fixed no-execution POLICY envelope for a workflow request (read-only):
            action_policy=no_execution, execution_policy=route_only, review/citation/source policies. It does
            not generate a final answer and does not execute an action."""
            return _assistant_result("assistant_get_workflow_policy", {
                "workflow_type": workflow_type, "query": query, "objective": objective, "domain": domain,
                "project_key": project_key, "source_root_key": source_root_key, "draft_id": draft_id,
                "packet_id": packet_id, "projection_id": projection_id, "context_pack_id": context_pack_id,
                "review_item_id": review_item_id, "memory_node_id": memory_node_id,
                "decision_id": decision_id, "preference_id": preference_id, "open_loop_id": open_loop_id})

        @mcp.tool()
        def assistant_get_workflow_summary(
            workflow_type: str | None = None, query: str | None = None, objective: str | None = None,
            domain: str | None = None, project_key: str | None = None, source_root_key: str | None = None,
            draft_id: str | None = None, packet_id: str | None = None, projection_id: str | None = None,
            context_pack_id: str | None = None, review_item_id: str | None = None,
            memory_node_id: str | None = None, decision_id: str | None = None,
            preference_id: str | None = None, open_loop_id: str | None = None,
        ) -> dict[str, Any]:
            """Return a bounded, NON-FINAL summary of the route decision (read-only): workflow_type, status,
            routing_decision, selected-artifact counts, deferred capabilities, warnings, and policy. Not a
            final or operator-approved answer, not action guidance — route/context metadata only."""
            return _assistant_result("assistant_get_workflow_summary", {
                "workflow_type": workflow_type, "query": query, "objective": objective, "domain": domain,
                "project_key": project_key, "source_root_key": source_root_key, "draft_id": draft_id,
                "packet_id": packet_id, "projection_id": projection_id, "context_pack_id": context_pack_id,
                "review_item_id": review_item_id, "memory_node_id": memory_node_id,
                "decision_id": decision_id, "preference_id": preference_id, "open_loop_id": open_loop_id})

    # N8C-18 read-only feedback / review-loop inspection. Reads only; enabled by default. These tools
    # retrieve bounded operator feedback records + ADVISORY, operator-review-required review-loop
    # recommendations. They NEVER write, change a review disposition, mutate any upstream record, stage an
    # action, or execute anything — the `feedback add --apply` writer is CLI-only. Served from the same
    # read-only DB snapshot via the broker.
    if assistant_feedback_enabled():

        @mcp.tool()
        def assistant_list_feedback(feedback_type: str | None = None, status: str | None = None,
                                    workflow_id: str | None = None, limit: int = 25) -> dict[str, Any]:
            """List persisted operator FEEDBACK records (read-only). Feedback is advisory input to the review
            loop for operator review only; it does not execute actions or change any review state."""
            return _assistant_result("assistant_list_feedback",
                                     {"feedback_type": feedback_type, "status": status,
                                      "workflow_id": workflow_id, "limit": limit})

        @mcp.tool()
        def assistant_get_feedback(feedback_id: str) -> dict[str, Any]:
            """Get one FEEDBACK record header (read-only). Advisory input only — never a review disposition."""
            return _assistant_result("assistant_get_feedback", {"feedback_id": feedback_id})

        @mcp.tool()
        def assistant_get_feedback_targets(feedback_id: str, limit: int = 100) -> dict[str, Any]:
            """List a feedback record's bounded targets + preserved provenance (read-only). Metadata only —
            no raw bodies, no live source read."""
            return _assistant_result("assistant_get_feedback_targets",
                                     {"feedback_id": feedback_id, "limit": limit})

        @mcp.tool()
        def assistant_get_feedback_recommendations(feedback_id: str | None = None,
                                                   recommendation_type: str | None = None,
                                                   limit: int = 25) -> dict[str, Any]:
            """List ADVISORY review-loop recommendations (read-only). Each is a SUGGESTION for operator
            review only — never an applied relabel, accept, reject, defer, or dispose."""
            return _assistant_result("assistant_get_feedback_recommendations",
                                     {"feedback_id": feedback_id,
                                      "recommendation_type": recommendation_type, "limit": limit})

        @mcp.tool()
        def assistant_get_feedback_summary() -> dict[str, Any]:
            """Bounded aggregate over persisted feedback (read-only counts by type/status)."""
            return _assistant_result("assistant_get_feedback_summary", {})

        @mcp.tool()
        def assistant_get_feedback_export(feedback_id: str, limit: int = 200) -> dict[str, Any]:
            """Bounded JSON export of a persisted FEEDBACK record (read-only; header + targets +
            recommendations). Advisory review-loop input only — no state change, no action."""
            return _assistant_result("assistant_get_feedback_export",
                                     {"feedback_id": feedback_id, "limit": limit})

    # N8C-19 read-only action-stage inspection — default-ON; independent kill switch
    # HB_MCP_ASSISTANT_ACTION_STAGES. Staging is NOT execution: every item is a candidate/blocked follow-up
    # pinned to not_executed / external_system=none / requires_operator_review=1. There is NO write/build/
    # apply/execute tool here (the `action-stage build --apply` writer is CLI-only).
    if assistant_action_stages_enabled():

        @mcp.tool()
        def assistant_list_action_stages(stage_type: str | None = None, status: str | None = None,
                                         workflow_type: str | None = None, limit: int = 25) -> dict[str, Any]:
            """List persisted ACTION STAGES (read-only). A stage bundles proposed follow-up CANDIDATES for
            operator review only — it executes nothing and changes no review state."""
            return _assistant_result("assistant_list_action_stages",
                                     {"stage_type": stage_type, "status": status,
                                      "workflow_type": workflow_type, "limit": limit})

        @mcp.tool()
        def assistant_get_action_stage(stage_id: str) -> dict[str, Any]:
            """Get one ACTION STAGE header (read-only). Staged candidates only — never executed."""
            return _assistant_result("assistant_get_action_stage", {"stage_id": stage_id})

        @mcp.tool()
        def assistant_get_action_stage_items(stage_id: str, staged_state: str | None = None,
                                             limit: int = 100) -> dict[str, Any]:
            """List a stage's proposed follow-up items (read-only). Every item is pinned to not_executed /
            external_system=none / requires_operator_review=1; staged_state is candidate or blocked only."""
            return _assistant_result("assistant_get_action_stage_items",
                                     {"stage_id": stage_id, "staged_state": staged_state, "limit": limit})

        @mcp.tool()
        def assistant_get_action_stage_citations(stage_id: str, limit: int = 100) -> dict[str, Any]:
            """List a stage's provenance citations (read-only). Bounded ids/metadata only — no raw bodies,
            no live source read."""
            return _assistant_result("assistant_get_action_stage_citations",
                                     {"stage_id": stage_id, "limit": limit})

        @mcp.tool()
        def assistant_get_action_stage_summary() -> dict[str, Any]:
            """Bounded aggregate over persisted stages (read-only counts by type/status)."""
            return _assistant_result("assistant_get_action_stage_summary", {})

        @mcp.tool()
        def assistant_get_action_stage_export(stage_id: str, limit: int = 200) -> dict[str, Any]:
            """Bounded JSON export of a persisted ACTION STAGE (read-only; header + items + citations). Staged
            follow-up candidates only — no execution field, no external ref, no state change."""
            return _assistant_result("assistant_get_action_stage_export",
                                     {"stage_id": stage_id, "limit": limit})

    # N8C-20 read-only quality/evaluation inspection — registered only when the quality gate is on
    # (default-ON). Advisory findings over existing N8C records; no build/apply/evaluate/repair tool here.
    if assistant_quality_enabled():

        @mcp.tool()
        def assistant_list_quality(target_kind: str | None = None, target_id: str | None = None,
                                   status: str | None = None, limit: int = 25) -> dict[str, Any]:
            """List persisted QUALITY RUNS (read-only). A quality run is an ADVISORY evaluation of one existing
            N8C record — it repairs nothing, executes nothing, and changes no review disposition."""
            return _assistant_result("assistant_list_quality",
                                     {"target_kind": target_kind, "target_id": target_id,
                                      "status": status, "limit": limit})

        @mcp.tool()
        def assistant_get_quality(quality_run_id: str) -> dict[str, Any]:
            """Get one QUALITY RUN header (read-only). Advisory evaluation only; ``evaluated`` is a run-record
            lifecycle status and implies no repair, acceptance, rejection, or application."""
            return _assistant_result("assistant_get_quality", {"quality_run_id": quality_run_id})

        @mcp.tool()
        def assistant_get_quality_findings(quality_run_id: str, finding_type: str | None = None,
                                           severity: str | None = None, limit: int = 200) -> dict[str, Any]:
            """List a quality run's ADVISORY findings (read-only). Each finding may recommend operator review
            but never sets or mutates a review disposition; every finding is evaluate_only /
            requires_operator_review=1."""
            return _assistant_result("assistant_get_quality_findings",
                                     {"quality_run_id": quality_run_id, "finding_type": finding_type,
                                      "severity": severity, "limit": limit})

        @mcp.tool()
        def assistant_get_quality_targets(quality_run_id: str, limit: int = 200) -> dict[str, Any]:
            """List the evaluated target(s) for a quality run (read-only). Bounded ids/state only — no raw
            bodies, no live source read, no upstream mutation."""
            return _assistant_result("assistant_get_quality_targets",
                                     {"quality_run_id": quality_run_id, "limit": limit})

        @mcp.tool()
        def assistant_get_quality_summary() -> dict[str, Any]:
            """Bounded aggregate over quality runs (read-only counts by target kind / status / finding type /
            severity)."""
            return _assistant_result("assistant_get_quality_summary", {})

        @mcp.tool()
        def assistant_get_quality_export(quality_run_id: str, limit: int = 200) -> dict[str, Any]:
            """Bounded JSON export of a persisted QUALITY RUN (read-only; header + advisory findings +
            evaluated targets). No raw bodies, no repair/execution field, no state change."""
            return _assistant_result("assistant_get_quality_export",
                                     {"quality_run_id": quality_run_id, "limit": limit})

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

    # N8C-22 client-exposure bridge: fallback catalog / help / gateway helper tools. Always registered
    # (read-only meta). They let clients that cannot ingest the full 78-tool manifest still discover and
    # reach the canonical assistant surface through a small, allowlisted entry point. They add NO new
    # capability: the gateway only routes to the canonical 78 via the same audited broker.dispatch path.
    @mcp.tool()
    def hb_assistant_catalog(group: str | None = None) -> dict[str, Any]:
        """Catalog of the read-only N8C assistant tool suite for connected clients. Lists the assistant groups
        and their canonical tools with purpose, required/optional args, result limits, and safety class,
        so a client can pick a tool then call it directly or via ``hb_assistant_tool_query``. Optionally
        filter to one ``group`` (nav, context_packs, memory, decision_memory, review, intelligence,
        research_packets, source_connector, answer_drafts, workflows, feedback, action_stages, quality).
        Read-only; returns no secrets, raw payloads, credentials, or absolute paths."""
        if group is not None and group not in ASSISTANT_TOOL_GROUPS:
            raise ValueError(f"unknown_assistant_group:{group}")
        index = _extract_client_tool_index(mcp)
        scope = {group: ASSISTANT_TOOL_GROUPS[group]} if group else dict(ASSISTANT_TOOL_GROUPS)
        return {
            "groups": [
                {"group": label, "tool_count": len(tools), "tools": list(tools)}
                for label, tools in scope.items()
            ],
            "tools": [_assistant_tool_meta(name, index) for tools in scope.values() for name in tools],
            "canonical_assistant_tool_count": len(ALL_ASSISTANT_TOOLS),
            "client_bridge_helper_tools": list(CLIENT_BRIDGE_HELPER_TOOLS),
            # Non-canonical gateway-reachable write surfaces (operator-authorized N8C-24 expansion). Kept in
            # SEPARATE sections so `tools` stays the canonical read-only 78; every one still passes the full
            # broker write-gate chain when invoked.
            "structured_intelligence_tools": [t for t in GATEWAY_ALLOWLIST
                                              if t.startswith(("pa_artifact_", "pa_session_",
                                                               "pa_canonical_", "pa_tool_manifest_",
                                                               "pa_vault_"))],
            "client_output_tools": list(ALL_PA_OUTPUT_TOOLS),
            "ai_output_tools": ["ai_outputs_card_upsert"],
            "prompt_routing_tools": [t for t in GATEWAY_ALLOWLIST if t.startswith("pa_prompt_")
                                     or t in ("pa_tool_family_get", "pa_workflow_recipe_get",
                                              "pa_tool_surface_freshness_check")],
            "gateway_allowlist_count": len(GATEWAY_ALLOWLIST),
            "exposure": assistant_client_exposure_status(),
            "safety": (
                "The `tools` list is the canonical read-only 78. The gateway also reaches the "
                "structured-intelligence, client-output, and AI-output WRITE surfaces (operator-authorized); "
                "every write still passes the full broker gate chain (safe-mode, per-tool gate, server-minted "
                "approval, idempotency, path safety). Denied/raw-SQL/shell/exec/root-db/legacy hb_output_* "
                "tools remain rejected."
            ),
        }

    @mcp.tool()
    def hb_assistant_tool_help(tool_name: str) -> dict[str, Any]:
        """Schema + usage guidance for ONE approved read-only N8C assistant tool (must be one of the
        canonical 78). Rejects unknown, denied, and non-assistant tool names. Use before calling a tool
        directly or via ``hb_assistant_tool_query``."""
        if tool_name in DENIED_TOOL_NAMES:
            return _gateway_failure(
                "hb_assistant_tool_help",
                f"denied_tool:{tool_name}",
                subject_tool=tool_name,
            )
        if tool_name not in GATEWAY_ALLOWLIST:
            return _gateway_failure(
                "hb_assistant_tool_help",
                f"unknown_or_non_assistant_tool:{tool_name}",
                subject_tool=tool_name,
            )
        index = _extract_client_tool_index(mcp)
        meta = _assistant_tool_meta(tool_name, index)
        entry = index.get(tool_name) or {}
        meta["input_schema"] = entry.get("input_schema") or {}
        meta["usage"] = (entry.get("description") or "").strip()
        meta["gateway"] = "hb_assistant_tool_query"
        if meta.get("examples"):
            meta["example_prompts"] = meta["examples"]
        return meta

    @mcp.tool()
    def hb_assistant_tool_query(tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Allowlisted gateway: call ONE tool by name for clients that cannot ingest the full manifest. The
        allowlist is the canonical 78 read-only assistant tools PLUS the operator-authorized structured-
        intelligence, client-output, and AI-output surfaces (GATEWAY_ALLOWLIST). Every gateway-routed WRITE
        still passes the full broker gate chain (safe-mode, per-tool write gate, server-minted approval,
        idempotency, path safety). It rejects denied names, raw SQL/shell/exec, root/db and legacy hb_output_*
        tools, non-allowlisted names, and unbounded limits. It is NOT a generic RPC escape hatch. On success
        it returns the same audited, bounded broker receipt (``ok``/``result``/``request_id``) the direct
        wrappers use; the same profile gates, per-group kill switches, and audit logging apply."""
        if not isinstance(tool_name, str) or not tool_name:
            return _gateway_failure("hb_assistant_tool_query", "tool_name_required")
        if tool_name in DENIED_TOOL_NAMES:
            return _gateway_failure(
                "hb_assistant_tool_query",
                f"denied_tool:{tool_name}",
                subject_tool=tool_name,
            )
        if tool_name not in GATEWAY_ALLOWLIST:
            return _gateway_failure(
                "hb_assistant_tool_query",
                f"not_an_allowlisted_assistant_tool:{tool_name}",
                subject_tool=tool_name,
            )
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return _gateway_failure(
                "hb_assistant_tool_query",
                "arguments_must_be_object",
                subject_tool=tool_name,
            )
        if arg_err := _gateway_arg_validation_error(arguments):
            return _gateway_failure(
                "hb_assistant_tool_query",
                arg_err,
                subject_tool=tool_name,
            )
        return broker.dispatch(tool_name, arguments)

    # N8C-23 Structured Intelligence Artifact Workspace tools. Read/advisory + staged-write (never the vault);
    # pa_artifact_promotion_apply is the single canonical write, guarded by server-minted approval +
    # validation + idempotency inside the broker/handler. Gated by artifact_workspace_enabled().
    if artifact_workspace_enabled():

        @mcp.tool()
        def pa_session_capture_stage(source_client: str, session_title: str, capture_trigger: str,
                                     session_summary: str, selected_excerpts: list[str] | None = None,
                                     source_client_session_ref: str | None = None,
                                     operator_id: str | None = None,
                                     redaction_state: str = "redacted") -> dict[str, Any]:
            """Stage a BOUNDED session capture (summary + selected excerpts; NO raw transcript). First step of
            'document this session'. Returns a session_id used to stage artifact proposals."""
            return _assistant_result("pa_session_capture_stage", {
                "source_client": source_client, "session_title": session_title,
                "capture_trigger": capture_trigger, "session_summary": session_summary,
                "selected_excerpts": selected_excerpts or [], "source_client_session_ref": source_client_session_ref,
                "operator_id": operator_id, "redaction_state": redaction_state})

        @mcp.tool()
        def pa_session_capture_get(session_id: str) -> dict[str, Any]:
            """Retrieve a staged session capture by session_id."""
            return _assistant_result("pa_session_capture_get", {"session_id": session_id})

        @mcp.tool()
        def pa_artifact_proposal_stage(session_id: str,
                                       candidate_artifacts: list[dict[str, Any]]) -> dict[str, Any]:
            """Stage a proposal bundle of candidate artifacts (decision/preference/open_loop/workflow/…) from a
            session. Returns the bundle id, proposal ids, and a human + machine review packet. Nothing is
            canonical yet."""
            return _assistant_result("pa_artifact_proposal_stage",
                                     {"session_id": session_id, "candidate_artifacts": candidate_artifacts})

        @mcp.tool()
        def pa_artifact_proposal_list(proposal_bundle_id: str | None = None, review_status: str | None = None,
                                      limit: int = 50) -> dict[str, Any]:
            """List staged artifact proposals (optionally by bundle / review_status)."""
            return _assistant_result("pa_artifact_proposal_list", {
                "proposal_bundle_id": proposal_bundle_id, "review_status": review_status, "limit": limit})

        @mcp.tool()
        def pa_artifact_proposal_get(proposal_id: str) -> dict[str, Any]:
            """Retrieve one artifact proposal."""
            return _assistant_result("pa_artifact_proposal_get", {"proposal_id": proposal_id})

        @mcp.tool()
        def pa_artifact_proposal_revise(proposal_id: str, body_markdown: str | None = None,
                                        structured_payload: dict[str, Any] | None = None,
                                        operator_instruction: str | None = None,
                                        revision_summary: str | None = None,
                                        created_by_client: str | None = None) -> dict[str, Any]:
            """Revise a proposal, creating a NEW version (v1 is never overwritten)."""
            return _assistant_result("pa_artifact_proposal_revise", {
                "proposal_id": proposal_id, "body_markdown": body_markdown,
                "structured_payload": structured_payload, "operator_instruction": operator_instruction,
                "revision_summary": revision_summary, "created_by_client": created_by_client})

        @mcp.tool()
        def pa_artifact_proposal_review(proposal_id: str, decision: str, operator_id: str | None = None,
                                        review_notes: str | None = None) -> dict[str, Any]:
            """Record an operator review decision (approve/reject/request_revision/merge/split/
            session_note_only/defer). 'approve' mints a SERVER-side approval id bound to the proposal."""
            return _assistant_result("pa_artifact_proposal_review", {
                "proposal_id": proposal_id, "decision": decision, "operator_id": operator_id,
                "review_notes": review_notes})

        @mcp.tool()
        def pa_artifact_proposal_compare(proposal_ids: list[str]) -> dict[str, Any]:
            """Compare a small set of proposals (bounded metadata)."""
            return _assistant_result("pa_artifact_proposal_compare", {"proposal_ids": proposal_ids})

        @mcp.tool()
        def pa_artifact_proposal_plan_promotion(proposal_bundle_id: str) -> dict[str, Any]:
            """Advisory promotion plan for the APPROVED proposals: proposed canonical ids, destination vault
            paths, tags, backlinks, duplicate warnings. Writes nothing."""
            return _assistant_result("pa_artifact_proposal_plan_promotion",
                                     {"proposal_bundle_id": proposal_bundle_id})

        @mcp.tool()
        def pa_artifact_promotion_validate(proposal_bundle_id: str,
                                           operator_id: str | None = None) -> dict[str, Any]:
            """Validate the plan and persist a validation receipt binding the exact canonical ids/paths/tags/
            hashes. Returns promotion_bundle_id + server-minted operator_approval_id + idempotency_key needed to
            apply. Writes no vault content."""
            return _assistant_result("pa_artifact_promotion_validate",
                                     {"proposal_bundle_id": proposal_bundle_id, "operator_id": operator_id})

        @mcp.tool()
        def pa_artifact_promotion_apply(promotion_bundle_id: str, operator_approval_id: str,
                                        idempotency_key: str | None = None,
                                        operator_id: str | None = None) -> dict[str, Any]:
            """Promote approved proposals to canonical records AND materialize Obsidian cards (the one canonical
            write). Requires the server-minted operator_approval_id + a passed validation whose hash still
            matches. Idempotent: a retry returns the existing receipt."""
            return _assistant_result("pa_artifact_promotion_apply", {
                "promotion_bundle_id": promotion_bundle_id, "operator_approval_id": operator_approval_id,
                "idempotency_key": idempotency_key, "operator_id": operator_id})

        @mcp.tool()
        def pa_artifact_promotion_receipt_get(promotion_receipt_id: str) -> dict[str, Any]:
            """Retrieve a promotion receipt."""
            return _assistant_result("pa_artifact_promotion_receipt_get",
                                     {"promotion_receipt_id": promotion_receipt_id})

        @mcp.tool()
        def pa_artifact_manifest_get(artifact_type: str | None = None, limit: int = 50) -> dict[str, Any]:
            """List canonical artifacts (the canonical artifact manifest view)."""
            return _assistant_result("pa_artifact_manifest_get",
                                     {"artifact_type": artifact_type, "limit": limit})

        @mcp.tool()
        def pa_vault_path_resolve(artifact_type: str, title: str, domain: str | None = None,
                                  canonical_id: str | None = None,
                                  operator_override_path: str | None = None) -> dict[str, Any]:
            """Resolve the destination vault path an artifact WOULD use (existing folders only; refuses new
            top-level folders / traversal). Read-only preview."""
            return _assistant_result("pa_vault_path_resolve", {
                "artifact_type": artifact_type, "title": title, "domain": domain,
                "canonical_id": canonical_id, "operator_override_path": operator_override_path})

        @mcp.tool()
        def pa_canonical_artifact_list(artifact_type: str | None = None, limit: int = 50) -> dict[str, Any]:
            """List promoted canonical artifacts for future retrieval."""
            return _assistant_result("pa_canonical_artifact_list",
                                     {"artifact_type": artifact_type, "limit": limit})

        @mcp.tool()
        def pa_canonical_artifact_get(canonical_id: str) -> dict[str, Any]:
            """Retrieve one canonical artifact by canonical_id."""
            return _assistant_result("pa_canonical_artifact_get", {"canonical_id": canonical_id})

    # Template-based structured-intelligence artifact author. The sanctioned client artifact-creation path:
    # instantiates a vault-resident template into the resolved taxonomy folder as a markdown file — NO DB
    # records (works on the read-only-DB profile, unlike the staged pipeline). Own gate; canonical write.
    if artifact_author_enabled():

        @mcp.tool()
        def pa_artifact_author(artifact_type: str, title: str, domain: str | None = None,
                               variables: dict[str, Any] | None = None,
                               sections: dict[str, str] | None = None,
                               source_client: str = "unknown",
                               operator_override_path: str | None = None) -> dict[str, Any]:
            """Create a structured-intelligence artifact as a TEMPLATE-BASED vault markdown file (no DB rows).
            Instantiates the vault template for ``artifact_type`` (decision / person_note / company_note /
            project_context / source_card_annotation) into the resolved taxonomy folder, filling ``{{title}}``
            + optional ``variables`` and scaffold ``sections`` (heading -> content). Canonical frontmatter is
            injected; content is redacted + size-capped. Fails closed for unmapped types. Returns the
            relative_path + sha256. This is the sanctioned client artifact-creation path."""
            return _assistant_result("pa_artifact_author", {
                "artifact_type": artifact_type, "title": title, "domain": domain,
                "variables": variables or {}, "sections": sections or {},
                "source_client": source_client, "operator_override_path": operator_override_path})

    # N8C-23 Client Tool Operating Manifest tools. Read/advisory + a staged refresh; refresh_promote is the
    # only manifest write and requires a server-minted approval + no-drift checksum. Gated separately.
    if client_tool_manifest_enabled():

        @mcp.tool()
        def pa_tool_manifest_get() -> dict[str, Any]:
            """The Client Tool Operating Manifest: which tool to use, when, sequences, safety classes, and
            freshness. Use this to route your tool choices."""
            return _assistant_result("pa_tool_manifest_get", {})

        @mcp.tool()
        def pa_tool_manifest_tool_help(tool_name: str) -> dict[str, Any]:
            """Manifest guidance for one tool (class, safety, read/write, replacement tools)."""
            return _assistant_result("pa_tool_manifest_tool_help", {"tool_name": tool_name})

        @mcp.tool()
        def pa_tool_manifest_workflow_get(workflow_name: str | None = None) -> dict[str, Any]:
            """Workflow route recipes (trigger phrases, tool sequence, approval points)."""
            return _assistant_result("pa_tool_manifest_workflow_get", {"workflow_name": workflow_name})

        @mcp.tool()
        def pa_tool_manifest_freshness_check() -> dict[str, Any]:
            """Compare the live tool surface to the recorded manifest (missing/extra tools, staleness)."""
            return _assistant_result("pa_tool_manifest_freshness_check", {})

        @mcp.tool()
        def pa_tool_manifest_review_plan() -> dict[str, Any]:
            """Advisory review plan for the tool manifest (whether a refresh is due). Writes nothing."""
            return _assistant_result("pa_tool_manifest_review_plan", {})

        @mcp.tool()
        def pa_tool_manifest_refresh_stage() -> dict[str, Any]:
            """Stage a manifest refresh (a diff + server-minted approval id). Does NOT write the manifest."""
            return _assistant_result("pa_tool_manifest_refresh_stage", {})

        @mcp.tool()
        def pa_tool_manifest_refresh_promote(refresh_proposal_id: str,
                                             operator_approval_id: str) -> dict[str, Any]:
            """Materialize a staged manifest refresh to 99 System/Manifests (md+json). Requires the server-minted
            operator_approval_id and a no-drift checksum. Never a silent rewrite."""
            return _assistant_result("pa_tool_manifest_refresh_promote", {
                "refresh_proposal_id": refresh_proposal_id, "operator_approval_id": operator_approval_id})

    # N8C-24 Connected Client Generated File Output Workspace. Bounded reads are always registered; the three
    # controlled writes (stage/commit/archive_commit) register only when client_output_write_enabled(). All
    # write to the `outputs` root only, behind server-minted approval + idempotency; never the vault/canonical.
    @mcp.tool()
    def pa_output_list(status: str | None = None, file_type: str | None = None,
                       source_session_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        """List generated outputs (bounded, metadata only) by status/file_type/session."""
        return _assistant_result("pa_output_list", {"status": status, "file_type": file_type,
                                                    "source_session_id": source_session_id, "limit": limit})

    @mcp.tool()
    def pa_output_metadata(output_id: str) -> dict[str, Any]:
        """Metadata for one generated output (no raw body)."""
        return _assistant_result("pa_output_metadata", {"output_id": output_id})

    @mcp.tool()
    def pa_output_read_excerpt(output_id: str, max_chars: int = 4000) -> dict[str, Any]:
        """Bounded excerpt of a text-like generated output. Office/PDF are metadata-only; ZIP lists members."""
        return _assistant_result("pa_output_read_excerpt", {"output_id": output_id, "max_chars": max_chars})

    @mcp.tool()
    def pa_output_zip_inspect(output_id: str) -> dict[str, Any]:
        """List the members of a generated ZIP output (bounded). Never extracts."""
        return _assistant_result("pa_output_zip_inspect", {"output_id": output_id})

    @mcp.tool()
    def pa_output_receipt_get(receipt_id: str) -> dict[str, Any]:
        """Retrieve the receipt for a generated output."""
        return _assistant_result("pa_output_receipt_get", {"receipt_id": receipt_id})

    @mcp.tool()
    def pa_output_manifest_get() -> dict[str, Any]:
        """Retrieve the generated-output manifest (bounded entry list)."""
        return _assistant_result("pa_output_manifest_get", {})

    @mcp.tool()
    def pa_output_archive_plan(output_id: str) -> dict[str, Any]:
        """Advisory plan to move a committed output to 90 Archive. Writes nothing; never deletes."""
        return _assistant_result("pa_output_archive_plan", {"output_id": output_id})

    if client_output_write_enabled():

        @mcp.tool()
        def pa_output_stage(title: str, file_type: str, content_mode: str = "text",
                            content_text: str | None = None, content_base64: str | None = None,
                            source_client: str | None = None, source_session_id: str | None = None,
                            related_canonical_ids: list[str] | None = None,
                            related_proposal_ids: list[str] | None = None,
                            destination_state: str = "pending", operator_id: str | None = None) -> dict[str, Any]:
            """Stage a generated output file (renders + validates bytes; does NOT write the final file).
            Returns output_id + a server-minted operator_approval_id + idempotency_key needed to commit."""
            return _assistant_result("pa_output_stage", {
                "title": title, "file_type": file_type, "content_mode": content_mode,
                "content_text": content_text, "content_base64": content_base64,
                "source_client": source_client, "source_session_id": source_session_id,
                "related_canonical_ids": related_canonical_ids, "related_proposal_ids": related_proposal_ids,
                "destination_state": destination_state, "operator_id": operator_id})

        @mcp.tool()
        def pa_output_commit(output_id: str, operator_approval_id: str,
                             idempotency_key: str | None = None, operator_id: str | None = None) -> dict[str, Any]:
            """Write a staged output to the outputs workspace. Requires the server-minted operator_approval_id;
            recomputes the staged content hash and fails closed on drift. Idempotent on the server key."""
            return _assistant_result("pa_output_commit", {
                "output_id": output_id, "operator_approval_id": operator_approval_id,
                "idempotency_key": idempotency_key, "operator_id": operator_id})

        @mcp.tool()
        def pa_output_archive_commit(output_id: str, operator_approval_id: str) -> dict[str, Any]:
            """Move a committed output to 90 Archive + write an archive receipt. Requires the server-minted
            operator_approval_id. Never deletes."""
            return _assistant_result("pa_output_archive_commit", {
                "output_id": output_id, "operator_approval_id": operator_approval_id})


    # assistant_output_* aliases — same handlers as pa_output_* (client-facing naming).
    @mcp.tool()
    def assistant_output_list(status: str | None = None, file_type: str | None = None,
                              source_session_id: str | None = None, limit: int = 50) -> dict[str, Any]:
        """Alias of pa_output_list."""
        return _assistant_result("assistant_output_list", {"status": status, "file_type": file_type,
                                                           "source_session_id": source_session_id, "limit": limit})

    @mcp.tool()
    def assistant_output_metadata(output_id: str) -> dict[str, Any]:
        """Alias of pa_output_metadata."""
        return _assistant_result("assistant_output_metadata", {"output_id": output_id})

    @mcp.tool()
    def assistant_output_read_excerpt(output_id: str, max_chars: int = 4000) -> dict[str, Any]:
        """Alias of pa_output_read_excerpt."""
        return _assistant_result("assistant_output_read_excerpt", {"output_id": output_id, "max_chars": max_chars})

    @mcp.tool()
    def assistant_output_zip_inspect(output_id: str) -> dict[str, Any]:
        """Alias of pa_output_zip_inspect."""
        return _assistant_result("assistant_output_zip_inspect", {"output_id": output_id})

    @mcp.tool()
    def assistant_output_receipt_get(receipt_id: str) -> dict[str, Any]:
        """Alias of pa_output_receipt_get."""
        return _assistant_result("assistant_output_receipt_get", {"receipt_id": receipt_id})

    @mcp.tool()
    def assistant_output_manifest_get() -> dict[str, Any]:
        """Alias of pa_output_manifest_get."""
        return _assistant_result("assistant_output_manifest_get", {})

    @mcp.tool()
    def assistant_output_archive_plan(output_id: str) -> dict[str, Any]:
        """Alias of pa_output_archive_plan."""
        return _assistant_result("assistant_output_archive_plan", {"output_id": output_id})

    if client_output_write_enabled():
        @mcp.tool()
        def assistant_output_stage(title: str, file_type: str, content_mode: str = "text",
                                   content_text: str | None = None, content_base64: str | None = None,
                                   source_client: str | None = None, source_session_id: str | None = None,
                                   related_canonical_ids: list[str] | None = None,
                                   related_proposal_ids: list[str] | None = None,
                                   destination_state: str = "pending", operator_id: str | None = None) -> dict[str, Any]:
            """Alias of pa_output_stage."""
            return _assistant_result("assistant_output_stage", {
                "title": title, "file_type": file_type, "content_mode": content_mode,
                "content_text": content_text, "content_base64": content_base64,
                "source_client": source_client, "source_session_id": source_session_id,
                "related_canonical_ids": related_canonical_ids, "related_proposal_ids": related_proposal_ids,
                "destination_state": destination_state, "operator_id": operator_id})

        @mcp.tool()
        def assistant_output_commit(output_id: str, operator_approval_id: str,
                                    idempotency_key: str | None = None, operator_id: str | None = None) -> dict[str, Any]:
            """Alias of pa_output_commit."""
            return _assistant_result("assistant_output_commit", {
                "output_id": output_id, "operator_approval_id": operator_approval_id,
                "idempotency_key": idempotency_key, "operator_id": operator_id})

        @mcp.tool()
        def assistant_output_archive_commit(output_id: str, operator_approval_id: str) -> dict[str, Any]:
            """Alias of pa_output_archive_commit."""
            return _assistant_result("assistant_output_archive_commit", {
                "output_id": output_id, "operator_approval_id": operator_approval_id})

    # Prompt Preflight & Tool Routing. Five READ-ONLY routing tools that expose the deterministic route
    # engine + tool-surface freshness guard. They never write/stage/promote/read source content — they only
    # reason over the static routing manifests. Gateway-reachable via GATEWAY_ALLOWLIST.
    if prompt_preflight_enabled():

        @mcp.tool()
        def pa_prompt_route(prompt: str, has_exact_id: bool = False) -> dict[str, Any]:
            """Preflight a raw prompt into a read-only route plan: intent → source-of-truth → tool family →
            workflow recipe → specific tools → authorization → retrieval budget → memory opportunity →
            fallback. Recommends only; performs no write, no staging, no promotion, and reads no content."""
            return _assistant_result("pa_prompt_route", {"prompt": prompt, "has_exact_id": has_exact_id})

        @mcp.tool()
        def pa_prompt_route_explain(prompt: str, has_exact_id: bool = False) -> dict[str, Any]:
            """Same route plan as pa_prompt_route plus the full workflow + family records behind the
            decision (why this family/workflow/tools). Read-only."""
            return _assistant_result("pa_prompt_route_explain",
                                     {"prompt": prompt, "has_exact_id": has_exact_id})

        @mcp.tool()
        def pa_tool_family_get(family_id: str | None = None) -> dict[str, Any]:
            """Get one tool family record (use_when/do_not_use/read-write class/negative instructions) or,
            with no id, the full family taxonomy. Read-only."""
            return _assistant_result("pa_tool_family_get", {"family_id": family_id})

        @mcp.tool()
        def pa_workflow_recipe_get(workflow_id: str | None = None) -> dict[str, Any]:
            """Get one workflow recipe (tool sequence, authorization, retrieval budget, provenance,
            fallbacks) or, with no id, all recipes. Read-only."""
            return _assistant_result("pa_workflow_recipe_get", {"workflow_id": workflow_id})

        @mcp.tool()
        def pa_tool_surface_freshness_check() -> dict[str, Any]:
            """Check whether the live tool surface (tools, families, classes, gateway scope) still matches
            the routing manifest. Reads warn on drift; write/promotion/archive routes fail closed. Read-only."""
            return _assistant_result("pa_tool_surface_freshness_check", {})

    # Stamp read-only / destructive annotations on every registered tool (after all conditional
    # registration so the full surface is covered). Purely additive metadata for connected-client
    # safety layers; the broker gate chain remains the enforcing control.
    _stamp_tool_annotations(mcp)

    # Capture the live tool-schema index once, now that the full surface is registered, so the persisted
    # manifest (built in a handler context without `mcp`) can carry the same purpose/args/limits.
    freeze_registered_schema_index(mcp)

    # NAS internet-facing profile: idempotently materialize the persisted client-tool manifest so
    # pa_tool_manifest_get returns a real active manifest out of the box (get/freshness/status agree).
    # Server-side self-materialization of the deterministic tool catalog — gated to the read-only NAS
    # profile, non-fatal, and a no-op when a matching active manifest already exists.
    try:
        from .artifact_tools import bootstrap_persisted_manifest  # noqa: PLC0415

        bootstrap_persisted_manifest(broker._config)
    except Exception:  # noqa: BLE001 — bootstrap must never break tool registration/startup
        pass
