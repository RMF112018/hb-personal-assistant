"""Prompt Preflight — tool FAMILY taxonomy (durable routing source, seeded as static data).

Families are the coarse routing unit: the preflight selects a family (or several, when ambiguous) before
picking a workflow and specific tools. ``family_for_tool`` maps every live tool to exactly one family so the
freshness guard can prove no registered tool is unclassified. Organization-neutral; no employer-specific
names/paths.
"""

from __future__ import annotations

from typing import Any

# read_write_class / safety_class use the same vocabulary as the Client Tool Operating Manifest.
FAMILIES: list[dict[str, Any]] = [
    {"family_id": "status_health", "purpose": "Server + data health and capability status.",
     "use_when": ["asking if the server/tools are up", "capability mode", "queue/failure status"],
     "do_not_use_when": ["retrieving content or writing anything"],
     "read_write_class": "read_only", "safety_class": "safe_read",
     "common_trigger_phrases": ["status", "is the server up", "health", "capability mode"],
     "primary_workflows": ["status_check"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["never treat status output as source-of-truth content"]},
    {"family_id": "tool_catalog_help_query", "purpose": "Discover which tools exist and how to call them.",
     "use_when": ["which tool should I use", "what tools exist", "how do I call X"],
     "do_not_use_when": ["you already know the tool"], "read_write_class": "read_only",
     "safety_class": "bounded_read", "common_trigger_phrases": ["what tools", "which tool", "how do I use"],
     "primary_workflows": ["tool_help_lookup"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["the gateway is not a raw RPC escape hatch"]},
    {"family_id": "client_tool_manifest", "purpose": "The versioned tool operating manifest + freshness.",
     "use_when": ["is the tool manifest current", "why was a tool selected"],
     "do_not_use_when": ["routing a specific user task"], "read_write_class": "read_only",
     "safety_class": "bounded_read", "common_trigger_phrases": ["manifest", "tool routing", "freshness"],
     "primary_workflows": ["manifest_lookup", "manifest_freshness_check"], "preferred_before": [],
     "fallback_after": [], "family_level_negative_instructions": ["manifest refresh is staged, never silent"]},
    {"family_id": "prompt_routing", "purpose": "This preflight/route layer itself.",
     "use_when": ["decide what to do with a prompt", "explain a route decision"],
     "do_not_use_when": ["you only need one known tool"], "read_write_class": "read_only",
     "safety_class": "advisory_only", "common_trigger_phrases": ["route this", "what should I do with"],
     "primary_workflows": ["context_preflight", "prompt_route"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["preflight never writes/stages/promotes/commits anything"]},
    {"family_id": "assistant_navigation", "purpose": "Read-only source/card/note navigation.",
     "use_when": ["find a source", "open a card", "browse notes"], "do_not_use_when": ["writing"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["find", "search sources", "open card", "where is"],
     "primary_workflows": ["source_file_search", "source_file_metadata_review", "source_file_bounded_read"],
     "preferred_before": ["assistant_source_connector", "legacy_low_level"], "fallback_after": [],
     "family_level_negative_instructions": ["prefer semantic nav over low-level root tools"]},
    {"family_id": "assistant_context_packs", "purpose": "Durable retrieval context packs.",
     "use_when": ["assemble context", "context pack"], "do_not_use_when": ["single fact lookup"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["context pack", "assemble context"],
     "primary_workflows": ["context_pack_retrieval"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": []},
    {"family_id": "assistant_memory", "purpose": "Source-backed compiled memory.",
     "use_when": ["what do we know about X", "recall"], "do_not_use_when": ["decisions specifically"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["what do we know", "recall", "memory"],
     "primary_workflows": ["context_pack_retrieval"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": []},
    {"family_id": "assistant_decision_memory", "purpose": "Decisions / preferences / open loops.",
     "use_when": ["what did we decide", "standing preference", "open loops"],
     "do_not_use_when": ["free-text source search"], "read_write_class": "read_only",
     "safety_class": "bounded_read",
     "common_trigger_phrases": ["what did we decide", "decision", "preference", "open loop"],
     "primary_workflows": ["canonical_decision_retrieval", "canonical_preference_retrieval",
                           "canonical_open_loop_retrieval"],
     "preferred_before": ["assistant_navigation"], "fallback_after": [],
     "family_level_negative_instructions": ["prefer canonical records over source search for decisions"]},
    {"family_id": "assistant_review", "purpose": "Review queue overlay (read-only).",
     "use_when": ["what needs review"], "do_not_use_when": ["writing a disposition"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["review queue", "needs review"],
     "primary_workflows": ["quality_findings_review"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": []},
    {"family_id": "assistant_intelligence", "purpose": "Review-aware projections.",
     "use_when": ["projection", "intelligence view"], "do_not_use_when": ["writing"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["projection", "intelligence"],
     "primary_workflows": ["context_pack_retrieval"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": []},
    {"family_id": "assistant_research_packets", "purpose": "Citation-backed research packets.",
     "use_when": ["research packet", "cited answer context"], "do_not_use_when": ["writing a draft"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["research packet", "citations"],
     "primary_workflows": ["context_pack_retrieval"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["answer CONTEXT only, not a finished answer"]},
    {"family_id": "assistant_source_connector", "purpose": "Indexed NAS source-file discovery.",
     "use_when": ["find the source file", "locate a file"], "do_not_use_when": ["reindexing"],
     "read_write_class": "read_only", "safety_class": "bounded_read",
     "common_trigger_phrases": ["source file", "find the file", "locate"],
     "primary_workflows": ["source_file_search", "source_file_metadata_review"],
     "preferred_before": ["legacy_low_level"], "fallback_after": ["assistant_navigation"],
     "family_level_negative_instructions": ["no client-triggered source reindex/rebuild"]},
    {"family_id": "assistant_answer_drafts", "purpose": "Citation-safe answer drafts (read/advisory).",
     "use_when": ["draft an answer with citations"], "do_not_use_when": ["saving a file"],
     "read_write_class": "read_only", "safety_class": "advisory_only",
     "common_trigger_phrases": ["draft answer", "cited draft"],
     "primary_workflows": ["context_pack_retrieval"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["a draft is not a saved file — use client_output_workspace to save"]},
    {"family_id": "assistant_workflows", "purpose": "Workflow route contract handlers (read-only).",
     "use_when": ["what workflow applies"], "do_not_use_when": ["executing an action"],
     "read_write_class": "read_only", "safety_class": "advisory_only",
     "common_trigger_phrases": ["workflow", "route contract"],
     "primary_workflows": ["prompt_route"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": []},
    {"family_id": "assistant_feedback", "purpose": "Feedback review loop (advisory).",
     "use_when": ["feedback review"], "do_not_use_when": ["writing"], "read_write_class": "read_only",
     "safety_class": "advisory_only", "common_trigger_phrases": ["feedback"],
     "primary_workflows": ["feedback_review"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": []},
    {"family_id": "assistant_action_stages", "purpose": "Action staging (staging is not execution).",
     "use_when": ["stage an action"], "do_not_use_when": ["executing/sending"],
     "read_write_class": "read_only", "safety_class": "advisory_only",
     "common_trigger_phrases": ["action stage", "stage action"],
     "primary_workflows": ["action_stage_review"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["staging never executes; no send/email/calendar"]},
    {"family_id": "assistant_quality", "purpose": "Advisory quality evaluation.",
     "use_when": ["quality findings"], "do_not_use_when": ["repairing"], "read_write_class": "read_only",
     "safety_class": "advisory_only", "common_trigger_phrases": ["quality", "findings"],
     "primary_workflows": ["quality_findings_review"], "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["advisory only; never repairs/rebuilds"]},
    {"family_id": "artifact_workspace", "purpose": "Session capture → artifact proposals → review (staged).",
     "use_when": ["document this session", "capture decisions/preferences to memory"],
     "do_not_use_when": ["generating a work-product file"], "read_write_class": "staged_write",
     "safety_class": "staged_write_requires_review",
     "common_trigger_phrases": ["document this session", "remember this", "capture", "save to memory"],
     "primary_workflows": ["document_session", "stage_artifact_proposals", "review_artifact_proposals",
                           "revise_artifact_proposal"],
     "preferred_before": ["canonical_promotion"], "fallback_after": [],
     "family_level_negative_instructions": ["staging never writes the vault; promotion needs explicit approval"]},
    {"family_id": "canonical_promotion", "purpose": "Approved canonical promotion + Obsidian materialization.",
     "use_when": ["promote approved records to canonical memory"],
     "do_not_use_when": ["ordinary file exports"], "read_write_class": "canonical_write",
     "safety_class": "canonical_promotion_requires_explicit_approval",
     "common_trigger_phrases": ["promote", "make canonical", "finalize the decision record"],
     "primary_workflows": ["plan_canonical_promotion", "validate_canonical_promotion",
                           "apply_canonical_promotion", "inspect_promotion_receipt"],
     "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["requires server-minted approval + validation; never a broad vault write"]},
    {"family_id": "obsidian_materialization", "purpose": "Canonical card materialization into existing folders.",
     "use_when": ["as part of canonical promotion"], "do_not_use_when": ["generated work products"],
     "read_write_class": "canonical_write", "safety_class": "canonical_promotion_requires_explicit_approval",
     "common_trigger_phrases": ["obsidian card"], "primary_workflows": ["apply_canonical_promotion"],
     "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["no new top-level vault folder; existing folders only"]},
    {"family_id": "client_output_workspace", "purpose": "Generated work-product files (docx/xlsx/pdf/…/zip).",
     "use_when": ["generate/save/export/create a file", "make a Word doc", "build a spreadsheet/PDF/zip"],
     "do_not_use_when": ["saving canonical memory", "writing an Obsidian note"],
     "read_write_class": "staged_write", "safety_class": "staged_write_requires_review",
     "common_trigger_phrases": ["generate a", "save this as", "export", "create a file", "word document",
                                "excel", "spreadsheet", "pdf", "powerpoint", "zip"],
     "primary_workflows": ["generate_docx_output", "generate_xlsx_output", "generate_pdf_output",
                           "generate_pptx_output", "generate_markdown_output", "generate_csv_output",
                           "generate_json_output", "generate_html_output", "generate_zip_package"],
     "preferred_before": ["legacy_low_level"], "fallback_after": [],
     "family_level_negative_instructions": ["never route generated files to the vault, canonical promotion, "
                                            "or the low-level scratch writer"]},
    {"family_id": "output_receipts_manifests", "purpose": "Generated-output receipts + manifest + archive.",
     "use_when": ["where did the file go", "output receipt/manifest", "archive an output"],
     "do_not_use_when": ["generating a new file"], "read_write_class": "read_only",
     "safety_class": "bounded_read",
     "common_trigger_phrases": ["where did", "receipt", "output manifest", "list outputs", "archive"],
     "primary_workflows": ["list_generated_outputs", "inspect_generated_output_metadata",
                           "retrieve_generated_output_receipt", "archive_generated_output"],
     "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["prefer manifest/receipts before reading file bodies"]},
    {"family_id": "legacy_low_level", "purpose": "Legacy root/db/scratch tools (avoid; prefer semantic).",
     "use_when": ["only if a semantic tool is unavailable or explicitly requested"],
     "do_not_use_when": ["a semantic/preferred tool exists"], "read_write_class": "read_only",
     "safety_class": "bounded_read", "common_trigger_phrases": [],
     "primary_workflows": [], "preferred_before": [],
     "fallback_after": ["assistant_source_connector", "assistant_navigation"],
     "family_level_negative_instructions": ["prefer pa_output_*/assistant_* over hb_output_*/hb_root_*/hb_db_select"]},
    {"family_id": "blocked_deprecated", "purpose": "Denied/blocked tools.",
     "use_when": [], "do_not_use_when": ["always — these are blocked"], "read_write_class": "blocked",
     "safety_class": "blocked", "common_trigger_phrases": [], "primary_workflows": [],
     "preferred_before": [], "fallback_after": [],
     "family_level_negative_instructions": ["never call raw SQL, shell, exec, or absolute-path reads"]},
]

FAMILY_IDS: frozenset[str] = frozenset(f["family_id"] for f in FAMILIES)

_DENIED = frozenset({"raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"})
_STATUS = frozenset({"hb_mcp_status", "hb_data_freshness", "hb_queue_status", "hb_recent_failures",
                     "hb_last_successful_runs", "hb_capability_mode"})
_LEGACY = frozenset({"hb_db_select", "hb_root_list", "hb_root_stat", "hb_root_search", "hb_root_read_file",
                     "hb_root_read_excerpt", "hb_output_list", "hb_output_stat", "hb_output_read",
                     "hb_output_write_file", "hb_output_create_dir", "search_vault"})
_HELP = frozenset({"hb_assistant_catalog", "hb_assistant_tool_help", "hb_assistant_tool_query"})
# assistant_ group → family_id (group label from ASSISTANT_TOOL_GROUPS)
_GROUP_FAMILY = {
    "nav": "assistant_navigation", "context_packs": "assistant_context_packs", "memory": "assistant_memory",
    "decision_memory": "assistant_decision_memory", "review": "assistant_review",
    "intelligence": "assistant_intelligence", "research_packets": "assistant_research_packets",
    "source_connector": "assistant_source_connector", "answer_drafts": "assistant_answer_drafts",
    "workflows": "assistant_workflows", "feedback": "assistant_feedback",
    "action_stages": "assistant_action_stages", "quality": "assistant_quality",
    # Source-structure map/route tools share the NAS source-discovery family (keeps family_for_tool
    # total without adding a family). Default-off, so absent from the live surface until enabled.
    "source_structure": "assistant_source_connector",
}
_OUTPUT_READS = frozenset({"pa_output_list", "pa_output_metadata", "pa_output_read_excerpt",
                           "pa_output_receipt_get", "pa_output_manifest_get", "pa_output_archive_plan",
                           "pa_output_zip_inspect"})
_OUTPUT_WRITES = frozenset({"pa_output_stage", "pa_output_commit", "pa_output_archive_commit"})
# Explicit tool→family (must not fall through to assistant_navigation).
_DECISION_MEMORY = frozenset({
    "assistant_get_decision", "assistant_list_decisions", "assistant_get_preference",
    "assistant_list_preferences", "assistant_list_open_loops", "assistant_get_open_loop",
})
_NAV_EXPLICIT = frozenset({
    "assistant_search_sources", "assistant_search_cards", "assistant_get_vault_note",
    "assistant_get_source", "assistant_get_card_for_source", "assistant_get_source_for_card",
    "assistant_get_card_state", "assistant_list_stale_cards", "assistant_list_duplicate_cards",
    "assistant_list_ambiguous_card_links", "assistant_recent_changes", "assistant_get_related_sources",
})


def family_for_tool(name: str, group: str | None = None) -> str:
    """Map a live tool to exactly one family_id (total function — always returns a valid family)."""
    if name in _DENIED:
        return "blocked_deprecated"
    if name in _STATUS:
        return "status_health"
    if name in _HELP:
        return "tool_catalog_help_query"
    if name.startswith("pa_prompt_") or name in ("pa_tool_family_get", "pa_workflow_recipe_get",
                                                  "pa_tool_surface_freshness_check",
                                                  "pa_tool_surface_runtime_attestation"):
        return "prompt_routing"
    if name.startswith("pa_tool_manifest"):
        return "client_tool_manifest"
    if name in _OUTPUT_WRITES:
        return "client_output_workspace"
    if name in _OUTPUT_READS:
        return "output_receipts_manifests"
    if name in ("pa_artifact_promotion_apply", "ai_outputs_card_upsert"):
        return "canonical_promotion"
    if name.startswith(("pa_session_", "pa_artifact_")) or name == "pa_vault_path_resolve":
        # staging/review/plan/validate/list/get all belong to the artifact workspace family
        return "artifact_workspace"
    if name in _DECISION_MEMORY:
        return "assistant_decision_memory"
    if name in _NAV_EXPLICIT:
        return "assistant_navigation"
    if name in _LEGACY:
        return "legacy_low_level"
    if group and group in _GROUP_FAMILY:
        return _GROUP_FAMILY[group]
    # Prefer explicit group mapping over bare assistant_ fallback.
    if name.startswith("assistant_") and group is None:
        # Unknown assistant tool without group — still classify, but parity tests should prefer
        # explicit membership lists above.
        return "assistant_navigation"
    if name.startswith("assistant_"):
        return "assistant_navigation"
    return "legacy_low_level"


def family_record(family_id: str) -> dict[str, Any] | None:
    return next((f for f in FAMILIES if f["family_id"] == family_id), None)
