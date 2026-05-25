"""EmailClassifier: orchestrates mention detection on persisted redacted previews,
updates body flags in store, and creates provenance links via SourceLinkRegistry.

All inputs are already redacted (body_preview_redacted only). No full bodies are ever accepted or logged.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from hb_assistant.links.registry import SourceLinkRegistry
from hb_assistant.normalize.email import Email
from hb_assistant.store.repositories import Store

from .detector import BodyMentionDetector


class ClassificationResult(BaseModel):
    """Redacted classification output matching resources/email-classification.schema.json."""

    message_source_record_id: str
    classifications: List[str] = Field(default_factory=list)
    body_mention_detected: bool
    confidence: float


class EmailClassifier:
    """High-level classifier for Phase 6.

    - Uses only persisted redacted previews.
    - Updates DB flags via Store.
    - Creates "mentions" (and optionally "waiting_on") links via Registry.
    - Mutates the in-memory Email model with the two body_* flags for convenience.
    """

    def __init__(
        self,
        store: Optional[Store] = None,
        registry: Optional[SourceLinkRegistry] = None,
        detector: Optional[BodyMentionDetector] = None,
    ):
        self.store = store or Store()
        self.registry = registry or SourceLinkRegistry(self.store)
        self.detector = detector or BodyMentionDetector()

    def classify_email(self, email: Email) -> ClassificationResult:
        if email.source_record_id is None:
            raise ValueError("Email must have source_record_id (must be persisted first)")

        det = self.detector.detect(email.body_preview_redacted)

        classifications: List[str] = []
        if det["body_mention_detected"]:
            classifications.append("bobby_mention")
        if "possible_direct_ask_or_waiting" in det.get("signals", []):
            classifications.append("possible_action_or_waiting")

        # 1. Update DB flags (idempotent safe)
        self.store.update_email_body_flags(
            source_record_id=email.source_record_id,
            body_checked=True,
            body_mention_detected=det["body_mention_detected"],
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
        )

        # 3. Mutate in-memory model (now that Email has the fields)
        email.body_checked = True
        email.body_mention_detected = det["body_mention_detected"]
        # Refresh links on model for caller convenience
        email.source_links = self.registry.get_links(email.source_record_id) or email.source_links

        return result
