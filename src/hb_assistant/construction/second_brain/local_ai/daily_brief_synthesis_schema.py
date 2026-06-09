"""Phase 10 correction — schema for the local-model-synthesized executive daily brief.

The local model must return JSON matching :class:`DailyBriefSynthesis`. ``extra="ignore"`` **drops**
unknown fields (a local model that emits a stray key never reaches the rendered brief, and nothing
the model returns is ever persisted/logged — receipts are hash-only — so the raw-content boundary is
unaffected). Structural mismatches (non-JSON, wrong types for known fields) still fail validation →
the structured-output client retries, then fails closed → a clearly-marked degraded brief. Size
limits (bullet counts, string lengths) are **clamped** by validators rather than rejected, so a
slightly over-long model answer normalizes instead of failing the whole brief.

These are the nine operator sections the brief must contain. No raw content lives here by contract;
the values are short synthesized prose referencing safe candidate/source IDs for traceability.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

_MAX_BULLET_CHARS = 500
_MAX_TITLE_CHARS = 200
_MAX_PROJECT_CHARS = 80
_MAX_PREP_CHARS = 700
_MAX_SOURCE_ID_CHARS = 48


def _clamp_str(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _clamp_str_list(values: object, *, max_items: int, max_chars: int) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for v in values:
        s = _clamp_str(v, max_chars)
        if s:
            out.append(s)
        if len(out) >= max_items:
            break
    return out


class BriefBullet(BaseModel):
    """A single synthesized insight bullet with optional traceability."""

    text: str
    source_id: str = ""
    project: str = ""

    model_config = {"extra": "ignore"}

    @field_validator("text")
    @classmethod
    def _v_text(cls, v: object) -> str:
        return _clamp_str(v, _MAX_BULLET_CHARS)

    @field_validator("source_id")
    @classmethod
    def _v_source(cls, v: object) -> str:
        return _clamp_str(v, _MAX_SOURCE_ID_CHARS)

    @field_validator("project")
    @classmethod
    def _v_project(cls, v: object) -> str:
        return _clamp_str(v, _MAX_PROJECT_CHARS)


class BriefMeetingItem(BaseModel):
    """A synthesized meeting-prep item for the day."""

    local_time: str = ""
    title: str
    project: str = "Needs Project Review"
    why_it_matters: str = ""
    prep: str = ""
    open_questions: list[str] = []
    source_id: str = ""
    recommended_next_action: str = ""

    model_config = {"extra": "ignore"}

    @field_validator("title")
    @classmethod
    def _v_title(cls, v: object) -> str:
        return _clamp_str(v, _MAX_TITLE_CHARS) or "(untitled meeting)"

    @field_validator("local_time", "recommended_next_action")
    @classmethod
    def _v_short(cls, v: object) -> str:
        return _clamp_str(v, _MAX_TITLE_CHARS)

    @field_validator("project")
    @classmethod
    def _v_project(cls, v: object) -> str:
        return _clamp_str(v, _MAX_PROJECT_CHARS) or "Needs Project Review"

    @field_validator("why_it_matters", "prep")
    @classmethod
    def _v_prep(cls, v: object) -> str:
        return _clamp_str(v, _MAX_PREP_CHARS)

    @field_validator("source_id")
    @classmethod
    def _v_source(cls, v: object) -> str:
        return _clamp_str(v, _MAX_SOURCE_ID_CHARS)

    @field_validator("open_questions")
    @classmethod
    def _v_questions(cls, v: object) -> list[str]:
        return _clamp_str_list(v, max_items=6, max_chars=_MAX_BULLET_CHARS)


class ProjectSignalGroup(BaseModel):
    """Plain-English project signal rollup, grouped by project."""

    project: str
    summary: str = ""
    items: list[BriefBullet] = []

    model_config = {"extra": "ignore"}

    @field_validator("project")
    @classmethod
    def _v_project(cls, v: object) -> str:
        return _clamp_str(v, _MAX_PROJECT_CHARS) or "Needs Project Review"

    @field_validator("summary")
    @classmethod
    def _v_summary(cls, v: object) -> str:
        return _clamp_str(v, _MAX_PREP_CHARS)

    @field_validator("items")
    @classmethod
    def _v_items(cls, v: object) -> list[BriefBullet]:
        return list(v)[:20] if isinstance(v, list) else []


class DailyBriefSynthesis(BaseModel):
    """The full local-model-synthesized operator brief (nine required sections)."""

    executive_summary: list[str] = []
    what_changed_since_last_brief: list[BriefBullet] = []
    critical_due_today: list[BriefBullet] = []
    open_commitments_follow_ups: list[BriefBullet] = []
    todays_meetings: list[BriefMeetingItem] = []
    project_signals: list[ProjectSignalGroup] = []
    recommended_next_actions: list[str] = []
    fyi_low_priority: list[str] = []
    needs_review_data_gaps: list[str] = []

    model_config = {"extra": "ignore"}

    @field_validator("executive_summary")
    @classmethod
    def _v_exec(cls, v: object) -> list[str]:
        return _clamp_str_list(v, max_items=7, max_chars=_MAX_BULLET_CHARS)

    @field_validator("recommended_next_actions")
    @classmethod
    def _v_actions(cls, v: object) -> list[str]:
        return _clamp_str_list(v, max_items=10, max_chars=_MAX_BULLET_CHARS)

    @field_validator("fyi_low_priority")
    @classmethod
    def _v_fyi(cls, v: object) -> list[str]:
        return _clamp_str_list(v, max_items=15, max_chars=_MAX_BULLET_CHARS)

    @field_validator("needs_review_data_gaps")
    @classmethod
    def _v_gaps(cls, v: object) -> list[str]:
        return _clamp_str_list(v, max_items=15, max_chars=_MAX_BULLET_CHARS)

    @field_validator(
        "what_changed_since_last_brief",
        "critical_due_today",
        "open_commitments_follow_ups",
    )
    @classmethod
    def _v_bullets(cls, v: object) -> list[BriefBullet]:
        return list(v)[:20] if isinstance(v, list) else []

    @field_validator("todays_meetings")
    @classmethod
    def _v_meetings(cls, v: object) -> list[BriefMeetingItem]:
        return list(v)[:20] if isinstance(v, list) else []

    @field_validator("project_signals")
    @classmethod
    def _v_signals(cls, v: object) -> list[ProjectSignalGroup]:
        return list(v)[:20] if isinstance(v, list) else []

    def is_empty(self) -> bool:
        """True when the model produced no usable operator content (→ treat as low-quality)."""
        return not (
            self.executive_summary
            or self.what_changed_since_last_brief
            or self.critical_due_today
            or self.open_commitments_follow_ups
            or self.todays_meetings
            or self.project_signals
            or self.recommended_next_actions
        )
