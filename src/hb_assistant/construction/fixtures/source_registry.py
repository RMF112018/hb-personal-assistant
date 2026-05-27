"""Synthetic source-registry fixtures (Pydantic-validatable).

Each fixture is a dict ready for ``SourceRegistry.model_validate(...)``.
No real tenant IDs; ``site_id`` / ``drive_id`` are obviously fake when
present.
"""

from __future__ import annotations

from typing import Any

MINIMAL_ONE_PROJECT: dict[str, Any] = {
    "projects": [
        {"project_key": "alpha", "display_name": "Alpha"},
    ],
    "sources": [
        {
            "source_key": "alpha-sharepoint",
            "project_key": "alpha",
            "kind": "sharepoint_site",
            "display_name": "Alpha SharePoint Site",
            "read_only": True,
            "resolution_status": "pending",
        },
    ],
}


MULTI_PROJECT_MULTI_KIND: dict[str, Any] = {
    "projects": [
        {"project_key": "alpha", "display_name": "Alpha"},
        {"project_key": "beta", "display_name": "Beta"},
    ],
    "sources": [
        {
            "source_key": "alpha-sharepoint",
            "project_key": "alpha",
            "kind": "sharepoint_site",
            "display_name": "Alpha SharePoint Site",
            "read_only": True,
            "resolution_status": "pending",
        },
        {
            "source_key": "alpha-library",
            "project_key": "alpha",
            "kind": "sharepoint_library",
            "display_name": "Alpha Document Library",
            "read_only": True,
            "resolution_status": "pending",
        },
        {
            "source_key": "beta-sharepoint",
            "project_key": "beta",
            "kind": "sharepoint_site",
            "display_name": "Beta SharePoint Site",
            "read_only": True,
            "resolution_status": "pending",
        },
        {
            "source_key": "bobby-onedrive-fixture",
            "kind": "onedrive_personal",
            "display_name": "Bobby OneDrive (fixture)",
            "read_only": True,
            "resolution_status": "pending",
        },
    ],
}


PENDING_ONLY: dict[str, Any] = {
    "projects": [
        {"project_key": "gamma", "display_name": "Gamma"},
    ],
    "sources": [
        {
            "source_key": f"gamma-source-{i}",
            "project_key": "gamma",
            "kind": "sharepoint_site",
            "display_name": f"Gamma Source {i}",
            "read_only": True,
            "resolution_status": "pending",
        }
        for i in range(1, 4)
    ],
}


SOURCE_REGISTRY_FIXTURES: dict[str, dict[str, Any]] = {
    "minimal_one_project": MINIMAL_ONE_PROJECT,
    "multi_project_multi_kind": MULTI_PROJECT_MULTI_KIND,
    "pending_only": PENDING_ONLY,
}
