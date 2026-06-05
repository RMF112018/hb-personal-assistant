"""Phase 06 — email relationship candidate builder (local-only synthesis).

Generates **candidate** links between project-matched emails and project identity,
Procore controls/financials, SharePoint/OneDrive files, and calendar meetings.
Reads only stored email intelligence + the repo's Procore/calendar/drive tables —
**no Graph call, no mailbox access**. The only writes are local
`email_relationship_candidates` rows.

Candidates are **not determinations**: each carries a confidence, `review_required`,
and a redacted evidence string that says "possible …" — never "valid claim" /
"liability confirmed". Sensitive topics (financial/legal) route to review.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.email.attachment_analyzer import classify_text_sensitivity
from hb_assistant.construction.email.project_matcher import load_pilot_project_descriptors
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.connection import get_connection

_PROCORE_DOMAINS = ("procore.com", "procoretech.com", "mail.procore.com")
_ACCEPT_THRESHOLD = 0.60

# Procore-control keyword -> candidate type (detected in the bounded preview).
_PROCORE_CONTROL_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("rfi", "procore_rfi"),
    ("submittal", "procore_submittal"),
    ("observation", "procore_observation"),
    ("change event", "procore_change_event"),
    ("change order", "procore_change_event"),
    ("rfq", "procore_rfq"),
    ("daily log", "procore_daily_log"),
    ("punch", "procore_observation"),
    ("inspection", "procore_observation"),
    ("meeting", "procore_meeting"),
)
# Financial keyword -> candidate type (routes to review).
_PROCORE_FINANCIAL_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("pay app", "procore_payment_application"),
    ("payment application", "procore_payment_application"),
    ("invoice", "procore_invoice"),
    ("contract", "procore_contract"),
    ("commitment", "procore_commitment"),
)
# Outlook meeting-email patterns (detected in the bounded preview).
_MEETING_PATTERNS = (
    "accepted:",
    "declined:",
    "tentative:",
    "invitation:",
    "canceled:",
    "cancelled:",
    "when:",
    "where:",
    "microsoft teams meeting",
    "join the meeting",
    "join teams meeting",
)
# Procore endpoints surfaced as availability context.
_PROCORE_CONTEXT_ENDPOINTS = (
    "rfis",
    "rfi-responses",
    "submittals",
    "meetings",
    "meeting-topics",
    "change-events",
    "observations",
    "inspections",
    "rfqs",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RelationshipCandidate(BaseModel):
    """One candidate link (metadata only; never a determination)."""

    candidate_id: str
    message_id: str
    candidate_type: str
    target_source_system: Optional[str] = None
    target_table: Optional[str] = None
    target_key: Optional[str] = None
    match_signal: str
    confidence: float
    review_required: bool
    evidence_redacted: str

    model_config = {"extra": "forbid"}


class RelationshipReport(BaseModel):
    """Outcome of a relationships run (counts + availability; no subjects/addresses)."""

    project_key: Optional[str] = None
    project_number: Optional[str] = None
    lookback_days: int
    received_after: str
    dry_run: bool
    persisted: bool
    messages_considered: int
    candidates_generated: int
    candidates_by_type: dict[str, int]
    review_required_count: int
    file_candidates_existing: int
    procore_available: dict[str, int]
    drive_items_available: int
    calendar_events_available: int
    samples: list[RelationshipCandidate]
    disclaimer: str = "candidates are not determinations; each requires human review"

    model_config = {"extra": "forbid"}


class RelationshipCandidateBuilder:
    """Local-only synthesis of email relationship candidates."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store

    def build(
        self,
        *,
        project_key: Optional[str] = None,
        lookback_days: Optional[int] = None,
        dry_run: bool = True,
        max_messages: int = 2000,
    ) -> RelationshipReport:
        lookback = max(1, min(int(lookback_days or 30), 366))
        descriptors = load_pilot_project_descriptors(project_key)
        descriptor = descriptors[0] if descriptors else None
        procore_project_id = descriptor.procore_project_id if descriptor else None
        project_number = descriptor.project_number if descriptor else None

        received_after = (_utc_now() - timedelta(days=lookback)).replace(microsecond=0).isoformat()

        procore_available = self._procore_availability(project_key)
        drive_items_available = self._count("construction_drive_items")
        calendar_events_available = self._count("calendar_events")
        financials_available = procore_available.get("financial_contracts", 0) > 0

        matches = self._store.list_email_project_matches(
            project_key=project_key, limit=max_messages
        )
        # Dedupe to one (best-confidence) match per message.
        best_by_message: dict[str, dict[str, Any]] = {}
        for m in matches:
            mid = m["message_id"]
            if mid not in best_by_message or m["confidence"] > best_by_message[mid]["confidence"]:
                best_by_message[mid] = m

        candidates: list[RelationshipCandidate] = []
        considered = 0
        file_candidates_existing = 0
        for mid, match in best_by_message.items():
            msg = self._store.get_email_message(mid)
            if msg is None:
                continue
            received = msg.get("received_datetime")
            if received and received < received_after:
                continue
            considered += 1
            candidates.extend(
                self._candidates_for_message(msg, match, procore_project_id, financials_available)
            )
            file_candidates_existing += sum(
                1
                for c in self._store.list_email_relationship_candidates(message_id=mid)
                if c["candidate_type"] in ("sharepoint_drive_item", "onedrive_drive_item")
            )

        if not dry_run:
            for c in candidates:
                self._store.upsert_email_relationship_candidate(
                    candidate_id=c.candidate_id,
                    message_id=c.message_id,
                    candidate_type=c.candidate_type,
                    match_signal=c.match_signal,
                    confidence=c.confidence,
                    project_key=project_key,
                    target_source_system=c.target_source_system,
                    target_table=c.target_table,
                    target_key=c.target_key,
                    review_required=c.review_required,
                    evidence_redacted=c.evidence_redacted,
                )

        by_type: dict[str, int] = {}
        for c in candidates:
            by_type[c.candidate_type] = by_type.get(c.candidate_type, 0) + 1
        review_count = sum(1 for c in candidates if c.review_required)

        if not dry_run:
            self._store.insert_email_processing_receipt(
                receipt_id=f"{uuid.uuid4()}:relationships",
                operation="relationship_candidates",
                status="ok",
                project_key=project_key,
                detail={
                    "messages_considered": considered,
                    "candidates_generated": len(candidates),
                    "by_type": by_type,
                },
            )

        return RelationshipReport(
            project_key=project_key,
            project_number=project_number,
            lookback_days=lookback,
            received_after=received_after,
            dry_run=dry_run,
            persisted=not dry_run,
            messages_considered=considered,
            candidates_generated=len(candidates),
            candidates_by_type=by_type,
            review_required_count=review_count,
            file_candidates_existing=file_candidates_existing,
            procore_available=procore_available,
            drive_items_available=drive_items_available,
            calendar_events_available=calendar_events_available,
            samples=candidates[:10],
        )

    # --- candidate generation -----------------------------------------------

    def _candidates_for_message(
        self,
        msg: dict[str, Any],
        match: dict[str, Any],
        procore_project_id: Optional[str],
        financials_available: bool,
    ) -> list[RelationshipCandidate]:
        mid = msg["message_id"]
        project_key = match.get("project_key")
        preview = (msg.get("body_preview_excerpt_redacted") or "").lower()
        sender_domain = (msg.get("sender_domain") or "").lower()
        out: list[RelationshipCandidate] = []

        # 1. project identity (always, from the stored match)
        conf = float(match.get("confidence") or 0.0)
        out.append(
            self._cand(
                mid,
                "project",
                "hb_construction",
                "construction_project_identity",
                project_key,
                "project_match",
                conf,
                conf < _ACCEPT_THRESHOLD,
                f"possible relationship to project {project_key}",
            )
        )

        is_procore = any(
            sender_domain == d or sender_domain.endswith("." + d) for d in _PROCORE_DOMAINS
        )

        # 2. procore control (procore-notification sender + control keyword)
        if is_procore:
            ctype = _first_keyword(preview, _PROCORE_CONTROL_KEYWORDS) or "procore_rfi"
            out.append(
                self._cand(
                    mid,
                    ctype,
                    "procore",
                    "procore_live_records",
                    procore_project_id,
                    "procore_notification",
                    0.85,
                    False,
                    f"possible {ctype.replace('procore_', '').replace('_', ' ')} relationship (procore notification)",
                )
            )

        # 3. procore financial (financial keyword + financials available)
        if financials_available:
            ftype = _first_keyword(preview, _PROCORE_FINANCIAL_KEYWORDS)
            if ftype:
                out.append(
                    self._cand(
                        mid,
                        ftype,
                        "procore",
                        "procore_financial_contracts",
                        procore_project_id,
                        "financial_keyword_in_preview",
                        0.60,
                        True,
                        f"possible {ftype.replace('procore_', '').replace('_', ' ')} relationship (financial)",
                    )
                )

        # 4. calendar meeting (outlook meeting-email pattern)
        if any(p in preview for p in _MEETING_PATTERNS):
            out.append(
                self._cand(
                    mid,
                    "calendar_event",
                    "microsoft-graph",
                    "calendar_events",
                    hash_value(msg.get("conversation_id") or mid),
                    "meeting_email_pattern",
                    0.60,
                    False,
                    "possible calendar meeting relationship",
                )
            )

        # 5. sensitive non-financial topic in preview -> mark review on the project candidate's evidence
        category, _level = classify_text_sensitivity(preview)
        if category and not out[0].review_required:
            out[0] = out[0].model_copy(
                update={
                    "review_required": True,
                    "evidence_redacted": out[0].evidence_redacted
                    + f"; sensitive topic: {category}",
                }
            )

        return out

    @staticmethod
    def _cand(
        message_id: str,
        candidate_type: str,
        target_source_system: str,
        target_table: str,
        target_key: Optional[str],
        match_signal: str,
        confidence: float,
        review_required: bool,
        evidence_redacted: str,
    ) -> RelationshipCandidate:
        cid = (
            hash_value(f"{message_id}|{candidate_type}|{target_table}|{target_key}|{match_signal}")
            or message_id
        )
        return RelationshipCandidate(
            candidate_id=cid,
            message_id=message_id,
            candidate_type=candidate_type,
            target_source_system=target_source_system,
            target_table=target_table,
            target_key=target_key,
            match_signal=match_signal,
            confidence=confidence,
            review_required=review_required,
            evidence_redacted=evidence_redacted,
        )

    # --- availability context (read-only counts) ----------------------------

    def _procore_availability(self, project_key: Optional[str]) -> dict[str, int]:
        avail: dict[str, int] = {}
        if not project_key:
            return avail
        conn = get_connection(self._store._db_path)  # noqa: SLF001 - read-only count
        for endpoint in _PROCORE_CONTEXT_ENDPOINTS:
            avail[endpoint] = self._count_where(
                conn,
                "procore_live_records",
                "project_key = ? AND endpoint_id = ?",
                (project_key, endpoint),
            )
        avail["financial_contracts"] = self._count_where(
            conn, "procore_financial_contracts", "project_key = ?", (project_key,)
        )
        return {k: v for k, v in avail.items() if v > 0}

    def _count(self, table: str) -> int:
        conn = get_connection(self._store._db_path)  # noqa: SLF001
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except Exception:
            return 0

    @staticmethod
    def _count_where(conn: Any, table: str, where: str, params: tuple) -> int:
        try:
            return int(
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0]
            )
        except Exception:
            return 0


def _first_keyword(text: str, mapping: tuple[tuple[str, str], ...]) -> Optional[str]:
    for keyword, value in mapping:
        if keyword in text:
            return value
    return None
