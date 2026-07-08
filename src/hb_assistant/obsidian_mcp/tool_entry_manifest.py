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
