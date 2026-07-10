"""Join canonical tool specs to live MCP registration, groups, gates, and schemas.

Surface-level only — never computes request-level approval / token / path executability.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.obsidian_mcp.canonical_tool_specs import (
    KNOWN_TOOL_GROUPS,
    PROMPT_ROUTING_TOOL_SPECS,
    resolve_tool_spec,
    tool_spec_public_entry,
)
from hb_assistant.obsidian_mcp.tool_metadata_types import SurfaceToolState

# Prompt-routing tool names (mirror of PROMPT_ROUTING_TOOLS without importing prompt_routing_tools).
_PROMPT_ROUTING_NAMES: tuple[str, ...] = tuple(PROMPT_ROUTING_TOOL_SPECS.keys())


def _assistant_group_map() -> dict[str, str]:
    from .broker import ASSISTANT_TOOL_GROUPS  # noqa: PLC0415

    return {t: g for g, tools in ASSISTANT_TOOL_GROUPS.items() for t in tools}


def _profile_group_enabled(group: str | None) -> bool:
    if group is None:
        return True
    from . import profile as prof  # noqa: PLC0415

    gates = {
        "nav": prof.assistant_nav_enabled,
        "context_packs": prof.assistant_context_packs_enabled,
        "memory": prof.assistant_memory_enabled,
        "decision_memory": prof.assistant_decision_memory_enabled,
        "review": prof.assistant_review_enabled,
        "intelligence": prof.assistant_intelligence_enabled,
        "research_packets": prof.assistant_research_packets_enabled,
        "source_connector": prof.assistant_source_connector_enabled,
        "answer_drafts": prof.assistant_answer_drafts_enabled,
        "workflows": prof.assistant_workflows_enabled,
        "feedback": prof.assistant_feedback_enabled,
        "action_stages": prof.assistant_action_stages_enabled,
        "quality": prof.assistant_quality_enabled,
        "source_structure": prof.assistant_source_structure_enabled,
        "prompt_routing": prof.prompt_preflight_enabled,
    }
    fn = gates.get(group)
    if fn is None:
        return True
    return bool(fn())


def installed_tool_names(config: Any) -> set[str]:
    """All tools known to the client-facing universe for this config (surface installed set)."""
    # Import PA tool *name tuples* only (avoid cycle with artifact_tools.current_tool_names).
    from .artifact_tools import PA_ARTIFACT_TOOLS, PA_MANIFEST_TOOLS  # noqa: PLC0415
    from .broker import ALL_ASSISTANT_TOOLS  # noqa: PLC0415
    from .client_output_tools import PA_OUTPUT_READ_TOOLS, PA_OUTPUT_WRITE_TOOLS  # noqa: PLC0415
    from .profile import (  # noqa: PLC0415
        ai_outputs_write_enabled,
        client_output_write_enabled,
        prompt_preflight_enabled,
    )
    from .tool_registration import CLIENT_BRIDGE_HELPER_TOOLS  # noqa: PLC0415

    names: set[str] = (
        set(ALL_ASSISTANT_TOOLS) | set(CLIENT_BRIDGE_HELPER_TOOLS)
        | set(PA_ARTIFACT_TOOLS) | set(PA_MANIFEST_TOOLS)
    )

    names |= {
        "hb_mcp_status", "hb_data_freshness", "hb_queue_status", "hb_recent_failures",
        "hb_last_successful_runs", "hb_capability_mode", "hb_db_select", "hb_root_list", "hb_root_stat",
        "hb_root_search", "hb_root_read_file", "hb_root_read_excerpt", "hb_output_list", "hb_output_stat",
        "hb_output_read",
    }
    names |= set(PA_OUTPUT_READ_TOOLS)
    if client_output_write_enabled():
        names |= set(PA_OUTPUT_WRITE_TOOLS)
    if ai_outputs_write_enabled():
        names.add("ai_outputs_card_upsert")
    if prompt_preflight_enabled():
        names |= set(_PROMPT_ROUTING_NAMES)
    return names


def tool_group_for(name: str, assistant_groups: dict[str, str] | None = None) -> str | None:
    ag = assistant_groups if assistant_groups is not None else _assistant_group_map()
    if name in ag:
        return ag[name]
    return KNOWN_TOOL_GROUPS.get(name)


def tool_name_set(config: Any) -> set[str]:
    return installed_tool_names(config)


def tool_group_map(config: Any) -> dict[str, str | None]:
    ag = _assistant_group_map()
    return {name: tool_group_for(name, ag) for name in installed_tool_names(config)}


def build_live_tool_surface(config: Any) -> dict[str, SurfaceToolState]:
    """Surface-level state for every installed tool name. No request-level fields."""
    from .broker import GATEWAY_ALLOWLIST  # noqa: PLC0415
    from .tool_registration import derive_tool_arg_meta, live_tool_schema_index  # noqa: PLC0415

    ag = _assistant_group_map()
    gateway = set(GATEWAY_ALLOWLIST)
    schema_index = live_tool_schema_index()
    out: dict[str, SurfaceToolState] = {}
    for name in sorted(installed_tool_names(config)):
        group = tool_group_for(name, ag)
        profile_on = _profile_group_enabled(group)
        spec = resolve_tool_spec(name, group)
        meta = derive_tool_arg_meta(name, schema_index)
        gateway_ok = name in gateway
        # Direct exposure: registered when profile gate on (assistant groups) or always for helpers.
        direct = profile_on
        if group == "prompt_routing":
            direct = profile_on
        server_policy_available = profile_on and (direct or gateway_ok)
        blocked: str | None = None
        if not profile_on:
            blocked = "kill_switch"
        elif not (direct or gateway_ok):
            blocked = "not_exposed"
        out[name] = SurfaceToolState(
            name=name,
            installed=True,
            profile_enabled=profile_on,
            directly_exposed=direct,
            gateway_allowlisted=gateway_ok,
            server_policy_available=server_policy_available,
            surface_blocked_reason=blocked,
            group=group,
            family=spec.family,
            read_write_class=spec.read_write_class,
            safety_class=spec.safety_class,
            tool_class=spec.tool_class,
            purpose=meta.get("purpose") or spec.purpose or spec.use_when,
            required_args=tuple(meta.get("required_args") or spec.required_args),
            optional_args=tuple(meta.get("optional_args") or spec.optional_args),
            limits=dict(meta.get("limits") or spec.limits or {}),
        )
    return out


def build_tool_index(config: Any) -> dict[str, dict[str, Any]]:
    """Manifest/help tool index: name -> public entry dict with group + schema meta."""
    surface = build_live_tool_surface(config)
    index: dict[str, dict[str, Any]] = {}
    for name, st in surface.items():
        entry = tool_spec_public_entry(
            name,
            st.group,
            required_args=list(st.required_args),
            optional_args=list(st.optional_args),
            limits=dict(st.limits),
            purpose=st.purpose,
        )
        entry["group"] = st.group  # legacy key used by build_manifest
        entry["installed"] = st.installed
        entry["profile_enabled"] = st.profile_enabled
        entry["directly_exposed"] = st.directly_exposed
        entry["gateway_allowlisted"] = st.gateway_allowlisted
        entry["server_policy_available"] = st.server_policy_available
        entry["surface_blocked_reason"] = st.surface_blocked_reason
        index[name] = entry
    return index


def gate_state_snapshot() -> dict[str, bool]:
    """Profile kill-switch snapshot for exposure checksum context."""
    from . import profile as prof  # noqa: PLC0415

    return {
        "nav": prof.assistant_nav_enabled(),
        "context_packs": prof.assistant_context_packs_enabled(),
        "memory": prof.assistant_memory_enabled(),
        "decision_memory": prof.assistant_decision_memory_enabled(),
        "review": prof.assistant_review_enabled(),
        "intelligence": prof.assistant_intelligence_enabled(),
        "research_packets": prof.assistant_research_packets_enabled(),
        "source_connector": prof.assistant_source_connector_enabled(),
        "answer_drafts": prof.assistant_answer_drafts_enabled(),
        "workflows": prof.assistant_workflows_enabled(),
        "feedback": prof.assistant_feedback_enabled(),
        "action_stages": prof.assistant_action_stages_enabled(),
        "quality": prof.assistant_quality_enabled(),
        "source_structure": prof.assistant_source_structure_enabled(),
        "prompt_preflight": prof.prompt_preflight_enabled(),
        "client_tool_manifest": prof.client_tool_manifest_enabled(),
        "client_output_write": prof.client_output_write_enabled(),
        "ai_outputs_write": prof.ai_outputs_write_enabled(),
    }


def surface_profile_label() -> str:
    from .profile import active_profile  # noqa: PLC0415

    try:
        return str(active_profile())
    except Exception:  # noqa: BLE001
        return "unknown"
