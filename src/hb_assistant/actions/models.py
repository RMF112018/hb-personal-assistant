"""Pydantic models for actions (minimal, follows discovered patterns like ClassificationResult/Email).

No full bodies or file contents. JSON serializable for CLI redacted output.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ActionItem(BaseModel):
    """Source-linked action candidate or persisted item.

    Matches discovered action_items table + source_links provenance.
    """

    stable_key: str
    title: str
    action_type: str = "task"  # "task" | "waiting_on" etc (from signals)
    due_date: Optional[str] = None
    confidence: float
    status: str = "open"
    sources: list[dict[str, Any]] = Field(default_factory=list)  # provenance links
