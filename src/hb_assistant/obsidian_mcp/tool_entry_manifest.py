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
        "use_when": "Apply an approved canonical promotion to Obsidian cards.",
        "do_not_use_when": "Ordinary file exports — use pa_output_* instead.",
        "examples": ["Promote the decision record to canonical memory"],
    },
    "pa_session_capture_stage": {
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
    family_id = family_for_tool(name, group)
    fam = family_record(family_id) or {}
    seed = TOOL_ENTRY_OVERRIDES.get(name, {})
    return {
        "tool_name": name,
        "tool_group": group,
        "tool_family": family_id,
        "read_write_class": fam.get("read_write_class", "read_only"),
        "safety_class": fam.get("safety_class", "safe_read"),
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
