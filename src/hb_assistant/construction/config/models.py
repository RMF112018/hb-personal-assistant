"""Pydantic models for the construction-agent source registry.

Models the read-only inventory of SharePoint sites, OneDrive scopes, and
construction project identities that downstream phase-01 steps (delta crawler,
manifests, vault writer, classifier) consume. Models are authoritative; the
on-disk JSON Schema artifacts under `resources/schemas/` are generated from
these definitions for cross-tool reference only.

Guardrails enforced at type level:
- ``SourceLocation.read_only`` is ``Literal[True]`` — a writeback flag cannot
  be constructed.
- Unknown ``kind`` values are rejected by the ``SourceKind`` Literal.
- Extra fields are forbidden on every model (``model_config = {"extra": "forbid"}``).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

SourceKind = Literal[
    "sharepoint_site",
    "sharepoint_library",
    "onedrive_personal",
    "onedrive_shared",
]

ResolutionStatus = Literal["pending", "resolved", "deprecated"]
ProjectStatus = Literal["active", "paused", "closed"]

_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validate_key(value: str, field_name: str) -> str:
    if not _KEY_RE.match(value):
        raise ValueError(
            f"{field_name} must be lowercase kebab-case (a-z0-9 with single hyphens); got {value!r}"
        )
    return value


class ProjectIdentity(BaseModel):
    """Construction project identity referenced by source locations."""

    project_key: str
    display_name: str
    status: ProjectStatus = "active"
    primary_company: str | None = None
    procore_company_id: str | None = None
    notes: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("project_key")
    @classmethod
    def _project_key_kebab(cls, v: str) -> str:
        return _validate_key(v, "project_key")


class SourceLocation(BaseModel):
    """A single read-only source endpoint (SharePoint site, OneDrive scope, etc.)."""

    source_key: str
    project_key: str | None = None
    kind: SourceKind
    display_name: str
    site_url: str | None = None
    site_id: str | None = None
    drive_id: str | None = None
    root_path: str | None = None
    read_only: Literal[True] = True
    resolution_status: ResolutionStatus = "pending"
    notes: str | None = None

    model_config = {"extra": "forbid"}

    @field_validator("source_key")
    @classmethod
    def _source_key_kebab(cls, v: str) -> str:
        return _validate_key(v, "source_key")


class SourceRegistry(BaseModel):
    """Top-level registry containing projects and their source endpoints."""

    projects: list[ProjectIdentity] = Field(default_factory=list)
    sources: list[SourceLocation] = Field(default_factory=list)

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
                if src.drive_id in seen_drive_ids:
                    raise ValueError(
                        f"drive_id {src.drive_id!r} reused across sources "
                        f"{seen_drive_ids[src.drive_id]!r} and {src.source_key!r}"
                    )
                seen_drive_ids[src.drive_id] = src.source_key

        return self
