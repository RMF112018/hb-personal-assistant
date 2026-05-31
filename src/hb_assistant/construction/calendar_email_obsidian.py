"""Phase 07B Prompt 10 — marker-bounded Obsidian calendar/email register (redacted).

Renders ONE marker-bounded register note per project that combines the redacted email
correspondence review (warnings + previews, from Prompt 09) with the calendar↔email
relationship candidates and bounded calendar counts. There is **no one-note-per-event /
per-email output** — a single grouped register per project.

Read-only on every layer: no Microsoft Graph calls, no token, no SQLite writes. The only
output is the Obsidian note, written to the vault **only** when ``dry_run=False``. Every
rendered note carries hashes / counts / datetimes only — no raw subject, body, address,
organizer, attendee, location, event id, iCal UID, or join/web URL. A self leak-scan runs
before any write; a note that would leak is never written.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.correspondence import CorrespondenceReviewBuilder
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.procore_no_writeback_proof import _scan_text_for_secrets

_BASE = "Work/HB Personal Assistant/07_Calendar_Email_Intelligence"
_MARKER_KEY = "register"

# Tokens that must never appear in a rendered register (raw calendar/email content).
_FORBIDDEN_TOKENS = (
    "<html",
    "<body",
    "from:",
    "to:",
    "cc:",
    "-----original message-----",
    "full_body_" + "plaintext",
    "raw email body",
    "begin:vcalendar",
    "begin:vevent",
    "join url",
    "joinurl",
    "teams.microsoft.com",
    "https://",
    "http://",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _scan_register_for_leaks(value: str) -> list[str]:
    """Return any leak indicators in the rendered register (empty when clean)."""
    lower = (value or "").lower()
    hits = [tok for tok in _FORBIDDEN_TOKENS if tok in lower]
    # A raw email address ("local@domain") must never appear.
    if re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value or ""):
        hits.append("raw_email_address")
    hits.extend(_scan_text_for_secrets(value or ""))
    return hits


def _table(headers: list[str], rows: list[list[str]], *, empty: str) -> str:
    if not rows:
        return f"_{empty}_"
    head = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    body = "\n".join("| " + " | ".join(_cell(c) for c in r) + " |" for r in rows)
    return "\n".join([head, sep, body])


def _cell(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).replace("|", "/")


class CalendarEmailObsidianReport(BaseModel):
    project_key: Optional[str] = None
    dry_run: bool
    generated_at: str
    notes_planned: int
    notes_written: int
    events_referenced: int
    threads_referenced: int
    warnings_referenced: int
    candidates_referenced: int
    plaintext_written: bool = False
    paths: list[str]
    guardrails: dict[str, Any]
    disclaimer: str = (
        "advisory register; previews and warnings are signals, not determinations; every "
        "sensitive/high-impact item requires human review; no raw subject, body, address, "
        "organizer, attendee, location, event id, iCal UID, or join/web URL is rendered — "
        "only hashes, counts, and datetimes"
    )

    model_config = {"extra": "forbid"}


class CalendarEmailObsidianProjector:
    """Render a marker-bounded, redacted calendar/email register per project (local-only)."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def project(
        self,
        *,
        project_key: Optional[str] = None,
        dry_run: bool = True,
        max_rows: int = 25,
    ) -> CalendarEmailObsidianReport:
        review = CorrespondenceReviewBuilder(self._store).review(
            project_key=project_key, lookback_days=3660, max_previews=max_rows, max_warnings=max_rows
        )
        candidates = self._store.list_meeting_email_relationship_candidates(
            project_key=project_key, limit=5000
        )
        events = self._store.list_calendar_event_index()
        events_review_required = sum(1 for e in events if e.get("review_required"))

        content = self._render(
            project_key=project_key,
            review=review,
            candidates=candidates,
            events_total=len(events),
            events_review_required=events_review_required,
            max_rows=max_rows,
        )
        leaks = _scan_register_for_leaks(content)
        if leaks:
            raise ValueError(f"refusing to render leaking calendar/email register: {leaks[:5]}")

        project = project_key or "all-projects"
        relative_path = f"{_BASE}/Projects/{project}/Calendar & Email Register.md"
        target = PathPolicy().get_vault_root() / relative_path

        written = 0
        if not dry_run:
            self._write(target, content)
            written = 1

        return CalendarEmailObsidianReport(
            project_key=project_key,
            dry_run=dry_run,
            generated_at=_utc_now(),
            notes_planned=1,
            notes_written=written,
            events_referenced=len(events),
            threads_referenced=review.threads_total,
            warnings_referenced=len(review.warnings),
            candidates_referenced=len(candidates),
            plaintext_written=False,
            paths=[str(target)],
            guardrails={
                "external_systems": "read_only",
                "graph_calls": "none",
                "writeback": "none",
                "sqlite_writes": "none",
                "one_note_per_item": False,
                "plaintext_in_obsidian": False,
                "leak_scanned": True,
                "microsoft_365_writeback_enabled": False,
            },
        )

    def _render(
        self,
        *,
        project_key: Optional[str],
        review: Any,
        candidates: list[dict[str, Any]],
        events_total: int,
        events_review_required: int,
        max_rows: int,
    ) -> str:
        project = project_key or "all-projects"
        lines: list[str] = [
            f"# Calendar & Email Register — {project}",
            "",
            f"_Generated {_utc_now()} · advisory register, signals not determinations._",
            "",
            "## Overview",
            "",
        ]
        overview = _table(
            ["Metric", "Count"],
            [
                ["Email threads", str(review.threads_total)],
                ["Threads review-required", str(review.threads_review_required)],
                ["Open review-queue items", str(review.review_queue_open)],
                ["Model classifications", str(review.classifications_total)],
                ["Classifications review-required", str(review.classifications_review_required)],
                ["Classifications risk-flagged", str(review.classification_risk_flagged)],
                ["Meeting↔email candidates", str(review.meeting_email_candidates_total)],
                [
                    "Candidates review-required",
                    str(review.meeting_email_candidates_review_required),
                ],
                ["Calendar events indexed", str(events_total)],
                ["Calendar events review-required", str(events_review_required)],
            ],
            empty="no data",
        )
        lines += [overview, "", "## Review Warnings", ""]
        lines.append(
            _table(
                ["Category", "Sensitivity", "Open", "Recommended action", "Explanation"],
                [
                    [
                        w.category,
                        w.sensitivity_level,
                        str(w.open_item_count),
                        w.recommended_review_action,
                        w.evidence_safe_explanation,
                    ]
                    for w in review.warnings[:max_rows]
                ],
                empty="no open review warnings",
            )
        )
        lines += ["", "## Correspondence Previews", ""]
        lines.append(
            _table(
                ["Thread ref", "Msgs", "Window", "Review?", "Summary"],
                [
                    [
                        p.thread_ref,
                        str(p.message_count),
                        f"{p.first_message_datetime or '?'} → {p.last_message_datetime or '?'}",
                        "yes" if p.review_required else "no",
                        p.summary_redacted or "",
                    ]
                    for p in review.previews[:max_rows]
                ],
                empty="no correspondence previews",
            )
        )
        lines += ["", "## Meeting ↔ Email Links", ""]
        lines.append(
            _table(
                ["Event ref", "Thread ref", "Class", "Confidence", "Review?", "Event window"],
                [
                    [
                        hash_value(c["event_index_id"]) or c["event_index_id"],
                        c.get("thread_key_hash") or "",
                        c.get("confidence_class") or "",
                        f"{float(c.get('confidence') or 0.0):.2f}",
                        "yes" if c.get("review_required") else "no",
                        self._event_window(c.get("source_reference_json")),
                    ]
                    for c in candidates[:max_rows]
                ],
                empty="no meeting↔email candidates",
            )
        )
        lines += [
            "",
            "## Guardrails",
            "",
            "- external systems: read-only · graph calls: none · writeback: none",
            "- one note per project (not per event/email) · no plaintext body · leak-scanned",
            "- advisory only — sensitive/high-impact items require human review",
        ]
        return "\n".join(lines)

    @staticmethod
    def _event_window(source_reference: Any) -> str:
        if not isinstance(source_reference, dict):
            return "?"
        start = source_reference.get("event_start_utc") or "?"
        end = source_reference.get("event_end_utc") or "?"
        return f"{start} → {end}"

    def _write(self, target: Any, content: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        start = f"<!-- HB-CALENDAR-EMAIL-{_MARKER_KEY.upper()}:START -->"
        end = f"<!-- HB-CALENDAR-EMAIL-{_MARKER_KEY.upper()}:END -->"
        if start not in existing or end not in existing:
            if existing and not existing.endswith("\n"):
                existing += "\n"
            existing = existing + f"\n{start}\n{end}\n"
        pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
        rendered = pattern.sub(rf"\1\n{content.strip()}\n\3", existing)
        leaks = _scan_register_for_leaks(rendered)
        if leaks:
            raise ValueError(f"forbidden content in calendar/email register: {leaks[:5]}")
        target.write_text(rendered, encoding="utf-8")
