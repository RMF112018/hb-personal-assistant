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

from .capability_registry import (
    CapabilityProfile,
    definitions_for_profile,
    gateway_names_for_profile,
    resolve_profile,
)

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
    selected = resolve_profile(getattr(config, "capability_profile", None))
    return {
        item.registered_name
        for item in definitions_for_profile(selected)
    }


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


def build_live_tool_surface(config: Any, *, for_manifest: bool = False) -> dict[str, SurfaceToolState]:
    """Surface-level state for every installed tool name. No request-level fields."""
    from .tool_registration import derive_tool_arg_meta, live_tool_schema_index  # noqa: PLC0415

    ag = _assistant_group_map()
    selected = resolve_profile(getattr(config, "capability_profile", None))
    definitions = {item.registered_name: item for item in definitions_for_profile(selected)}
    gateway = set(gateway_names_for_profile(selected))
    schema_index = live_tool_schema_index()
    out: dict[str, SurfaceToolState] = {}
    for name in sorted(installed_tool_names(config)):
        group = tool_group_for(name, ag)
        profile_on = _profile_group_enabled(group)
        definition = definitions[name]
        spec = resolve_tool_spec(name, group)
        meta = derive_tool_arg_meta(name, schema_index)
        if for_manifest:
            from hb_assistant.obsidian_mcp.canonical_tool_specs import normalize_manifest_purpose  # noqa: PLC0415

            purpose = normalize_manifest_purpose(
                str(meta.get("purpose") or spec.purpose or spec.use_when or ""),
            )
            required_args = tuple(meta.get("required_args") or ())
            optional_args = tuple(meta.get("optional_args") or ())
            limits = dict(meta.get("limits") or {})
        else:
            purpose = meta.get("purpose") or spec.purpose or spec.use_when
            required_args = tuple(meta.get("required_args") or spec.required_args)
            optional_args = tuple(meta.get("optional_args") or spec.optional_args)
            limits = dict(meta.get("limits") or spec.limits or {})
        gateway_ok = name in gateway
        # Direct exposure: registered when profile gate on (assistant groups) or always for helpers.
        direct = profile_on and (
            definition.direct_exposure or selected is CapabilityProfile.LEGACY_V12
        )
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
            purpose=purpose,
            required_args=required_args,
            optional_args=optional_args,
            limits=limits,
        )
    return out


def manifest_schema_parity_check(config: Any) -> dict[str, Any]:
    """Compare manifest-facing arg metadata to the frozen registration schema index."""
    from .tool_registration import (  # noqa: PLC0415
        derive_tool_arg_meta,
        live_tool_schema_index,
        schema_index_frozen,
    )

    index = live_tool_schema_index()
    if not schema_index_frozen():
        return {
            "ok": False,
            "reason": "schema_index_not_frozen",
            "diffs": [],
            "missing_tools": [],
            "frozen_tool_count": 0,
        }

    built = build_tool_index(config, for_manifest=True)
    diffs: list[dict[str, Any]] = []
    missing_tools: list[str] = []

    def _index_name_for_manifest_tool(name: str) -> str | None:
        if name in index:
            return name
        if name.startswith("pa_output_"):
            alias = "assistant_output_" + name[len("pa_output_") :]
            if alias in index:
                return alias
        return None

    for name in sorted(installed_tool_names(config)):
        index_name = _index_name_for_manifest_tool(name)
        if index_name is None:
            missing_tools.append(name)
            continue
        meta = derive_tool_arg_meta(index_name, index)
        entry = built.get(name) or {}
        for field in ("required_args", "optional_args"):
            expected = sorted(meta.get(field) or [])
            actual = sorted(entry.get(field) or [])
            if expected != actual:
                diffs.append({
                    "tool_name": name,
                    "field": field,
                    "expected": expected,
                    "actual": actual,
                })
        expected_purpose = str(meta.get("purpose") or "").strip()
        actual_purpose = str(entry.get("purpose") or "").strip()
        if expected_purpose and actual_purpose and expected_purpose != actual_purpose:
            diffs.append({
                "tool_name": name,
                "field": "purpose",
                "expected": expected_purpose,
                "actual": actual_purpose,
            })

    ok = not diffs and not missing_tools
    return {
        "ok": ok,
        "reason": None if ok else "schema_parity_mismatch",
        "diffs": diffs,
        "missing_tools": missing_tools,
        "frozen_tool_count": len(index),
    }


def build_tool_index(config: Any, *, for_manifest: bool = False) -> dict[str, dict[str, Any]]:
    """Manifest/help tool index: name -> public entry dict with group + schema meta."""
    surface = build_live_tool_surface(config, for_manifest=for_manifest)
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


def surface_profile_label(config: Any | None = None) -> str:
    from .profile import active_profile  # noqa: PLC0415

    try:
        capability = resolve_profile(getattr(config, "capability_profile", None)).value
        return f"{active_profile()}+{capability}"
    except Exception:  # noqa: BLE001
        return "unknown"
