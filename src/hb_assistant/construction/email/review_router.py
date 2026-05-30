"""Phase 06 Prompt 10 — email review routing + encrypted-body eligibility (local-only).

Decides, for each project-matched email already indexed in SQLite, three things:

1. **review routing** — sensitive (any review category) or low-confidence project
   matches are routed to ``email_review_queue`` before any body-derived intelligence
   is trusted;
2. **encrypted-body capture eligibility** — whether the message is eligible for a
   read-only full-body *fetch* and for *encrypted-at-rest* storage (text vault only),
   bounded by per-run policy and folder/lookback scope;
3. **decision metadata** — the per-message :class:`EmailBodyCaptureDecision` recorded
   alongside each routed review row (additive V13 columns).

Local-only: reads stored ``email_project_matches`` + ``email_messages`` (bounded,
redacted previews) — **no Graph call, no mailbox access**. Plaintext body is never
fetched, stored, or emitted here; this prompt only computes eligibility. The actual
encrypted capture path lives in the indexer (``--include-encrypted-body``).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel

from hb_assistant.construction.email.project_matcher import load_pilot_project_descriptors
from hb_assistant.construction.email.review_categories import (
    classify_review_categories,
    get_review_category,
)
from hb_assistant.construction.policy.email_active import (
    EmailIntelligenceActivePolicy,
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

POLICY_VERSION = "phase06-email-active-v1"

# Folder roles that are out of operational scope (never body-capture eligible).
_EXCLUDED_FOLDER_ROLES = {
    "deleted", "deleted_items", "junk", "junk_email", "drafts", "draft",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.90:
        return "high"
    if confidence >= 0.75:
        return "medium"
    return "low"


class EmailBodyCaptureDecision(BaseModel):
    """Per-message encrypted-body capture decision (metadata only; no body text)."""

    message_id: str
    eligible_for_full_body_fetch: bool
    eligible_for_encrypted_body_storage: bool
    encrypted_storage_mode: Literal["encrypted_text_vault", "not_allowed"]
    review_required_before_body_use: bool
    review_required_after_indexing: bool
    sensitivity_categories: list[str]
    decision_reasons: list[str]
    policy_version: str

    model_config = {"extra": "forbid"}


class ReviewRoutingSample(BaseModel):
    """Evidence-safe preview of one routing decision (redacted; never body text)."""

    message_ref: str  # hashed message id — never the raw Graph id
    project_match_confidence: str  # "high" | "medium" | "low"
    sensitivity_categories: list[str]
    review_required: bool
    body_capture_eligible: bool
    encrypted_body_capture_allowed: bool
    encrypted_storage_mode: Literal["encrypted_text_vault", "not_allowed"]
    plaintext_body_persistence_allowed: Literal[False] = False

    model_config = {"extra": "forbid"}


class ReviewRoutingReport(BaseModel):
    """Outcome of a review-routing run (counts + redacted samples; no content)."""

    project_key: Optional[str] = None
    project_number: Optional[str] = None
    lookback_days: int
    received_after: str
    dry_run: bool
    persisted: bool
    policy_version: str
    messages_considered: int
    routed_to_review: int
    review_items_enqueued: int
    body_capture_eligible_count: int
    encrypted_body_storage_eligible_count: int
    review_required_before_body_use_count: int
    categories_seen: dict[str, int]
    queue_open: int
    queue_resolved: int
    samples: list[ReviewRoutingSample]
    disclaimer: str = (
        "routing is conservative; categories are signals not determinations; "
        "plaintext body is never persisted"
    )

    model_config = {"extra": "forbid"}


class _MessageRouting(BaseModel):
    """Internal: a message's decision + the review items it produces."""

    decision: EmailBodyCaptureDecision
    project_key: Optional[str]
    confidence: float
    review_items: list[dict[str, Any]]

    model_config = {"extra": "forbid"}


