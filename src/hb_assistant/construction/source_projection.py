"""Project the YAML-driven :class:`SourceRegistry` into the V5 canonical
``construction_source_locations`` table at runtime.

The Phase 02 schema migration created the V5 canonical tables additively
alongside the Phase 01 V2/V3/V4 tables, but no projection path existed
from the in-memory registry into the SQLite table. This module closes
that gap so downstream Phase 03 work can query source state via V5
joins (e.g., ``construction_source_sync_state`` × ``construction_source_locations``)
instead of re-loading the YAML registry on every read path.

The projection is strictly read-only against Microsoft 365 — the only
side effect is local SQLite writes to ``construction_source_locations``.

Mapping rules (registry ``SourceLocation`` → V5 ``upsert_source_location``):

- ``source_key`` → ``source_id`` (stable identity)
- ``kind`` → ``source_scope``
- ``display_name`` → ``source_name``
- ``source_system`` → ``source_system`` (inferred from kind when null on
  Phase 01 compat records, since V5 enforces ``NOT NULL``)
- ``root_path`` → ``folder_path``
- For ``sharepoint_site_page`` kind, ``page_url`` → ``folder_web_url``
  (V5 has no dedicated ``page_url`` column; the page URL semantically
  is "where the data lives in SharePoint" for site-page sources)
- ``baseline_policy`` / ``folder_policies`` → ``baseline_policy_json`` /
  ``folder_policies_json`` (deterministic JSON serialization via the
  store's ``_dump_json`` helper)

Lossy fields (no V5 column, by design — registry remains source of truth):
``crawl_mode``, ``indexing_depth``, ``match_status``, ``match_confidence``,
``review_required``, ``baseline`` (snapshot, distinct from ``baseline_policy``).
These do NOT block projection; they are documented in
:class:`ProjectedSource.skip_reason` for affected sources.

Read-only enforcement is defense-in-depth at three layers:

1. ``SourceLocation.read_only: Literal[True]`` (model layer).
2. ``ConstructionStore.upsert_source_location`` raises ``ValueError`` if
   ``read_only`` is anything other than ``True`` (store layer).
3. V5 schema ``CHECK(read_only = 1)`` (database layer).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from hb_assistant.construction.config.models import SourceLocation, SourceRegistry
from hb_assistant.construction.store import ConstructionStore


class ProjectedSource(BaseModel):
    """Per-source projection outcome."""

    source_id: str
    source_scope: str
    project_key: Optional[str]
    status: Literal["projected", "compat_projected", "skipped"]
    skip_reason: Optional[str] = None
    lossy_fields: list[str] = []


class ProjectionReport(BaseModel):
    """Aggregated projection result for a single registry walk."""

    total: int
    projected: int
    compat_projected: int
    skipped: int
    by_scope: dict[str, int]
    items: list[ProjectedSource]


def _infer_source_system(kind: str) -> str:
    """Infer V5 ``source_system`` from the registry's ``kind`` for Phase 01
    compat records that carry ``source_system: None``. V5 enforces
    ``source_system NOT NULL`` so we must always supply a value."""
    if kind.startswith("sharepoint"):
        return "sharepoint"
    if kind == "onedrive_personal" or kind == "onedrive_personal_root":
        return "onedrive_personal"
    if kind == "onedrive_business_root":
        return "onedrive_business"
    if kind == "onedrive_shared" or kind == "onedrive_shared_library":
        return "onedrive_shared_libraries"
    return "unknown"


def _is_legacy_compat(src: SourceLocation) -> bool:
    """Phase 01 compat records carry ``source_system: None`` and a
    notes string flagging them as compatibility entries."""
    if src.source_system is not None:
        return False
    if not src.notes:
        return False
    return "Phase 01 compat record" in src.notes


def _lossy_fields_for(src: SourceLocation) -> list[str]:
    """List registry fields that the V5 schema cannot represent."""
    lossy: list[str] = []
    if src.crawl_mode is not None:
        lossy.append("crawl_mode")
    if src.indexing_depth is not None:
        lossy.append("indexing_depth")
    if src.match_status is not None:
        lossy.append("match_status")
    if src.match_confidence is not None:
        lossy.append("match_confidence")
    if src.review_required:
        lossy.append("review_required")
    if src.baseline is not None:
        lossy.append("baseline_snapshot")
    return lossy


def _resolve_folder_web_url(src: SourceLocation) -> Optional[str]:
    """For ``sharepoint_site_page`` kind, prefer ``page_url`` since V5
    has no dedicated page_url column. For all other kinds, pass
    ``folder_web_url`` through unchanged."""
    if src.kind == "sharepoint_site_page" and src.page_url:
        return src.page_url
    return src.folder_web_url


def project_registry_to_v5_source_locations(
    registry: SourceRegistry,
    store: Optional[ConstructionStore] = None,
    *,
    dry_run: bool = False,
) -> ProjectionReport:
    """Project every source in ``registry`` into the V5
    ``construction_source_locations`` table via
    :meth:`ConstructionStore.upsert_source_location`.

    Defensive precheck: refuses to write if the input registry has
    duplicate ``source_key`` values (registry-layer validation already
    enforces uniqueness, but this guards against synthesized registries
    bypassing the validator).

    When ``dry_run`` is ``True`` the same :class:`ProjectionReport` is
    computed (per-source mapping, by_scope, projected/compat counts) but
    **no** SQLite write occurs — ``store`` may be ``None``. This backs the
    dry-run-default ``graph files sources`` command. When ``dry_run`` is
    ``False`` a ``store`` is required.

    Returns a :class:`ProjectionReport` summarizing per-source outcomes.
    Does NOT touch Microsoft 365, the Obsidian vault, or any tables
    besides ``construction_source_locations``.
    """
    if not dry_run and store is None:
        raise ValueError(
            "project_registry_to_v5_source_locations requires a store when dry_run=False"
        )

    seen: dict[str, str] = {}
    for src in registry.sources:
        if src.source_key in seen:
            raise ValueError(
                f"duplicate source_id in projection input: {src.source_key!r} appears twice"
            )
        seen[src.source_key] = src.source_key

    items: list[ProjectedSource] = []
    by_scope: dict[str, int] = {}
    projected = 0
    compat_projected = 0
    skipped = 0

    for src in registry.sources:
        compat = _is_legacy_compat(src)
        source_system = src.source_system or _infer_source_system(src.kind)
        baseline_policy = (
            src.baseline_policy.model_dump(mode="json", exclude_none=True)
            if src.baseline_policy is not None
            else None
        )
        folder_policies = (
            src.folder_policies.model_dump(mode="json", exclude_none=True)
            if src.folder_policies is not None
            else None
        )

        if not dry_run:
            assert store is not None  # guaranteed by the dry_run/store precheck above
            store.upsert_source_location(
                source_id=src.source_key,
                source_system=source_system,
                source_scope=src.kind,
                source_name=src.display_name,
                project_key=src.project_key,
                project_number=src.project_number,
                project_name=src.project_name,
                tenant_id=src.tenant_id,
                site_url=src.site_url,
                site_id=src.site_id,
                drive_id=src.drive_id,
                folder_item_id=src.folder_item_id,
                folder_path=src.root_path,
                folder_web_url=_resolve_folder_web_url(src),
                library_name=src.library_name,
                list_id=src.list_id,
                local_sync_path=src.local_sync_path,
                sync_mode=src.sync_mode,
                sync_frequency_minutes=src.sync_frequency_minutes,
                enabled=src.enabled,
                read_only=src.read_only,
                baseline_policy=baseline_policy,
                folder_policies=folder_policies,
            )

        lossy = _lossy_fields_for(src)
        status: Literal["projected", "compat_projected", "skipped"] = (
            "compat_projected" if compat else "projected"
        )
        if compat:
            compat_projected += 1
        else:
            projected += 1
        by_scope[src.kind] = by_scope.get(src.kind, 0) + 1

        items.append(
            ProjectedSource(
                source_id=src.source_key,
                source_scope=src.kind,
                project_key=src.project_key,
                status=status,
                skip_reason=None,
                lossy_fields=lossy,
            )
        )

    return ProjectionReport(
        total=len(registry.sources),
        projected=projected,
        compat_projected=compat_projected,
        skipped=skipped,
        by_scope=by_scope,
        items=items,
    )
