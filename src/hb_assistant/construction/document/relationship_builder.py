"""Phase 07C Prompt 08 — document->record relationship candidates (deterministic-first).

Creates conservative, source-linked advisory candidates connecting each document card to
the Procore records it belongs with, written to ``construction_document_relationship_candidates``
(FK -> document_card_id). Candidates only — no card mutation, no auto-promotion, no external
writeback, no raw content read.

The only safe, project-aligned link available today is **document -> Procore record type**: every
document card and every Procore live record share ``project_key``, so a card whose classified
document type aligns to a Procore record type (rfi/submittal/change_order/inspection/daily_log/
contract/...) gets one heuristic, review-required candidate referencing that project-scoped record
type by a hashed key. Email and calendar targets are deferred: their live records are not yet
project-key-aligned to the documents (calendar project_key is null; email carries no project_key),
so emitting candidates there would be speculative. Record-level deterministic linking (a document's
record number to a specific Procore record) is also deferred — cards persist no raw record number,
so no safe record-level identifier match exists.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from hb_assistant.construction.document.contracts import load_document_contract
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_BUILDER_NAME = "deterministic_v1"

# Classified document type -> (Procore endpoint_id, contract target_record_type). Only types
# that align to a Procore record type produce a candidate; everything else is skipped.
_ALIGNMENT: dict[str, tuple[str, str]] = {
    "rfi": ("rfis", "rfi"),
    "submittal": ("submittals", "submittal"),
    "change_order": ("prime-change-orders", "change_order"),
    "inspection_report": ("inspections", "inspection"),
    "daily_report": ("daily-log-dcrs", "daily_log"),
    "contract": ("commitment-contracts", "contract"),
    "pay_application": ("subcontractor-invoices", "commitment"),
}


def build_document_relationship_candidates(
    store: Any,
    *,
    apply: bool = False,
    contract: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Build advisory document->record relationship candidates (Procore arm).

    Counts are computed regardless of ``apply``; rows are written only when ``apply=True``.
    The card is never mutated (candidates-only). Procore is read-only (a count of canonical
    live records per project + endpoint); no raw Procore payload is read or persisted.
    """
    contract = contract or load_document_contract("document_relationship_candidate_contract")

    # document_card_id -> classified document_type (the card column is 'unknown' until review).
    doc_type: dict[str, str] = {}
    for row in store.list_document_classification_candidates():
        dcid = row.get("document_card_id")
        dt = row.get("document_type")
        if dcid and dt:
            doc_type[dcid] = dt

    cards = store.list_document_cards()
    candidates = 0
    review_required_count = 0
    unmatched_skipped = 0
    by_target_system: dict[str, int] = {}
    by_target_record_type: dict[str, int] = {}
    by_candidate_type: dict[str, int] = {}
    by_confidence_class: dict[str, int] = {}
    # Cache (project_key, endpoint_id) -> has-records to avoid repeated counts.
    presence: dict[tuple[str, str], bool] = {}

    for card in cards:
        pk = card.get("project_key")
        document_card_id = card["document_card_id"] or card["card_id"]
        dt = doc_type.get(document_card_id) or card.get("document_type")
        if not pk or dt not in _ALIGNMENT:
            unmatched_skipped += 1
            continue

        endpoint_id, target_record_type = _ALIGNMENT[dt]
        key = (pk, endpoint_id)
        if key not in presence:
            presence[key] = (
                store.count_procore_live_records(project_key=pk, endpoint_id=endpoint_id) > 0
            )
        if not presence[key]:
            # The project has no records of the aligned type — do not link.
            unmatched_skipped += 1
            continue

        candidate_type = "heuristic"
        confidence_class = "moderate_heuristic"
        confidence = 0.55
        candidates += 1
        review_required_count += 1
        by_target_system["procore"] = by_target_system.get("procore", 0) + 1
        by_target_record_type[target_record_type] = (
            by_target_record_type.get(target_record_type, 0) + 1
        )
        by_candidate_type[candidate_type] = by_candidate_type.get(candidate_type, 0) + 1
        by_confidence_class[confidence_class] = by_confidence_class.get(confidence_class, 0) + 1

        if apply:
            candidate_id = hash_value(
                f"{document_card_id}|{_BUILDER_NAME}|procore|{target_record_type}"
            )
            target_record_key_hash = hash_value(f"{pk}|procore|{endpoint_id}")
            signals_json = json.dumps(
                {
                    "builder": _BUILDER_NAME,
                    "signals": ["shared_project_key", "document_type_alignment"],
                    "target_endpoint_hash": hash_value(endpoint_id),
                },
                sort_keys=True,
            )
            source_reference_json = json.dumps(
                {
                    "target_system": "procore",
                    "target_record_type": target_record_type,
                    "project_key": pk,
                    "document_type": dt,
                },
                sort_keys=True,
            )
            store.upsert_document_relationship_candidate(
                candidate_id=candidate_id,
                document_card_id=document_card_id,
                target_system="procore",
                target_record_type=target_record_type,
                target_record_key_hash=target_record_key_hash,
                relationship_type="project_document_type_alignment",
                candidate_type=candidate_type,
                confidence=confidence,
                confidence_class=confidence_class,
                source_reference_json=source_reference_json,
                signals_json=signals_json,
                review_required=True,
                promotion_status="candidate",
            )

    return {
        "command": "graph files build-document-relationships",
        "mode": "apply" if apply else "dry_run",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "contract_version": contract.get("version"),
        "summary": {
            "cards_total": len(cards),
            "candidates": candidates,
            "review_required": review_required_count,
            "unmatched_skipped": unmatched_skipped,
            "by_target_system": dict(sorted(by_target_system.items())),
            "by_target_record_type": dict(sorted(by_target_record_type.items())),
            "by_candidate_type": dict(sorted(by_candidate_type.items())),
            "by_confidence_class": dict(sorted(by_confidence_class.items())),
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
            "deferred_target_systems": ["email", "calendar"],
        },
    }
