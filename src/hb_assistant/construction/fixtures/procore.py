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


# Phase 04 Prompt 05: synthetic submittal list response.
#
# Three submittals with four nested responses and two nested packages total.
# All identifiers are synthetic (``synthetic-`` prefix) so the repo-wide
# sensitive scan allowlist does not need extending. Submittal #3 deliberately
# exercises the review-routing heuristics (status ``revise_and_resubmit``,
# title contains "contract amendment", missing assignee / ball_in_court).
SUBMITTAL_SAMPLE_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": "synthetic-sub-001",
        "number": "S-101",
        "title": "Door hardware schedule",
        "type": "Shop Drawing",
        "specification_section": "08 71 00",
        "status": "approved",
        "assignee_id": "synthetic-user-21",
        "ball_in_court_id": "synthetic-user-21",
        "due_date": "2026-06-10",
        "initiated_at": "2026-05-15T10:00:00Z",
        "created_at": "2026-05-15T10:00:00Z",
        "updated_at": "2026-05-22T11:00:00Z",
        "html_url": "https://app.procore.example/projects/1/submittals/synthetic-sub-001",
        "responses": [
            {
                "id": "synthetic-sub-001-resp-a",
                "author_id": "synthetic-user-7",
                "response_status": "approved_as_noted",
                "created_at": "2026-05-21T09:00:00Z",
                "updated_at": "2026-05-21T09:00:00Z",
                "comment": "Hardware set H-4 confirmed; see annotated drawings.",
            },
        ],
        "packages": [
            {
                "id": "synthetic-sub-001-pkg-a",
                "number": "PKG-08-A",
                "title": "Door & hardware package",
                "status": "open",
                "created_at": "2026-05-14T08:00:00Z",
                "updated_at": "2026-05-22T11:00:00Z",
            },
        ],
    },
    {
        "id": "synthetic-sub-002",
        "number": "S-102",
        "title": "Mechanical equipment cut sheets",
        "type": "Product Data",
        "specification_section": "23 00 00",
        "status": "open",
        "assignee_id": "synthetic-user-13",
        "ball_in_court_id": "synthetic-user-13",
        "due_date": "2026-06-20",
        "initiated_at": "2026-05-18T13:00:00Z",
        "created_at": "2026-05-18T13:00:00Z",
        "updated_at": "2026-05-26T17:30:00Z",
        "html_url": "https://app.procore.example/projects/1/submittals/synthetic-sub-002",
        "responses": [
            {
                "id": "synthetic-sub-002-resp-a",
                "author_id": "synthetic-user-9",
                "response_status": "pending_review",
                "created_at": "2026-05-24T12:00:00Z",
                "updated_at": "2026-05-24T12:00:00Z",
                "comment": "Reviewing chiller efficiency data.",
            },
            {
                "id": "synthetic-sub-002-resp-b",
                "author_id": "synthetic-user-13",
                "response_status": "pending_review",
                "created_at": "2026-05-26T17:30:00Z",
                "updated_at": "2026-05-26T17:30:00Z",
                "comment": "Awaiting performance curves from vendor.",
            },
        ],
        "packages": [],
    },
    {
        "id": "synthetic-sub-003",
        "number": "S-103",
        "title": "Contract amendment: partition framing scope shift",
        "type": "Other",
        "specification_section": "09 22 00",
        "status": "revise_and_resubmit",
        "assignee_id": None,
        "ball_in_court_id": None,
        "due_date": "2026-07-01",
        "initiated_at": "2026-05-23T08:00:00Z",
        "created_at": "2026-05-23T08:00:00Z",
        "updated_at": "2026-05-27T12:00:00Z",
        "html_url": "https://app.procore.example/projects/1/submittals/synthetic-sub-003",
        "responses": [
            {
                "id": "synthetic-sub-003-resp-a",
                "author_id": "synthetic-user-2",
                "response_status": "revise_and_resubmit",
                "created_at": "2026-05-27T12:00:00Z",
                "updated_at": "2026-05-27T12:00:00Z",
                "comment": "Resubmit with revised scope language and pricing exhibits.",
            },
        ],
        "packages": [
            {
                "id": "synthetic-sub-003-pkg-a",
                "number": "PKG-09-B",
                "title": "Partition scope amendment package",
                "status": "open",
                "created_at": "2026-05-23T08:00:00Z",
                "updated_at": "2026-05-27T12:00:00Z",
                "description": "Captures the amended framing limits and ceiling height adjustments.",
            },
        ],
    },
]


