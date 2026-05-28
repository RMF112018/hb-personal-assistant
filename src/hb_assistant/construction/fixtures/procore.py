"""Synthetic Procore endpoint-contract + projects-registry fixtures.

Each fixture is a dict ready for ``ProcoreEndpointContract.model_validate``
or ``ProcoreProjectsRegistry.model_validate``.

The minimal-valid contract covers every required category and enforces
the hard guardrails (correspondence = excluded; schedule/tasks = deferred)
so it loads cleanly. Project fixtures cover pilot-only and all-pending
edge cases the seed registry doesn't exercise alone.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.procore.models import REQUIRED_CATEGORIES


def _minimal_endpoints() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cat in REQUIRED_CATEGORIES:
        if cat == "correspondence":
            status, sens = "excluded", "critical"
            verif: dict[str, Any] = {
                "verification_status": "excluded_by_guardrail",
                "verification_reason": "Fixture: excluded by hard guardrail.",
            }
        elif cat in ("schedule", "tasks"):
            status, sens = "deferred", "medium"
            verif = {
                "verification_status": "deferred_by_guardrail",
                "verification_reason": "Fixture: deferred by hard guardrail.",
            }
        else:
            status, sens = "validated", "low"
            verif = {
                "verification_status": "official_docs_verified",
                "official_reference_url": f"https://developers.procore.com/fixture/{cat}",
                "verified_at_utc": "2026-05-27T00:00:00Z",
                "verified_by": "fixture",
            }
        rows.append({
            "endpoint_id": f"fixture-ep-{cat}",
            "http_method": "GET",
            "path_template": f"/vapid/projects/{{project_id}}/{cat.replace('-', '_')}",
            "category": cat,
            "status": status,
            "sensitivity": sens,
            "included_in_phase_01": status not in ("excluded", "deferred"),
            **verif,
        })
    return rows


MINIMAL_VALID_CONTRACT: dict[str, Any] = {
    "version": 1,
    "company_id": "5280",
    "company_display_name": "HB Construction (fixture)",
    "endpoints": _minimal_endpoints(),
}


PILOT_ONLY_PROJECTS: dict[str, Any] = {
    "company_id": "5280",
    "projects": [
        {
            "hb_project_key": "alpha",
            "procore_project_id": "1000100",
            "procore_project_name": "Alpha",
            "status": "pilot",
        },
        {
            "hb_project_key": "beta",
            "procore_project_id": "2000200",
            "procore_project_name": "Beta",
            "status": "pilot",
        },
    ],
}


ALL_PENDING_PROJECTS: dict[str, Any] = {
    "company_id": "5280",
    "projects": [
        {
            "hb_project_key": f"pending-{i}",
            "procore_project_id": "",
            "procore_project_name": "",
            "status": "pending",
        }
        for i in range(1, 4)
    ],
}


PROCORE_CONTRACT_FIXTURES: dict[str, dict[str, Any]] = {
    "minimal_valid_contract": MINIMAL_VALID_CONTRACT,
}

PROCORE_PROJECTS_FIXTURES: dict[str, dict[str, Any]] = {
    "pilot_only_projects": PILOT_ONLY_PROJECTS,
    "all_pending_projects": ALL_PENDING_PROJECTS,
}
