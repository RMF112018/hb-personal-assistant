"""Phase 07C Prompt 10 — safe Obsidian projections for document intelligence.

Local-only renderer over the V24 document-intelligence SQLite tables (document cards,
classification / project-match / relationship candidates, and the project preview).
Produces **grouped, low-noise**, marker-bounded markdown artifacts — never one note per
document:

- Project Document Register (one per project): counts grouped by document type, confidence
  class, extraction disposition, review state, and relationship record type, plus the
  review-controlled preview's warnings and a source reference. **Counts only** — no raw
  document name, full path, URL, or text.
- Project Document Review (one per project): review-required counts by category, routed to
  the review queue (not inlined per-document).

Mirrors :class:`FileObsidianProjector` (grouped artifacts + marker-bounded ``_write_artifact``
+ output fence + dry-run-default). Read-only against Microsoft 365, Procore, and the vault:
SQLite only — no Graph, no writeback, no source files or document text copied into Obsidian.
Dry-run is the default; ``--apply`` writes the marker-bounded sections idempotently. Scope is
limited to projects that already have a review-controlled preview (Prompt 09).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_BASE = "Work/HB Personal Assistant/07C_Document_Intelligence"
_MARKER_PREFIX = "HB-DOCS"
_UNCLASSIFIED = "unknown_needs_review"

_PEM_MARKER = "-----" + "begin"
_FORBIDDEN_MARKERS = (
    "deltatoken=",
    "?token=",
    "&token=",
    "sig=",
    "@microsoft.graph.downloadurl",
    "authorization:",
    "bearer ",
    "access_token",
    "refresh_token",
    "client_secret",
    "http://",
    "https://",
    _PEM_MARKER,
    "full_document_text",
    "full_body_" + "plaintext",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _assert_output_fence(rendered: str) -> None:
    lower = (rendered or "").lower()
    for tok in _FORBIDDEN_MARKERS:
        if tok in lower:
            raise ValueError(
                f"output-fence violation: forbidden marker {tok!r} in generated document "
                "Obsidian content"
            )


def _md_cell(value: Any) -> str:
    text = " ".join(str(value if value is not None else "").split())
    return text.replace("|", "/")


def _counts(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        v = it.get(key)
        out[str(v if v is not None else "unknown")] = out.get(
            str(v if v is not None else "unknown"), 0
        ) + 1
    return dict(sorted(out.items()))


@dataclass
class _DocArtifact:
    kind: str
    relative_path: str
    marker_key: str
    content: str


class DocumentObsidianProjector:
    """Build/write grouped document-intelligence Obsidian artifacts from local SQLite state."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def project(
        self,
        *,
        project_key: Optional[str] = None,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        previews = self._store.list_document_intelligence_previews(project_key=project_key)
        cards = self._store.list_document_cards()
        classification = self._store.list_document_classification_candidates()
        relationships = self._store.list_document_relationship_candidates()

        card_project: dict[str, str] = {}
        cards_by_project: dict[str, list[dict[str, Any]]] = {}
        sources_by_project: dict[str, set[str]] = {}
        for card in cards:
            pk = card.get("project_key")
            if not pk:
                continue
            dcid = card["document_card_id"] or card["card_id"]
            card_project[dcid] = pk
            cards_by_project.setdefault(pk, []).append(card)
            sources_by_project.setdefault(pk, set()).add(card.get("source_id") or "")

        def _grouped(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
            out: dict[str, list[dict[str, Any]]] = {}
            for r in rows:
                pk = card_project.get(r.get("document_card_id"))
                if pk:
                    out.setdefault(pk, []).append(r)
            return out

        clf_by_project = _grouped(classification)
        rel_by_project = _grouped(relationships)

        artifacts: list[_DocArtifact] = []
        per_project: list[dict[str, Any]] = []
        rendered: dict[str, dict[str, str]] = {}

        for prev in previews:
            pk = prev.get("project_key")
            if not pk:
                continue
            pcards = cards_by_project.get(pk, [])
            clf = clf_by_project.get(pk, [])
            rel = rel_by_project.get(pk, [])
            warnings = self._parse_warnings(prev.get("warnings_json"))

            register = self._render_register(prev, pk, pcards, clf, rel, warnings)
            review = self._render_review(prev, pk, pcards, clf, rel, warnings)
            artifacts.append(
                _DocArtifact(
                    kind="document_register",
                    relative_path=f"{_BASE}/Projects/{pk}/Document Register.md",
                    marker_key="document_register",
                    content=register,
                )
            )
            artifacts.append(
                _DocArtifact(
                    kind="document_review",
                    relative_path=f"{_BASE}/Review/{pk} Document Review.md",
                    marker_key="document_review",
                    content=review,
                )
            )
            rendered[pk] = {"register": register, "review": review}
            per_project.append(
                {
                    "project_key": pk,
                    "documents": len(pcards),
                    "confidence_class": prev.get("confidence_class"),
                    "review_required": bool(prev.get("review_required")),
                }
            )

        for a in artifacts:
            _assert_output_fence(a.content)

        written = 0
        abs_paths: list[str] = []
        if dry_run:
            abs_paths = [str(self._abs_target_path(a.relative_path)) for a in artifacts]
        else:
            for a in artifacts:
                abs_paths.append(str(self._write_artifact(a)))
                written += 1

        return {
            "command": "graph files document-obsidian",
            "mode": "dry_run" if dry_run else "apply",
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "summary": {
                "projects": len(previews),
                "notes_planned": len(artifacts),
                "notes_written": written,
                "by_project": per_project,
            },
            "paths": abs_paths,
            "rendered": rendered,
            "guardrails": {
                "external_systems": "read_only",
                "writeback": "none",
                "graph_calls": "none",
                "source_traceability": True,
                "full_text_persisted": False,
                "source_file_copied_to_vault": False,
                "raw_paths_rendered": False,
                "one_note_per_document": False,
                "marker_bounded_writes": True,
            },
        }

    # --- helpers --------------------------------------------------------------

    @staticmethod
    def _parse_warnings(warnings_json: Optional[str]) -> dict[str, Any]:
        if not warnings_json:
            return {}
        try:
            data = json.loads(warnings_json)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def _abs_target_path(self, relative_path: str) -> Path:
        return PathPolicy().get_vault_root() / relative_path

    def _write_artifact(self, artifact: _DocArtifact) -> Path:
        target = self._abs_target_path(artifact.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        start = f"<!-- {_MARKER_PREFIX}-{artifact.marker_key.upper()}:START -->"
        end = f"<!-- {_MARKER_PREFIX}-{artifact.marker_key.upper()}:END -->"
        if start not in existing or end not in existing:
            if existing and not existing.endswith("\n"):
                existing += "\n"
            existing = existing + f"\n{start}\n{end}\n"
        pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
        result = pattern.sub(rf"\1\n{artifact.content.strip()}\n\3", existing)
        _assert_output_fence(result)
        target.write_text(result, encoding="utf-8")
        return target

    # --- renderers ------------------------------------------------------------

    def _render_register(
        self,
        prev: dict[str, Any],
        pk: str,
        cards: list[dict[str, Any]],
        clf: list[dict[str, Any]],
        rel: list[dict[str, Any]],
        warnings: dict[str, Any],
    ) -> str:
        total = len(cards)
        classified = sum(1 for c in clf if c.get("document_type") not in (None, _UNCLASSIFIED))
        source_ref = warnings.get("source_reference", {})
        distinct_sources = source_ref.get("distinct_sources", "")
        lines = [
            "---",
            "type: document_intelligence_register",
            f"project_key: {_md_cell(pk)}",
            "source: construction_phase07c_document_intelligence",
            f"confidence_class: {_md_cell(prev.get('confidence_class'))}",
            f"generated_at: {_utc_now()}",
            "external_systems: read_only",
            "writeback: none",
            "source_traceability: true",
            "---",
            "",
            f"# Project Document Register — {_md_cell(pk)}",
            "",
            f"_Local SQLite read-model projection — no Graph/Procore call. {total} document(s); "
            f"{classified} classified; confidence {_md_cell(prev.get('confidence_class'))}._",
            "",
            "## Counts by document type",
            "",
        ]
        lines += [f"- {_md_cell(k)}: {v}" for k, v in _counts(clf, "document_type").items()] or [
            "- (none)"
        ]
        lines += ["", "## Counts by confidence class", ""]
        lines += [
            f"- {_md_cell(k)}: {v}" for k, v in _counts(clf, "confidence_class").items()
        ] or ["- (none)"]
        lines += ["", "## Counts by extraction eligibility", ""]
        lines += [
            f"- {_md_cell(k)}: {v}" for k, v in _counts(cards, "extraction_eligibility").items()
        ] or ["- (none)"]
        lines += ["", "## Counts by review status", ""]
        lines += [f"- {_md_cell(k)}: {v}" for k, v in _counts(cards, "review_status").items()] or [
            "- (none)"
        ]
        lines += ["", "## Relationship candidates by record type", ""]
        lines += [
            f"- {_md_cell(k)}: {v}" for k, v in _counts(rel, "target_record_type").items()
        ] or ["- (none)"]
        lines += ["", "## Warnings", ""]
        lines += [f"- {_md_cell(w)}" for w in warnings.get("warnings", [])] or [
            "- (none)"
        ]
        lines += [
            "",
            "## Source reference",
            "",
            f"- Project key: {_md_cell(pk)}",
            f"- Documents: {total}",
            f"- Indexed sources: {_md_cell(distinct_sources)}",
            "",
            "## Guardrails",
            "",
            "- Counts only — no document names, full paths, URLs, or document text.",
            "- No Microsoft 365 / Procore writeback; read-only SQLite projection.",
            "- No source files copied into Obsidian; marker-bounded + idempotent.",
            "- Advisory only; review required before any promotion; no high-impact conclusions.",
        ]
        return "\n".join(lines)

    def _render_review(
        self,
        prev: dict[str, Any],
        pk: str,
        cards: list[dict[str, Any]],
        clf: list[dict[str, Any]],
        rel: list[dict[str, Any]],
        warnings: dict[str, Any],
    ) -> str:
        review = warnings.get("review", {})
        clf_review = sum(1 for c in clf if c.get("review_required"))
        rel_review = sum(1 for r in rel if r.get("review_required"))
        manual = _counts(cards, "extraction_eligibility").get("manual_approval_required", 0)
        unclassified = sum(1 for c in clf if c.get("document_type") == _UNCLASSIFIED)
        lines = [
            "---",
            "type: document_intelligence_review",
            f"project_key: {_md_cell(pk)}",
            "source: construction_phase07c_document_intelligence",
            f"generated_at: {_utc_now()}",
            "review_sensitive: true",
            "---",
            "",
            f"# Project Document Review — {_md_cell(pk)}",
            "",
            f"_{review.get('documents_pending_review', len(cards))} document(s) + "
            f"{review.get('candidate_items_pending_review', clf_review + rel_review)} candidate "
            "item(s) pending review. Items are routed to the review queue — not inlined here._",
            "",
            "## Review-required by category",
            "",
            f"- Classification candidates requiring review: {clf_review}",
            f"- Relationship candidates requiring review: {rel_review}",
            f"- Documents requiring manual extraction approval: {manual}",
            f"- Unclassified ({_UNCLASSIFIED}) backlog: {unclassified}",
            "",
            "## Guardrails",
            "",
            "- Counts only — no per-document note, no document names/paths/text.",
            "- Review-required items cannot auto-promote; controller review required.",
            "- No legal/claim/financial/personnel/safety conclusions.",
        ]
        return "\n".join(lines)