PROCORE_SUBMITTAL_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "submittal_sample_payload": SUBMITTAL_SAMPLE_PAYLOAD,
}


# Phase 04 Prompt 06: synthetic observation list response.
#
# Three observations with three nested comments. All identifiers are synthetic
# (``synthetic-`` prefix). Observation #1 is benign (housekeeping). Observation
# #2 carries a ``near-miss`` type (status-fragment safety trigger). Observation
# #3 has an "injury" keyword in the description (body-fragment scan triggers
# safety routing) and a missing assignee.
OBSERVATION_SAMPLE_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": "synthetic-obs-001",
        "number": "OBS-001",
        "title": "Housekeeping at the loading dock",
        "type": "general",
        "subtype": "housekeeping",
        "status": "open",
        "assignee_id": "synthetic-user-31",
        "created_by_id": "synthetic-user-12",
        "observed_at": "2026-05-20T08:30:00Z",
        "due_date": "2026-05-25",
        "created_at": "2026-05-20T08:30:00Z",
        "updated_at": "2026-05-20T08:30:00Z",
        "severity": "low",
        "priority": "normal",
        "html_url": "https://app.procore.example/projects/1/observations/synthetic-obs-001",
        "description": "Reminder to keep the loading dock clear of pallets at end of shift.",
        "comments": [
            {
                "id": "synthetic-obs-001-comment-a",
                "author_id": "synthetic-user-31",
                "created_at": "2026-05-21T09:00:00Z",
                "updated_at": "2026-05-21T09:00:00Z",
                "body": "Crew briefed at toolbox talk. Closed.",
            },
        ],
    },
    {
        "id": "synthetic-obs-002",
        "number": "OBS-002",
        "title": "Stacked materials in walkway",
        "type": "near-miss",
        "subtype": "housekeeping",
        "status": "open",
        "assignee_id": "synthetic-user-9",
        "created_by_id": "synthetic-user-9",
        "observed_at": "2026-05-23T14:15:00Z",
        "due_date": "2026-05-28",
        "created_at": "2026-05-23T14:15:00Z",
        "updated_at": "2026-05-26T17:00:00Z",
        "severity": "medium",
        "priority": "high",
        "html_url": "https://app.procore.example/projects/1/observations/synthetic-obs-002",
        "description": "Drywall stacked across the egress path; identified during the walk.",
        "comments": [
            {
                "id": "synthetic-obs-002-comment-a",
                "author_id": "synthetic-user-2",
                "created_at": "2026-05-26T17:00:00Z",
                "updated_at": "2026-05-26T17:00:00Z",
                "body": "Materials relocated; corridor cleared and re-verified.",
            },
        ],
    },
    {
        "id": "synthetic-obs-003",
        "number": "OBS-003",
        "title": "Worker reports finger laceration",
        "type": "incident",
        "subtype": "injury",
        "status": "open",
        "assignee_id": None,
        "created_by_id": "synthetic-user-7",
        "observed_at": "2026-05-26T11:00:00Z",
        "due_date": "2026-05-27",
        "created_at": "2026-05-26T11:00:00Z",
        "updated_at": "2026-05-27T08:30:00Z",
        "severity": "high",
        "priority": "urgent",
        "html_url": "https://app.procore.example/projects/1/observations/synthetic-obs-003",
        "description": (
            "Worker sustained a minor laceration to the index finger while "
            "handling a metal stud; first aid administered on site; injury "
            "reported per protocol; corrective action under review."
        ),
        "comments": [
            {
                "id": "synthetic-obs-003-comment-a",
                "author_id": "synthetic-user-1",
                "created_at": "2026-05-27T08:30:00Z",
                "updated_at": "2026-05-27T08:30:00Z",
                "body": "Routing to safety officer for follow-up and root cause review.",
            },
        ],
    },
]


PROCORE_OBSERVATION_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "observation_sample_payload": OBSERVATION_SAMPLE_PAYLOAD,
}


