"""Body mention detection and email classification (Phase 6).

Operates exclusively on redacted body_preview_redacted persisted by Phase 4/5.
Never touches or logs full email bodies. Deterministic alias-based detection for MVP.
"""

from .aliases import AliasResolver
from .body_inspector import BodyInspector
from .detector import BodyMentionDetector
from .classifier import EmailClassifier, ClassificationResult

__all__ = [
    "AliasResolver",
    "BodyInspector",
    "BodyMentionDetector",
    "EmailClassifier",
    "ClassificationResult",
]
