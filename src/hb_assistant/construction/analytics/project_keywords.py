"""Project keyword training service for the optional analytics UI shell.

Framework-free. Callers (FastAPI routes or future consumers) pass db_path.
All persistence via ConstructionStore. No live endpoints, no CLI shellout,
no raw content ever leaves the service.

Implements Prompt 05 / UI-05: registry CRUD (add/edit/disable/delete/exclude),
strength levels, explicit rejection of standard/template folder names, suggest
from safe project signals, and redacted-only explain_match that reports which
enabled keywords fire and why (strength + location).
"""

from __future__ import annotations

import contextlib
from typing import Any, Optional

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

# Per 06_PROJECT_MATCHING_KEYWORDS.md and validation_contract.json assertion
# "no_folder_names_as_keywords". These (and close variants) must never be
# added as project keywords. Service-layer gate; not a schema constraint.
DEFAULT_EXCLUDED_FOLDER_NAMES: frozenset[str] = frozenset(
    {
        "drawings",
        "specifications",
        "submittals",
        "rfis",
        "photos",
        "contracts",
        "correspondence",
        "change orders",
        "changeorders",
        "financials",
        "meeting minutes",
        "meetingminutes",
        "closeout",
    }
)


def _normalize_term(term: str) -> str:
    t = (term or "").strip().lower()
    t = " ".join(t.replace("-", " ").replace("_", " ").split())
    if t.endswith("s") and len(t) > 3:
        t = t[:-1].strip()
    return t[:128]


def _is_excluded_folder(term_normalized: str) -> bool:
    n = term_normalized or ""
    return n in DEFAULT_EXCLUDED_FOLDER_NAMES or (n + "s") in DEFAULT_EXCLUDED_FOLDER_NAMES


def _guardrails() -> dict[str, Any]:
    return {
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
        "no_folder_names_as_keywords": True,
        "raw_content_never_stored": True,
    }


