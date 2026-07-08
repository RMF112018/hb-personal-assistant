"""N8C-23 vault path resolver — route a canonical artifact into the EXISTING vault structure.

Deterministic routing by (artifact_type, domain) into folders that already exist. NEVER creates a new
top-level taxonomy (``Second Brain/Canonical/`` and friends are refused). The pure ``resolve_relative_path``
is safe by construction (server-generated); ``resolve_write_path`` additionally validates against a live
vault via the existing obsidian_mcp path guards before any write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .llm_chat_templates import sanitize_filename_title

# The existing top-level vault folders (Part 5). A resolved path's first segment MUST be one of these — a new
# top-level folder is refused. This is the guard against a broad new taxonomy.
EXISTING_TOP_LEVEL_FOLDERS: frozenset[str] = frozenset(
    {
        "00 Inbox", "90 Archive", "99 System", "AI Outputs", "Attachments", "Daily",
        "Email Archive", "Home", "MOCs", "Source Notes", "Templates", "Work",
    }
)

# (artifact_type, domain_class) -> destination folder. domain_class ∈ {work, home, shared, system, any}.
# Home/personal collapses to "home". Unknown domains fall back to the "any" row, then a safe Inbox default.
_ROUTING: dict[tuple[str, str], str] = {
    ("session_note", "any"): "00 Inbox",
    ("decision", "work"): "Work/03 Decisions",
    ("decision", "home"): "Home/01 Personal Admin",
    ("preference", "work"): "Work/07 Knowledge",
    ("preference", "home"): "Home/01 Personal Admin",
    ("open_loop", "work"): "Work/04 Actions",
    ("open_loop", "home"): "Home/01 Personal Admin",
    ("workflow", "work"): "Work/07 Knowledge",
    ("workflow", "home"): "Home/07 Learning",
    ("research_packet", "work"): "Work/07 Knowledge",
    ("research_packet", "home"): "Home/07 Learning",
    ("answer_draft", "any"): "AI Outputs",
    ("architecture_note", "work"): "Work/07 Knowledge",
    ("architecture_note", "home"): "Home/07 Learning",
    ("source_card_annotation", "work"): "Source Notes/Work",
    ("source_card_annotation", "home"): "Source Notes/Home",
    ("source_card_annotation", "shared"): "Source Notes/Shared",
    ("person_note", "work"): "Work/05 People",
    ("person_note", "home"): "Home/08 People",
    ("company_note", "work"): "Work/06 Companies",
    ("project_context", "work"): "Work/01 Projects",
    ("review_item", "any"): "Work/07 Knowledge",
    ("quality_finding", "any"): "99 System/Receipts",
    ("feedback", "any"): "Work/07 Knowledge",
    ("action_stage", "work"): "Work/04 Actions",
    ("action_stage", "home"): "Home/01 Personal Admin",
    ("knowledge_note", "work"): "Work/07 Knowledge",
    ("knowledge_note", "home"): "Home/07 Learning",
}

# System destinations (Part 13) — receipts / manifests / runbooks live under 99 System.
RECEIPTS_FOLDER = "99 System/Receipts"
MANIFESTS_FOLDER = "99 System/Manifests"
RUNBOOKS_FOLDER = "99 System/Runbooks"

_DEFAULT_FOLDER = "00 Inbox"


@dataclass(frozen=True)
class ResolvedVaultPath:
    resolved_relative_path: str
    folder: str
    filename: str
    path_warnings: tuple[str, ...]


def _domain_class(domain: str | None) -> str:
    d = (domain or "").strip().lower()
    if d in {"work"}:
        return "work"
    if d in {"home", "personal", "home/personal"}:
        return "home"
    if d in {"shared"}:
        return "shared"
    if d in {"system"}:
        return "system"
    return "any"


def _route_folder(artifact_type: str, domain: str | None) -> tuple[str, tuple[str, ...]]:
    dc = _domain_class(domain)
    warnings: list[str] = []
    for key in ((artifact_type, dc), (artifact_type, "any"), (artifact_type, "work")):
        if key in _ROUTING:
            return _ROUTING[key], tuple(warnings)
    warnings.append(f"no_route_for:{artifact_type}/{dc}:defaulted_to_inbox")
    return _DEFAULT_FOLDER, tuple(warnings)


def resolve_relative_path(
    *,
    artifact_type: str,
    domain: str | None,
    canonical_id: str,
    title: str,
    operator_override_path: str | None = None,
) -> ResolvedVaultPath:
    """Deterministic, pure routing → a vault-relative path under an EXISTING top-level folder.

    Refuses (raises ValueError) an override that introduces a new top-level folder, is absolute, or traverses.
    """
    warnings: list[str] = []
    if operator_override_path:
        rel = operator_override_path.strip().replace("\\", "/").strip("/")
        if not rel or rel.startswith("/") or ".." in rel.split("/"):
            raise ValueError(f"unsafe_override_path:{operator_override_path}")
        top = rel.split("/", 1)[0]
        if top not in EXISTING_TOP_LEVEL_FOLDERS:
            raise ValueError(f"override_introduces_new_top_level_folder:{top}")
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        filename = rel.rsplit("/", 1)[-1]
        if not filename.endswith(".md"):
            filename = f"{filename}.md"
        rel_path = f"{folder}/{filename}" if folder else filename
        return ResolvedVaultPath(rel_path, folder or top, filename, ("operator_override",))

    folder, route_warnings = _route_folder(artifact_type, domain)
    warnings.extend(route_warnings)
    top = folder.split("/", 1)[0]
    if top not in EXISTING_TOP_LEVEL_FOLDERS:  # defense in depth — routing table must stay in-structure
        raise ValueError(f"route_introduces_new_top_level_folder:{top}")
    safe_title = sanitize_filename_title(title)
    filename = f"{canonical_id} - {safe_title}.md"
    rel_path = f"{folder}/{filename}"
    return ResolvedVaultPath(rel_path, folder, filename, tuple(warnings))


def resolve_write_path(config: Any, resolved: ResolvedVaultPath) -> dict[str, Any]:
    """Validate a resolved relative path against a LIVE vault (traversal/outside-root/hidden/protected).

    Reuses the existing obsidian_mcp guards. Returns bounded metadata; raises on any unsafe path.
    """
    from .pathsafe import path_blocked  # noqa: PLC0415
    from .tools import resolve_safe_path  # noqa: PLC0415

    rel = resolved.resolved_relative_path
    if path_blocked(rel, include_hidden=True):
        raise ValueError(f"path_blocked:{rel}")
    safe = resolve_safe_path(config, rel)  # raises on absolute / traversal / outside vault root
    top = rel.split("/", 1)[0]
    if top not in EXISTING_TOP_LEVEL_FOLDERS:
        raise ValueError(f"path_introduces_new_top_level_folder:{top}")
    return {
        "resolved_relative_path": rel,
        "resolved_absolute_path": str(safe.path),
        "destination_exists": safe.path.exists(),
        "requires_directory_creation": not safe.path.parent.exists(),
        "path_warnings": list(resolved.path_warnings),
    }
