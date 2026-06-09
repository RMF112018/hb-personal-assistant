"""Local model evaluation — safe fixture contracts.

Two fixture sources:

* **Synthetic fixtures** (this module, committed). Redacted, deterministic, safe to commit. Each
  carries a bounded ``input_redacted`` context (what the prompt is built from) and a canned
  ``synthetic_output`` JSON string used by the *offline* backend (:class:`StaticOutputClient`) so
  the harness exercises the full generate→validate→metrics path with no daemon and no network.
* **Raw local fixtures** (opt-in, *outside the repo only*). For an operator who wants to evaluate a
  real model against real-but-local samples. :func:`load_raw_fixtures` **refuses any path inside the
  repository** (raw operator content must never be committed) and never returns the raw text to
  callers that persist evidence — it is for local operator consumption only.

No fixture here contains a URL, email address, join link, or token; the synthetic outputs are
schema-valid and redaction-clean by construction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from hb_assistant.config.path_policy import PathPolicy

#: The five evaluated task families (mirrors the package scope). At least three are backed by a
#: real production schema (``ActionCandidate`` / ``DailyBriefSynthesis``); calendar/procore use
#: compact eval schemas defined in :mod:`model_eval`.
TASK_FAMILIES: tuple[str, ...] = (
    "email_action_extraction_json",
    "daily_brief_synthesis_quality",
    "calendar_prep_summary",
    "procore_digest_summary",
    "short_operator_catchup",
)


class ModelEvalFixture(BaseModel):
    """One redacted evaluation fixture for a single task family."""

    fixture_id: str
    task_family: str
    #: Bounded, redacted context the live prompt is built from (safe to commit).
    input_redacted: dict[str, Any] = Field(default_factory=dict)
    #: Canned schema-valid model output (JSON string) used by the offline backend.
    synthetic_output: str
    #: Section keys used by the usefulness rubric (optional; defaults to validated keys).
    expected_sections: list[str] = Field(default_factory=list)
    #: Rubric expectations (e.g. ``{"require_source_links": true}``).
    rubric: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


def _json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True)


# --- synthetic outputs (schema-valid, redaction-clean) ---------------------------------------
_EMAIL_OUTPUT = _json(
    {
        "candidate_type": "task",
        "title": "Send revised steel shop-drawing transmittal to design team",
        "project_key": "RIVERFRONT-TOWER",
        "assignee": "user",
        "due_at": None,
        "urgency": "high",
        "waiting_state": "waiting_on_me",
        "source_refs": ["thread:steel-rev-3"],
        "confidence": 0.82,
        "reason": "Thread requests Bobby return the revised transmittal before the next coordination call.",
        "review_status": "pending",
        "safety_category": "normal",
        "recommended_next_action": "draft_followup",
        "external_action_requires_approval": True,
    }
)

_SYNTHESIS_OUTPUT = _json(
    {
        "executive_summary": [
            "Two items are genuinely due today; everything else can wait until the afternoon block.",
            "Steel coordination remains the critical path — the revised transmittal is the gating item.",
        ],
        "what_changed_since_last_brief": [
            {
                "text": "Owner approved the revised foundation sequence over the weekend.",
                "source_id": "cand:wk-101",
                "project": "RIVERFRONT-TOWER",
            }
        ],
        "critical_due_today": [
            {
                "text": "Return the steel shop-drawing transmittal before the 2pm coordination call.",
                "source_id": "cand:wk-204",
                "project": "RIVERFRONT-TOWER",
            }
        ],
        "open_commitments_follow_ups": [
            {
                "text": "Superintendent still owes the updated three-week look-ahead.",
                "source_id": "cand:wk-220",
                "project": "HARBOR-PLAZA",
            }
        ],
        "todays_meetings": [
            {
                "local_time": "2:00 PM",
                "title": "Steel coordination",
                "project": "RIVERFRONT-TOWER",
                "why_it_matters": "Resolves the gating transmittal and unblocks fabrication.",
                "prep": "Bring the revised transmittal and the open RFI list.",
                "open_questions": ["Is the connection detail at grid C resolved?"],
                "source_id": "cand:mtg-9",
                "recommended_next_action": "prepare_meeting",
            }
        ],
        "project_signals": [
            {
                "project": "HARBOR-PLAZA",
                "summary": "Two Procore items aging past 7 days.",
                "items": [{"text": "Submittal 042 awaiting architect.", "source_id": "cand:pc-5"}],
            }
        ],
        "recommended_next_actions": ["Finish and send the steel transmittal first."],
        "fyi_low_priority": ["Parking-lot striping rescheduled to next week."],
        "needs_review_data_gaps": ["Three candidates have no project assigned."],
    }
)

_CATCHUP_OUTPUT = _json(
    {
        "executive_summary": [
            "You have one hard deadline today and two open loops waiting on others.",
            "Nothing high-stakes is blocked on you beyond the steel transmittal.",
        ],
        "critical_due_today": [
            {
                "text": "Steel transmittal due before 2pm.",
                "source_id": "cand:wk-204",
                "project": "RIVERFRONT-TOWER",
            }
        ],
        "recommended_next_actions": ["Send the steel transmittal, then review the look-ahead."],
    }
)

_CALENDAR_OUTPUT = _json(
    {
        "meetings": [
            {
                "local_time": "9:00 AM",
                "title": "OAC weekly",
                "project": "RIVERFRONT-TOWER",
                "why_it_matters": "Owner expects a schedule recovery update.",
                "prep": "Bring the updated milestone slip summary.",
                "source_id": "cand:mtg-1",
            },
            {
                "local_time": "2:00 PM",
                "title": "Steel coordination",
                "project": "RIVERFRONT-TOWER",
                "why_it_matters": "Gating transmittal review.",
                "prep": "Revised transmittal + open RFIs.",
                "source_id": "cand:mtg-9",
            },
        ]
    }
)

_PROCORE_OUTPUT = _json(
    {
        "signals": [
            {
                "project": "HARBOR-PLAZA",
                "title": "Submittal 042 aging past 7 days",
                "risk": "Architect review overdue; threatens curtain-wall release.",
                "recommended_next_action": "Escalate to architect at today's OAC.",
                "source_id": "cand:pc-5",
            }
        ]
    }
)


def synthetic_fixtures() -> list[ModelEvalFixture]:
    """The committed synthetic eval fixtures (one per task family)."""
    return [
        ModelEvalFixture(
            fixture_id="syn-email-001",
            task_family="email_action_extraction_json",
            input_redacted={
                "thread_subject_redacted": "Steel shop-drawing revision 3",
                "summary_redacted": "Design team asks Bobby to return the revised transmittal before the coordination call.",
            },
            synthetic_output=_EMAIL_OUTPUT,
            expected_sections=["title", "source_refs", "recommended_next_action"],
            rubric={"require_source_links": True},
        ),
        ModelEvalFixture(
            fixture_id="syn-synth-001",
            task_family="daily_brief_synthesis_quality",
            input_redacted={
                "summary_redacted": "One due-today item, two open loops, one Procore aging signal, one meeting to prep."
            },
            synthetic_output=_SYNTHESIS_OUTPUT,
            expected_sections=[
                "executive_summary",
                "critical_due_today",
                "open_commitments_follow_ups",
                "todays_meetings",
                "project_signals",
                "recommended_next_actions",
            ],
            rubric={"require_source_links": True},
        ),
        ModelEvalFixture(
            fixture_id="syn-catchup-001",
            task_family="short_operator_catchup",
            input_redacted={
                "summary_redacted": "Quick catch-up: one deadline, two waiting-on-others loops."
            },
            synthetic_output=_CATCHUP_OUTPUT,
            expected_sections=[
                "executive_summary",
                "critical_due_today",
                "recommended_next_actions",
            ],
            rubric={"require_source_links": True},
        ),
        ModelEvalFixture(
            fixture_id="syn-calendar-001",
            task_family="calendar_prep_summary",
            input_redacted={"summary_redacted": "Two meetings worth prepping today."},
            synthetic_output=_CALENDAR_OUTPUT,
            expected_sections=["meetings"],
            rubric={"require_source_links": True},
        ),
        ModelEvalFixture(
            fixture_id="syn-procore-001",
            task_family="procore_digest_summary",
            input_redacted={
                "summary_redacted": "One aging Procore submittal threatens a downstream release."
            },
            synthetic_output=_PROCORE_OUTPUT,
            expected_sections=["signals"],
            rubric={"require_source_links": True},
        ),
    ]


def synthetic_fixtures_for(task_families: list[str] | None = None) -> list[ModelEvalFixture]:
    """Synthetic fixtures filtered to ``task_families`` (all when None/empty)."""
    fixtures = synthetic_fixtures()
    if not task_families:
        return fixtures
    wanted = set(task_families)
    return [f for f in fixtures if f.task_family in wanted]


class RawFixtureRefusedError(RuntimeError):
    """Raised when a raw-fixture directory is unsafe (inside the repo / missing)."""


def load_raw_fixtures(directory: str | Path) -> list[ModelEvalFixture]:
    """Load opt-in raw operator fixtures from a directory **outside the repository**.

    Refuses (fail-closed) any path that resolves inside the repo root — raw operator content must
    never be committed. Each ``*.json`` file must already match the :class:`ModelEvalFixture` shape;
    redaction of those local files is the operator's responsibility and they are never persisted to
    evidence by the harness.
    """
    repo_root = PathPolicy().resolve_repo_root().resolve()
    path = Path(directory).expanduser().resolve()
    try:
        path.relative_to(repo_root)
        inside_repo = True
    except ValueError:
        inside_repo = False
    if inside_repo:
        raise RawFixtureRefusedError(
            "raw fixture directory is inside the repository; raw operator content must live outside the repo"
        )
    if not path.is_dir():
        raise RawFixtureRefusedError(f"raw fixture directory not found: {path}")
    fixtures: list[ModelEvalFixture] = []
    for fixture_file in sorted(path.glob("*.json")):
        parsed = json.loads(fixture_file.read_text(encoding="utf-8"))
        fixtures.append(ModelEvalFixture.model_validate(parsed))
    return fixtures
