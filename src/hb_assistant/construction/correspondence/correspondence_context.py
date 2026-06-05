"""Phase 07D Prompt 10 — review-controlled correspondence context (read-only projection).

Ties each email thread summary to the records it relates to — meetings, RFIs, submittals, changes,
commitments, daily-log issues, inspections, and documents — **only where relationships already
exist** in the cross-source substrate. This is a read-only projection: it reads existing redacted
read models and the V25 substrate edges and returns an advisory report — nothing is written to
SQLite or any external system, and no relationship is promoted.

Anchoring: each ``email_thread_summaries`` row is the anchor. Thread↔meeting ties come from
``meeting_email_relationship_candidates`` (matched on ``thread_key_hash == hash_value(thread_key)``);
thread↔record ties come from the email-source ``cross_source_relationship_candidates`` rolled up from
message to thread via ``email_messages`` (message_id → thread_key). Weak / model / sensitive ties
keep the thread/category ``review_required`` and are never auto-promoted.

Guardrails: local-first, read-only against external systems **and** local SQLite (no writes); the
output carries only the bounded ``summary_redacted`` (metadata-only by policy), counts, local record
refs / hashes / endpoint names, confidence classes, and evidence-trail ids — never a raw email body,
subject, web link, signed/download URL, token, or secret. Outputs are advisory; no determinations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_CONTEXT_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "persistence": "none_read_only_projection",
    "no_raw_content": True,
    "refs_are_local_ids_or_hashes": True,
    "advisory_only": True,
    "no_final_determinations": True,
    "auto_promotion": False,
}

_RECORD_CATEGORIES = (
    "meetings",
    "rfis",
    "submittals",
    "changes",
    "commitments",
    "daily_log_issues",
    "inspections",
    "documents",
)

# Confidence classes that keep a tie review-required (in addition to any review_required flag).
_REVIEW_CONFIDENCE_CLASSES = frozenset({"weak_heuristic", "model_proposed", "stale_or_unresolved"})


def _categorize(target_family: Any, target_record_type: Any, relationship_type: Any) -> str:
    """Classify a record tie into one of the 8 categories (or 'project'/'other')."""
    tt = str(target_record_type or "").lower()
    rt = str(relationship_type or "").lower()
    tf = str(target_family or "").lower()
    if "meeting" in tt or "meeting" in rt or tf == "calendar":
        return "meetings"
    if (
        tf == "document"
        or "sharepoint" in tt
        or "drive_item" in tt
        or "document" in tt
        or "attachment" in rt
    ):
        return "documents"
    if "rfi" in tt:
        return "rfis"
    if "submittal" in tt:
        return "submittals"
    if "change" in tt or "change" in rt:
        return "changes"
    if "daily" in tt or "daily" in rt:
        return "daily_log_issues"
    if "inspection" in tt:
        return "inspections"
    if "commitment" in tt or "contract" in tt or "invoice" in tt or "pay" in tt:
        return "commitments"
    if "project" in tt or rt == "project_match":
        return "project"
    return "other"


class CorrespondenceContextBuilder:
    """Project email thread summaries onto their related records (read-only)."""

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()

    def _message_to_thread(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for m in self._store.list_email_messages(limit=100000):
            mid = m.get("message_id")
            tk = m.get("thread_key")
            if mid and tk:
                out[str(mid)] = str(tk)
        return out

    def context(
        self,
        *,
        project_filter: Optional[str] = None,
        lookback_days: Optional[int] = None,
        max_per_category: int = 25,
        now_utc: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Tie email thread summaries to related records. Read-only; persists nothing."""
        cutoff: Optional[datetime] = None
        if lookback_days is not None:
            now = now_utc or datetime.now(timezone.utc)
            cutoff = now - timedelta(days=int(lookback_days))
        threads = self._store.list_email_thread_summaries(project_key=project_filter, limit=100000)
        msg_to_thread = self._message_to_thread()

        # thread_key (via hash) -> list of meeting ties
        meetings_by_hash: dict[str, list[dict[str, Any]]] = {}
        for cand in self._store.list_meeting_email_relationship_candidates(
            project_key=project_filter, limit=100000
        ):
            meetings_by_hash.setdefault(str(cand.get("thread_key_hash")), []).append(cand)

        # thread_key -> {category: [ties]}
        records_by_thread: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for edge in self._store.list_cross_source_relationship_candidates(
            project_key=project_filter, limit=100000
        ):
            if edge.get("source_family") != "email":
                continue
            thread_key = msg_to_thread.get(str(edge.get("source_record_ref")))
            if thread_key is None:
                continue
            category = _categorize(
                edge.get("target_family"),
                edge.get("target_record_type"),
                edge.get("relationship_type"),
            )
            tie = {
                "ref": str(edge.get("target_record_ref")),
                "relationship_type": str(edge.get("relationship_type")),
                "confidence_class": str(edge.get("confidence_class")),
                "review_required": bool(
                    edge.get("review_required")
                    or edge.get("sensitive_high_impact")
                    or edge.get("model_proposed")
                    or edge.get("confidence_class") in _REVIEW_CONFIDENCE_CLASSES
                ),
                "evidence_trail_id": edge.get("evidence_trail_id"),
            }
            records_by_thread.setdefault(thread_key, {}).setdefault(category, []).append(tie)

        thread_reports: list[dict[str, Any]] = []
        by_category_total: dict[str, int] = {}
        threads_linked = 0
        project_confirmations = 0
        review_required_threads = 0

        for t in threads:
            thread_key = str(t.get("thread_key"))
            if cutoff is not None and not self._within_lookback(
                t.get("last_message_datetime"), cutoff
            ):
                continue
            related: dict[str, list[dict[str, Any]]] = {}

            # meetings (thread <-> calendar event)
            for cand in meetings_by_hash.get(hash_value(thread_key) or thread_key, []):
                related.setdefault("meetings", []).append(
                    {
                        "ref": str(cand.get("event_index_id")),
                        "relationship_type": "meeting_email_correlation",
                        "confidence_class": str(cand.get("confidence_class")),
                        "review_required": bool(
                            cand.get("review_required")
                            or cand.get("model_proposed")
                            or cand.get("confidence_class") in _REVIEW_CONFIDENCE_CLASSES
                        ),
                        "evidence_trail_id": None,
                    }
                )

            # record ties (rfis / documents / changes / ...)
            project_confirmed = False
            for category, ties in records_by_thread.get(thread_key, {}).items():
                if category == "project":
                    project_confirmed = True
                    continue
                if category == "other":
                    continue
                related.setdefault(category, []).extend(ties)

            record_categories = {c: v for c, v in related.items() if c in _RECORD_CATEGORIES}
            if not record_categories and not project_confirmed:
                continue  # only tie threads where relationships exist
            if record_categories:
                threads_linked += 1
            if project_confirmed:
                project_confirmations += 1

            review_required = bool(t.get("review_required")) or any(
                tie["review_required"] for ties in record_categories.values() for tie in ties
            )
            if review_required:
                review_required_threads += 1

            capped = {c: ties[:max_per_category] for c, ties in sorted(record_categories.items())}
            by_cat_counts: dict[str, int] = {}
            for c, ties in record_categories.items():
                by_cat_counts[c] = len(ties)
                by_category_total[c] = by_category_total.get(c, 0) + len(ties)

            thread_reports.append(
                {
                    "thread_key": thread_key,
                    "project_key": t.get("project_key"),
                    "message_count": t.get("message_count"),
                    "last_activity": t.get("last_message_datetime"),
                    "summary_redacted": t.get("summary_redacted"),
                    "review_required": review_required,
                    "project_confirmed": project_confirmed,
                    "by_category": dict(sorted(by_cat_counts.items())),
                    "related": capped,
                }
            )

        return {
            "command": "construction-agent correspondence context",
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "project_filter": project_filter,
            "lookback_days": lookback_days,
            "summary": {
                "threads_total": len(threads),
                "threads_linked": threads_linked,
                "project_confirmations": project_confirmations,
                "review_required_threads": review_required_threads,
                "by_category": dict(sorted(by_category_total.items())),
            },
            "threads": thread_reports,
            "guardrails": _CONTEXT_GUARDRAILS,
        }

    @staticmethod
    def _within_lookback(last_dt: Any, cutoff: datetime) -> bool:
        if not last_dt:
            return False
        text = str(last_dt)
        text = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff


def correspondence_context_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage summary over correspondence-context ties (the summary block only)."""
    report = CorrespondenceContextBuilder(store).context(project_filter=project_filter)
    return {
        "command": "construction-agent correspondence status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": report["summary"],
        "guardrails": _CONTEXT_GUARDRAILS,
    }
