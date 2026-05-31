"""Phase 07C Prompt 04 — document card materializer.

Materializes ``construction_document_cards`` from the indexed drive-item layer
(``construction_drive_item_inventory``) using SAFE fields only — hashed identity,
redacted title, bounded metadata. Raw file names, web URLs, and parent paths are
NEVER copied into a card; only ``sha256[:16]`` hashes / ``[redacted:...]`` summaries
are persisted, and the six card guard columns stay at their ``CHECK(... = 0)``
defaults.

Rules (07_DOCUMENT_CARD_MATERIALIZATION_PLAN): one card per active file-like drive
item; folders are source context only; deleted items produce no active card;
scope-non-compliant sources (per the document-source policy) are blocked; cards
materialize as review-required candidates (document type / project match /
extraction are deferred to later 07C prompts — no auto-promotion). Idempotent: the
``document_card_id`` is a stable hash of (source, drive, item), so re-running
upserts the same rows.

Read-only against Microsoft 365 (reads the already-indexed inventory; no token, no
Graph call). Writes only local SQLite, and only when ``apply=True``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.document.source_scope import non_compliant_source_keys
from hb_assistant.construction.policy.document_source_policy import (
    DocumentSourcePolicy,
    load_document_source_policy,
)
from hb_assistant.normalize.redaction import hash_value, redact_subject
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

# Size-class thresholds mirror construction/policy/file_ingestion.py LargeFilePolicy
# (extract_warning_bytes / block_extract_bytes) so "oversize" matches the controlled
# extraction bound.
_SMALL_MAX = 1_048_576  # 1 MB
_MEDIUM_MAX = 26_214_400  # 26 MB (extract warning)
_LARGE_MAX = 104_857_600  # 104 MB (extract block) -> at/above is oversize

_MIME_BY_EXT: dict[str, str] = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "csv": "text/csv",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "zip": "application/zip",
    "dwg": "image/vnd.dwg",
    "dxf": "image/vnd.dxf",
    "rvt": "application/octet-stream",
}


def _file_extension(name: Optional[str]) -> Optional[str]:
    if not name or "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].strip().lower()
    return ext or None


def _size_class(size_bytes: Optional[int]) -> str:
    if size_bytes is None:
        return "unknown"
    if size_bytes < _SMALL_MAX:
        return "small"
    if size_bytes < _MEDIUM_MAX:
        return "medium"
    if size_bytes < _LARGE_MAX:
        return "large"
    return "oversize"


def _path_token_hashes(parent_path: Optional[str]) -> Optional[str]:
    if not parent_path:
        return None
    tokens = [t for t in parent_path.replace("\\", "/").split("/") if t]
    if not tokens:
        return None
    return json.dumps([hash_value(t) for t in tokens])


def _system_of(kind: str) -> str:
    if kind.startswith("sharepoint"):
        return "sharepoint"
    if kind.startswith("onedrive"):
        return "onedrive"
    return "other"


def _safe_card_fields(row: dict[str, Any], source: SourceLocation) -> dict[str, Any]:
    """Derive the safe (hashed/redacted/bounded) card upsert kwargs for a row.

    Never returns a raw name / web_url / parent_path value.
    """
    source_id = row["source_key"]
    drive_id = row.get("drive_id")
    item_id = row.get("item_id")
    name = row.get("name")
    document_card_id = hash_value(f"{source_id}|{drive_id}|{item_id}")
    ext = _file_extension(name)
    return {
        "card_id": document_card_id,
        "document_card_id": document_card_id,
        "source_id": source_id,
        "drive_item_id": item_id,
        "project_key": source.project_key,
        "document_type": "unknown",
        "status": "candidate",
        "confidence": None,
        "needs_review": True,
        "card_path": None,
        "drive_id_hash": hash_value(drive_id),
        "drive_item_id_hash": hash_value(item_id),
        "project_number_hash": hash_value(source.project_number),
        "title_hash": hash_value(name),
        "title_redacted": redact_subject(name),
        "file_extension": ext,
        "mime_type": _MIME_BY_EXT.get(ext) if ext else None,
        "size_class": _size_class(row.get("size_bytes")),
        "source_path_hash": hash_value(row.get("parent_path")),
        "source_path_token_hashes_json": _path_token_hashes(row.get("parent_path")),
        "last_modified_datetime": row.get("last_modified"),
        "source_reference_json": json.dumps(
            {
                "source_id": source_id,
                "drive_id_hash": hash_value(drive_id),
                "drive_item_id_hash": hash_value(item_id),
                "last_modified": row.get("last_modified"),
            }
        ),
        "review_status": "pending",
        "review_required": True,
        "review_reasons_json": json.dumps(["unclassified_document_type"]),
        "extraction_eligibility": "not_evaluated",
        "confidence_class": "unknown",
        "guardrail_flags_json": json.dumps(
            {
                "hashed_identity": True,
                "redacted_title": True,
                "no_raw_path_persisted": True,
                "no_raw_url_persisted": True,
                "no_raw_text_persisted": True,
            }
        ),
    }


def materialize_document_cards(
    store: Any,
    *,
    apply: bool = False,
    registry: Optional[SourceRegistry] = None,
    policy: Optional[DocumentSourcePolicy] = None,
) -> dict[str, Any]:
    """Materialize document cards from the drive-item inventory.

    Counts are computed regardless of ``apply``; rows are written only when
    ``apply=True``. ``registry`` / ``policy`` default to the live seeds and may be
    injected for testing.
    """
    registry = registry if registry is not None else load_source_registry()
    policy = policy if policy is not None else load_document_source_policy()
    blocked = non_compliant_source_keys(registry, policy)
    source_by_key = {s.source_key: s for s in registry.sources}

    inventory_rows = 0
    folders_skipped = 0
    deleted_skipped = 0
    unknown_source_skipped = 0
    blocked_source_skipped = 0
    cards_written = 0
    by_system: dict[str, int] = {}

    for source_key in store.distinct_inventory_source_keys():
        for row in store.list_inventory(source_key=source_key):
            inventory_rows += 1
            if row.get("is_folder"):
                folders_skipped += 1
                continue
            if (row.get("status") or "active") != "active":
                deleted_skipped += 1
                continue
            source = source_by_key.get(source_key)
            if source is None:
                unknown_source_skipped += 1
                continue
            if source_key in blocked:
                blocked_source_skipped += 1
                continue
            # Active, file-like, compliant -> materialize a review-required card.
            fields = _safe_card_fields(row, source)
            if apply:
                store.upsert_document_card(**fields)
            cards_written += 1
            system = _system_of(str(source.kind))
            by_system[system] = by_system.get(system, 0) + 1

    considered = cards_written
    return {
        "command": "graph files materialize-document-cards",
        "mode": "apply" if apply else "dry_run",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "summary": {
            "inventory_rows": inventory_rows,
            "folders_skipped": folders_skipped,
            "deleted_skipped": deleted_skipped,
            "unknown_source_skipped": unknown_source_skipped,
            "blocked_source_skipped": blocked_source_skipped,
            "considered": considered,
            "cards_written": cards_written,
            "review_required": cards_written,
        },
        "by_system": by_system,
        "blocked_source_count": len(blocked),
        "guardrails": {
            "external_systems": "read_only",
            "microsoft_365_writeback": "none",
            "graph_calls": "none",
            "local_sqlite_write": apply,
            "raw_document_text_persisted": False,
            "raw_path_or_url_persisted": False,
            "hashed_identity": True,
            "auto_promotion": False,
        },
    }
