"""Obsidian vault writer and Daily Brief module (Phase 8).

Marker-bounded, source-traceable, redacted-only generation for Daily Notes and AI Outputs.
Preserves 100% of user content outside markers. Dry-run supported.
Integrates with Store + SourceLinkRegistry for action_items, classified signals, and links.
"""

from .writer import MarkerBoundedWriter
from .brief import DailyBriefGenerator

__all__ = [
    "MarkerBoundedWriter",
    "DailyBriefGenerator",
]
