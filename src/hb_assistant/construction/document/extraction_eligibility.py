"""Phase 07C Prompt 07 — controlled extraction eligibility (deterministic-first).

Decides, *before any content download or parse*, the extraction disposition of each
``construction_document_cards`` row and persists it to the card's
``extraction_eligibility`` column (one of: not_evaluated / metadata_only / eligible /
manual_approval_required / blocked / skipped). No download, no parse, no model, no
content read — the decision is computed deterministically from card metadata
(file extension, size class, document type, review state, project binding) plus the
existing V18 file-ingestion policy and the document review rules.

Precedence (first match wins): dangerous/blocked or oversize kinds are dispositioned
first; non-text-parseable kinds (images, CAD, archives, video) become ``metadata_only``
regardless of review because they can never yield extracted text; text-parseable
review-required cards route to ``manual_approval_required`` (honoring "review-required
files cannot extract"); only a non-review, parseable, deterministically project-bound
card becomes ``eligible`` — and ``eligible`` means *may* be extracted on an explicit,
separately-gated request, never an automatic download.
"""

from __future__ import annotations

from typing import Any, Optional

from hb_assistant.construction.document.contracts import load_document_contract
from hb_assistant.construction.policy.document_classification import (
    DocumentReviewRules,
    load_document_review_rules,
)
from hb_assistant.construction.policy.file_ingestion import (
    FileIngestionPolicy,
    load_file_ingestion_policy,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_REVIEW_STATUSES_HOLDING = {"pending", "blocked"}


def _disposition(
    card: dict[str, Any],
    ingestion: FileIngestionPolicy,
    review_required_types: set[str],
) -> tuple[str, str]:
    """Return (extraction_eligibility, reason_code) for one card (deterministic)."""
    ext = (card.get("file_extension") or "").strip().lower().lstrip(".")
    size_class = card.get("size_class") or "unknown"
    document_type = card.get("document_type") or ""
    review_required = bool(card.get("review_required"))
    review_status = card.get("review_status") or ""
    disp = ingestion.extension_dispositions

    if not ext:
        return "skipped", "no_extension"
    if ext in disp.blocked:
        return "blocked", "policy_disallowed_extension"
    if size_class == "oversize":
        return "blocked", "oversize"
    if ext in disp.metadata_only:
        return "metadata_only", "metadata_only_extension"
    if (
        review_required
        or review_status in _REVIEW_STATUSES_HOLDING
        or document_type in review_required_types
    ):
        return "manual_approval_required", "review_required"
    if ext not in disp.eligible:
        return "metadata_only", "unparseable_extension"
    if not card.get("project_key") or not card.get("project_number_hash"):
        return "manual_approval_required", "low_project_confidence"
    return "eligible", "eligible"


def evaluate_extraction_eligibility(
    store: Any,
    *,
    apply: bool = False,
    ingestion_policy: Optional[FileIngestionPolicy] = None,
    review_rules: Optional[DocumentReviewRules] = None,
) -> dict[str, Any]:
    """Evaluate and (when ``apply``) persist each card's extraction disposition.

    Counts are computed regardless of ``apply``; the ``extraction_eligibility`` column
    is written only when ``apply=True``. No other card field is touched. Nothing is
    ever downloaded, parsed, or persisted as text.
    """
    ingestion = ingestion_policy or load_file_ingestion_policy()
    rules = review_rules or load_document_review_rules()
    review_required_types = set(rules.review_required_when.document_type)
    contract = load_document_contract("controlled_extraction_contract")

    cards = store.list_document_cards()
    by_eligibility: dict[str, int] = {}
    by_reason_code: dict[str, int] = {}
    review_held = 0

    for card in cards:
        disposition, reason = _disposition(card, ingestion, review_required_types)
        by_eligibility[disposition] = by_eligibility.get(disposition, 0) + 1
        by_reason_code[reason] = by_reason_code.get(reason, 0) + 1
        if disposition != "eligible" and bool(card.get("review_required")):
            review_held += 1
        if apply:
            store.update_document_card_extraction_eligibility(
                card_id=card["card_id"],
                extraction_eligibility=disposition,
            )

    return {
        "command": "graph files evaluate-extraction-eligibility",
        "mode": "apply" if apply else "dry_run",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "contract_version": contract.get("version"),
        "summary": {
            "cards_total": len(cards),
            "evaluated": len(cards),
            "eligible": by_eligibility.get("eligible", 0),
            "review_required_held_from_extraction": review_held,
            "by_eligibility": dict(sorted(by_eligibility.items())),
            "by_reason_code": dict(sorted(by_reason_code.items())),
        },
        "guardrails": {
            "external_systems": "read_only",
            "graph_calls": "none",
            "model_invoked": False,
            "deterministic_first": True,
            "download_performed": False,
            "parse_performed": False,
            "raw_document_text_persisted": False,
            "raw_path_or_url_persisted": False,
            "auto_promotion": False,
            "card_columns_mutated": ["extraction_eligibility"] if apply else [],
            "card_eligibility_updated": apply,
        },
    }
