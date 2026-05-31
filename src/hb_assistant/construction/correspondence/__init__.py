"""Phase 07B correspondence intelligence (read-only, advisory).

Aggregates already-ingested, redacted email/calendar read models into project-level
correspondence previews and review warnings. Read-only with respect to every external
system **and** to local SQLite (no writes at all); every output is advisory — signals, not
determinations.
"""

from __future__ import annotations

from .correspondence_review import (
    CorrespondencePreview,
    CorrespondenceReviewBuilder,
    CorrespondenceReviewReport,
    CorrespondenceWarning,
)

__all__ = [
    "CorrespondencePreview",
    "CorrespondenceReviewBuilder",
    "CorrespondenceReviewReport",
    "CorrespondenceWarning",
]
