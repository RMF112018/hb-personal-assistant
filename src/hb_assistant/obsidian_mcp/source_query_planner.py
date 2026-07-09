"""Deterministic source query planner for connected clients.

Classifies source-related prompts into intents and recommends tool sequences.
No LLM, no filesystem, no DB writes. Pure routing/planning.
"""

from __future__ import annotations

import re
from typing import Any

from .source_project_number import query_project_candidates

# Intent classes for source planning (distinct from prompt-preflight destructive routes).
INTENT_FIND_FILE = "find_specific_file"
INTENT_FIND_PROJECT = "find_project"
INTENT_MAP_ROOT = "map_source_root"
INTENT_MAP_PROJECT = "map_project_folder"
INTENT_LIST_CHILDREN = "list_folder_children"
INTENT_SUMMARIZE = "summarize_folder"
INTENT_ANSWER_KNOWN = "answer_from_known_file"
INTENT_ANSWER_MULTI = "answer_from_multiple_files"
INTENT_COMPARE = "compare_documents"
INTENT_RECENT = "find_recent_files"
INTENT_MISSING = "find_expected_missing_files"
INTENT_UNSUPPORTED = "read_unsupported_file"
INTENT_HEALTH = "source_index_health"
INTENT_VAULT = "vault_search"
INTENT_OUTPUT = "generated_output"
INTENT_DESTRUCTIVE = "destructive_source_refusal"
INTENT_ARBITRARY_WRITE = "arbitrary_path_write_refusal"
INTENT_SECRET = "secret_extraction_refusal"
INTENT_UNKNOWN = "unknown"

_UNSUPPORTED_EXTS = (".xer", ".mpp", " xer", "primavera", "p6 schedule file")
_MAP_CUES = ("map ", "map the", "folder structure", "tree under", "show me the folder",
             "what's in the", "what is in the", "structure under", "explore the")
_ROOT_CUES = ("source root", "2023 projects", "work root", "nas work", "roots list")
_HEALTH_CUES = ("source index", "index fresh", "is my source", "index health", "fresh enough")
_RECENT_CUES = ("latest", "most recent", "recently modified", "newest")
_MISSING_CUES = ("missing from", "expected closeout", "what files are missing")
_OUTPUT_CUES = ("markdown output", "create a markdown", "save as docx", "generated output",
                "temporary zip", "create a temporary", "export to pdf", "save as csv")
_VAULT_CUES = ("search my vault", "vault decisions", "obsidian", "in the vault")
_DESTRUCTIVE_CUES = ("delete this source", "delete the tropical", "remove the folder",
                     "wipe the source", "destroy the project folder")
_ARBITRARY_WRITE = ("write a file to /tmp", "write to /tmp", "/tmp/anything", "save to /etc/")
_SECRET_CUES = ("show me secrets", "show tokens", "extract password", "dump credentials",
                "api keys")


