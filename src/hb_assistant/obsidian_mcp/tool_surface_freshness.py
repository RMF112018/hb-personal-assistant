"""Prompt Preflight — tool-surface freshness guard.

Compares the LIVE registered tool surface (tool names, their family/read-write/safety class, and the
gateway allowlist scope) against the stored routing manifest (families + workflows + tool entries). Any
drift — added / removed / renamed tools, a tool whose family or class changed, a workflow that references a
now-missing tool, or a changed gateway scope — makes the surface *stale*. Read routes proceed with a
warning; write / promotion / archive routes must fail closed on a stale surface. Read-only; never writes.
"""

from __future__ import annotations

from typing import Any

from .tool_entry_manifest import build_tool_entry
from .tool_family_manifest import FAMILY_IDS, family_for_tool
from .workflow_recipe_manifest import WORKFLOWS


def check_tool_surface(
    live_tools: dict[str, str | None],
    *,
    stored_entries: dict[str, dict[str, Any]] | None = None,
    live_gateway_allowlist: frozenset[str] | set[str] | None = None,
    stored_gateway_allowlist: frozenset[str] | set[str] | None = None,
    check_workflow_coverage: bool = True,
) -> dict[str, Any]:
    """Return a freshness report over the live tool surface vs the stored routing manifest.

    ``live_tools`` maps live tool name -> tool group. ``stored_entries`` maps name -> stored routing entry
    (as persisted at manifest build). When ``stored_entries`` is None, only structural self-consistency is
    checked (every live tool classifies into a known family; every workflow tool resolves).
    """
    warnings: list[str] = []
    live_names = set(live_tools)

    # 1) Every live tool must classify into a known family.
    unclassified = sorted(
        n for n in live_names if family_for_tool(n, live_tools.get(n)) not in FAMILY_IDS
    )
    if unclassified:
        warnings.append(f"tools with no known family: {unclassified}")

    # 2) Every workflow tool_sequence entry must resolve to a live tool (prompt-routing tools excepted —
    #    they are the routing layer itself and may be validated separately).
    _routing_layer = {"pa_prompt_route", "pa_prompt_route_explain", "pa_tool_family_get",
                      "pa_workflow_recipe_get", "pa_tool_surface_freshness_check"}
    workflow_missing_tools: list[str] = []
    if check_workflow_coverage:
        for wf in WORKFLOWS:
            for tool in wf["tool_sequence"]:
                if tool not in live_names and tool not in _routing_layer:
                    workflow_missing_tools.append(f"{wf['workflow_id']}:{tool}")
    if workflow_missing_tools:
        warnings.append(f"workflows reference missing tools: {sorted(set(workflow_missing_tools))}")

    added: list[str] = []
    removed: list[str] = []
    family_changed: list[str] = []
    class_changed: list[str] = []
    if stored_entries is not None:
        stored_names = set(stored_entries)
        added = sorted(live_names - stored_names)
        removed = sorted(stored_names - live_names)
        for name in sorted(live_names & stored_names):
            live_entry = build_tool_entry(name, live_tools.get(name))
            stored = stored_entries[name]
            if live_entry["tool_family"] != stored.get("tool_family"):
                family_changed.append(name)
            if (live_entry["read_write_class"] != stored.get("read_write_class")
                    or live_entry["safety_class"] != stored.get("safety_class")):
                class_changed.append(name)
        if added:
            warnings.append(f"tools added since manifest: {added}")
        if removed:
            warnings.append(f"tools removed since manifest: {removed}")
        if family_changed:
            warnings.append(f"tools whose family changed: {family_changed}")
        if class_changed:
            warnings.append(f"tools whose read/write or safety class changed: {class_changed}")

    # 3) Gateway scope drift (the operator-authorized allowlist must match what routing assumes).
    gateway_added: list[str] = []
    gateway_removed: list[str] = []
    gateway_current = True
    if live_gateway_allowlist is not None and stored_gateway_allowlist is not None:
        live_g, stored_g = set(live_gateway_allowlist), set(stored_gateway_allowlist)
        gateway_added = sorted(live_g - stored_g)
        gateway_removed = sorted(stored_g - live_g)
        gateway_current = not (gateway_added or gateway_removed)
        if not gateway_current:
            warnings.append(
                f"gateway allowlist scope changed (added={gateway_added}, removed={gateway_removed})"
            )

    stale = bool(
        unclassified or workflow_missing_tools or added or removed or family_changed or class_changed
        or not gateway_current
    )
    if stored_entries is None and live_gateway_allowlist is None:
        staleness_state = "structural_only"
    elif stale:
        staleness_state = "stale"
    else:
        staleness_state = "current"

    return {
        "stale": stale,
        "staleness_state": staleness_state,
        "warnings": warnings,
        "unclassified_tools": unclassified,
        "workflow_missing_tools": sorted(set(workflow_missing_tools)),
        "added_tools": added,
        "removed_tools": removed,
        "family_changed_tools": family_changed,
        "class_changed_tools": class_changed,
        "gateway_added": gateway_added,
        "gateway_removed": gateway_removed,
        "tool_surface_gateway_current": gateway_current,
        "live_tool_count": len(live_names),
        "review_required": stale,
    }
