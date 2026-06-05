"""Phase 07B Prompt 09 — review-controlled correspondence intelligence (read-only).

Produces a project-level, advisory correspondence preview: redacted thread previews (from
the metadata-only thread summaries) plus aggregated **review warnings** drawn from the open
email review queue and enriched with the review-category registry's evidence-safe metadata.

This is **read-only on every layer** — no Microsoft Graph calls, no token, no writeback to
any external system, and no local SQLite writes. Output is advisory only: warnings and
previews are signals, never final determinations; sensitive/high-impact items always route
to human review.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from hb_assistant.construction.email.review_categories import get_review_category
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value

_MAX_PREVIEWS = 10
_MAX_WARNINGS = 50
_SENSITIVITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


class CorrespondenceWarning(BaseModel):
    """One project-level review warning aggregated from the open review queue."""

    category: str
    label: str
    sensitivity_level: str
    recommended_review_action: str
    evidence_safe_explanation: str
    open_item_count: int

    model_config = {"extra": "forbid"}


class CorrespondencePreview(BaseModel):
    """Evidence-safe preview of one correspondence thread (redacted; no raw content)."""

    thread_ref: str
    message_count: int
    first_message_datetime: Optional[str] = None
    last_message_datetime: Optional[str] = None
    review_required: bool
    summary_redacted: Optional[str] = None

    model_config = {"extra": "forbid"}


class CorrespondenceReviewReport(BaseModel):
    """Project-level correspondence preview + review warnings (advisory, read-only)."""

    project_key: Optional[str] = None
    lookback_days: int
    generated_at: str
    read_only: bool = True
    persisted: bool = False
    threads_total: int
    threads_review_required: int
    review_queue_open: int
    classifications_total: int
    classifications_review_required: int
    classification_risk_flagged: int
    meeting_email_candidates_total: int
    meeting_email_candidates_review_required: int
    warnings: list[CorrespondenceWarning] = Field(default_factory=list)
    previews: list[CorrespondencePreview] = Field(default_factory=list)
    guardrails: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "correspondence previews and warnings are advisory signals, not determinations; "
        "every sensitive/high-impact item requires human review; no raw subject, body, or "
        "address is read or emitted"
    )

    model_config = {"extra": "forbid"}


class CorrespondenceReviewBuilder:
    """Build a read-only, project-level correspondence preview + review warnings."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def review(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: int = 30,
        max_previews: int = _MAX_PREVIEWS,
        max_warnings: int = _MAX_WARNINGS,
    ) -> CorrespondenceReviewReport:
        lookback = max(1, min(int(lookback_days), 3660))
        cutoff = _now() - timedelta(days=lookback)

        threads = [
            t
            for t in self._store.list_email_thread_summaries(project_key=project_key)
            if self._within_lookback(t.get("last_message_datetime"), cutoff)
        ]
        threads_review_required = sum(1 for t in threads if t.get("review_required"))

        classifications = self._store.list_email_model_classifications(project_key=project_key)
        classifications_review_required = sum(
            1 for c in classifications if c.get("review_required")
        )
        classification_risk_flagged = sum(1 for c in classifications if c.get("risk_flags"))

        candidates = self._store.list_meeting_email_relationship_candidates(project_key=project_key)
        candidates_review_required = sum(1 for c in candidates if c.get("review_required"))

        warnings = self._build_warnings(project_key=project_key, max_warnings=max_warnings)
        previews = self._build_previews(threads, max_previews=max_previews)

        return CorrespondenceReviewReport(
            project_key=project_key,
            lookback_days=lookback,
            generated_at=_now().isoformat(),
            threads_total=len(threads),
            threads_review_required=threads_review_required,
            review_queue_open=self._store.count_email_review_queue(
                project_key=project_key, status="open"
            ),
            classifications_total=len(classifications),
            classifications_review_required=classifications_review_required,
            classification_risk_flagged=classification_risk_flagged,
            meeting_email_candidates_total=len(candidates),
            meeting_email_candidates_review_required=candidates_review_required,
            warnings=warnings,
            previews=previews,
            guardrails={
                "external_systems": "read_only",
                "writeback": "none",
                "graph_calls": "none",
                "sqlite_writes": "none",
                "determinations": "none_advisory_only",
                "microsoft_365_writeback_enabled": False,
            },
        )

    @staticmethod
    def _within_lookback(last_message_datetime: Optional[str], cutoff: datetime) -> bool:
        parsed = _parse_dt(last_message_datetime)
        # Keep threads with unparseable/missing timestamps rather than silently dropping.
        return parsed is None or parsed >= cutoff

    def _build_warnings(
        self, *, project_key: Optional[str], max_warnings: int
    ) -> list[CorrespondenceWarning]:
        counts: dict[str, int] = {}
        for item in self._store.list_email_review_queue(project_key=project_key, status="open"):
            category = item.get("category") or "unspecified"
            counts[category] = counts.get(category, 0) + 1

        warnings: list[CorrespondenceWarning] = []
        for category, count in counts.items():
            meta = get_review_category(category)
            if meta is not None:
                warnings.append(
                    CorrespondenceWarning(
                        category=meta.id,
                        label=meta.label,
                        sensitivity_level=meta.sensitivity_level,
                        recommended_review_action=meta.recommended_review_action,
                        evidence_safe_explanation=meta.evidence_safe_explanation,
                        open_item_count=count,
                    )
                )
            else:
                warnings.append(
                    CorrespondenceWarning(
                        category=category,
                        label=category.replace("_", " ").title(),
                        sensitivity_level="medium",
                        recommended_review_action="route_to_review_no_determination",
                        evidence_safe_explanation=("review required; not a determination"),
                        open_item_count=count,
                    )
                )
        warnings.sort(
            key=lambda w: (
                _SENSITIVITY_ORDER.get(w.sensitivity_level, 9),
                -w.open_item_count,
                w.category,
            )
        )
        return warnings[:max_warnings]

    @staticmethod
    def _build_previews(
        threads: list[dict[str, Any]], *, max_previews: int
    ) -> list[CorrespondencePreview]:
        ordered = sorted(
            threads,
            key=lambda t: (t.get("last_message_datetime") or "", t.get("thread_key") or ""),
            reverse=True,
        )
        previews: list[CorrespondencePreview] = []
        for thread in ordered[:max_previews]:
            thread_key = thread.get("thread_key") or ""
            previews.append(
                CorrespondencePreview(
                    thread_ref=hash_value(thread_key) or thread_key,
                    message_count=int(thread.get("message_count") or 0),
                    first_message_datetime=thread.get("first_message_datetime"),
                    last_message_datetime=thread.get("last_message_datetime"),
                    review_required=bool(thread.get("review_required")),
                    summary_redacted=thread.get("summary_redacted"),
                )
            )
        return previews
