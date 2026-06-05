"""Canonical V5 read-model adapter for the manifest projection layer.

Prompts 05–06 built the V5 read model:

- :func:`hb_assistant.construction.source_projection.project_registry_to_v5_source_locations`
  lands canonical rows into ``construction_source_locations``.
- :func:`hb_assistant.construction.drive_item_bridge.read_drive_items_unified`
  returns a unified V2+V5 list of :class:`V5DriveItem` with V5-wins
  precedence on key collisions.

This module is the thin adapter that lets the existing
:class:`hb_assistant.construction.manifests.service.ManifestService`
renderer pathway consume canonical V5 source IDs without rewriting the
service. The V2-keyed ``build_document_card`` path stays exactly as it
was; this module adds a parallel canonical path that:

1. Looks up a V5 canonical source by ``source_id`` (fails closed when
   absent).
2. Reads drive items via ``read_drive_items_unified(store, source_id=…)``.
3. Adapts each :class:`V5DriveItem` to the inventory-row dict shape that
   :meth:`ManifestService.build_document_card` already consumes.

Read-only. No SQLite writes, no filesystem mutation, no HTTP calls.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from hb_assistant.construction.drive_item_bridge import (
    V5DriveItem,
    read_drive_items_unified,
)
from hb_assistant.construction.store import ConstructionStore


class CanonicalSourceNotFound(LookupError):
    """Raised when the requested V5 ``source_id`` is not in
    ``construction_source_locations``. The canonical read path fails
    closed — callers may not fall back to V2 silently."""


@dataclass(frozen=True)
class CanonicalSourceRef:
    """Identity holder for a V5 canonical source.

    ``source_id`` is the V5 canonical identifier (the
    ``construction_source_locations.source_id`` primary key). ``source_key``
    is the V2 registry alias preserved so existing renderer surfaces that
    expect the legacy key continue to work during the migration window.
    By the V5 projection rules they currently carry identical string
    values; the dataclass keeps them as named, distinct attributes so the
    renderer pathway can plumb them to distinct frontmatter fields.
    """

    source_id: str
    source_key: str
    project_key: Optional[str]


@dataclass(frozen=True)
class CanonicalDocumentCardInput:
    """Bundle the canonical read-path produces for one source: the
    identity reference plus the adapted inventory-row dicts ready to feed
    :meth:`ManifestService.build_document_card_from_source_id`."""

    ref: CanonicalSourceRef
    rows: list[dict[str, Any]]


def v5_drive_item_to_inventory_row(item: V5DriveItem) -> dict[str, Any]:
    """Map a :class:`V5DriveItem` to the dict shape that
    :meth:`ManifestService.build_document_card` already consumes.

    The legacy path reads inventory rows from
    :meth:`ConstructionStore.list_inventory_changed_since`, which returns
    dicts keyed by the V2 column names. This function reproduces that
    exact key set from V5 fields so the existing renderer requires no
    change.
    """
    return {
        "source_key": item.source_id,
        "drive_id": item.drive_id,
        "item_id": item.drive_item_id,
        "name": item.name,
        "web_url": item.web_url,
        "parent_path": item.path,
        "size_bytes": item.size_bytes,
        "is_folder": bool(item.is_folder),
        "last_modified": item.last_modified_datetime,
        "etag": None,
        "status": "deleted" if item.deleted else "active",
        "first_seen_at": None,
        "last_seen_at": None,
    }


def resolve_canonical_source(
    store: ConstructionStore,
    *,
    source_id: str,
) -> CanonicalSourceRef:
    """Look up the V5 ``construction_source_locations`` row for
    ``source_id`` and return a :class:`CanonicalSourceRef`. Raises
    :class:`CanonicalSourceNotFound` if absent — the canonical read path
    is fail-closed."""
    row = store.get_source_location(source_id)
    if row is None:
        raise CanonicalSourceNotFound(
            f"canonical source_id {source_id!r} not present in "
            "construction_source_locations; run the V5 source projection first"
        )
    return CanonicalSourceRef(
        source_id=row["source_id"],
        source_key=row["source_id"],
        project_key=row.get("project_key"),
    )


def read_canonical_document_card_input(
    store: ConstructionStore,
    *,
    source_id: str,
    v2_limit: Optional[int] = None,
    v5_limit: Optional[int] = None,
) -> CanonicalDocumentCardInput:
    """One-shot canonical read: resolve the V5 source, read unified
    drive items, and project each to the inventory-row dict shape.

    Pure read path — no writes. Fails closed when ``source_id`` is not
    present in ``construction_source_locations``.
    """
    ref = resolve_canonical_source(store, source_id=source_id)
    items = read_drive_items_unified(
        store,
        source_id=source_id,
        v2_limit=v2_limit,
        v5_limit=v5_limit,
    )
    rows = [v5_drive_item_to_inventory_row(item) for item in items]
    return CanonicalDocumentCardInput(ref=ref, rows=rows)
