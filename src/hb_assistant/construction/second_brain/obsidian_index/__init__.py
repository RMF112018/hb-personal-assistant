"""Phase 08A approved Obsidian indexing (Synthesized Prompt 05).

Indexes only system-generated/approved, marker-bounded notes into the V26
obsidian_index_* tables (metadata only). Read-only over the vault; no source-note
mutation, no raw content, no raw vault browsing.
"""

from __future__ import annotations

from .indexer import (
    build_approved_obsidian_index_proof,
    build_index,
    list_approved_obsidian_index_entries,
    scan_approved_notes,
    write_index_manifest,
)
from .models import ObsidianIndexEntry, ObsidianIndexManifest
from .policy import (
    ObsidianIndexPolicy,
    ObsidianIndexPolicyError,
    load_obsidian_index_policy,
)

__all__ = [
    "build_approved_obsidian_index_proof",
    "build_index",
    "list_approved_obsidian_index_entries",
    "scan_approved_notes",
    "write_index_manifest",
    "ObsidianIndexEntry",
    "ObsidianIndexManifest",
    "ObsidianIndexPolicy",
    "ObsidianIndexPolicyError",
    "load_obsidian_index_policy",
]
