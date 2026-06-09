"""V2↔V5 drive-item bridge: project legacy V2 inventory rows into the
canonical V5 row shape, and provide a union-read that combines both
tables with V5-wins precedence on key collisions.

Design choice — **read model**, not bulk mirror:

- The live delta crawler still writes only to V2
  (``construction_drive_item_inventory``); the V5 table
  (``construction_drive_items``) is the canonical target for future
  Phase 03 writes.
- This module provides a pure projection (V2 row → V5-shape) plus a
  union-read so callers can begin reading V5-shaped data today without
  duplicating storage and without a destructive migration.
- When a later prompt flips the crawler to write V5 directly, the union
  read naturally degrades to V5-only (V5 wins on key collisions) and
  this module needs no change.

Read-only invariants:

- Pure-Python projection; no SQLite write paths.
- No filesystem mutation, no HTTP client, no source-system call.
- ``V5DriveItem.model_config = {"extra": "forbid"}`` keeps body/text/
  content keys out of the shape at the type layer.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from pydantic import BaseModel

from hb_assistant.construction.store import ConstructionStore

# Registry of V2 fields that the V5 schema cannot represent. The bridge
# records these per-source on the BridgeReport so downstream auditors
# know what's left behind by the projection.
_LOSSY_V2_FIELDS: tuple[str, ...] = ("etag", "first_seen_at", "last_seen_at")


class V5DriveItem(BaseModel):
    """Canonical V5 ``construction_drive_items`` row shape (V5 base + V15 rich metadata).

    ``extra: forbid`` makes it a type-layer guard against accidental
    leakage of body/content/text/excerpt fields through the bridge —
    Pydantic raises ``ValidationError`` if any caller tries to pass an
    extra key.
    """

    source_id: str
    drive_id: str
    drive_item_id: str
    parent_drive_item_id: Optional[str] = None
    site_id: Optional[str] = None
    list_id: Optional[str] = None
    list_item_id: Optional[str] = None
    name: Optional[str] = None
    path: Optional[str] = None
    web_url: Optional[str] = None
    is_folder: bool = False
    is_file: bool = False
    file_extension: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    last_modified_datetime: Optional[str] = None
    deleted: bool = False
    quick_xor_hash: Optional[str] = None
    project_number_detected: Optional[str] = None
    document_type_detected: Optional[str] = None
    indexing_policy: Optional[str] = None
    classification_status: Optional[str] = None
    created_utc: Optional[str] = None
    updated_utc: Optional[str] = None
    # v15 Phase 06 (Files) rich driveItem metadata (all metadata; no body/content).
    is_package: bool = False
    e_tag: Optional[str] = None
    c_tag: Optional[str] = None
    created_datetime: Optional[str] = None
    parent_reference_path: Optional[str] = None
    folder_child_count: Optional[int] = None
    sharepoint_web_id: Optional[str] = None
    sharepoint_list_item_id: Optional[str] = None
    file_hashes_json: Optional[str] = None
    package_json_redacted: Optional[str] = None
    remote_item_json_redacted: Optional[str] = None
    first_seen_utc: Optional[str] = None
    last_seen_utc: Optional[str] = None
    # V17 project matching + V44 operational metadata.
    project_key: Optional[str] = None
    match_confidence: Optional[str] = None
    match_status: Optional[str] = None
    review_required: bool = False
    review_reason: Optional[str] = None
    match_signals_json: Optional[str] = None
    parent_folder_name: Optional[str] = None
    last_modified_by_display_name: Optional[str] = None
    last_modified_by_user_id: Optional[str] = None
    last_modified_by_email: Optional[str] = None
    last_modified_by_application_display_name: Optional[str] = None
    last_modified_by_raw_json: Optional[str] = None

    model_config = {"extra": "forbid"}


class BridgeReport(BaseModel):
    """Per-source overlap counts for the V2↔V5 bridge."""

    source_id: str
    v2_only: int
    v5_only: int
    both: int
    total_unified: int
    lossy_v2_fields: list[str]


def v2_row_to_v5(v2_row: dict[str, Any]) -> V5DriveItem:
    """Project a single V2 ``construction_drive_item_inventory`` row dict
    into the canonical V5 shape.

    Pure, deterministic, side-effect-free. Mapping rules:

    - ``source_key`` → ``source_id``; ``item_id`` → ``drive_item_id``.
    - ``parent_path`` → ``path``; V5 ``parent_drive_item_id`` stays None
      because V2 doesn't track parent IDs.
    - ``status == 'deleted'`` → ``deleted = True``; otherwise False.
    - ``is_file`` is inferred as ``not is_folder`` (V2 items are folder
      XOR file in practice; this preserves the V5 boolean separation).
    - ``etag``/``first_seen_at``/``last_seen_at`` are dropped — V5 has
      no equivalent columns (they appear in ``BridgeReport.lossy_v2_fields``).
    - V5-only fields (``site_id``, ``list_id``, ``file_extension``, etc.)
      stay ``None`` — V2 doesn't carry them; future Phase 03 writes
      targeting V5 directly will populate them.
    """
    is_folder = bool(v2_row.get("is_folder", False))
    status = v2_row.get("status", "active")
    return V5DriveItem(
        source_id=v2_row["source_key"],
        drive_id=v2_row["drive_id"],
        drive_item_id=v2_row["item_id"],
        parent_drive_item_id=None,
        site_id=None,
        list_id=None,
        list_item_id=None,
        name=v2_row.get("name"),
        path=v2_row.get("parent_path"),
        web_url=v2_row.get("web_url"),
        is_folder=is_folder,
        is_file=(not is_folder),
        file_extension=None,
        mime_type=None,
        size_bytes=v2_row.get("size_bytes"),
        last_modified_datetime=v2_row.get("last_modified"),
        deleted=(status == "deleted"),
        quick_xor_hash=None,
        project_number_detected=None,
        document_type_detected=None,
        indexing_policy=None,
        classification_status=None,
        created_utc=None,
        updated_utc=None,
    )


def _v5_row_to_v5(v5_row: dict[str, Any]) -> V5DriveItem:
    """Adapt a raw V5 store row dict (from ``list_drive_items``) to
    :class:`V5DriveItem`. The store already returns booleans for the
    three bool columns and the keys match exactly, so this is mostly
    a pass-through with explicit shape validation."""
    return V5DriveItem(**v5_row)


def read_drive_items_unified(
    store: ConstructionStore,
    *,
    source_id: str,
    v2_limit: Optional[int] = None,
    v5_limit: Optional[int] = None,
) -> list[V5DriveItem]:
    """Read V2 inventory + V5 drive_items for a single source and return
    a unified list of :class:`V5DriveItem`.

    Precedence on ``(source_id, drive_item_id)`` collisions: **V5 wins**.
    This way, once a later prompt flips the crawler to write directly to
    V5, callers transparently switch over to V5-canonical data without
    code change — the V2 row becomes a no-op shadow until cleanup.

    ``v2_limit``/``v5_limit`` cap the per-table read for sweep safety.
    Strictly read-only — no SQLite, filesystem, or Microsoft 365 writes.
    """
    v5_rows = store.list_drive_items(source_id=source_id, limit=v5_limit)
    v2_rows = store.list_inventory(source_key=source_id, limit=v2_limit)

    by_item_id: dict[str, V5DriveItem] = {}
    # Insert V2-derived first so V5 can overwrite on collision.
    for row in v2_rows:
        item = v2_row_to_v5(row)
        by_item_id[item.drive_item_id] = item
    for row in v5_rows:
        item = _v5_row_to_v5(row)
        by_item_id[item.drive_item_id] = item
    return sorted(by_item_id.values(), key=lambda i: i.drive_item_id)


def summarize_bridge(
    store: ConstructionStore,
    source_ids: Iterable[str],
    *,
    per_source_limit: Optional[int] = None,
) -> dict[str, BridgeReport]:
    """Per-source overlap stats. Caller passes the source_ids to inspect
    (typically the keys of the live registry)."""
    out: dict[str, BridgeReport] = {}
    for source_id in source_ids:
        v2_rows = store.list_inventory(source_key=source_id, limit=per_source_limit)
        v5_rows = store.list_drive_items(source_id=source_id, limit=per_source_limit)
        v2_ids = {row["item_id"] for row in v2_rows}
        v5_ids = {row["drive_item_id"] for row in v5_rows}
        both = v2_ids & v5_ids
        v2_only = v2_ids - v5_ids
        v5_only = v5_ids - v2_ids
        out[source_id] = BridgeReport(
            source_id=source_id,
            v2_only=len(v2_only),
            v5_only=len(v5_only),
            both=len(both),
            total_unified=len(v2_ids | v5_ids),
            lossy_v2_fields=list(_LOSSY_V2_FIELDS),
        )
    return out
