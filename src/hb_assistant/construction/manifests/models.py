"""Pydantic models for construction-agent manifests and receipts.

All models are recomputable projections of SQLite state. They never carry
source-document body, content, or text — only metadata identifiers and counts.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SourceManifestEntry(BaseModel):
    item_id: str
    name: Optional[str] = None
    web_url: Optional[str] = None
    parent_path: Optional[str] = None
    size_bytes: Optional[int] = None
    is_folder: bool = False
    status: str = "active"
    last_modified: Optional[str] = None

    model_config = {"extra": "forbid"}


class SourceManifest(BaseModel):
    source_key: str
    project_key: Optional[str] = None
    kind: str
    display_name: str
    resolution_status: str = "pending"
    drive_id: Optional[str] = None
    web_url: Optional[str] = None
    generated_at: str
    run_id: str
    item_counts: dict[str, int] = Field(default_factory=dict)
    sample_entries: list[SourceManifestEntry] = Field(default_factory=list)
    sample_size_cap: int = 20
    delta_link_fingerprint: Optional[str] = None
    last_sync_at: Optional[str] = None
    guardrails: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class SyncReceipt(BaseModel):
    run_id: str
    source_key: str
    mode: str  # "dry_run" | "apply"
    status: str  # "ok" | "auth_required" | "unresolved" | "failed" | "projected"
    started_at: str
    finished_at: Optional[str] = None
    pages_seen: int = 0
    items_seen: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_deleted: int = 0
    delta_link_recorded: bool = False
    error_redacted: Optional[str] = None
    guardrails: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ProcessingReceipt(BaseModel):
    run_id: str
    mode: str
    started_at: str
    finished_at: Optional[str] = None
    source_count: int
    per_source: list[SyncReceipt] = Field(default_factory=list)
    totals: dict[str, int] = Field(default_factory=dict)
    error_summary: list[str] = Field(default_factory=list)
    guardrails: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}
