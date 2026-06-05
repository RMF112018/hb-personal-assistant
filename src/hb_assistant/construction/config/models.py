"""Pydantic models for the construction-agent source registry.

Models the read-only inventory of SharePoint sites, OneDrive scopes, and
construction project identities that downstream phase-01 steps (delta crawler,
manifests, vault writer, classifier) consume. Models are authoritative; the
on-disk JSON Schema artifacts under `resources/schemas/` are generated from
these definitions for cross-tool reference only.

Phase 02 compatibility bridge:
- Field aliases let YAML use either Phase 01 names (``source_key``, ``kind``,
  ``display_name``, ``root_path``) or Phase 02 canonical names (``source_id``,
  ``source_scope``, ``source_name``, ``folder_path``). Internal field names stay
  on the Phase 01 spelling because downstream code (graph resolver, manifests,
  vault writer, classifier, CLI, fixtures) is still keyed on those names.
  Providing both alias spellings on the same record with conflicting values
  raises a stop-condition error.
- Typed sub-models cover ``BaselinePolicy`` (crawl strategy), ``BaselineSnapshot``
  (inventory counts), ``FolderPolicies`` (per-category folder lists), and
  ``DefaultPolicies`` (registry-level safe defaults). Hard guardrails reject any
  attempt to enable source-document copies into Obsidian or full-document text
  in vault notes.

Guardrails enforced at type level:
- ``SourceLocation.read_only`` is ``Literal[True]`` — a writeback flag cannot
  be constructed.
- Unknown ``kind`` / ``source_scope`` values are rejected by the ``SourceKind``
  Literal.
- ``DefaultPolicies.copy_originals_to_vault`` and
  ``DefaultPolicies.store_full_text_in_vault_notes`` must be ``False``.
- Folders cannot simultaneously appear in ``review_required`` and
  ``deep_index_allowed``.
- Extra fields are forbidden on every model.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

SourceKind = Literal[
    # Phase 01 source kinds.
    "sharepoint_site",
    "sharepoint_library",
    "onedrive_personal",
    "onedrive_shared",
    # Phase 02 canonical source scopes.
    "sharepoint_project_drive_folder",
    "sharepoint_site_page",
    "onedrive_business_root",
    "onedrive_personal_root",
    "onedrive_shared_library",
    "procore_project",
    "mailbox_deferred",
]

SourceSystem = Literal[
    "sharepoint",
    "onedrive_business",
    "onedrive_personal",
    "onedrive_shared_libraries",
    "procore",
    "outlook",
]

ResolutionStatus = Literal[
    # Phase 01 statuses.
    "pending",
    "resolved",
    "deprecated",
    # Phase 02 statuses.
    "graph_delta_ready",
    "pending_graph_resolution",
    "pending_drive_resolution",
    "pending_source_resolution",
]

ProjectStatus = Literal["active", "paused", "closed"]

BaselineMode = Literal[
    "inventory_first",
    "shallow_metadata_first",
    "metadata_only",
    "deep_index",
]

BaselineStatus = Literal["pending", "in_progress", "complete", "failed"]

IndexingDepth = Literal[
    "metadata_only",
    "metadata_summary_links",
    "selective_extraction",
    "deep_index",
]

MatchStatus = Literal["matched", "unmatched"]
MatchConfidence = Literal["high", "medium", "low", "none"]

# Identifiers may be Phase 01 kebab-case (e.g. ``tropical-sharepoint``) or
# Phase 02 canonical snake-case (e.g. ``sp_2023projects_23_435_01_tropical_sl``).
_KEY_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def _validate_key(value: str, field_name: str) -> str:
    if not _KEY_RE.match(value):
        raise ValueError(
            f"{field_name} must be lowercase a-z0-9 with single hyphens or underscores "
            f"as separators; got {value!r}"
        )
    return value


def _check_conflicting_aliases(data: dict[str, Any], pairs: list[tuple[str, str]]) -> None:
    """Reconcile alias pairs in-place.

    Raises ``ValueError`` if both names of a pair are present with non-equal
    values. When both names are present with identical values, the alias copy
    is dropped so Pydantic's ``extra="forbid"`` is not tripped.
    """
    for canonical, alias in pairs:
        if canonical in data and alias in data:
            if data[canonical] != data[alias]:
                raise ValueError(
                    f"conflicting alias values for {canonical!r} ({data[canonical]!r}) "
                    f"and {alias!r} ({data[alias]!r}); provide one or matching values"
                )
            del data[alias]


class DefaultPolicies(BaseModel):
    """Registry-level safe defaults declared at the top of the canonical seed."""

    read_only: bool = True
    copy_originals_to_vault: bool = False
    store_full_text_in_vault_notes: bool = False
    store_extracted_text_in_sqlite: bool | str = "selective"
    store_embeddings: bool | str = "selective"
    require_review_for_sensitive: bool = True
    sync_mode: str = "graph_delta"

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _hard_guardrails(self) -> "DefaultPolicies":
        if self.read_only is not True:
            raise ValueError(
                "default_policies.read_only must remain True; Phase 02 has no writeback path"
            )
        if self.copy_originals_to_vault is True:
            raise ValueError(
                "default_policies.copy_originals_to_vault must be False "
                "(no source-document copies into Obsidian)"
            )
        if self.store_full_text_in_vault_notes is True:
            raise ValueError(
                "default_policies.store_full_text_in_vault_notes must be False "
                "(no full-document text in vault notes)"
            )
        return self


class BaselinePolicy(BaseModel):
    """Per-source crawl-strategy policy."""

    mode: BaselineMode
    deep_index_default: bool = False
    classify_project_matches: bool = False
    graph_delta_required: bool = False
    local_folder_watcher: str | None = None
    require_review_for_sensitive: bool = False
    notes: str | None = None
    policy_tags: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class BaselineSnapshot(BaseModel):
    """Inventory snapshot recorded for a resolved source."""

    baseline_status: BaselineStatus | None = None
    baseline_unique_item_count: int | None = None
    baseline_file_count: int | None = None
    baseline_folder_count: int | None = None
    baseline_file_size_gb: float | None = None

    model_config = {"extra": "forbid"}


class FolderPolicies(BaseModel):
    """Per-source folder routing — three category lists keyed off folder name."""

    deep_index_allowed: list[str] = Field(default_factory=list)
    metadata_only: list[str] = Field(default_factory=list)
    review_required: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _no_silent_deep_index_of_review_required(self) -> "FolderPolicies":
        review_set = {f.casefold() for f in self.review_required}
        deep_set = {f.casefold() for f in self.deep_index_allowed}
        overlap = review_set & deep_set
        if overlap:
            raise ValueError(
                "folder cannot be in both review_required and deep_index_allowed: "
                f"{sorted(overlap)}"
            )
        return self


class ProjectIdentity(BaseModel):
    """Construction project identity referenced by source locations."""

    project_key: str
    display_name: str = Field(
        validation_alias=AliasChoices("display_name", "project_name"),
    )
    status: ProjectStatus = "active"
    primary_company: str | None = None
    procore_company_id: str | None = None
    procore_project_id: str | None = None
    project_number: str | None = None
    project_name_normalized: str | None = None
    notes: str | None = None

    model_config = {"extra": "forbid", "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _check_alias_conflicts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            _check_conflicting_aliases(data, [("display_name", "project_name")])
        return data

    @field_validator("project_key")
    @classmethod
    def _project_key_kebab(cls, v: str) -> str:
        return _validate_key(v, "project_key")


class SourceLocation(BaseModel):
    """A single read-only source endpoint (SharePoint site, OneDrive scope, etc.).

    Accepts both Phase 01 field names (``source_key``, ``kind``, ``display_name``,
    ``root_path``) and Phase 02 canonical names (``source_id``, ``source_scope``,
    ``source_name``, ``folder_path``) via validation aliases. Internal field
    names stay on the Phase 01 spelling.
    """

    source_key: str = Field(
        validation_alias=AliasChoices("source_key", "source_id"),
    )
    project_key: str | None = None
    kind: SourceKind = Field(
        validation_alias=AliasChoices("kind", "source_scope"),
    )
    display_name: str = Field(
        validation_alias=AliasChoices("display_name", "source_name"),
    )

    # Phase 02 system + project descriptors.
    source_system: SourceSystem | None = None
    project_number: str | None = None
    project_name: str | None = None
    tenant_id: str | None = None

    # SharePoint / OneDrive addressing.
    site_url: str | None = None
    site_id: str | None = None
    drive_id: str | None = None
    folder_item_id: str | None = None
    root_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("root_path", "folder_path"),
    )
    folder_web_url: str | None = None
    library_name: str | None = None
    list_id: str | None = None
    page_url: str | None = None
    local_sync_path: str | None = None
    # Phase 07C OneDrive selected-folder allowlist (drive-item ids). A OneDrive
    # source is scope-compliant only when this is non-empty; root-wide OneDrive
    # indexing is not allowed by the 07C document-source policy.
    selected_folder_item_ids: list[str] | None = None
    # Phase 07D — explicit OneDrive all-folders opt-in. Fail-closed default False:
    # implicit root-wide indexing stays blocked. When True on a recognized OneDrive
    # root scope, the operator has explicitly approved indexing the root and all
    # nested folders (an "all-folders allowlist"), which the source-scope evaluator
    # treats as compliant. It is never an implicit permission to crawl.
    allow_all_folders: bool = False

    # Crawl + match descriptors.
    sync_mode: str | None = None
    sync_frequency_minutes: int | None = None
    crawl_mode: str | None = None
    indexing_depth: IndexingDepth | None = None
    match_status: MatchStatus | None = None
    match_confidence: MatchConfidence | None = None

    # Policy + lifecycle.
    read_only: Literal[True] = True
    resolution_status: ResolutionStatus = "pending"
    enabled: bool = True
    review_required: bool = False
    baseline: BaselineSnapshot | None = None
    baseline_policy: BaselinePolicy | None = None
    folder_policies: FolderPolicies | None = None
    notes: str | None = None

    model_config = {"extra": "forbid", "populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _check_alias_conflicts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            _check_conflicting_aliases(
                data,
                [
                    ("source_key", "source_id"),
                    ("kind", "source_scope"),
                    ("display_name", "source_name"),
                    ("root_path", "folder_path"),
                ],
            )
        return data

    @field_validator("source_key")
    @classmethod
    def _source_key_identifier(cls, v: str) -> str:
        return _validate_key(v, "source_key")


class SourceRegistry(BaseModel):
    """Top-level registry containing projects and their source endpoints."""

    projects: list[ProjectIdentity] = Field(default_factory=list)
    sources: list[SourceLocation] = Field(default_factory=list)
    default_policies: DefaultPolicies | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _check_consistency(self) -> "SourceRegistry":
        project_keys = [p.project_key for p in self.projects]
        if len(project_keys) != len(set(project_keys)):
            dupes = sorted({k for k in project_keys if project_keys.count(k) > 1})
            raise ValueError(f"duplicate project_key entries: {dupes}")

        source_keys = [s.source_key for s in self.sources]
        if len(source_keys) != len(set(source_keys)):
            dupes = sorted({k for k in source_keys if source_keys.count(k) > 1})
            raise ValueError(f"duplicate source_key entries: {dupes}")

        known_projects = set(project_keys)
        for src in self.sources:
            if src.project_key is not None and src.project_key not in known_projects:
                raise ValueError(
                    f"source {src.source_key!r} references unknown project_key {src.project_key!r}"
                )

        seen_site_ids: dict[str, str] = {}
        for src in self.sources:
            if src.site_id:
                if src.site_id in seen_site_ids:
                    raise ValueError(
                        f"site_id {src.site_id!r} reused across sources "
                        f"{seen_site_ids[src.site_id]!r} and {src.source_key!r}"
                    )
                seen_site_ids[src.site_id] = src.source_key

        seen_drive_ids: dict[str, str] = {}
        for src in self.sources:
            if src.drive_id:
                # drive_id may legitimately repeat across folders in the same drive
                # (Phase 02 canonical seed has multiple 2026Projects entries sharing
                # the site drive_id). Folder-level uniqueness is enforced via
                # folder_item_id instead.
                seen_drive_ids.setdefault(src.drive_id, src.source_key)

        seen_folder_item_ids: dict[str, str] = {}
        for src in self.sources:
            if src.folder_item_id:
                if src.folder_item_id in seen_folder_item_ids:
                    raise ValueError(
                        f"folder_item_id {src.folder_item_id!r} reused across sources "
                        f"{seen_folder_item_ids[src.folder_item_id]!r} and {src.source_key!r}"
                    )
                seen_folder_item_ids[src.folder_item_id] = src.source_key

        return self
