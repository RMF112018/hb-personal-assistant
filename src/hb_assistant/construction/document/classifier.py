"""Phase 07C Prompt 05 — document type classifier (deterministic-first).

Classifies each ``construction_document_cards`` row into a construction document
type using deterministic signals first (known record number -> folder token hashes
-> filename token hashes -> extension/mime), then writes one advisory candidate to
``construction_document_classification_candidates`` (FK -> document_card_id). Model
output is advisory-only and is NOT invoked here (deterministic-first; offline-safe).

Tokens are re-derived from the raw inventory ``name`` / ``parent_path`` in memory and
matched against a hashed keyword vocabulary; only the resolved type, signal class,
confidence, and hashed/typed signal evidence are persisted — never a raw filename,
path, prompt, or response. Sensitive/high-impact document types and weak/unknown
results route to review; nothing is auto-promoted, and the card is left unchanged
(candidates-only).
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from hb_assistant.construction.policy import ReviewPolicyEvaluator, load_review_rules
from hb_assistant.construction.policy.document_classification import (
    DocumentReviewRules,
    DocumentTypeClassificationPolicy,
    load_document_review_rules,
    load_document_type_classification_policy,
)
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_CLASSIFIER_NAME = "deterministic_v1"

# Unambiguous extension -> document type (deterministic by file kind).
_EXT_TYPE: dict[str, str] = {
    "dwg": "drawings",
    "dxf": "drawings",
    "png": "photo_media",
    "jpg": "photo_media",
    "jpeg": "photo_media",
    "tif": "photo_media",
    "tiff": "photo_media",
    "heic": "photo_media",
    "mpp": "schedule",
}

# Known construction record-number patterns -> document type. Only the matched
# TYPE is recorded; the raw record number is never persisted.
_RECORD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brfi[\s_\-#]*\d", re.IGNORECASE), "rfi"),
    (re.compile(r"\bchange[\s_\-]*order", re.IGNORECASE), "change_order"),
    (re.compile(r"\b(?:co|pco|cor)[\s_\-#]*\d", re.IGNORECASE), "change_order"),
    (re.compile(r"\bsub(?:mittal)?[\s_\-#]*\d", re.IGNORECASE), "submittal"),
    (
        re.compile(
            r"\b(?:payapp|pay[\s_\-]*app|g70[23]|application[\s_\-]*for[\s_\-]*payment)",
            re.IGNORECASE,
        ),
        "pay_application",
    ),
    (re.compile(r"\binsp(?:ection)?[\s_\-#]*\d", re.IGNORECASE), "inspection_report"),
    (re.compile(r"\baddend(?:um|a)\b", re.IGNORECASE), "addenda"),
]


def _token_hashes(text: Optional[str]) -> set[str]:
    """Normalized token hashes (lowercase, split on non-alphanumeric incl. underscore,
    len>=2) plus a de-pluralized variant so folder names like 'RFIs'/'Drawings' match
    the singular policy vocabulary. Returns hashes only — never raw tokens."""
    if not text:
        return set()
    forms: set[str] = set()
    for raw in re.split(r"[\W_]+", text):
        t = raw.lower()
        if len(t) < 2:
            continue
        forms.add(t)
        if len(t) > 3 and t.endswith("s"):
            forms.add(t[:-1])
    return {h for h in (hash_value(t) for t in forms) if h}


def _detect_record_number(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    for pat, typ in _RECORD_PATTERNS:
        if pat.search(name):
            return typ
    return None


def _build_vocab(
    policy: DocumentTypeClassificationPolicy,
) -> tuple[dict[str, tuple[str, str]], dict[str, int]]:
    """hash(keyword) -> (document_type, keyword) and document_type -> policy-order rank.

    The rank gives a stable, policy-ordered winner when a name/folder matches keywords
    of more than one type (set iteration order is otherwise nondeterministic).
    """
    vocab: dict[str, tuple[str, str]] = {}
    type_rank: dict[str, int] = {}
    for rank, (doc_type, keywords) in enumerate(policy.document_types.items()):
        type_rank[doc_type] = rank
        for kw in keywords:
            h = hash_value(kw.lower())
            if h:
                vocab[h] = (doc_type, kw.lower())
    return vocab, type_rank


def _best_match(
    hashes: set[str],
    vocab: dict[str, tuple[str, str]],
    type_rank: dict[str, int],
) -> tuple[Optional[tuple[str, str]], set[str]]:
    """Deterministic winner ((type, keyword)) + the set of all matched types."""
    matches = [vocab[h] for h in hashes if h in vocab]
    if not matches:
        return None, set()
    best = min(matches, key=lambda tk: (type_rank.get(tk[0], 999), tk[0], tk[1]))
    return best, {t for t, _ in matches}


def _classify_one(
    card: dict[str, Any],
    inv_row: Optional[dict[str, Any]],
    vocab: dict[str, tuple[str, str]],
    type_rank: dict[str, int],
) -> dict[str, Any]:
    name = inv_row.get("name") if inv_row else None
    parent_path = inv_row.get("parent_path") if inv_row else None
    ext = (card.get("file_extension") or "").lower() or None

    contributing: list[str] = []
    matched_keyword: Optional[str] = None

    # Deterministic matches (winner + all matched types for conflict detection).
    folder_match, folder_types = _best_match(_token_hashes(parent_path), vocab, type_rank)
    name_match, name_types = _best_match(_token_hashes(name), vocab, type_rank)
    matched_types: set[str] = folder_types | name_types

    winning_type: Optional[str] = None
    winning_signal = "none"
    signal_class = "heuristic"
    confidence = 0.0
    confidence_class = "unknown"

    rec_type = _detect_record_number(name)
    if rec_type:
        winning_type, winning_signal = rec_type, "record_number"
        signal_class, confidence_class, confidence = "deterministic", "deterministic", 0.95
        contributing.append("record_number")
        matched_types.add(rec_type)
    elif folder_match:
        winning_type, matched_keyword = folder_match
        winning_signal = "folder_token_hashes"
        signal_class, confidence_class, confidence = "deterministic", "deterministic", 0.9
        contributing.append("folder_token_hashes")
    elif name_match:
        winning_type, matched_keyword = name_match
        winning_signal = "filename_token_hashes"
        signal_class, confidence_class, confidence = "deterministic", "high_heuristic", 0.85
        contributing.append("filename_token_hashes")
    elif ext in _EXT_TYPE:
        winning_type = _EXT_TYPE[ext]
        winning_signal = "extension_mime"
        signal_class, confidence_class, confidence = "deterministic", "high_heuristic", 0.8
        contributing.append("extension_mime")
        matched_types.add(winning_type)
    else:
        winning_type = "unknown_needs_review"

    conflicting = len({t for t in matched_types if t != "unknown_needs_review"}) > 1
    return {
        "document_type": winning_type,
        "winning_signal": winning_signal,
        "signal_class": signal_class,
        "confidence": confidence,
        "confidence_class": confidence_class,
        "matched_keyword": matched_keyword,
        "file_extension": ext,
        "contributing_signals": contributing,
        "conflicting": conflicting,
    }


def classify_document_cards(
    store: Any,
    *,
    apply: bool = False,
    classification_policy: Optional[DocumentTypeClassificationPolicy] = None,
    review_rules: Optional[DocumentReviewRules] = None,
    review_evaluator: Optional[ReviewPolicyEvaluator] = None,
) -> dict[str, Any]:
    """Classify every document card and write advisory classification candidates.

    Counts are computed regardless of ``apply``; rows are written only when
    ``apply=True``. The card is never mutated (candidates-only).
    """
    policy = classification_policy or load_document_type_classification_policy()
    rules = review_rules or load_document_review_rules()
    evaluator = review_evaluator or ReviewPolicyEvaluator(load_review_rules())
    vocab, type_rank = _build_vocab(policy)

    # Hydrate inventory once per source: (source_key, item_id) -> row.
    inv_index: dict[tuple[str, str], dict[str, Any]] = {}
    for source_key in store.distinct_inventory_source_keys():
        for row in store.list_inventory_for_source(source_key):
            inv_index[(source_key, row["item_id"])] = row

    cards = store.list_document_cards()
    review_required_count = 0
    by_type: dict[str, int] = {}
    by_signal: dict[str, int] = {}
    by_confidence: dict[str, int] = {}

    for card in cards:
        inv_row = inv_index.get((card["source_id"], card.get("drive_item_id")))
        result = _classify_one(card, inv_row, vocab, type_rank)
        doc_type = result["document_type"]

        # Review routing: sensitivity (folder/name rules) + type/confidence/flags.
        sensitive_categories: list[str] = []
        review_reasons: list[str] = []
        flags: list[str] = []
        name = inv_row.get("name") if inv_row else None
        parent_path = inv_row.get("parent_path") if inv_row else None
        matches = evaluator.evaluate(
            source_key=card["source_id"],
            project_key=card.get("project_key"),
            item={
                "item_id": card.get("drive_item_id"),
                "name": name,
                "parent_path": parent_path,
            },
        )
        if matches:
            sensitive_categories = sorted({m.classification_label for m in matches})
            flags.append("sensitive")
            review_reasons.append("sensitive_folder_or_name_match")

        review_required = bool(matches)
        if doc_type in rules.review_required_when.document_type:
            review_required = True
            review_reasons.append("review_required_document_type")
        if result["confidence_class"] in rules.review_required_when.confidence_class:
            review_required = True
            review_reasons.append("low_or_advisory_confidence")
        if result["conflicting"]:
            review_required = True
            flags.append("conflicting_type_signals")
            review_reasons.append("conflicting_type_signals")

        if review_required:
            review_required_count += 1
        by_type[doc_type] = by_type.get(doc_type, 0) + 1
        by_signal[result["signal_class"]] = by_signal.get(result["signal_class"], 0) + 1
        by_confidence[result["confidence_class"]] = (
            by_confidence.get(result["confidence_class"], 0) + 1
        )

        if apply:
            document_card_id = card["document_card_id"] or card["card_id"]
            candidate_id = hash_value(f"{document_card_id}|{_CLASSIFIER_NAME}")
            signals_json = json.dumps(
                {
                    "classifier": _CLASSIFIER_NAME,
                    "policy_version": policy.version,
                    "winning_signal": result["winning_signal"],
                    "matched_keyword": result["matched_keyword"],
                    "file_extension": result["file_extension"],
                    "contributing_signals": result["contributing_signals"],
                    "sensitive_categories": sensitive_categories,
                    "flags": sorted(set(flags)),
                    "review_reasons": sorted(set(review_reasons)),
                }
            )
            store.upsert_document_classification_candidate(
                candidate_id=candidate_id,
                document_card_id=document_card_id,
                document_type=doc_type,
                classifier_name=_CLASSIFIER_NAME,
                signal_class=result["signal_class"],
                confidence=result["confidence"],
                confidence_class=result["confidence_class"],
                signals_json=signals_json,
                review_required=review_required,
                promotion_status="candidate",
            )

    return {
        "command": "graph files classify-document-cards",
        "mode": "apply" if apply else "dry_run",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "policy_version": policy.version,
        "summary": {
            "cards_total": len(cards),
            "classified": len(cards),
            "review_required": review_required_count,
            "by_document_type": dict(sorted(by_type.items())),
            "by_signal_class": dict(sorted(by_signal.items())),
            "by_confidence_class": dict(sorted(by_confidence.items())),
        },
        "guardrails": {
            "external_systems": "read_only",
            "graph_calls": "none",
            "model_invoked": False,
            "deterministic_first": True,
            "raw_document_text_persisted": False,
            "raw_prompt_or_response_persisted": False,
            "auto_promotion": False,
            "card_mutated": False,
        },
    }
