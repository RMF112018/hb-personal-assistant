"""Phase 08A approved Obsidian index structures (Synthesized Prompt 05).

Index records for system-generated/approved, marker-bounded notes. Metadata only:
hashes, bounded path/heading labels, section markers, review/confidence enums,
counts. No raw note content, signed/download URLs, secrets, or tokens.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

Mode = Literal["dry_run", "apply"]


class ObsidianIndexEntry(BaseModel):
    """One indexed marker section of an approved generated note (metadata only)."""

    note_path_redacted: str
    note_path_hash: str
    section_marker: str | None = None
    heading_redacted: str | None = None
    content_hash: str
    modified_utc: str | None = None
    project_key: str | None = None
    source_type: str | None = None
    confidence_class: str = "high"
    review_tier: int = 1
    review_status: str = "auto_advisory"
    source_ref_count: int = 0
    stale_unknown_flags: list[str] = []
    approved_root_label: str = ""

    model_config = {"extra": "forbid"}

    @field_validator("note_path_redacted", "heading_redacted")
    @classmethod
    def _no_url(cls, value: str | None) -> str | None:
        if value and ("http://" in value or "https://" in value):
            raise ValueError("index label must not contain a URL")
        return value

    @field_validator("review_tier")
    @classmethod
    def _tier_in_range(cls, value: int) -> int:
        if value not in (1, 2, 3):
            raise ValueError("review_tier must be 1, 2, or 3")
        return value


class ObsidianIndexManifest(BaseModel):
    """An index run over the approved roots (dry_run preview or apply)."""

    manifest_id: str
    mode: Mode
    vault_root_fingerprint: str
    approved_roots: list[str] = []
    entry_count: int = 0
    excluded_count: int = 0
    policy_version: str = "unknown"
    entries: list[ObsidianIndexEntry] = []

    model_config = {"extra": "forbid"}
