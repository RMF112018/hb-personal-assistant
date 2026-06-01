"""Phase 07B correspondence intelligence (read-only, advisory).

Aggregates already-ingested, redacted email/calendar read models into project-level
correspondence previews and review warnings. Read-only with respect to every external
system **and** to local SQLite (no writes at all); every output is advisory — signals, not
determinations.
"""

from __future__ import annotations

from .correspondence_context import (
    CorrespondenceContextBuilder,
    correspondence_context_status,
)
from .correspondence_review import (
    CorrespondencePreview,
    CorrespondenceReviewBuilder,
    CorrespondenceReviewReport,
    CorrespondenceWarning,
)

__all__ = [
    "CorrespondenceContextBuilder",
    "CorrespondencePreview",
    "CorrespondenceReviewBuilder",
    "CorrespondenceReviewReport",
    "CorrespondenceWarning",
    "correspondence_context_status",
]
