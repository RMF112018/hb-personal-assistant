"""Authoritative semantic metadata for tools, families, and workflows.

Static ToolSpec / classification authority lives here. Family and workflow *records* are
still seeded from the compatibility modules but classification, routing-tool specs, and
replacement-map semantics are owned here so help/manifest/freshness share one model.

Family/workflow seed lists remain importable from their historic modules (thin re-export
targets); this module is the single place for ToolSpec resolution and tool classification.
"""

from __future__ import annotations

from typing import Any

from .tool_metadata_types import (
    AvailabilityKind,
    ExposureDeclaration,
    LifecycleSpec,
    ToolSpec,
)

# ---------------------------------------------------------------------------
# Explicit ToolSpecs for control-plane / routing tools (must appear in help)
# ---------------------------------------------------------------------------

PROMPT_ROUTING_TOOL_SPECS: dict[str, ToolSpec] = {
    "pa_prompt_route": ToolSpec(
        name="pa_prompt_route",
        family="prompt_routing",
        group="prompt_routing",
        purpose="Read-only preflight: classify a prompt into intent, family, workflow, tools, and authorization.",
        required_args=("prompt",),
        optional_args=("has_exact_id",),
        read_write_class="read_only",
        safety_class="advisory_only",
        tool_class="advisory_routing",
        exposure=ExposureDeclaration(
            direct_by_design=True,
            gateway_by_design=True,
            availability=AvailabilityKind.FEATURE_FLAGGED,
            profile_gate="HB_MCP_PROMPT_PREFLIGHT",
        ),
        use_when="Decide which tool/workflow to use before acting; never executes.",
        do_not_use_when="You already know the exact tool and arguments.",
        workflow_roles=("context_preflight", "prompt_route"),
        examples=("Find my project notes.", "Which tool lists source roots? Do not execute."),
    ),
    "pa_prompt_route_explain": ToolSpec(
        name="pa_prompt_route_explain",
        family="prompt_routing",
        group="prompt_routing",
        purpose="Same route plan as pa_prompt_route plus full workflow and family records for debugging.",
        required_args=("prompt",),
        optional_args=("has_exact_id",),
        read_write_class="read_only",
        safety_class="advisory_only",
        tool_class="advisory_routing",
        exposure=ExposureDeclaration(
            direct_by_design=True,
            gateway_by_design=True,
            availability=AvailabilityKind.FEATURE_FLAGGED,
            profile_gate="HB_MCP_PROMPT_PREFLIGHT",
        ),
        use_when="Low confidence, ambiguity, operator review, or debugging a route.",
        do_not_use_when="A compact high-confidence route from pa_prompt_route is enough.",
        workflow_roles=("prompt_route",),
        examples=("Explain why this prompt routes to source_file_search.",),
    ),
    "pa_tool_family_get": ToolSpec(
        name="pa_tool_family_get",
        family="prompt_routing",
        group="prompt_routing",
        purpose="Return one tool-family record or the full family list (read-only).",
        required_args=(),
        optional_args=("family_id",),
        read_write_class="read_only",
        safety_class="advisory_only",
        tool_class="advisory_routing",
        exposure=ExposureDeclaration(
            availability=AvailabilityKind.FEATURE_FLAGGED,
            profile_gate="HB_MCP_PROMPT_PREFLIGHT",
        ),
    ),
    "pa_workflow_recipe_get": ToolSpec(
        name="pa_workflow_recipe_get",
        family="prompt_routing",
        group="prompt_routing",
        purpose="Return one workflow recipe or the full workflow list (read-only).",
        required_args=(),
        optional_args=("workflow_id",),
        read_write_class="read_only",
        safety_class="advisory_only",
        tool_class="advisory_routing",
        exposure=ExposureDeclaration(
            availability=AvailabilityKind.FEATURE_FLAGGED,
            profile_gate="HB_MCP_PROMPT_PREFLIGHT",
        ),
    ),
    "pa_tool_surface_freshness_check": ToolSpec(
        name="pa_tool_surface_freshness_check",
        family="prompt_routing",
        group="prompt_routing",
        purpose="Compare live tool surface against routing manifests (read-only freshness report).",
        required_args=(),
        optional_args=(),
        read_write_class="read_only",
        safety_class="advisory_only",
        tool_class="advisory_routing",
        exposure=ExposureDeclaration(
            availability=AvailabilityKind.FEATURE_FLAGGED,
            profile_gate="HB_MCP_PROMPT_PREFLIGHT",
        ),
    ),
}

