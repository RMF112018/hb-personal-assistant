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


# Phase 04 Prompt 04: synthetic RFI list response.
#
# Three RFIs with five nested replies total. All identifiers are synthetic and
# carry the literal ``synthetic-`` prefix so the repo-wide sensitive scan
# allowlist does not need to be extended. RFI #3 deliberately exercises the
# review-routing heuristics (status contains "legal", subject contains
# "change order", missing assignee).
RFI_SAMPLE_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": "synthetic-rfi-001",
        "number": "RFI-001",
        "subject": "Door schedule clarification",
        "status": "open",
        "assignee_id": "synthetic-user-7",
        "due_date": "2026-06-15",
        "initiated_at": "2026-05-20T13:00:00Z",
        "created_at": "2026-05-20T13:00:00Z",
        "updated_at": "2026-05-22T09:30:00Z",
        "html_url": "https://app.procore.example/projects/1/rfis/synthetic-rfi-001",
        "replies": [
            {
                "id": "synthetic-rfi-001-reply-a",
                "author_id": "synthetic-user-9",
                "created_at": "2026-05-21T10:00:00Z",
                "updated_at": "2026-05-21T10:00:00Z",
                "body": "Please confirm the hardware set for the type-A doors.",
            },
            {
                "id": "synthetic-rfi-001-reply-b",
                "author_id": "synthetic-user-7",
                "created_at": "2026-05-22T09:30:00Z",
                "updated_at": "2026-05-22T09:30:00Z",
                "body": "Hardware set H-4 per the latest revision.",
            },
        ],
    },
    {
        "id": "synthetic-rfi-002",
        "number": "RFI-002",
        "subject": "Slab thickness at column line B",
        "status": "answered",
        "assignee_id": "synthetic-user-3",
        "due_date": "2026-06-01",
        "initiated_at": "2026-05-18T08:15:00Z",
        "created_at": "2026-05-18T08:15:00Z",
        "updated_at": "2026-05-19T16:45:00Z",
        "html_url": "https://app.procore.example/projects/1/rfis/synthetic-rfi-002",
        "replies": [
            {
                "id": "synthetic-rfi-002-reply-a",
                "author_id": "synthetic-user-3",
                "created_at": "2026-05-19T16:45:00Z",
                "updated_at": "2026-05-19T16:45:00Z",
                "body": "Eight-inch slab per detail S-203.",
            },
        ],
    },
    {
        "id": "synthetic-rfi-003",
        "number": "RFI-003",
        "subject": "Change order request: scope shift on partition framing",
        "status": "legal_review_required",
        "assignee_id": None,
        "due_date": "2026-06-30",
        "initiated_at": "2026-05-25T11:20:00Z",
        "created_at": "2026-05-25T11:20:00Z",
        "updated_at": "2026-05-26T15:00:00Z",
        "html_url": "https://app.procore.example/projects/1/rfis/synthetic-rfi-003",
        "replies": [
            {
                "id": "synthetic-rfi-003-reply-a",
                "author_id": "synthetic-user-1",
                "created_at": "2026-05-26T08:00:00Z",
                "updated_at": "2026-05-26T08:00:00Z",
                "body": "Routing to legal for review of the scope adjustment language.",
            },
            {
                "id": "synthetic-rfi-003-reply-b",
                "author_id": "synthetic-user-2",
                "created_at": "2026-05-26T15:00:00Z",
                "updated_at": "2026-05-26T15:00:00Z",
                "body": "Holding pending counsel input.",
            },
        ],
    },
]


PROCORE_RFI_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "rfi_sample_payload": RFI_SAMPLE_PAYLOAD,
}
