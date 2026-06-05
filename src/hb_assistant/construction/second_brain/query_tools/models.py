"""Phase 08A SQLite query-tool result + receipt structures (Prompt 06).

A `QueryToolResult` is the bounded, source-linked output of one allowlisted query
tool. Rows reuse the retrieval `RetrievalItem` (already rejects raw reference field
names); the result adds bounding metadata, a per-tier summary, and `source_refs`.
A field validator rejects any forbidden raw reference field name in `source_refs`.
`QueryToolReceipt` mirrors the V26 ``query_tool_receipts`` columns (metadata only).
No raw bodies, document text, calendar payloads, prompts, responses, URLs, or
secrets — ever.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

from ..reasoning import FORBIDDEN_REFERENCE_FIELDS
from ..retrieval import RetrievalItem

QueryToolStatus = Literal["ok", "empty", "no_read_model"]


class QueryToolResult(BaseModel):
    """Bounded, source-linked result of one allowlisted SQLite query tool."""

    tool_name: str
    project_key: str | None = None
    status: QueryToolStatus = "empty"
    items: list[RetrievalItem] = []
    source_refs: list[dict[str, str]] = []
    row_count: int = 0
    char_count: int = 0
    truncated: bool = False
    review_tier_summary: dict[str, int] = {}
    warnings: list[str] = []

    model_config = {"extra": "forbid"}

    @field_validator("source_refs")
    @classmethod
    def _refs_have_no_forbidden_fields(cls, value: list[dict[str, str]]) -> list[dict[str, str]]:
        for ref in value:
            forbidden = set(ref) & FORBIDDEN_REFERENCE_FIELDS
            if forbidden:
                raise ValueError(f"forbidden raw field(s) in source_ref: {sorted(forbidden)}")
        return value


class QueryToolReceipt(BaseModel):
    """Metadata-only audit row mirroring V26 ``query_tool_receipts``."""

    tool_receipt_id: str
    retrieval_receipt_id: str | None = None
    tool_name: str
    project_key: str | None = None
    row_count: int = 0
    char_count: int = 0
    truncated: bool = False
    status: str = "empty"
    created_utc: str

    model_config = {"extra": "forbid"}