def _norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def plan_source_query(prompt: str, *, freshness: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a bounded deterministic plan for a natural-language source prompt."""
    prompt_l = _norm(prompt)
    projects = query_project_candidates(prompt)
    # Also catch project numbers embedded in longer prompts
    if not projects:
        from .source_project_number import normalize_project_number  # noqa: PLC0415

        n, c, _ = normalize_project_number(prompt, allow_compact=False)
        if n and c >= 0.35:
            projects = [n]

    # Safety short-circuits first
    if any(c in prompt_l for c in _SECRET_CUES):
        return _refusal(prompt, INTENT_SECRET, "Refuse secret/token extraction.", projects)
    if any(c in prompt_l for c in _ARBITRARY_WRITE):
        return _refusal(prompt, INTENT_ARBITRARY_WRITE,
                        "Refuse arbitrary host path writes; use generated-output workspace only.",
                        projects)
    if any(c in prompt_l for c in _DESTRUCTIVE_CUES):
        return _refusal(prompt, INTENT_DESTRUCTIVE,
                        "Refuse destructive source-folder ops; prefer reversible vault archive plans only.",
                        projects)
    if any(c in prompt_l for c in _OUTPUT_CUES) or (
        "create" in prompt_l and any(x in prompt_l for x in ("markdown", "docx", "zip", "pdf", "xlsx"))
    ):
        return _plan(
            prompt, INTENT_OUTPUT, 0.85, projects,
            tools=["pa_output_stage", "pa_output_commit", "assistant_output_stage", "assistant_output_commit"],
            layers=["route_only"], rank="n/a",
            rationale="Generated-file request → client output workspace (staged write).",
            fallback="Do not write to vault or arbitrary host paths.",
        )
    if any(c in prompt_l for c in _VAULT_CUES):
        return _plan(
            prompt, INTENT_VAULT, 0.8, projects,
            tools=["search_vault", "assistant_search_sources", "vault_dataview_query"],
            layers=["metadata_discovery"], rank="vault",
            rationale="Vault-scoped request — do not use NAS source file search as primary.",
            fallback="If vault miss, clarify whether NAS source was intended.",
        )
    if any(c in prompt_l for c in _HEALTH_CUES):
        return _plan(
            prompt, INTENT_HEALTH, 0.9, projects,
            tools=["assistant_source_index_health", "assistant_source_status", "assistant_source_quality"],
            layers=["route_only"], rank="n/a",
            rationale="Freshness/health question about the source index.",
            fallback="hb_data_freshness for cross-domain status.",
        )
    if any(x in prompt_l for x in _UNSUPPORTED_EXTS) or "read this xer" in prompt_l:
        return _plan(
            prompt, INTENT_UNSUPPORTED, 0.9, projects,
            tools=["assistant_source_file_search", "assistant_source_file_metadata",
                   "assistant_source_file_read"],
            layers=["metadata_discovery"], rank="project_path_then_fts",
            rationale="Unsupported schedule/binary type — discover + metadata only; do not invent content.",
            fallback="Show nearby readable siblings via metadata neighbors.",
        )
    if any(c in prompt_l for c in _MISSING_CUES):
        return _plan(
            prompt, INTENT_MISSING, 0.7, projects,
            tools=["assistant_source_project_map", "assistant_source_folder_map",
                   "assistant_source_folder_summary", "assistant_source_files_list"],
            layers=["metadata_discovery"], rank="folder_authority",
            rationale="Expected-missing inventory — map folder then list children; never invent files.",
            fallback="assistant_source_query_plan with project number.",
        )
    if "folder structure" in prompt_l or "children of" in prompt_l or (
        "under the" in prompt_l and "folder" in prompt_l
    ) or "structure under" in prompt_l:
        return _plan(
            prompt, INTENT_LIST_CHILDREN, 0.85, projects,
            tools=["assistant_source_folder_map", "assistant_source_files_list"],
            layers=["metadata_discovery"], rank="structure_map",
            rationale="List folder children / tree under a folder.",
            fallback="assistant_source_project_map then folder_map.",
        )
    if any(c in prompt_l for c in _ROOT_CUES) or re.search(r"\b20\d{2} projects\b", prompt_l):
        return _plan(
            prompt, INTENT_MAP_ROOT, 0.85, projects,
            tools=["assistant_source_root_map", "assistant_source_folder_map", "assistant_source_scope_explain"],
            layers=["metadata_discovery"], rank="structure_map",
            rationale="Root-level inventory request.",
            fallback="assistant_source_roots_list for file-index roots.",
        )
    if any(c in prompt_l for c in _MAP_CUES) or "map the project" in prompt_l:
        if projects or "project" in prompt_l:
            return _plan(
                prompt, INTENT_MAP_PROJECT, 0.9, projects,
                tools=["assistant_source_query_plan", "assistant_source_project_map",
                       "assistant_source_folder_map", "assistant_source_folder_summary"],
                layers=["metadata_discovery"], rank="structure_map",
                rationale="Project/folder map request — use structure map tools, not file search only.",
                fallback="assistant_source_root_map then folder_map.",
            )
        return _plan(
            prompt, INTENT_MAP_ROOT, 0.85, projects,
            tools=["assistant_source_root_map", "assistant_source_folder_map"],
            layers=["metadata_discovery"], rank="structure_map",
            rationale="Source root exploration — map roots/folders first.",
            fallback="assistant_source_search_route.",
        )
    if "summarize" in prompt_l and "folder" in prompt_l:
        return _plan(
            prompt, INTENT_SUMMARIZE, 0.8, projects,
            tools=["assistant_source_folder_summary", "assistant_source_folder_map"],
            layers=["metadata_discovery"], rank="structure_map",
            rationale="Folder rollup/summary request.",
            fallback="assistant_source_project_map.",
        )
    if any(c in prompt_l for c in _RECENT_CUES) and any(
        w in prompt_l for w in ("schedule", "file", "update", "document", "pdf")
    ):
        return _plan(
            prompt, INTENT_RECENT, 0.8, projects,
            tools=["assistant_source_file_search", "assistant_source_file_metadata"],
            layers=["candidate_triage"], rank="project_path_recency_fts",
            rationale="Latest/recent source file lookup with multi-stage ranking.",
            fallback="assistant_source_project_map then files_list.",
        )
    if "compare" in prompt_l and any(w in prompt_l for w in ("document", "file", "pdf", "version")):
        return _plan(
            prompt, INTENT_COMPARE, 0.7, projects,
            tools=["assistant_source_file_search", "assistant_source_file_metadata",
                   "assistant_source_file_read"],
            layers=["candidate_triage", "bounded_read"], rank="project_path_then_fts",
            rationale="Compare documents — triage then bounded read of selected files only.",
            fallback="assistant_source_project_map.",
        )
    if (projects or any(n in prompt_l for n in ("tropical", "project "))) and any(
        w in prompt_l for w in ("find", "search", "files for", "billing", "pdf", "schedule")
    ):
        return _plan(
            prompt, INTENT_FIND_PROJECT if (projects or "project" in prompt_l or "billing" in prompt_l) else INTENT_FIND_FILE,
            0.85, projects,
            tools=["assistant_source_query_plan", "assistant_source_project_map",
                   "assistant_source_file_search", "assistant_source_file_metadata"],
            layers=["metadata_discovery", "candidate_triage"], rank="project_path_filename_content_fts",
            rationale="Project-number / project-file search with normalized project matching.",
            fallback="assistant_source_search_route then file_search.",
        )
    if any(w in prompt_l for w in ("find", "search", "look for", "locate")):
        return _plan(
            prompt, INTENT_FIND_FILE, 0.7, projects,
            tools=["assistant_source_file_search", "assistant_source_file_metadata"],
            layers=["candidate_triage"], rank="project_path_filename_content_fts",
            rationale="Generic source file search.",
            fallback="assistant_source_search_route.",
        )

    return _plan(
        prompt, INTENT_UNKNOWN, 0.3, projects,
        tools=["assistant_source_query_plan", "assistant_source_index_health"],
        layers=["route_only"], rank="n/a",
        rationale="Could not confidently classify source intent.",
        fallback="Ask clarifying question before deep search.",
    )


def _freshness_caveats(freshness: dict[str, Any] | None) -> list[str]:
    if not freshness:
        return ["Confirm source index freshness via assistant_source_index_health before high-stakes answers."]
    caveats: list[str] = []
    if freshness.get("stale") or freshness.get("write_blocked_by_staleness"):
        caveats.append("Tool surface or data may be stale — prefer health check first.")
    return caveats or ["No freshness flags provided; still prefer health for broad NAS answers."]


def _plan(
    prompt: str,
    intent: str,
    confidence: float,
    projects: list[str],
    *,
    tools: list[str],
    layers: list[str],
    rank: str,
    rationale: str,
    fallback: str,
    root_scope: str | None = None,
) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "intent": intent,
        "confidence": confidence,
        "detected_root_scope": root_scope,
        "detected_project_numbers": projects,
        "normalized_search_terms": _terms(prompt, projects),
        "candidate_folder_scope": None,
        "search_layers": layers,
        "ranking_strategy": rank,
        "fallback_strategy": fallback,
        "recommended_tool_sequence": tools,
        "safety_freshness_caveats": [
            "Never return absolute host paths.",
            "Never invent content for unsupported files.",
            "Do not write outside staged output / vault plan tools.",
            "Confirm source index freshness via assistant_source_index_health before high-stakes answers.",
        ],
        "routing_rationale": rationale,
        "preflight_is_read_only": True,
    }


def _refusal(prompt: str, intent: str, reason: str, projects: list[str]) -> dict[str, Any]:
    return {
        "prompt": prompt,
        "intent": intent,
        "confidence": 0.95,
        "detected_root_scope": None,
        "detected_project_numbers": projects,
        "normalized_search_terms": [],
        "candidate_folder_scope": None,
        "search_layers": ["route_only"],
        "ranking_strategy": "n/a",
        "fallback_strategy": "Refuse; offer safe advisory alternative only.",
        "recommended_tool_sequence": [],
        "safety_freshness_caveats": [reason, "Never execute destructive or secret-exposing tools."],
        "routing_rationale": reason,
        "preflight_is_read_only": True,
        "refused": True,
    }


def _terms(prompt: str, projects: list[str]) -> list[str]:
    terms = list(projects)
    for tok in re.split(r"[^\w.\-]+", prompt):
        t = tok.strip()
        if len(t) >= 3 and t.lower() not in {"the", "and", "for", "find", "show", "map", "this", "that"}:
            if t not in terms:
                terms.append(t)
        if len(terms) >= 12:
            break
    return terms
