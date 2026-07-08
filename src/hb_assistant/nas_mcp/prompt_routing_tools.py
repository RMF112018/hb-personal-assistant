"""Prompt Preflight & Tool Routing — MCP handler surface (read-only).

Five ``pa_prompt_*`` / routing tools that expose the deterministic route engine + freshness guard to
connected clients. All are READ-ONLY: they never write, stage, promote, or read source content. None of
the names contains a write-verb or finality substring; none joins ``ALL_ASSISTANT_TOOLS``. They are
gateway-reachable via ``GATEWAY_ALLOWLIST``. Organization-neutral.
"""

from __future__ import annotations

from typing import Any

from ..obsidian_mcp.prompt_preflight import explain_route, route_prompt
from ..obsidian_mcp.tool_family_manifest import FAMILIES, family_record
from ..obsidian_mcp.tool_surface_freshness import check_tool_surface
from ..obsidian_mcp.workflow_recipe_manifest import WORKFLOWS, workflow_record
from .config import NasMcpConfig

# All read-only; gateway-reachable routing tools.
PROMPT_ROUTING_TOOLS: tuple[str, ...] = (
    "pa_prompt_route",
    "pa_prompt_route_explain",
    "pa_tool_family_get",
    "pa_workflow_recipe_get",
    "pa_tool_surface_freshness_check",
)


class PromptRoutingError(ValueError):
    """Raised for a bad routing-tool request (missing arg / unknown id)."""


def _require(a: dict[str, Any], key: str) -> Any:
    v = a.get(key)
    if v in (None, ""):
        raise PromptRoutingError(f"missing_required_arg:{key}")
    return v


def current_tool_groups(config: NasMcpConfig) -> dict[str, str | None]:
    """Live tool name -> group, including the routing-layer tools. Read-only view for freshness."""
    from .artifact_tools import current_tool_names  # noqa: PLC0415
    from .broker import ASSISTANT_TOOL_GROUPS  # noqa: PLC0415

    tool_to_group = {t: g for g, tools in ASSISTANT_TOOL_GROUPS.items() for t in tools}
    names = set(current_tool_names(config)) | set(PROMPT_ROUTING_TOOLS)
    return {name: tool_to_group.get(name) for name in names}


def live_freshness(config: NasMcpConfig) -> dict[str, Any]:
    """Compute the live tool-surface freshness report (structural + gateway scope). Never raises."""
    try:
        from .broker import GATEWAY_ALLOWLIST  # noqa: PLC0415

        groups = current_tool_groups(config)
        gateway = frozenset(GATEWAY_ALLOWLIST) | set(PROMPT_ROUTING_TOOLS)
        return check_tool_surface(
            groups,
            live_gateway_allowlist=gateway,
            stored_gateway_allowlist=gateway,  # self-consistency baseline; drift vs a stored snapshot
        )
    except Exception as exc:  # noqa: BLE001 — freshness must never crash status/routing
        return {"stale": False, "staleness_state": "unknown", "warnings": [f"freshness_error:{exc}"],
                "review_required": False, "tool_surface_gateway_current": True}


def dispatch_prompt_routing_tool(config: NasMcpConfig, tool_name: str, arguments: dict[str, Any], *,
                                 runtime_commit: str = "unknown") -> dict[str, Any]:
    a = arguments or {}
    available = frozenset(current_tool_groups(config))

    if tool_name in ("pa_prompt_route", "pa_prompt_route_explain"):
        prompt = str(_require(a, "prompt"))
        fresh = live_freshness(config)
        fn = explain_route if tool_name == "pa_prompt_route_explain" else route_prompt
        return fn(prompt, available_tools=available, has_exact_id=bool(a.get("has_exact_id", False)),
                  freshness=fresh)
    if tool_name == "pa_tool_family_get":
        fid = a.get("family_id")
        if fid:
            rec = family_record(str(fid))
            if not rec:
                raise PromptRoutingError(f"unknown_family_id:{fid}")
            return {"family": rec}
        return {"families": FAMILIES}
    if tool_name == "pa_workflow_recipe_get":
        wid = a.get("workflow_id")
        if wid:
            rec = workflow_record(str(wid))
            if not rec:
                raise PromptRoutingError(f"unknown_workflow_id:{wid}")
            return {"workflow": rec}
        return {"workflows": WORKFLOWS}
    if tool_name == "pa_tool_surface_freshness_check":
        return live_freshness(config)
    raise PromptRoutingError(f"unknown_prompt_routing_tool:{tool_name}")


def prompt_preflight_status(config: NasMcpConfig) -> dict[str, Any]:
    """Status fields for hb_mcp_status. Never raises."""
    from .profile import prompt_preflight_enabled  # noqa: PLC0415

    out = {
        "prompt_preflight_enabled": prompt_preflight_enabled(),
        "prompt_preflight_family_count": len(FAMILIES),
        "prompt_preflight_workflow_count": len(WORKFLOWS),
        "tool_surface_manifest_current": True,
        "tool_surface_last_checked_at": None,
        "tool_surface_missing_count": 0,
        "tool_surface_extra_count": 0,
        "tool_surface_schema_mismatch_count": 0,
        "tool_surface_gateway_current": True,
        "tool_surface_staleness_state": "unknown",
    }
    try:
        fr = live_freshness(config)
        out.update({
            "tool_surface_manifest_current": not fr.get("stale", False),
            "tool_surface_missing_count": len(fr.get("removed_tools", [])),
            "tool_surface_extra_count": len(fr.get("added_tools", [])),
            "tool_surface_schema_mismatch_count": (
                len(fr.get("family_changed_tools", [])) + len(fr.get("class_changed_tools", []))),
            "tool_surface_gateway_current": fr.get("tool_surface_gateway_current", True),
            "tool_surface_staleness_state": fr.get("staleness_state", "unknown"),
        })
    except Exception:  # noqa: BLE001
        pass
    return out
