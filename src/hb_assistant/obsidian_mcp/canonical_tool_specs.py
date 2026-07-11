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
    "pa_tool_surface_runtime_attestation": ToolSpec(
        name="pa_tool_surface_runtime_attestation",
        family="prompt_routing",
        group="prompt_routing",
        purpose="Execution-aware attestation: schema load, discoverability, gateway alias, dry diagnostic per exposed tool.",
        required_args=(),
        optional_args=(),
        read_write_class="read_only",
        safety_class="advisory_only",
        tool_class="advisory_routing",
        exposure=ExposureDeclaration(
            availability=AvailabilityKind.FEATURE_FLAGGED,
            profile_gate="HB_MCP_PROMPT_PREFLIGHT",
        ),
        use_when="Post-deploy or operator review to prove advertised tools are callable.",
        do_not_use_when="Static manifest drift only — use pa_tool_surface_freshness_check first.",
    ),
}

# N8C-22 client bridge helpers — catalog/help are read-only; tool_query is a write-capable gateway proxy.
CLIENT_BRIDGE_TOOL_SPECS: dict[str, ToolSpec] = {
    "hb_assistant_catalog": ToolSpec(
        name="hb_assistant_catalog",
        family="tool_catalog_help_query",
        group="client_bridge",
        purpose="List tools exposed to connected clients with group and classification metadata.",
        required_args=(),
        optional_args=(),
        read_write_class="read_only",
        safety_class="bounded_read",
        tool_class="manifest_lookup",
        exposure=ExposureDeclaration(direct_by_design=True, gateway_by_design=True),
        use_when="Discover which tools exist before choosing a workflow.",
        do_not_use_when="You already know the exact tool — use hb_assistant_tool_help or call it directly.",
        examples=("What tools are available?", "List assistant tools"),
    ),
    "hb_assistant_tool_help": ToolSpec(
        name="hb_assistant_tool_help",
        family="tool_catalog_help_query",
        group="client_bridge",
        purpose="Return schema and guidance for one registered tool (read-only lookup).",
        required_args=("tool_name",),
        optional_args=(),
        read_write_class="read_only",
        safety_class="bounded_read",
        tool_class="manifest_lookup",
        exposure=ExposureDeclaration(direct_by_design=True, gateway_by_design=True),
        use_when="You know the tool name and need required args and limits.",
        do_not_use_when="Routing a user task — use pa_prompt_route first.",
        examples=("How do I call assistant_get_decision?",),
    ),
    "hb_assistant_tool_query": ToolSpec(
        name="hb_assistant_tool_query",
        family="tool_catalog_help_query",
        group="client_bridge",
        purpose=(
            "Gateway proxy to invoke one allowlisted tool by name; may route to staged or canonical "
            "writes — broker gates every downstream call."
        ),
        required_args=("tool_name",),
        optional_args=("arguments",),
        read_write_class="write_proxy",
        safety_class="broker_gated_proxy",
        tool_class="gateway_proxy",
        exposure=ExposureDeclaration(direct_by_design=True, gateway_by_design=True),
        use_when="Invoke a known allowlisted tool when direct exposure is unavailable.",
        do_not_use_when="A directly exposed read tool suffices — prefer direct invocation.",
        examples=("Call assistant_list_decisions via gateway",),
    ),
}

# Explicit group for tools whose group is not inferable from ASSISTANT_TOOL_GROUPS alone.
# Option A: registration group is concrete; family may be broader (e.g. source_structure tools
# remain family assistant_source_connector via family_for_tool).
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
    "assistant_source_file_search": "source_connector",
    "assistant_source_file_metadata": "source_connector",
    "assistant_source_file_read": "source_connector",
    "assistant_source_status": "source_connector",
    "assistant_source_index_health": "source_connector",
    "assistant_source_query_plan": "source_connector",
    "assistant_source_root_map": "source_structure",
    "assistant_source_folder_map": "source_structure",
    "assistant_source_folder_summary": "source_structure",
    "assistant_source_search_route": "source_structure",
    "assistant_source_scope_explain": "source_structure",
    "assistant_source_project_map": "source_structure",
    "assistant_source_quality": "source_structure",
    "assistant_search_sources": "nav",
    "assistant_search_cards": "nav",
    "assistant_get_vault_note": "nav",
    "assistant_get_decision": "decision_memory",
    "assistant_list_decisions": "decision_memory",
    "assistant_get_preference": "decision_memory",
    "assistant_list_preferences": "decision_memory",
    "assistant_list_open_loops": "decision_memory",
    "assistant_get_open_loop": "decision_memory",
    # list tools already covered above
    "pa_artifact_proposal_stage": "artifact_workspace",
    "pa_session_capture_stage": "artifact_workspace",
    "pa_artifact_proposal_list": "artifact_workspace",
    "pa_artifact_proposal_review": "artifact_workspace",
    "pa_artifact_promotion_apply": "artifact_workspace",
}

# Capabilities exercised by operator_authorization_policy values.
POLICY_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "read": ("read",),
    "staged_write": ("read", "stage", "write"),
    "canonical_promotion": ("read", "promote"),
    "archive": ("read", "archive"),
}

MANIFEST_PURPOSE_MAX_LEN = 240