class ReviewRouter:
    """Local-only review routing + encrypted-body eligibility for indexed email."""

    def __init__(
        self,
        store: ConstructionStore,
        policy: Optional[EmailIntelligenceActivePolicy] = None,
    ) -> None:
        self._store = store
        self._policy = policy or load_email_intelligence_active_policy()

    def route(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        dry_run: bool = True,
        max_messages: int = 200,
    ) -> ReviewRoutingReport:
        lookback = max(1, min(int(lookback_days or self._policy.default_lookback_days), 366))
        descriptors = load_pilot_project_descriptors(project_key)
        descriptor = descriptors[0] if descriptors else None
        project_number = descriptor.project_number if descriptor else None

        received_after = (
            (_utc_now() - timedelta(days=lookback)).replace(microsecond=0).isoformat()
        )

        matches = self._store.list_email_project_matches(
            project_key=project_key, limit=max_messages
        )
        # Dedupe to the best-confidence match per message.
        best_by_message: dict[str, dict[str, Any]] = {}
        for m in matches:
            mid = m["message_id"]
            if mid not in best_by_message or m["confidence"] > best_by_message[mid]["confidence"]:
                best_by_message[mid] = m

        budget = int(self._policy.max_full_body_fetch_per_run)
        body_fetch_used = 0

        routings: list[_MessageRouting] = []
        considered = 0
        # Deterministic order so the per-run cap is stable across runs.
        for mid in sorted(best_by_message):
            match = best_by_message[mid]
            msg = self._store.get_email_message(mid)
            if msg is None:
                continue
            received = msg.get("received_datetime")
            if received and received < received_after:
                continue
            considered += 1
            routing = self._route_message(
                msg, match, body_fetch_budget_remaining=budget - body_fetch_used
            )
            if routing.decision.eligible_for_full_body_fetch:
                body_fetch_used += 1
            routings.append(routing)

        if not dry_run:
            self._persist(routings, project_key)

        return self._report(
            routings,
            project_key=project_key,
            project_number=project_number,
            lookback=lookback,
            received_after=received_after,
            dry_run=dry_run,
        )

    # --- per-message decision -------------------------------------------------

    def _route_message(
        self,
        msg: dict[str, Any],
        match: dict[str, Any],
        *,
        body_fetch_budget_remaining: int,
    ) -> _MessageRouting:
        mid = msg["message_id"]
        project_key = match.get("project_key")
        confidence = float(match.get("confidence") or 0.0)
        preview = msg.get("body_preview_excerpt_redacted") or ""
        categories = classify_review_categories(preview)

        low_confidence = confidence < float(self._policy.low_confidence_threshold)
        match_review = bool(match.get("review_required"))
        review_required = bool(categories) or low_confidence or match_review

        folder_excluded = self._folder_excluded(msg.get("source_id"))

        reasons: list[str] = []
        # Full-body fetch eligibility (read-only fetch, policy-gated, bounded + scoped).
        eligible_fetch = True
        if folder_excluded:
            eligible_fetch = False
            reasons.append("folder_excluded")
        if not self._policy.full_body_storage_allowed:
            eligible_fetch = False
            reasons.append("policy_disallows_full_body_storage")
        if eligible_fetch and body_fetch_budget_remaining <= 0:
            eligible_fetch = False
            reasons.append("per_run_body_fetch_cap_reached")
        if eligible_fetch:
            reasons.append("project_matched_within_lookback")

        storage_allowed_by_policy = (
            self._policy.full_body_storage_allowed
            and self._policy.full_body_storage_mode == "encrypted_text_vault"
        )
        eligible_storage = eligible_fetch and storage_allowed_by_policy
        mode: Literal["encrypted_text_vault", "not_allowed"] = (
            "encrypted_text_vault" if eligible_storage else "not_allowed"
        )

        if categories:
            reasons.append("sensitive_categories:" + ",".join(categories))
        if low_confidence:
            reasons.append("low_confidence_project_match")

        decision = EmailBodyCaptureDecision(
            message_id=mid,
            eligible_for_full_body_fetch=eligible_fetch,
            eligible_for_encrypted_body_storage=eligible_storage,
            encrypted_storage_mode=mode,
            review_required_before_body_use=review_required,
            review_required_after_indexing=review_required,
            sensitivity_categories=categories,
            decision_reasons=reasons,
            policy_version=POLICY_VERSION,
        )

        review_items = (
            self._build_review_items(decision, project_key, confidence, low_confidence)
            if review_required
            else []
        )
        return _MessageRouting(
            decision=decision,
            project_key=project_key,
            confidence=confidence,
            review_items=review_items,
        )

    def _build_review_items(
        self,
        decision: EmailBodyCaptureDecision,
        project_key: Optional[str],
        confidence: float,
        low_confidence: bool,
    ) -> list[dict[str, Any]]:
        decision_json = decision.model_dump_json()
        items: list[dict[str, Any]] = []
        for cid in decision.sensitivity_categories:
            category = get_review_category(cid)
            if category is None:  # pragma: no cover - registry is the source of truth
                continue
            items.append(
                self._review_item(
                    decision.message_id,
                    project_key,
                    category=category.id,
                    sensitivity=category.sensitivity_level,
                    reason=category.evidence_safe_explanation,
                    suggested_action=category.recommended_review_action,
                    confidence=confidence,
                    decision=decision,
                    decision_json=decision_json,
                )
            )
        if not decision.sensitivity_categories and low_confidence:
            items.append(
                self._review_item(
                    decision.message_id,
                    project_key,
                    category="low_confidence_project_match",
                    sensitivity="medium",
                    reason="low-confidence project match; verify before relying on it",
                    suggested_action="verify_project_match",
                    confidence=confidence,
                    decision=decision,
                    decision_json=decision_json,
                )
            )
        return items

    @staticmethod
    def _review_item(
        message_id: str,
        project_key: Optional[str],
        *,
        category: str,
        sensitivity: str,
        reason: str,
        suggested_action: str,
        confidence: float,
        decision: EmailBodyCaptureDecision,
        decision_json: str,
    ) -> dict[str, Any]:
        review_id = hash_value(f"{message_id}|{category}|{reason}") or f"{message_id}:{category}"
        return {
            "review_id": review_id,
            "message_id": message_id,
            "project_key": project_key,
            "category": category,
            "sensitivity": sensitivity,
            "reason": reason,
            "suggested_action": suggested_action,
            "confidence": confidence,
            "body_capture_eligible": decision.eligible_for_full_body_fetch,
            "encrypted_body_capture_allowed": decision.eligible_for_encrypted_body_storage,
            "review_required_before_body_use": decision.review_required_before_body_use,
            "body_capture_decision_json": decision_json,
        }

    def _folder_excluded(self, source_id: Optional[str]) -> bool:
        if not source_id:
            return False
        folder = self._store.get_email_source_location(source_id)
        if folder is None:
            return False
        if not bool(folder.get("include_in_sync", True)):
            return True
        return str(folder.get("folder_role") or "").lower() in _EXCLUDED_FOLDER_ROLES

    # --- persistence + reporting ----------------------------------------------

    def _persist(self, routings: list[_MessageRouting], project_key: Optional[str]) -> None:
        enqueued = 0
        for routing in routings:
            for item in routing.review_items:
                inserted = self._store.enqueue_email_review_item(
                    review_id=item["review_id"],
                    message_id=item["message_id"],
                    category=item["category"],
                    sensitivity=item["sensitivity"],
                    reason=item["reason"],
                    suggested_action=item["suggested_action"],
                    confidence=item["confidence"],
                    project_key=item["project_key"],
                    body_capture_eligible=item["body_capture_eligible"],
                    encrypted_body_capture_allowed=item["encrypted_body_capture_allowed"],
                    review_required_before_body_use=item["review_required_before_body_use"],
                    body_capture_decision_json=item["body_capture_decision_json"],
                )
                if inserted:
                    enqueued += 1
        self._store.insert_email_processing_receipt(
            receipt_id=f"{uuid.uuid4()}:review_routing",
            operation="review_routing",
            status="ok",
            project_key=project_key,
            detail={
                "messages_considered": len(routings),
                "review_items_enqueued": enqueued,
            },
        )

    def _report(
        self,
        routings: list[_MessageRouting],
        *,
        project_key: Optional[str],
        project_number: Optional[str],
        lookback: int,
        received_after: str,
        dry_run: bool,
    ) -> ReviewRoutingReport:
        categories_seen: dict[str, int] = {}
        routed = 0
        items_enqueued = 0
        body_eligible = 0
        storage_eligible = 0
        review_before_body = 0
        samples: list[ReviewRoutingSample] = []

        for routing in routings:
            decision = routing.decision
            if routing.review_items:
                routed += 1
                items_enqueued += len(routing.review_items)
            if decision.eligible_for_full_body_fetch:
                body_eligible += 1
            if decision.eligible_for_encrypted_body_storage:
                storage_eligible += 1
            if decision.review_required_before_body_use:
                review_before_body += 1
            for cid in decision.sensitivity_categories:
                categories_seen[cid] = categories_seen.get(cid, 0) + 1
            if len(samples) < 10:
                samples.append(
                    ReviewRoutingSample(
                        message_ref=(hash_value(decision.message_id) or decision.message_id)[:16],
                        project_match_confidence=_confidence_band(routing.confidence),
                        sensitivity_categories=decision.sensitivity_categories,
                        review_required=decision.review_required_after_indexing,
                        body_capture_eligible=decision.eligible_for_full_body_fetch,
                        encrypted_body_capture_allowed=decision.eligible_for_encrypted_body_storage,
                        encrypted_storage_mode=decision.encrypted_storage_mode,
                    )
                )

        return ReviewRoutingReport(
            project_key=project_key,
            project_number=project_number,
            lookback_days=lookback,
            received_after=received_after,
            dry_run=dry_run,
            persisted=not dry_run,
            policy_version=POLICY_VERSION,
            messages_considered=len(routings),
            routed_to_review=routed,
            review_items_enqueued=items_enqueued,
            body_capture_eligible_count=body_eligible,
            encrypted_body_storage_eligible_count=storage_eligible,
            review_required_before_body_use_count=review_before_body,
            categories_seen=categories_seen,
            queue_open=self._store.count_email_review_queue(project_key=project_key, status="open"),
            queue_resolved=self._store.count_email_review_queue(
                project_key=project_key, status="resolved"
            ),
            samples=samples,
        )
