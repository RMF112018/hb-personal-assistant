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
    from .live_tool_surface import tool_group_map  # noqa: PLC0415

    return tool_group_map(config)


def live_freshness(config: NasMcpConfig) -> dict[str, Any]:
    """Compute live tool-surface freshness vs independent stored baseline when available.

    Never self-compares live gateway to itself as the sole baseline and claims current.
    On failure returns check_failed (stale=true), never a false current state.
    """
    try:
        from ..obsidian_mcp.client_tool_manifest import (  # noqa: PLC0415
            ClientToolManifestRepository,
            build_live_surface_fingerprints,
        )
        from .artifact_tools import _build_tool_index, _runtime_manifest_build_kwargs  # noqa: PLC0415
        from .broker import GATEWAY_ALLOWLIST, runtime_commit  # noqa: PLC0415
        from .live_tool_surface import gate_state_snapshot, surface_profile_label  # noqa: PLC0415

        groups = current_tool_groups(config)
        live_gateway = frozenset(GATEWAY_ALLOWLIST) | set(PROMPT_ROUTING_TOOLS)
        build_kwargs = _runtime_manifest_build_kwargs()
        live_fps = build_live_surface_fingerprints(
            _build_tool_index(config, for_manifest=True),
            surface_profile=build_kwargs.get("surface_profile"),
            gate_state_snapshot=build_kwargs.get("gate_state_snapshot"),
            gateway_allowlist=build_kwargs.get("gateway_allowlist"),
        )

        stored_entries: dict[str, dict[str, Any]] | None = None
        stored_gateway: frozenset[str] | None = None
        stored_semantic: str | None = None
        stored_exposure: str | None = None
        stored_runtime: str | None = None
        stored_profile: str | None = None
        try:
            mrepo = ClientToolManifestRepository(str(config.db_path))
            active = mrepo.get_active()
            if active:
                stored_entries = {
                    e["tool_name"]: e for e in active.get("entries") or []
                }
                stored_semantic = active.get("semantic_surface_checksum")
                stored_exposure = active.get("exposure_checksum")
                stored_runtime = active.get("generated_from_runtime_commit")
                stored_profile = active.get("surface_profile")
                gw = active.get("gateway_allowlist")
                if isinstance(gw, (list, set, frozenset)):
                    stored_gateway = frozenset(gw)
        except Exception:  # noqa: BLE001
            stored_entries = None

        if stored_entries is None and stored_semantic is None:
            return check_tool_surface(
                groups,
                stored_entries=None,
                check_workflow_coverage=True,
            )
        return check_tool_surface(
            groups,
            stored_entries=stored_entries,
            live_gateway_allowlist=live_gateway,
            stored_gateway_allowlist=stored_gateway,
            live_runtime_commit=runtime_commit(),
            stored_runtime_commit=stored_runtime,
            live_semantic_checksum=live_fps.get("semantic_surface_checksum"),
            stored_semantic_checksum=stored_semantic,
            live_exposure_checksum=live_fps.get("exposure_checksum"),
            stored_exposure_checksum=stored_exposure,
            live_profile=surface_profile_label(),
            stored_profile=stored_profile,
            help_index=dict.fromkeys(groups, True),
        )
    except Exception as exc:  # noqa: BLE001 — freshness must never crash status/routing
        return check_tool_surface(
            {},
            check_error=str(type(exc).__name__),
        )


def dispatch_prompt_routing_tool(config: NasMcpConfig, tool_name: str, arguments: dict[str, Any], *,
                                 runtime_commit: str = "unknown") -> dict[str, Any]:
    a = arguments or {}
    available = frozenset(current_tool_groups(config))
    groups = current_tool_groups(config)

    if tool_name in ("pa_prompt_route", "pa_prompt_route_explain"):
        prompt = str(_require(a, "prompt"))
        fresh = live_freshness(config)
        fn = explain_route if tool_name == "pa_prompt_route_explain" else route_prompt
        return fn(
            prompt,
            available_tools=available,
            has_exact_id=bool(a.get("has_exact_id", False)),
            freshness=fresh,
            tool_groups=groups,
        )
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
        out["tool_surface_staleness_state"] = "check_failed"
        out["tool_surface_manifest_current"] = False
    return out
