"""Read-only orchestration for the source-structure index (API + MCP clients).

Every method returns bounded, curated dicts built from whitelisted fields — root-relative
``rel_path`` + opaque ``folder_id`` only, never an absolute host path. This is the single surface
API routes and MCP tools call; it performs no filesystem access and no live scan.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.obsidian_mcp.source_structure_models import (
    MAX_HINTS,
    StructureCursor,
    clamp_limit,
)
from hb_assistant.obsidian_mcp.source_structure_repository import (
    SourceStructureRepository,
    folder_id_for,
)

# query_family → (preferred root classes, avoided root classes, note)
_FAMILY_ROUTING: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "construction_project": (("construction_work", "work"), ("backup_mirror", "generated_output"),
                             "Search authoritative construction work roots first."),
    "project_file_lookup": (("construction_work", "work"), ("backup_mirror", "generated_output"),
                            "Search authoritative work roots for project files."),
    "financials": (("construction_work", "work"), ("backup_mirror", "generated_output", "vault"),
                   "Financial records live under work project roots, not the vault or backups."),
    "rfi": (("construction_work", "work"), ("backup_mirror", "generated_output"), ""),
    "submittal": (("construction_work", "work"), ("backup_mirror", "generated_output"), ""),
    "drawing": (("construction_work", "work"), ("backup_mirror", "generated_output"), ""),
    "construction_doc_lookup": (("construction_work", "work"),
                                ("backup_mirror", "generated_output"), ""),
    "generated_output_lookup": (("generated_output",), ("backup_mirror",),
                                "Generated artifacts are not source truth."),
    "vault_note_lookup": (("vault",), (),
                          "Use vault/card tools; the vault is supplemental context."),
    "personal_file_lookup": (("personal",), ("backup_mirror",),
                             "Personal roots are selective and sensitive."),
    "backup_lookup": (("backup_mirror",), (),
                      "Backup/mirror roots are low-trust; prefer the live source when it exists."),
}

_CLIENT_FOLDER_KEYS = (
    "folder_id", "root_key", "parent_folder_id", "rel_path", "name", "depth", "folder_class",
    "doc_family", "trust_tier", "search_rank", "is_noise", "is_backup_mirror",
    "is_generated_output", "is_sensitive", "is_project_candidate", "project_number",
    "project_name_hint", "child_folder_count", "file_count", "dominant_extensions",
    "classification_confidence",
)


def _client_folder(f: dict) -> dict:
    """Project a folder row to the whitelisted client shape (drops any non-listed key)."""
    return {k: f.get(k) for k in _CLIENT_FOLDER_KEYS}


class SourceStructureService:
    def __init__(self, db_path: str | Path | None = None,
                 repo: SourceStructureRepository | None = None) -> None:
        self._repo = repo or SourceStructureRepository(db_path)

    def status(self) -> dict:
        return self._repo.status()

    # -- root map -------------------------------------------------------------------------------
    def root_map(self, *, query_family: str | None = None, limit: int | None = None) -> dict:
        roots = self._repo.list_roots(limit=limit)
        preferred, avoided, note = _FAMILY_ROUTING.get(query_family or "", ((), (), ""))
        out = []
        for r in roots:
            if query_family and preferred:
                if r["root_class"] in preferred:
                    rationale = "preferred for this query family"
                elif r["root_class"] in avoided:
                    rationale = "downranked for this query family"
                else:
                    rationale = "available"
            else:
                rationale = _root_default_rationale(r)
            out.append({**r, "rationale": rationale})
        if query_family:
            out.sort(key=lambda x: (x["root_class"] not in preferred, x["default_search_rank"]))
        return {"query_family": query_family, "note": note, "roots": out}

    # -- folder map -----------------------------------------------------------------------------
    def folder_map(
        self, *, root_key: str | None = None, parent_folder_id: str | None = None,
        depth: int | None = None, folder_class: str | None = None, doc_family: str | None = None,
        project_number: str | None = None, include_noise: bool = False,
        limit: int | None = None, cursor: str | None = None,
    ) -> dict:
        n = clamp_limit(limit)
        offset = StructureCursor.decode(cursor).offset
        items, total = self._repo.list_folders(
            root_key=root_key, parent_folder_id=parent_folder_id, depth=depth,
            folder_class=folder_class, doc_family=doc_family, project_number=project_number,
            include_noise=include_noise, limit=n, offset=offset,
        )
        next_cursor = StructureCursor(offset + n).encode() if offset + n < total else None
        return {
            "folders": [_client_folder(f) for f in items],
            "total": total, "next_cursor": next_cursor,
        }

    # -- folder summary -------------------------------------------------------------------------
    def folder_summary(self, folder_id: str) -> dict | None:
        folder = self._repo.get_folder(folder_id)
        if not folder:
            return None
        summary = self._repo.get_summary("folder", folder_id)
        child_counts = self._repo.child_class_counts(folder_id)
        warnings = self._folder_warnings(folder)
        hints = self._repo.list_hints(query_family=None, limit=MAX_HINTS)
        relevant_hints = [h for h in hints if h.get("folder_id") == folder_id][:MAX_HINTS]
        return {
            "folder": _client_folder(folder),
            "summary": summary,
            "child_class_counts": child_counts,
            "routing_hints": relevant_hints,
            "quality_warnings": warnings,
        }

    @staticmethod
    def _folder_warnings(folder: dict) -> list[str]:
        warnings = []
        if folder.get("is_backup_mirror"):
            warnings.append("backup/mirror — low trust; prefer the live source")
        if folder.get("is_generated_output"):
            warnings.append("generated output — not source truth")
        if folder.get("is_noise"):
            warnings.append("noise/system folder — never a search target")
        if folder.get("is_sensitive"):
            warnings.append("sensitive/personal — use only when explicitly relevant")
        if folder.get("classification_confidence", 1.0) < 0.5:
            warnings.append("low-confidence classification")
        return warnings

    # -- search route ---------------------------------------------------------------------------
    def search_route(
        self, *, query: str | None = None, query_family: str | None = None,
        project_number: str | None = None, doc_family: str | None = None,
        limit: int | None = None,
    ) -> dict:
        n = clamp_limit(limit)
        family = query_family or _infer_family(query, doc_family, project_number)
        preferred, avoided, note = _FAMILY_ROUTING.get(family or "", ((), (), ""))

        roots = self._repo.list_roots()
        preferred_roots = [r for r in roots if r["root_class"] in preferred] if preferred else roots
        avoided_roots = [r["root_key"] for r in roots if r["root_class"] in avoided]

        # Candidate folders: project number wins; else doc-family filter under preferred roots.
        folders: list[dict] = []
        if project_number:
            folders = self._repo.project_folders(project_number, limit=n)
        else:
            pref_keys = [r["root_key"] for r in preferred_roots]
            for rk in pref_keys[:5]:
                items, _ = self._repo.list_folders(
                    root_key=rk, doc_family=doc_family, limit=n, offset=0
                )
                folders.extend(items)
            folders.sort(key=lambda f: f["search_rank"])
            folders = folders[:n]

        confidence = 0.8 if (project_number or doc_family) else (0.6 if preferred else 0.3)
        rationale = note or (
            f"Routed to {', '.join(preferred)} roots"
            if preferred else "No specific family matched; showing default ranking."
        )
        return {
            "query": query, "query_family": family,
            "preferred_roots": [
                {"root_key": r["root_key"], "root_class": r["root_class"],
                 "trust_tier": r["trust_tier"], "default_search_rank": r["default_search_rank"]}
                for r in preferred_roots
            ],
            "avoided_roots": avoided_roots,
            "preferred_folders": [_client_folder(f) for f in folders],
            "rationale": rationale, "confidence": confidence,
        }

    # -- scope explain --------------------------------------------------------------------------
    def scope_explain(self, *, root_key: str | None = None,
                      folder_id: str | None = None) -> dict | None:
        if folder_id:
            folder = self._repo.get_folder(folder_id)
            if not folder:
                return None
            return {
                "subject": "folder",
                "folder": _client_folder(folder),
                "policy": _folder_usage(folder),
                "reason": _folder_reason(folder),
                "warnings": self._folder_warnings(folder),
            }
        if root_key:
            roots = {r["root_key"]: r for r in self._repo.list_roots()}
            r = roots.get(root_key)
            if not r:
                return None
            return {
                "subject": "root",
                "root": r,
                "policy": r["index_policy"],
                "reason": _root_default_rationale(r),
                "allowed_usage": _root_usage(r),
            }
        return None

    # -- project map ----------------------------------------------------------------------------
    def project_map(self, project_number: str, *, limit: int | None = None) -> dict:
        folders = self._repo.project_folders(project_number, limit=limit)
        doc_families = sorted({f["doc_family"] for f in folders if f.get("doc_family")})
        candidates = []
        for f in folders:
            if f.get("folder_class") == "project_root":
                rel = "primary_project_folder"
            elif f.get("is_backup_mirror"):
                rel = "backup_folder"
            elif f.get("is_generated_output"):
                rel = "generated_output_folder"
            elif f.get("doc_family"):
                rel = "supporting_folder"
            else:
                rel = "candidate"
            candidates.append({
                **_client_folder(f), "relationship_type": rel,
                "confidence": f.get("classification_confidence"),
            })
        return {
            "project_number": project_number,
            "candidate_folders": candidates,
            "doc_family_coverage": doc_families,
        }

    # -- quality --------------------------------------------------------------------------------
    def quality(
        self, *, severity: str | None = None, finding_type: str | None = None,
        status: str | None = "open", limit: int | None = None, cursor: str | None = None,
    ) -> dict:
        n = clamp_limit(limit)
        offset = StructureCursor.decode(cursor).offset
        items, total = self._repo.list_findings(
            severity=severity, finding_type=finding_type, status=status, limit=n, offset=offset,
        )
        next_cursor = StructureCursor(offset + n).encode() if offset + n < total else None
        return {"findings": items, "total": total, "next_cursor": next_cursor}


# --- rationale helpers ------------------------------------------------------------------------
def _root_default_rationale(r: dict) -> str:
    if r["root_class"] == "construction_work":
        return "highest-priority construction source"
    if r["root_class"] == "work":
        return "primary work source"
    if r["root_class"] == "generated_output":
        return "generated outputs — lookup only, not source truth"
    if r["root_class"] == "backup_mirror":
        return "backup/mirror — low trust, downranked"
    if r["root_class"] == "vault":
        return "supplemental vault notes"
    if r["root_class"] == "personal":
        return "personal/sensitive — selective use"
    return "unclassified root"


def _root_usage(r: dict) -> str:
    if r["root_class"] in {"construction_work", "work"}:
        return "preferred_for_source_queries"
    if r["root_class"] == "generated_output":
        return "output_lookup_only"
    if r["root_class"] == "backup_mirror":
        return "explicit_request_only"
    if r["root_class"] == "vault":
        return "supplemental_context"
    if r["root_class"] == "personal":
        return "personal_context_only"
    return "review_before_use"


def _folder_usage(f: dict) -> str:
    if f.get("is_noise"):
        return "never_search"
    if f.get("is_backup_mirror"):
        return "explicit_request_only"
    if f.get("is_generated_output"):
        return "output_lookup_only"
    if f.get("is_sensitive"):
        return "personal_context_only"
    return "searchable"


def _folder_reason(f: dict) -> str:
    cls = f.get("folder_class")
    fam = f.get("doc_family")
    if f.get("is_noise"):
        return f"'{f.get('name')}' is a system/noise folder"
    if f.get("is_backup_mirror"):
        return f"'{f.get('name')}' is a backup/mirror copy"
    if f.get("is_generated_output"):
        return f"'{f.get('name')}' holds generated outputs"
    if f.get("project_number"):
        return f"project {f.get('project_number')} folder ({cls})"
    if fam:
        return f"{fam} documents ({cls})"
    return f"classified as {cls}"


def _infer_family(query: str | None, doc_family: str | None,
                  project_number: str | None) -> str | None:
    if doc_family in {"rfi", "submittal", "drawings"}:
        return {"drawings": "drawing"}.get(doc_family, doc_family)
    if doc_family in {"pay_app", "change_order", "contract"}:
        return "financials"
    if project_number:
        return "construction_project"
    if not query:
        return None
    q = query.lower()
    if any(k in q for k in ("backup", "time machine")):
        return "backup_lookup"
    if any(k in q for k in ("output", "generated", "receipt", "manifest")):
        return "generated_output_lookup"
    if any(k in q for k in ("note", "card", "vault", "obsidian")):
        return "vault_note_lookup"
    if any(k in q for k in ("submittal", "rfi", "drawing", "pay app", "change order", "project")):
        return "construction_project"
    return None


def folder_ref(root_key: str, rel_path: str) -> str:
    """Public helper so callers can compute a folder_id without importing the repository."""
    return folder_id_for(root_key, rel_path)