# Explicit group for tools whose group is not inferable from ASSISTANT_TOOL_GROUPS alone.
KNOWN_TOOL_GROUPS: dict[str, str] = {
    **dict.fromkeys(PROMPT_ROUTING_TOOL_SPECS, "prompt_routing"),
    "hb_assistant_catalog": "client_bridge",
    "hb_assistant_tool_help": "client_bridge",
    "hb_assistant_tool_query": "client_bridge",
    "hb_mcp_status": "status",
    "hb_data_freshness": "status",
    "hb_queue_status": "status",
    "hb_recent_failures": "status",
    "hb_last_successful_runs": "status",
    "hb_capability_mode": "status",
    "assistant_source_roots_list": "source_connector",
    "assistant_source_root_map": "source_structure",
}

# Capabilities exercised by operator_authorization_policy values.
POLICY_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "read": ("read",),
    "staged_write": ("read", "stage", "write"),
    "canonical_promotion": ("read", "promote"),
    "archive": ("read", "archive"),
}


def replacement_map() -> dict[str, str]:
    return {
        "hb_root_search": "assistant_source_file_search",
        "hb_root_read_file": "assistant_source_file_read",
        "search_vault": "assistant_search_sources",
        "hb_db_select": "assistant_* semantic retrieval tools",
        "direct_note_creation": "pa_artifact_proposal_stage → review → pa_artifact_promotion_apply",
        "hb_output_write_file": "pa_output_stage",
        "hb_output_create_dir": "pa_output_stage",
    }


_DENIED = frozenset({"raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"})
_LEGACY_LOW = frozenset({
    "hb_db_select", "hb_root_list", "hb_root_stat", "hb_root_search", "hb_root_read_file",
    "hb_root_read_excerpt", "search_vault",
})


def classify_tool(name: str, group: str | None = None) -> tuple[str, str, str]:
    """Return (tool_class, safety_class, read_write_class) — canonical classification."""
    if name in PROMPT_ROUTING_TOOL_SPECS:
        spec = PROMPT_ROUTING_TOOL_SPECS[name]
        return spec.tool_class, spec.safety_class, spec.read_write_class
    if name in _DENIED:
        return "blocked_or_deprecated", "blocked", "blocked"
    if name == "ai_outputs_card_upsert":
        return "canonical_promotion", "canonical_promotion_requires_explicit_approval", "canonical_write"
    if name in ("pa_artifact_promotion_apply", "pa_tool_manifest_refresh_promote"):
        return "canonical_promotion", "canonical_promotion_requires_explicit_approval", "canonical_write"
    if name in (
        "pa_session_capture_stage", "pa_artifact_proposal_stage", "pa_artifact_proposal_revise",
        "pa_artifact_proposal_review", "pa_tool_manifest_refresh_stage",
    ):
        return "staged_write", "staged_write_requires_review", "staged_write"
    if name in ("pa_output_stage", "pa_output_commit", "pa_output_archive_commit"):
        return "staged_write", "staged_write_requires_review", "staged_write"
    if name.startswith("pa_output_"):
        return "read_only_retrieval", "bounded_read", "read_only"
    if name in (
        "pa_artifact_proposal_plan_promotion", "pa_artifact_promotion_validate",
        "pa_tool_manifest_review_plan", "pa_vault_path_resolve",
    ):
        return "advisory_routing", "advisory_only", "read_only"
    if name.startswith("pa_tool_manifest") or name in (
        "hb_assistant_catalog", "hb_assistant_tool_help", "hb_assistant_tool_query",
    ):
        return "manifest_lookup", "bounded_read", "read_only"
    if name in (
        "hb_mcp_status", "hb_data_freshness", "hb_queue_status", "hb_recent_failures",
        "hb_last_successful_runs", "hb_capability_mode",
    ):
        return "read_only_status", "safe_read", "read_only"
    if name in _LEGACY_LOW or name.startswith("hb_output_"):
        return "legacy_low_level", "bounded_read", "read_only"
    if group == "review" or "review" in name:
        return "read_only_review", "bounded_read", "read_only"
    return "read_only_retrieval", "bounded_read", "read_only"


