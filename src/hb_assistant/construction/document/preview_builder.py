"""Phase 07C Prompt 09 — review-controlled document intelligence (project previews).

Produces one **project-level** document-intelligence preview per project, rolled up from the
already-populated document cards + classification / project-match / relationship candidates +
extraction dispositions. Each preview is a bounded, counts-only redacted summary with a
confidence class, a warnings list, and visible review state, written to
``construction_document_intelligence_previews`` (preview_kind="project_document_intelligence",
document_card_id NULL).

Read-only and conservative: pure counts and statuses — never a raw document name, path, URL, or
excerpt; no legal/claim/financial/personnel/safety conclusion; no external writeback; no card
mutation; no auto-promotion. Source references (project key + document + distinct-source counts)
are carried in ``warnings_json``.
"""

from __future__ import annotations

import json
from typing import Any

from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_PREVIEW_KIND = "project_document_intelligence"
_UNCLASSIFIED = "unknown_needs_review"


def _rollup_confidence_class(classified: int, total: int) -> str:
    """Project preview confidence from the classified fraction (deterministic rule)."""
    if total <= 0:
        return "unknown"
    fraction = classified / total
    if fraction >= 0.8:
        return "high_heuristic"
    if fraction >= 0.5:
        return "moderate_heuristic"
    if fraction >= 0.2:
        return "weak_heuristic"
    return "unknown"


def _counts(items: Any, key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        v = it.get(key)
        if v is None:
            v = "unknown"
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def build_document_intelligence_previews(
    store: Any,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Build one project-level document-intelligence preview per project.

    Counts are computed regardless of ``apply``; rows are written only when ``apply=True``.
    No card is mutated; no content is read. The preview is a counts-only rollup with a
    confidence class, warnings, and review state.
    """
    cards = store.list_document_cards()
    classification = store.list_document_classification_candidates()
    matches = store.list_document_project_match_candidates()
    relationships = store.list_document_relationship_candidates()

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

    def _by_project(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            pk = card_project.get(r.get("document_card_id"))
            if pk:
                grouped.setdefault(pk, []).append(r)
        return grouped

    clf_by_project = _by_project(classification)
    match_by_project = _by_project(matches)
    rel_by_project = _by_project(relationships)

    previews = 0
    review_required_count = 0
    by_confidence_class: dict[str, int] = {}
    rollup: list[dict[str, Any]] = []

    for pk in sorted(cards_by_project):
        pcards = cards_by_project[pk]
        total = len(pcards)
        clf = clf_by_project.get(pk, [])
        mtch = match_by_project.get(pk, [])
        rel = rel_by_project.get(pk, [])

        classified = sum(1 for c in clf if c.get("document_type") not in (None, _UNCLASSIFIED))
        unclassified = sum(1 for c in clf if c.get("document_type") == _UNCLASSIFIED)
        confidence_class = _rollup_confidence_class(classified, total)

        documents_pending_review = sum(1 for c in pcards if c.get("review_required"))
        candidate_items_pending_review = (
            sum(1 for c in clf if c.get("review_required"))
            + sum(1 for r in rel if r.get("review_required"))
            + sum(1 for m in mtch if m.get("review_required"))
        )
        review_required = bool(documents_pending_review or candidate_items_pending_review)

        by_extraction = _counts(pcards, "extraction_eligibility")
        by_size = _counts(pcards, "size_class")
        by_clf_confidence = _counts(clf, "confidence_class")
        by_rel_target = _counts(rel, "target_record_type")
        distinct_sources = len({s for s in sources_by_project.get(pk, set()) if s})

        warnings: list[str] = []
        if unclassified:
            warnings.append(
                f"{unclassified} of {total} documents are unclassified "
                f"({_UNCLASSIFIED}) — pending review."
            )
        eligible = by_extraction.get("eligible", 0)
        warnings.append(
            f"{eligible} documents extraction-eligible; "
            f"{by_extraction.get('manual_approval_required', 0)} manual-approval, "
            f"{by_extraction.get('metadata_only', 0)} metadata-only, "
            f"{by_extraction.get('blocked', 0)} blocked."
        )
        if rel:
            warnings.append(
                f"{len(rel)} relationship candidate(s) (heuristic, review-required); "
                "email/calendar relationship arms deferred."
            )
        warnings.append(
            "All candidates are advisory; no auto-promotion; review required before any "
            "promotion. No legal/claim/financial/personnel/safety conclusions."
        )

        preview_redacted = "\n".join(
            [
                f"Project {pk} — document intelligence preview",
                f"Documents: {total} (by size {json.dumps(by_size, sort_keys=True)})",
                f"Classification: {classified} classified, {unclassified} {_UNCLASSIFIED} "
                f"(by confidence {json.dumps(by_clf_confidence, sort_keys=True)})",
                f"Project match: {len(mtch)} candidate(s)",
                f"Extraction: {json.dumps(by_extraction, sort_keys=True)}",
                f"Relationships: {len(rel)} candidate(s) "
                f"(by record type {json.dumps(by_rel_target, sort_keys=True)})",
                f"Review: {documents_pending_review} document(s) + "
                f"{candidate_items_pending_review} candidate item(s) pending",
                f"Sources: {distinct_sources} indexed source(s)",
            ]
        )

        warnings_json = json.dumps(
            {
                "warnings": warnings,
                "source_reference": {
                    "project_key": pk,
                    "document_count": total,
                    "distinct_sources": distinct_sources,
                },
                "review": {
                    "documents_pending_review": documents_pending_review,
                    "candidate_items_pending_review": candidate_items_pending_review,
                },
            },
            sort_keys=True,
        )

        previews += 1
        if review_required:
            review_required_count += 1
        by_confidence_class[confidence_class] = by_confidence_class.get(confidence_class, 0) + 1
        rollup.append(
            {
                "project_key": pk,
                "documents": total,
                "classified": classified,
                "unclassified": unclassified,
                "confidence_class": confidence_class,
                "project_match_candidates": len(mtch),
                "relationship_candidates": len(rel),
                "by_extraction_eligibility": by_extraction,
                "documents_pending_review": documents_pending_review,
                "candidate_items_pending_review": candidate_items_pending_review,
                "review_required": review_required,
            }
        )

        if apply:
            preview_id = hash_value(f"{pk}|{_PREVIEW_KIND}")
            store.upsert_document_intelligence_preview(
                preview_id=preview_id,
                project_key=pk,
                preview_kind=_PREVIEW_KIND,
                confidence_class=confidence_class,
                preview_redacted=preview_redacted,
                warnings_json=warnings_json,
                document_card_id=None,
                review_required=review_required,
            )

    return {
        "command": "graph files build-document-previews",
        "mode": "apply" if apply else "dry_run",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "summary": {
            "projects": len(cards_by_project),
            "previews": previews,
            "review_required": review_required_count,
            "by_confidence_class": dict(sorted(by_confidence_class.items())),
            "rollup": rollup,
        },
        "guardrails": {
            "external_systems": "read_only",
            "graph_calls": "none",
            "model_invoked": False,
            "deterministic_first": True,
            "raw_document_text_persisted": False,
            "raw_path_or_url_persisted": False,
            "external_writeback": False,
            "auto_promotion": False,
            "card_mutated": False,
            "high_impact_conclusions": False,
        },
    }