# Tools the July 2026 routing audit exercised — must carry disambiguating help (F-017).
AUDIT_HELP_TOOL_NAMES: frozenset[str] = frozenset({
    "hb_mcp_status",
    "hb_assistant_tool_help",
    "hb_assistant_tool_query",
    "assistant_source_file_search",
    "assistant_source_file_metadata",
    "assistant_search_sources",
    "assistant_search_cards",
    "assistant_get_vault_note",
    "assistant_list_decisions",
    "assistant_get_decision",
    "assistant_list_preferences",
    "assistant_get_preference",
    "assistant_list_open_loops",
    "assistant_get_open_loop",
    "pa_session_capture_stage",
    "pa_artifact_proposal_stage",
    "pa_artifact_promotion_apply",
})

GENERIC_FAMILY_PURPOSES: frozenset[str] = frozenset({
    "Read-only source/card/note navigation.",
    "Indexed NAS source-file discovery.",
    "Decisions / preferences / open loops.",
})


def normalize_manifest_purpose(text: str, *, max_len: int = MANIFEST_PURPOSE_MAX_LEN) -> str:
    """Cap manifest-facing purpose text at a sentence boundary (no mid-sentence truncation)."""
    s = " ".join(str(text or "").split())
    if not s:
        return ""
    if len(s) <= max_len:
        return s if s[-1] in ".!?" else f"{s}."
    chunk = s[:max_len].rstrip()
    if " " in chunk:
        chunk = chunk.rsplit(" ", 1)[0].rstrip()
    if chunk and chunk[-1] not in ".!?":
        chunk = chunk.rstrip(",;:") + "."
    return chunk


def purpose_is_complete(text: str) -> bool:
    """True when purpose is a bounded, complete sentence suitable for client help."""
    s = str(text or "").strip()
    if not s or len(s) > MANIFEST_PURPOSE_MAX_LEN:
        return False
    if "…" in s or "[truncated]" in s.lower():
        return False
    return s[-1] in ".!?"


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
    if name in CLIENT_BRIDGE_TOOL_SPECS:
        spec = CLIENT_BRIDGE_TOOL_SPECS[name]
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
    if name in (
        "pa_output_stage", "pa_output_commit", "pa_output_archive_commit", "pa_output_cancel",
        # Client-facing N8C-24 write aliases: same handlers/gate as their pa_output_* twins, so they
        # must classify as staged_write too — not fall through to read_only and be advertised to
        # connected clients (manifest/catalog/help) as safe reads while the broker gate blocks them.
        "assistant_output_stage", "assistant_output_commit", "assistant_output_archive_commit",
        "assistant_output_cancel",
    ):
        return "staged_write", "staged_write_requires_review", "staged_write"
    if name.startswith("pa_output_"):
        return "read_only_retrieval", "bounded_read", "read_only"
    if name in (
        "pa_artifact_proposal_plan_promotion", "pa_artifact_promotion_validate",
        "pa_tool_manifest_review_plan", "pa_vault_path_resolve",
    ):
        return "advisory_routing", "advisory_only", "read_only"
    if name.startswith("pa_tool_manifest"):
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
    if name in CLIENT_BRIDGE_TOOL_SPECS:
        return CLIENT_BRIDGE_TOOL_SPECS[name]
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
        purpose=seed.get("purpose", "") or seed.get("use_when", "") or fam.get("purpose", ""),
        read_write_class=rw or fam.get("read_write_class", "read_only"),
        safety_class=safety or fam.get("safety_class", "bounded_read"),
        tool_class=tool_class,
        exposure=ExposureDeclaration(availability=availability),
        lifecycle=lifecycle,
        use_when=seed.get("use_when", ""),
        do_not_use_when=seed.get("do_not_use_when", ""),
        examples=tuple(seed.get("examples", [])),
        common_failure_modes=tuple(seed.get("common_failure_modes", [])),
    )


def tool_spec_public_entry(name: str, group: str | None = None, *,
                           required_args: list[str] | None = None,
                           optional_args: list[str] | None = None,
                           limits: dict[str, Any] | None = None,
                           purpose: str | None = None) -> dict[str, Any]:
    """Dict shape used by manifest entries / tool help."""
    spec = resolve_tool_spec(name, group)
    tc, sc, rw = classify_tool(name, group)
    resolved_purpose = purpose if purpose is not None else (spec.purpose or spec.use_when)
    examples = list(spec.examples)
    if not examples and spec.use_when:
        examples = [spec.use_when]
    return {
        "tool_name": name,
        "tool_group": group if group is not None else spec.group,
        "tool_family": spec.family,
        "tool_class": tc,
        "safety_class": sc,
        "read_write_class": rw,
        "purpose": resolved_purpose,
        "preferred_for": list(examples),
        "avoid_when": [spec.do_not_use_when] if spec.do_not_use_when else [],
        "required_args": list(required_args if required_args is not None else spec.required_args),
        "optional_args": list(optional_args if optional_args is not None else spec.optional_args),
        "limits": dict(limits if limits is not None else spec.limits),
        "workflow_roles": list(spec.workflow_roles),
        "replacement_tools": list(spec.lifecycle.replaced_by),
        "common_failure_modes": list(spec.common_failure_modes),
        "examples": examples,
        "deprecated": spec.lifecycle.deprecated,
        "availability": spec.exposure.availability.value,
        "direct_exposure_by_design": spec.exposure.direct_by_design,
        "gateway_exposure_by_design": spec.exposure.gateway_by_design,
    }