def resolve_tool_spec(name: str, group: str | None = None) -> ToolSpec:
    """Total function: always returns a ToolSpec for ``name``."""
    if name in PROMPT_ROUTING_TOOL_SPECS:
        return PROMPT_ROUTING_TOOL_SPECS[name]
    from .tool_entry_manifest import TOOL_ENTRY_OVERRIDES  # noqa: PLC0415
    from .tool_family_manifest import family_for_tool, family_record  # noqa: PLC0415

    g = group if group is not None else KNOWN_TOOL_GROUPS.get(name)
    family_id = family_for_tool(name, g)
    fam = family_record(family_id) or {}
    tool_class, safety, rw = classify_tool(name, g)
    seed = TOOL_ENTRY_OVERRIDES.get(name, {})
    repl_map = replacement_map()
    replaced_by: tuple[str, ...] = tuple(seed.get("replaced_by", []))
    if not replaced_by and name in repl_map:
        replaced_by = (repl_map[name],)
    lifecycle = LifecycleSpec(
        state="deprecated" if seed.get("deprecated") else "active",
        deprecated=bool(seed.get("deprecated", False)),
        replaced_by=replaced_by,
    )
    availability = AvailabilityKind.DEPRECATED if lifecycle.deprecated else AvailabilityKind.REQUIRED
    if name.startswith("assistant_"):
        availability = AvailabilityKind.PROFILE_CONDITIONAL
    return ToolSpec(
        name=name,
        family=family_id,
        group=g,
        purpose=seed.get("use_when", "") or fam.get("purpose", ""),
        read_write_class=rw or fam.get("read_write_class", "read_only"),
        safety_class=safety or fam.get("safety_class", "bounded_read"),
        tool_class=tool_class,
        exposure=ExposureDeclaration(availability=availability),
        lifecycle=lifecycle,
        use_when=seed.get("use_when", ""),
        do_not_use_when=seed.get("do_not_use_when", ""),
        examples=tuple(seed.get("examples", [])),
    )


def tool_spec_public_entry(name: str, group: str | None = None, *,
                           required_args: list[str] | None = None,
                           optional_args: list[str] | None = None,
                           limits: dict[str, Any] | None = None,
                           purpose: str | None = None) -> dict[str, Any]:
    """Dict shape used by manifest entries / tool help."""
    spec = resolve_tool_spec(name, group)
    tc, sc, rw = classify_tool(name, group)
    return {
        "tool_name": name,
        "tool_group": group if group is not None else spec.group,
        "tool_family": spec.family,
        "tool_class": tc,
        "safety_class": sc,
        "read_write_class": rw,
        "purpose": purpose if purpose is not None else (spec.purpose or spec.use_when),
        "preferred_for": list(spec.examples),
        "avoid_when": [spec.do_not_use_when] if spec.do_not_use_when else [],
        "required_args": list(required_args if required_args is not None else spec.required_args),
        "optional_args": list(optional_args if optional_args is not None else spec.optional_args),
        "limits": dict(limits if limits is not None else spec.limits),
        "workflow_roles": list(spec.workflow_roles),
        "replacement_tools": list(spec.lifecycle.replaced_by),
        "common_failure_modes": list(spec.common_failure_modes),
        "examples": list(spec.examples),
        "deprecated": spec.lifecycle.deprecated,
        "availability": spec.exposure.availability.value,
        "direct_exposure_by_design": spec.exposure.direct_by_design,
        "gateway_exposure_by_design": spec.exposure.gateway_by_design,
    }