class ProjectKeywordsService:
    """Local registry for project-matching keyword training.

    Exposes list/add/update/delete + status (enable/disable/exclude) + strength.
    Provides suggest (safe signals only) and explain_match (redacted preview of
    why a candidate would match a project via enabled keywords).
    """

    def __init__(self, *, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._store = ConstructionStore(db_path)

    def list_keywords(
        self, project_key: str, *, include_disabled: bool = True, include_excluded: bool = False
    ) -> dict[str, Any]:
        if not project_key:
            return {
                "surface": "analytics.project_keywords.list",
                "project_key": None,
                "keywords": [],
                "guardrails": _guardrails(),
            }
        kws = self._store.list_project_keyword_registry(
            project_key=project_key,
            include_excluded=include_excluded,
            limit=500,
        )
        if not include_disabled:
            kws = [k for k in kws if k.get("registry_status") == "enabled"]
        return {
            "surface": "analytics.project_keywords.list",
            "project_key": project_key,
            "count": len(kws),
            "keywords": kws,
            "guardrails": _guardrails(),
        }

    def add_keyword(
        self,
        project_key: str,
        term: str,
        *,
        strength: str = "normal",
        provenance: str = "user_manual",
        notes_redacted: Optional[str] = None,
    ) -> dict[str, Any]:
        norm = _normalize_term(term)
        if not norm:
            return {
                "ok": False,
                "kind": "keyword_rejected",
                "reason_code": "empty_term",
                "guardrails": _guardrails(),
            }
        if _is_excluded_folder(norm):
            return {
                "ok": False,
                "kind": "keyword_rejected",
                "reason_code": "standard_folder_name_excluded",
                "message": "Standard/template folder names must not be used as project keywords.",
                "normalized": norm,
                "guardrails": _guardrails(),
            }
        keyword_id = hash_value(f"{project_key}:{norm}") or ""
        self._store.upsert_project_keyword_registry_entry(
            keyword_id=keyword_id,
            project_key=project_key,
            keyword_normalized=norm,
            keyword_class="phrase",
            strength=strength,
            registry_status="enabled",
            provenance=provenance,
            notes_redacted=notes_redacted,
        )
        return {
            "ok": True,
            "kind": "keyword_added",
            "keyword_id": keyword_id,
            "project_key": project_key,
            "normalized": norm,
            "strength": strength,
            "guardrails": _guardrails(),
        }

    def update_keyword(
        self,
        keyword_id: str,
        *,
        strength: Optional[str] = None,
        registry_status: Optional[str] = None,
        notes_redacted: Optional[str] = None,
    ) -> dict[str, Any]:
        existing = self._store.get_project_keyword_registry_entry(keyword_id)
        if not existing:
            return {
                "ok": False,
                "kind": "keyword_not_found",
                "keyword_id": keyword_id,
                "guardrails": _guardrails(),
            }
        new_strength = strength or existing.get("strength") or "normal"
        new_status = registry_status or existing.get("registry_status") or "enabled"
        if registry_status is not None:
            self._store.set_project_keyword_registry_status(
                keyword_id=keyword_id, registry_status=new_status
            )
        if strength is not None or notes_redacted is not None:
            self._store.upsert_project_keyword_registry_entry(
                keyword_id=keyword_id,
                project_key=existing["project_key"],
                keyword_normalized=existing["keyword_normalized"],
                keyword_class=existing.get("keyword_class") or "phrase",
                strength=new_strength,
                registry_status=new_status,
                provenance=existing.get("provenance") or "user_manual",
                provenance_ref_hash=existing.get("provenance_ref_hash"),
                notes_redacted=(
                    notes_redacted if notes_redacted is not None else existing.get("notes_redacted")
                ),
            )
        return {
            "ok": True,
            "kind": "keyword_updated",
            "keyword_id": keyword_id,
            "strength": new_strength,
            "registry_status": new_status,
            "guardrails": _guardrails(),
        }

    def delete_keyword(self, keyword_id: str) -> dict[str, Any]:
        self._store.delete_project_keyword_registry_entry(keyword_id)
        return {
            "ok": True,
            "kind": "keyword_deleted",
            "keyword_id": keyword_id,
            "guardrails": _guardrails(),
        }

    def suggest_keywords(self, project_key: str) -> dict[str, Any]:
        """Derive low-confidence candidate terms from safe project signals only.

        Uses project_identity (name/number). Never emits standard folder names.
        Suggestions require explicit user add to become active keywords.
        """
        suggestions: list[dict[str, Any]] = []
        ident = None
        with contextlib.suppress(Exception):
            ident = self._store.get_project_identity(project_key)
        if ident:
            for field, label in (
                ("project_name_raw", "project_name"),
                ("hb_project_number", "project_number"),
            ):
                val = ident.get(field)
                if val:
                    norm = _normalize_term(str(val))
                    if norm and not _is_excluded_folder(norm):
                        suggestions.append(
                            {
                                "normalized": norm,
                                "strength": "normal" if label == "project_name" else "strong",
                                "provenance": "import_procore"
                                if "procore" in (ident.get("project_stage") or "")
                                else "system_suggested",
                                "reason": label,
                            }
                        )
        seen: set[str] = set()
        uniq: list[dict[str, Any]] = []
        for s in suggestions:
            if s["normalized"] not in seen:
                seen.add(s["normalized"])
                uniq.append(s)
        return {
            "surface": "analytics.project_keywords.suggest",
            "project_key": project_key,
            "candidates": uniq[:20],
            "guardrails": _guardrails(),
            "note": "Suggestions are advisory; POST to persist after user confirmation.",
        }

    def explain_match(
        self, project_key: str, *, candidate: str | dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Redacted-only preview: which enabled keywords would contribute to a match.

        Input candidate may be a redacted string or a small dict of redacted fields
        (e.g. {"subject_redacted": "...", "name_redacted": "..."}). Output lists
        firing keywords with strength, provenance, and a coarse match_location.
        Never includes or echoes raw source values.
        """
        enabled = self._store.list_project_keyword_registry(
            project_key=project_key, registry_status="enabled", limit=500
        )
        text = ""
        if isinstance(candidate, str):
            text = _normalize_term(candidate)
        elif isinstance(candidate, dict):
            for k in (
                "text_redacted",
                "subject_redacted",
                "name_redacted",
                "title_redacted",
                "signal",
            ):
                v = candidate.get(k)
                if isinstance(v, str):
                    text += " " + _normalize_term(v)
            text = text.strip() or _normalize_term(str(candidate)[:200])
        matches: list[dict[str, Any]] = []
        for kw in enabled:
            norm = kw.get("keyword_normalized") or ""
            if not norm:
                continue
            if norm in text or text in norm:
                matches.append(
                    {
                        "keyword_id": kw["keyword_id"],
                        "normalized": norm,
                        "strength": kw.get("strength"),
                        "registry_status": kw.get("registry_status"),
                        "match_location": "contains",
                        "provenance": kw.get("provenance"),
                    }
                )
        return {
            "surface": "analytics.project_keywords.explain",
            "project_key": project_key,
            "candidate_preview_hash": hash_value(text) if text else None,
            "matched_keywords": matches,
            "count": len(matches),
            "guardrails": _guardrails(),
            "note": "Preview only. Actual matches are evaluated by the construction pipeline using enabled registry entries.",
        }
