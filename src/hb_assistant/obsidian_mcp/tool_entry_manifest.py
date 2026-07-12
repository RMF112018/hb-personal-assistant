"""Prompt Preflight — per-tool routing ENTRY records (durable routing source).

A tool entry joins the live tool surface (name + group) to its family, read/write class, safety class, and
seed guidance (use_when / do_not_use_when / replacement / examples). Entries are built from the live tool
list so the freshness guard can prove every registered tool has an entry. Organization-neutral.
"""

from __future__ import annotations

from typing import Any

from .tool_family_manifest import family_for_tool, family_record

# Per-tool seed overrides for the tools where routing guidance matters most. Everything else gets a
# derived-from-family default. Keys are tool names.
TOOL_ENTRY_OVERRIDES: dict[str, dict[str, Any]] = {
    "pa_output_stage": {
        "use_when": "First step to generate any work-product file (docx/xlsx/pdf/pptx/md/csv/json/html/zip).",
        "do_not_use_when": "Writing canonical memory or an Obsidian note.",
        "replacement_for": ["hb_output_write_file"],
        "examples": ["Generate a Word doc and save it", "Make a PDF report"],
    },
    "pa_output_commit": {
        "use_when": "Commit a staged output using the server-minted approval id.",
        "do_not_use_when": "Before staging, or with an invented approval id.",
        "examples": ["Save the staged document"],
    },
    "pa_output_archive_commit": {
        "use_when": "Move a committed output to 90 Archive using the plan's approval id (never deletes).",
        "do_not_use_when": "Deleting a file (deletion is not offered).",
    },
    "pa_output_cancel": {
        "use_when": "Terminally cancel a staged (never-committed) output using its staging approval id.",
        "do_not_use_when": "Cancelling a committed/archived output (those move forward, never back).",
        "examples": ["Discard the staged draft I no longer need"],
    },
    "hb_output_write_file": {
        "use_when": "Legacy/internal scratch only; hard-denied remotely.",
        "do_not_use_when": "Any connected-client generated file — use pa_output_stage/commit instead.",
        "deprecated": True, "replaced_by": ["pa_output_stage", "pa_output_commit"],
    },
    "hb_output_create_dir": {
        "use_when": "Legacy/internal scratch only.", "do_not_use_when": "Connected-client output.",
        "deprecated": True, "replaced_by": ["pa_output_stage"],
    },
    "pa_artifact_promotion_apply": {
        "purpose": "Apply an approved canonical promotion bundle to Obsidian decision, preference, or open-loop cards.",
        "use_when": "Apply an approved canonical promotion to Obsidian cards.",
        "do_not_use_when": "Ordinary file exports — use pa_output_* instead.",
        "examples": ["Promote the decision record to canonical memory"],
        "common_failure_modes": ["missing operator_approval_id", "promotion_not_validated"],
    },
    "pa_session_capture_stage": {
        "purpose": "Capture a session summary before staging artifact proposals for review.",
        "use_when": "Capture a session before staging artifact proposals.",
        "do_not_use_when": "Generating a work-product file.",
        "examples": ["Document this session", "Remember what we decided"],
    },
    "hb_db_select": {
        "use_when": "Legacy low-level DB read; prefer semantic assistant_* tools.",
        "do_not_use_when": "A semantic tool exists.", "deprecated": True,
    },
    "hb_root_search": {
        "use_when": "Legacy low-level file search; prefer assistant_source_file_search.",
        "do_not_use_when": "A semantic source-connector tool is available.", "deprecated": True,
        "replaced_by": ["assistant_source_file_search"],
    },
    "hb_assistant_tool_query": {
        "use_when": "Invoke one allowlisted tool by name when direct exposure is unavailable.",
        "do_not_use_when": "A directly exposed read tool suffices, or you need routing advice first.",
        "examples": ["Call assistant_list_decisions through the gateway"],
    },
    "hb_mcp_status": {
        "purpose": "Report MCP server health, capability mode, and queue status without reading content.",
        "use_when": "Check whether the server and tool profiles are up before other calls.",
        "do_not_use_when": "Searching vault notes or NAS source files.",
        "examples": ["Is the server up?"],
    },
    "assistant_source_file_search": {
        "purpose": "Search indexed NAS source file contents and filenames; not for Obsidian vault notes.",
        "use_when": "Find project documents, PDFs, contracts, or work files on indexed NAS roots.",
        "do_not_use_when": "Vault note search — use assistant_search_sources instead.",
        "examples": ["Search my work files for budget", "Find the original PDF contract"],
        "common_failure_modes": ["missing query", "unknown source_root_key"],
    },
    "assistant_source_file_metadata": {
        "purpose": "Inspect metadata for one indexed source file before a bounded read.",
        "use_when": "You have a source_id from search and need trust/size/type details first.",
        "do_not_use_when": "Broad file discovery — search with assistant_source_file_search first.",
        "examples": ["Show metadata for the matched source file"],
    },
    "assistant_source_file_read": {
        "purpose": (
            "Read a bounded excerpt from one trusted indexed NAS source file; not complete-file "
            "retrieval. Requires a safe root and an exact selected file; the excerpt may be truncated or "
            "fall back to the indexed excerpt."
        ),
        "use_when": (
            "You selected an exact source_id/path from search on a safe root and need a short verbatim "
            "excerpt to confirm content."
        ),
        "do_not_use_when": (
            "The root is not trusted, you need the whole file, or you only need file details "
            "(use assistant_source_file_metadata) or discovery (use assistant_source_file_search)."
        ),
        "examples": ["Read the top of the matched contract PDF", "Show the first lines of the selected file"],
        "common_failure_modes": [
            "untrusted / unready root (blocked_root_unready)",
            "unsupported binary type",
            "excerpt truncated at the bounded limit",
            "indexed-excerpt fallback when a live read is unavailable",
        ],
    },
    "assistant_search_sources": {
        "purpose": "Search Obsidian vault notes and indexed source cards by query; not NAS file bodies.",
        "use_when": "Find vault meeting notes, project notes, or generated cards.",
        "do_not_use_when": "Indexed NAS work-file search — use assistant_source_file_search.",
        "examples": ["Search the vault for meeting notes", "Find notes in obsidian"],
    },
    "assistant_search_cards": {
        "purpose": "Search generated source-linked cards when assistant_search_sources is too broad.",
        "use_when": "Narrow vault/card discovery after an initial assistant_search_sources pass.",
        "do_not_use_when": "NAS source file discovery.",
        "examples": ["Search cards about the schedule baseline"],
    },
    "assistant_get_vault_note": {
        "purpose": "Read one vault note by path after search narrowed candidates.",
        "use_when": "You selected a note path from assistant_search_sources or assistant_search_cards.",
        "do_not_use_when": "You still need discovery — search first.",
        "examples": ["Open the vault note at the selected path"],
    },
    "assistant_list_decisions": {
        "purpose": "List canonical decision records with optional topical query filter before get-by-id.",
        "use_when": "Discover which decision to retrieve when no decision_id is known.",
        "do_not_use_when": "You already have decision_id — call assistant_get_decision directly.",
        "examples": ["What did we decide about X?", "List decisions about budget"],
        "common_failure_modes": ["empty bounded list — refine query or list without filter"],
    },
    "assistant_get_decision": {
        "purpose": "Fetch one canonical decision record by decision_id.",
        "use_when": "You have a validated decision_id from list or promotion receipt.",
        "do_not_use_when": "Topic-only discovery — list with assistant_list_decisions first.",
        "examples": ["Get decision DEC-20260708-7847F4"],
        "common_failure_modes": ["missing decision_id", "decision_not_found"],
    },
    "assistant_list_preferences": {
        "purpose": "List standing preference records with optional topical query filter.",
        "use_when": "Discover preferences when no preference_id is known.",
        "do_not_use_when": "You already have preference_id — call assistant_get_preference.",
        "examples": ["What preferences do I have for budgeting?"],
    },
    "assistant_get_preference": {
        "purpose": "Fetch one canonical preference record by preference_id.",
        "use_when": "You have a validated preference_id.",
        "do_not_use_when": "Topic-only discovery — list with assistant_list_preferences first.",
        "examples": ["Retrieve preference PREF-20260708-2D3D8D"],
        "common_failure_modes": ["missing preference_id"],
    },
    "assistant_list_open_loops": {
        "purpose": "List unresolved open-loop records with optional topical query filter.",
        "use_when": "See what remains pending without a known open_loop_id.",
        "do_not_use_when": "You already have open_loop_id — call assistant_get_open_loop.",
        "examples": ["What open loops remain?", "List open loops about scheduling"],
    },
    "assistant_get_open_loop": {
        "purpose": "Fetch one canonical open-loop record by open_loop_id.",
        "use_when": "You have a validated open_loop_id.",
        "do_not_use_when": "Topic-only discovery — list with assistant_list_open_loops first.",
        "examples": ["Retrieve open loop LOOP-20260708-B21D38"],
        "common_failure_modes": ["missing open_loop_id"],
    },
    "pa_artifact_proposal_stage": {
        "purpose": "Stage artifact proposals for operator review from a captured session.",
        "use_when": "Submit structured candidates after pa_session_capture_stage.",
        "do_not_use_when": "Generating a standalone client output file — use pa_output_stage.",
        "examples": ["Stage this for review", "Submit for review"],
        "common_failure_modes": ["missing session_id", "missing candidate_artifacts"],
    },
    # Source-Structure Layered Index (default-off group). These return bounded, root-relative MAPS of
    # the precomputed index; they never read file contents. For actual file discovery/reads, follow up
    # with assistant_source_file_search / assistant_source_file_read (named in use_when/do_not_use_when).
    "assistant_source_root_map": {
        "use_when": "First step to choose WHICH NAS root to search for a query (routes by family, "
                    "downranks backups/generated output).",
        "do_not_use_when": "You already know the folder — use assistant_source_folder_map or "
                           "assistant_source_file_search to find files.",
    },
    "assistant_source_folder_map": {
        "use_when": "List candidate folders under a root/project with classification (doc family, "
                    "trust, noise) before searching for files.",
        "do_not_use_when": "Reading file contents or listing actual files — use "
                           "assistant_source_file_search then assistant_source_file_read.",
    },
    "assistant_source_folder_summary": {
        "use_when": "Inspect one folder's classification, child mix, and routing warnings by folder_id.",
        "do_not_use_when": "Enumerating files in the folder — use assistant_source_file_search.",
    },
    "assistant_source_search_route": {
        "use_when": "Ask WHERE to look for a project/doc-family query; returns preferred + avoided "
                    "roots and candidate folders.",
        "do_not_use_when": "Performing the actual file search — follow up with "
                           "assistant_source_file_search / assistant_source_file_read.",
    },
    "assistant_source_scope_explain": {
        "use_when": "Explain why a root/folder is preferred, downranked, or off-limits (trust + policy).",
        "do_not_use_when": "Searching for or reading files.",
    },
    "assistant_source_project_map": {
        "use_when": "Map a project number to its candidate folders and document-family coverage.",
        "do_not_use_when": "Reading a specific document — use assistant_source_file_read.",
    },
    "assistant_source_quality": {
        "use_when": "Review advisory index-quality findings (duplicates, low confidence, partial "
                    "project numbers) before trusting routing.",
        "do_not_use_when": "Searching or reading source files.",
    },
}


def build_tool_entry(name: str, group: str | None = None) -> dict[str, Any]:
    """Build one per-tool routing entry (total — always returns a record)."""
    from .canonical_tool_specs import classify_tool  # noqa: PLC0415

    family_id = family_for_tool(name, group)
    fam = family_record(family_id) or {}
    _tool_class, safety_class, read_write_class = classify_tool(name, group)
    seed = TOOL_ENTRY_OVERRIDES.get(name, {})
    return {
        "tool_name": name,
        "tool_group": group,
        "tool_family": family_id,
        "read_write_class": read_write_class,
        "safety_class": safety_class,
        "use_when": seed.get("use_when", ""),
        "do_not_use_when": seed.get("do_not_use_when", ""),
        "deprecated": bool(seed.get("deprecated", False)),
        "replaced_by": seed.get("replaced_by", []),
        "replacement_for": seed.get("replacement_for", []),
        "examples": seed.get("examples", []),
    }


def build_tool_entries(tool_groups: dict[str, str | None]) -> list[dict[str, Any]]:
    """Build entries for every (name -> group) in ``tool_groups``."""
    return [build_tool_entry(name, group) for name, group in sorted(tool_groups.items())]