# Phase 04 Prompt 07: synthetic meeting list response.
#
# Three meetings, all `synthetic-` prefixed. #1 = bland weekly OAC (low-risk
# default). #2 = "change order discussion" title fragment triggers review.
# #3 = "legal hold review" in status fires the status-fragment heuristic.
MEETING_SAMPLE_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": "synthetic-mtg-001",
        "number": "MTG-001",
        "title": "Weekly OAC",
        "status": "scheduled",
        "start_time": "2026-05-25T15:00:00Z",
        "end_time": "2026-05-25T16:00:00Z",
        "location": "Job trailer conference room",
        "organizer_id": "synthetic-user-15",
        "project_id": "synthetic-proj-1",
        "created_at": "2026-05-15T08:00:00Z",
        "updated_at": "2026-05-22T09:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-001",
    },
    {
        "id": "synthetic-mtg-002",
        "number": "MTG-002",
        "title": "Change order discussion: partition framing scope",
        "status": "scheduled",
        "start_time": "2026-05-28T13:00:00Z",
        "end_time": "2026-05-28T14:30:00Z",
        "location": "Owner conference room",
        "organizer_id": "synthetic-user-3",
        "project_id": "synthetic-proj-1",
        "created_at": "2026-05-22T10:00:00Z",
        "updated_at": "2026-05-26T16:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-002",
    },
    {
        "id": "synthetic-mtg-003",
        "number": "MTG-003",
        "title": "Project alignment",
        "status": "legal_hold_review",
        "start_time": "2026-06-02T09:00:00Z",
        "end_time": "2026-06-02T10:00:00Z",
        "location": "Remote",
        "organizer_id": "synthetic-user-1",
        "project_id": "synthetic-proj-1",
        "created_at": "2026-05-26T11:00:00Z",
        "updated_at": "2026-05-27T08:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-003",
    },
]


# Phase 04 Prompt 07: synthetic meeting-topic list response (separate
# endpoint, peer to meetings — not nested under any parent payload).
#
# Four topics, all `synthetic-` prefixed. Each references a parent meeting
# via ``parent_meeting_id``. Topic #2 carries a safety description (the
# body-scan trigger sets safety_route=true). Topic #3 has "claim" in the
# title (review fires but safety_route stays false — claim is a generic
# review fragment, not a safety-specific one). Topics #1 and #4 are benign.
MEETING_TOPIC_SAMPLE_PAYLOAD: list[dict[str, Any]] = [
    {
        "id": "synthetic-topic-001",
        "title": "Schedule update",
        "status": "open",
        "sequence_number": 1,
        "assignee_id": "synthetic-user-15",
        "due_date": "2026-06-01",
        "parent_meeting_id": "synthetic-mtg-001",
        "created_at": "2026-05-22T10:00:00Z",
        "updated_at": "2026-05-22T10:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-001/topics/synthetic-topic-001",
        "description": "Walk the look-ahead schedule for next two weeks.",
        "action_items": "Subcontractor commitments confirmed by Wednesday.",
    },
    {
        "id": "synthetic-topic-002",
        "title": "Site safety walk follow-up",
        "status": "open",
        "sequence_number": 2,
        "assignee_id": "synthetic-user-2",
        "due_date": "2026-05-30",
        "parent_meeting_id": "synthetic-mtg-001",
        "created_at": "2026-05-22T10:00:00Z",
        "updated_at": "2026-05-22T10:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-001/topics/synthetic-topic-002",
        "description": "Reviewing minor injury incident from last week's drywall installation.",
        "action_items": [
            "Issue corrective action notice to trade",
            "Update PPE briefing materials",
        ],
    },
    {
        "id": "synthetic-topic-003",
        "title": "Owner claim regarding partition scope",
        "status": "open",
        "sequence_number": 1,
        "assignee_id": "synthetic-user-3",
        "due_date": "2026-06-05",
        "parent_meeting_id": "synthetic-mtg-002",
        "created_at": "2026-05-26T16:00:00Z",
        "updated_at": "2026-05-26T16:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-002/topics/synthetic-topic-003",
        "description": "Owner has filed a request for scope clarification under the contract amendment process.",
        "action_items": "Counsel to review and respond by close of week.",
    },
    {
        "id": "synthetic-topic-004",
        "title": "Logistics for next pour",
        "status": "open",
        "sequence_number": 1,
        "assignee_id": "synthetic-user-9",
        "due_date": "2026-06-04",
        "parent_meeting_id": "synthetic-mtg-003",
        "created_at": "2026-05-27T08:00:00Z",
        "updated_at": "2026-05-27T08:00:00Z",
        "html_url": "https://app.procore.example/projects/1/meetings/synthetic-mtg-003/topics/synthetic-topic-004",
        "description": "Pre-pour checklist and mix truck routing.",
        "action_items": "Confirm flagger coverage with city.",
    },
]


PROCORE_MEETING_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "meeting_sample_payload": MEETING_SAMPLE_PAYLOAD,
}

PROCORE_MEETING_TOPIC_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "meeting_topic_sample_payload": MEETING_TOPIC_SAMPLE_PAYLOAD,
}
