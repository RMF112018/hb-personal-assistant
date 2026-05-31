"""Phase 07C Prompt 06 — document project matcher (deterministic-first).

Records *which project* each ``construction_document_cards`` row belongs to by reading
the deterministic binding the card already carries (`project_key` from the source
location + `project_number_hash`) and corroborating it against the project registry's
full project-number hash. One advisory candidate per matchable card is written to
``construction_document_project_match_candidates`` (FK -> document_card_id).

No Graph call, no model, no raw path/name/URL: the card binding is consumed as-is and
only the project key, candidate type, confidence, and hashed/typed signal evidence are
persisted. A project_number_hash that disagrees with the registry routes to review as a
``conflict`` candidate (never auto-promoted). The card is left unchanged (candidates-only).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from hb_assistant.construction.config import load_source_registry
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_MATCHER_NAME = "deterministic_v1"


def match_document_projects(
    store: Any,
    *,
    apply: bool = False,
    registry: Optional[Any] = None,
) -> dict[str, Any]:
    """Match every document card to a project and write advisory match candidates.

    Counts are computed regardless of ``apply``; rows are written only when
    ``apply=True``. The card is never mutated (candidates-only). Deterministic source
    binding (and corroborating full project-number hash) only — no heuristic re-parse
    of raw paths/names, no model. A project_number_hash that disagrees with the
    registry routes to review as a ``conflict`` (no auto-promotion).
    """
    registry = registry or load_source_registry()
    # project_key -> full project-number hash (registry source of truth).
    project_hash: dict[str, str] = {}
    for project in registry.projects:
        if project.project_number:
            h = hash_value(project.project_number)
            if h:
                project_hash[project.project_key] = h

    cards = store.list_document_cards()
    matched = 0
    deterministic_count = 0
    review_required_count = 0
    conflict_count = 0
    unmatched_skipped = 0
    by_project_key: dict[str, int] = {}
    by_confidence_class: dict[str, int] = {}
    by_candidate_type: dict[str, int] = {}

    for card in cards:
        pk = card.get("project_key")
        if not pk:
            # project_key is NOT NULL on the candidate table; without a project we
            # cannot write a candidate. Such cards await source/project resolution.
            unmatched_skipped += 1
            continue

        pnh = card.get("project_number_hash")
        expected = project_hash.get(pk)

        if pnh and expected and pnh == expected:
            signals = {
                "matcher": _MATCHER_NAME,
                "signals": ["source_location_project_key", "full_project_number_hash"],
            }
            candidate_type = "deterministic"
            confidence_class = "deterministic"
            confidence = 0.95
            deterministic = True
            review_required = False
        elif pnh and expected and pnh != expected:
            # Source binding and registry project-number hash disagree -> review.
            signals = {
                "matcher": _MATCHER_NAME,
                "signals": ["source_location_project_key", "project_number_hash_conflict"],
            }
            candidate_type = "conflict"
            confidence_class = "weak_heuristic"
            confidence = 0.3
            deterministic = False
            review_required = True
        else:
            # Source binding only (no corroborating number hash available).
            signals = {
                "matcher": _MATCHER_NAME,
                "signals": ["source_location_project_key"],
            }
            candidate_type = "deterministic"
            confidence_class = "deterministic"
            confidence = 0.9
            deterministic = True
            review_required = False

        matched += 1
        if deterministic:
            deterministic_count += 1
        if review_required:
            review_required_count += 1
        if candidate_type == "conflict":
            conflict_count += 1
        by_project_key[pk] = by_project_key.get(pk, 0) + 1
        by_confidence_class[confidence_class] = by_confidence_class.get(confidence_class, 0) + 1
        by_candidate_type[candidate_type] = by_candidate_type.get(candidate_type, 0) + 1

        if apply:
            document_card_id = card["document_card_id"] or card["card_id"]
            candidate_id = hash_value(f"{document_card_id}|{_MATCHER_NAME}|{pk}")
            signals_json = json.dumps(signals, sort_keys=True)
            store.upsert_document_project_match_candidate(
                candidate_id=candidate_id,
                document_card_id=document_card_id,
                project_key=pk,
                candidate_type=candidate_type,
                confidence=confidence,
                confidence_class=confidence_class,
                signals_json=signals_json,
                deterministic=deterministic,
                model_proposed=False,
                review_required=review_required,
                promotion_status="candidate",
            )

    return {
        "command": "graph files match-document-projects",
        "mode": "apply" if apply else "dry_run",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "summary": {
            "cards_total": len(cards),
            "matched": matched,
            "deterministic": deterministic_count,
            "review_required": review_required_count,
            "conflict": conflict_count,
            "unmatched_skipped": unmatched_skipped,
            "by_project_key": dict(sorted(by_project_key.items())),
            "by_confidence_class": dict(sorted(by_confidence_class.items())),
            "by_candidate_type": dict(sorted(by_candidate_type.items())),
        },
        "guardrails": {
            "external_systems": "read_only",
            "graph_calls": "none",
            "model_invoked": False,
            "deterministic_first": True,
            "raw_document_text_persisted": False,
            "raw_path_or_url_persisted": False,
            "auto_promotion": False,
            "card_mutated": False,
        },
    }
