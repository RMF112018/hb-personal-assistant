"""EmailClassifier: orchestrates mention detection on persisted redacted previews,
updates body flags in store, and creates provenance links via SourceLinkRegistry.

All inputs are already redacted (body_preview_redacted only). No full bodies are ever accepted or logged.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from pydantic import BaseModel, Field

from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.normalize.email import Email
from hb_assistant.store.repositories import Store

from .body_inspector import BodyInspector
from .detector import BodyMentionDetector


class ClassificationResult(BaseModel):
    """Redacted classification output matching resources/email-classification.schema.json.

    Addendum Prompt 05 extension: detection_method records whether the mention
    came from preview only or the bounded full-body inspector path.
    """

    message_source_record_id: str
    classifications: List[str] = Field(default_factory=list)
    body_mention_detected: bool
    confidence: float
    detection_method: str = "preview"  # "preview" | "body" | "none"


class EmailClassifier:
    """High-level classifier for Phase 6 + Addendum Prompt 05.

    - Primary: persisted redacted previews (fast path, unchanged).
    - Fallback (Prompt 05): when a body_fetcher is provided and preview misses,
      calls the bounded body inspector (via MailClient.get_message_body_for_inspection
      or test mock). Never persists raw body.
    - Updates DB flags via Store (now includes optional detection method/excerpt when schema extended).
    - Creates "mentions" (and optionally "waiting_on") links via Registry.
    - Mutates in-memory Email model.
    """

    def __init__(
        self,
        store: Optional[Store] = None,
        registry: Optional[SourceLinkRegistry] = None,
        detector: Optional[BodyMentionDetector] = None,
        body_inspector: Optional[BodyInspector] = None,
        body_fetcher: Optional[Callable[[str], str]] = None,  # message_id -> bounded body text
    ):
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(self.store)
        self.detector = detector or BodyMentionDetector()
        self.body_inspector = body_inspector or BodyInspector()
        self.body_fetcher = body_fetcher

    def classify_email(self, email: Email) -> ClassificationResult:
        if email.source_record_id is None:
            raise ValueError("Email must have source_record_id (must be persisted first)")

        det = self.detector.detect(email.body_preview_redacted)
        method = "preview"
        excerpt: Optional[str] = None

        # Prompt 05 body fallback (only if preview missed and fetcher available)
        if not det["body_mention_detected"] and self.body_fetcher and email.id:
            try:
                raw_body = self.body_fetcher(str(email.id))
                body_det = self.body_inspector.inspect(raw_body)
                if body_det["body_mention_detected"]:
                    det = body_det
                    method = "body"
                    excerpt = body_det.get("match_excerpt_redacted")
            except Exception:
                # Never let body fetch/inspect break classification
                pass

        classifications: List[str] = []
        if det["body_mention_detected"]:
            classifications.append("bobby_mention")
        if "possible_direct_ask_or_waiting" in det.get("signals", []):
            classifications.append("possible_action_or_waiting")

        # 1. Update DB flags (idempotent safe; extended for P05 when store supports)
        self.store.update_email_body_flags(
            source_record_id=email.source_record_id,
            body_checked=True,
            body_mention_detected=det["body_mention_detected"],
            # body_detection_method and excerpt passed through if store supports (additive)
            body_detection_method=method if method != "preview" else None,
            body_match_excerpt_redacted=excerpt,
        )

        # 2. Create provenance link
        link_type = "mentions" if det["body_mention_detected"] else "derived_from"
        self.registry.link_sources(
            from_id=email.source_record_id,
            to_id=email.source_record_id,
            link_type=link_type,
            confidence=det["confidence"],
        )

        # Optional waiting_on link for signals
        if "possible_action_or_waiting" in classifications:
            self.registry.link_sources(
                from_id=email.source_record_id,
                to_id=email.source_record_id,
                link_type="waiting_on",
                confidence=0.6,
            )

        result = ClassificationResult(
            message_source_record_id=str(email.source_record_id),
            classifications=classifications,
            body_mention_detected=det["body_mention_detected"],
            confidence=det["confidence"],
            detection_method=method,
        )

        # 3. Mutate in-memory model (now that Email has the fields)
        email.body_checked = True
        email.body_mention_detected = det["body_mention_detected"]
        if excerpt:
            email.body_excerpt_redacted = excerpt  # type: ignore[attr-defined]
        # Refresh links on model for caller convenience
        email.source_links = self.registry.get_links(email.source_record_id) or email.source_links

        return result
