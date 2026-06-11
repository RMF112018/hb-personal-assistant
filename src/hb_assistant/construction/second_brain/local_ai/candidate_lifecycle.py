"""Phase 10 V50 — cross-family candidate lifecycle service + state contract.

An append-only overlay (``candidate_lifecycle_events`` / ``candidate_merge_links`` /
``candidate_suppression_rules``, migration V50) that EXTENDS — never replaces — the V41/V43
per-family review status. For task/commitment candidates the existing ``candidate_review`` service
remains canonical for ``review_status``; the lifecycle overlay adds cross-family states (merge,
group suppression, close/reopen) that no single per-family table can express. The unified read
model consumes both, so there is no dual truth.

Everything here is local-DB only, idempotent, and raw-safe: only redacted titles/notes, reason
codes, hashes, ids, and canonical states move. No external writeback, no raw bodies/URLs/tokens.
See ``references/lifecycle_state_contract.md`` for the canonical states + precedence.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from . import candidate_review
from .candidate_lifecycle_duplicates import duplicate_group_key
from .schema import PHASE_10_GUARD_COLUMNS

# --- subject taxonomy ------------------------------------------------------

SUBJECT_TYPES: tuple[str, ...] = (
    "task_candidate",
    "commitment_candidate",
    "daily_brief_action",
    "accepted_task",
    "accepted_commitment",
    "follow_up_watch",
)

#: Subject types that map onto an existing task/commitment review_status (canonical there).
_REVIEW_SUBJECTS: frozenset[str] = frozenset({"task_candidate", "commitment_candidate"})

#: subject_type -> candidate_type used for candidate_source_refs lookups (None = inherited).
_SUBJECT_SOURCE_TYPE: dict[str, Optional[str]] = {
    "task_candidate": "task",
    "commitment_candidate": "commitment",
    "daily_brief_action": "daily_brief_action",
    "accepted_task": "task",
    "accepted_commitment": "commitment",
    "follow_up_watch": None,
}

#: Families that REQUIRE source refs to be accepted/promoted (the source-ref gate).
SOURCE_REQUIRED_SUBJECTS: frozenset[str] = frozenset(
    {"task_candidate", "commitment_candidate", "daily_brief_action"}
)

#: Families for which a null project_key means "needs project review" (new candidate families).
PROJECT_LIKE_SUBJECTS: frozenset[str] = frozenset(
    {"task_candidate", "commitment_candidate", "daily_brief_action"}
)

#: The three append-only V50 tables (guard-sum must stay 0).
LIFECYCLE_TABLES: tuple[str, ...] = (
    "candidate_lifecycle_events",
    "candidate_merge_links",
    "candidate_suppression_rules",
)

# --- canonical states + precedence ----------------------------------------

STATE_SOURCE_MISSING = "source_missing"
STATE_MERGED = "merged"
STATE_SUPPRESSED = "suppressed"
STATE_REJECTED = "rejected"
STATE_SNOOZED = "snoozed"
STATE_CLOSED = "closed"
STATE_PROJECT_REVIEW_REQUIRED = "project_review_required"
STATE_NEEDS_REVIEW = "needs_review"
STATE_STALE = "stale"
STATE_ACCEPTED = "accepted"
STATE_NEW = "new"

CANONICAL_STATES: tuple[str, ...] = (
    STATE_NEW,
    STATE_NEEDS_REVIEW,
    STATE_ACCEPTED,
    STATE_REJECTED,
    STATE_SNOOZED,
    STATE_MERGED,
    STATE_CLOSED,
    STATE_SUPPRESSED,
    STATE_STALE,
    STATE_SOURCE_MISSING,
    STATE_PROJECT_REVIEW_REQUIRED,
)

#: Lower index = higher precedence when several states apply (lifecycle_state_contract.md).
_PRECEDENCE: tuple[str, ...] = (
    STATE_SOURCE_MISSING,
    STATE_MERGED,
    STATE_SUPPRESSED,
    STATE_REJECTED,
    STATE_SNOOZED,
    STATE_CLOSED,
    STATE_PROJECT_REVIEW_REQUIRED,
    STATE_NEEDS_REVIEW,
    STATE_STALE,
    STATE_ACCEPTED,
    STATE_NEW,
)
_PRECEDENCE_RANK: dict[str, int] = {s: i for i, s in enumerate(_PRECEDENCE)}

#: The default review queue shows only to-review states (accepted items are handled elsewhere;
#: the daily brief surfaces accepted/stale/waiting separately). Returned snooze maps to
#: needs_review, so it is included here implicitly.
REVIEW_QUEUE_DEFAULT_STATES: frozenset[str] = frozenset(
    {STATE_NEW, STATE_NEEDS_REVIEW, STATE_PROJECT_REVIEW_REQUIRED, STATE_STALE, STATE_SOURCE_MISSING}
)
#: Hidden from the normal daily brief (future snooze is computed separately).
HIDDEN_FROM_BRIEF_STATES: frozenset[str] = frozenset(
    {STATE_REJECTED, STATE_SUPPRESSED, STATE_MERGED, STATE_CLOSED, STATE_SNOOZED}
)
#: Operator still has work to do on these.
ACTIONABLE_STATES: frozenset[str] = frozenset(
    {STATE_NEW, STATE_NEEDS_REVIEW, STATE_PROJECT_REVIEW_REQUIRED, STATE_STALE}
)

# --- event types -----------------------------------------------------------

EVENT_ACCEPT = "accept"
EVENT_REJECT = "reject"
EVENT_SNOOZE = "snooze"
EVENT_MERGE = "merge"
EVENT_CLOSE = "close"
EVENT_REOPEN = "reopen"
EVENT_MARK_DUPLICATE = "mark_duplicate"
EVENT_SUPPRESS = "suppress"

_NOTE_MAX = 240
_STALE_AFTER_DAYS = 14

# --- redaction helpers (operator notes only; DB titles are already redacted) ---

_URL_RE = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|io|gov|edu)/\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_TOKEN_RE = re.compile(r"\b(bearer|token|secret|authorization)\s*[:=]?\s*\S+", re.IGNORECASE)
_HTML_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_WS_RE = re.compile(r"\s+")


def scrub_note(text: Optional[str], *, max_chars: int = _NOTE_MAX) -> Optional[str]:
    """Scrub URLs/emails/token-looking strings/HTML tags from free text, then bound it (raw-safe).

    Used for operator notes AND as a defensive re-scrub of already-redacted DB text at the read-model
    boundary, so no raw URL/token/email/HTML can reach a lifecycle output even if an upstream field
    was not fully redacted.
    """
    if not text:
        return None
    t = _URL_RE.sub("[link]", str(text))
    t = _EMAIL_RE.sub("[addr]", t)
    t = _TOKEN_RE.sub("[redacted]", t)
    t = _HTML_RE.sub("", t)
    t = _WS_RE.sub(" ", t).strip()
    return t[:max_chars] or None


def utc_now() -> str:
    """Current UTC timestamp (ISO-8601)."""
    return datetime.now(timezone.utc).isoformat()


_utc_now = utc_now  # internal alias


def _parse(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_future(ts: Optional[str], now_utc: str) -> bool:
    """True when ``ts`` is strictly after ``now_utc`` (both ISO-8601)."""
    a, b = _parse(ts), _parse(now_utc)
    return bool(a and b and a > b)


_is_future = is_future  # internal alias


# --- bucketing -------------------------------------------------------------

def age_bucket(created_utc: Optional[str], now_utc: str) -> str:
    """today | 1_3d | 4_7d | 8_14d | 15d_plus | unknown (age since created)."""
    c, n = _parse(created_utc), _parse(now_utc)
    if not c or not n:
        return "unknown"
    days = (n - c).days
    if days <= 0:
        return "today"
    if days <= 3:
        return "1_3d"
    if days <= 7:
        return "4_7d"
    if days <= 14:
        return "8_14d"
    return "15d_plus"


def due_bucket(due_at_utc: Optional[str], now_utc: str) -> str:
    """overdue | today | next_3d | next_7d | future | none | unknown (time to due)."""
    if not due_at_utc:
        return "none"
    d, n = _parse(due_at_utc), _parse(now_utc)
    if not d or not n:
        return "unknown"
    days = (d - n).days
    if d < n:
        return "overdue"
    if days <= 0:
        return "today"
    if days <= 3:
        return "next_3d"
    if days <= 7:
        return "next_7d"
    return "future"


# --- per-family base-state mappers ----------------------------------------

def review_status_to_state(review_status: Optional[str], confidence: Optional[float]) -> str:
    """Map a task/commitment review_status to a canonical disposition state."""
    rs = (review_status or "pending").lower()
    if rs == "accepted":
        return STATE_ACCEPTED
    if rs == "rejected":
        return STATE_REJECTED
    if rs == "snoozed":
        return STATE_SNOOZED
    if rs == "suppressed":
        return STATE_SUPPRESSED
    # pending: low-confidence rows are flagged for explicit review.
    if confidence is not None and confidence < 0.6:
        return STATE_NEEDS_REVIEW
    return STATE_NEW


def accepted_status_to_state(
    status: Optional[str], completed_utc: Optional[str], accepted_utc: Optional[str], now_utc: str
) -> str:
    """Map an accepted task/commitment row to a canonical state (closed / stale / accepted)."""
    st = (status or "open").lower()
    if completed_utc or st in ("completed", "done", "closed", "resolved"):
        return STATE_CLOSED
    a, n = _parse(accepted_utc), _parse(now_utc)
    if a and n and (n - a).days >= _STALE_AFTER_DAYS:
        return STATE_STALE
    return STATE_ACCEPTED


def watch_status_to_state(watch_status: Optional[str]) -> str:
    """Map a follow-up watch status to a canonical state."""
    ws = (watch_status or "").lower()
    if ws == "closed":
        return STATE_CLOSED
    if ws == "stale":
        return STATE_STALE
    if ws in ("needs_review", "contradictory", "insufficient_evidence"):
        return STATE_NEEDS_REVIEW
    return STATE_ACCEPTED


def resolve_state(
    disposition_state: str,
    *,
    source_missing: bool = False,
    project_review_required: bool = False,
    snoozed_future: bool = False,
    suppressed: bool = False,
    merged: bool = False,
) -> str:
    """Pick the highest-precedence applicable canonical state."""
    applicable: set[str] = {disposition_state}
    if source_missing:
        applicable.add(STATE_SOURCE_MISSING)
    if project_review_required:
        applicable.add(STATE_PROJECT_REVIEW_REQUIRED)
    if snoozed_future:
        applicable.add(STATE_SNOOZED)
    if suppressed:
        applicable.add(STATE_SUPPRESSED)
    if merged:
        applicable.add(STATE_MERGED)
    return min(applicable, key=lambda s: _PRECEDENCE_RANK.get(s, len(_PRECEDENCE)))


# --- subject context (single source of truth for ops + read model) --------

def source_ref_candidate_id(subject_type: str, subject_id: str) -> Optional[tuple[str, str]]:
    """Return (candidate_type, candidate_id) for source-ref lookup, or None if not applicable.

    Accepted/watch subjects inherit their candidate's refs: accepted ids are
    ``acc-task:{cid}`` / ``acc-commit:{cid}`` so the candidate id is recoverable.
    """
    ctype = _SUBJECT_SOURCE_TYPE.get(subject_type)
    if ctype is None:
        return None
    if subject_type in ("accepted_task", "accepted_commitment"):
        cid = subject_id.split(":", 1)[1] if ":" in subject_id else subject_id
        return ctype, cid
    return ctype, subject_id


def source_ref_count(store: Any, subject_type: str, subject_id: str) -> Optional[int]:
    """Count source refs for a subject. None means 'not applicable' (e.g. follow_up_watch)."""
    resolved = source_ref_candidate_id(subject_type, subject_id)
    if resolved is None:
        return None
    ctype, cid = resolved
    return len(store.list_candidate_source_refs(candidate_type=ctype, candidate_id=cid, limit=200))


def subject_context(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve the full lifecycle context for one subject (used by ops and the read model).

    Returns the resolved ``lifecycle_state`` plus the inputs that produced it. Reads the
    per-family base state, the latest lifecycle overlay event, active suppression rules, and
    merge links — never any raw content.
    """
    now = now_utc or _utc_now()
    overlay = store.latest_lifecycle_states().get((subject_type, subject_id))
    overlay_state = overlay.get("new_state") if overlay else None
    effective_until = overlay.get("effective_until_utc") if overlay else None

    refs = source_ref_count(store, subject_type, subject_id)
    source_missing = subject_type in SOURCE_REQUIRED_SUBJECTS and (refs == 0)

    # disposition state: overlay wins over base when present, else per-family base.
    base_state = _base_state(store, subject_type, subject_id, now)
    disposition = overlay_state or base_state
    snoozed_future = False
    if disposition == STATE_SNOOZED:
        if _is_future(effective_until, now):
            snoozed_future = True
        else:
            # a returned snooze falls back to needs_review (operator should act)
            disposition = STATE_NEEDS_REVIEW

    project_key = _project_key(store, subject_type, subject_id)
    project_review_required = (
        subject_type in PROJECT_LIKE_SUBJECTS and not project_key and not source_missing
    )

    suppressed = _is_suppressed(store, subject_type, subject_id)
    merged = _is_merged_source(store, subject_type, subject_id)

    state = resolve_state(
        disposition,
        source_missing=source_missing,
        project_review_required=project_review_required,
        snoozed_future=snoozed_future,
        suppressed=suppressed,
        merged=merged,
    )
    return {
        "lifecycle_state": state,
        "base_state": base_state,
        "overlay_state": overlay_state,
        "source_ref_count": refs,
        "source_missing": source_missing,
        "project_key": project_key,
        "project_review_required": project_review_required,
        "snoozed_future": snoozed_future,
        "effective_until_utc": effective_until if snoozed_future else None,
        "suppressed": suppressed,
        "merged": merged,
    }


def _row(store: Any, subject_type: str, subject_id: str) -> Optional[dict[str, Any]]:
    if subject_type == "task_candidate":
        return store.get_task_candidate(subject_id)
    if subject_type == "commitment_candidate":
        return store.get_commitment_candidate(subject_id)
    if subject_type == "daily_brief_action":
        rows = store.list_daily_brief_action_candidates(limit=100000)
        return next(
            (r for r in rows if r.get("daily_brief_action_candidate_id") == subject_id), None
        )
    if subject_type == "accepted_task":
        rows = store.list_accepted_tasks(limit=100000)
        return next((r for r in rows if r.get("accepted_task_id") == subject_id), None)
    if subject_type == "accepted_commitment":
        rows = store.list_accepted_commitments(limit=100000)
        return next((r for r in rows if r.get("accepted_commitment_id") == subject_id), None)
    if subject_type == "follow_up_watch":
        rows = store.list_follow_up_watch_items(limit=100000)
        return next((r for r in rows if r.get("watch_item_id") == subject_id), None)
    return None


def _base_state(store: Any, subject_type: str, subject_id: str, now_utc: str) -> str:
    row = _row(store, subject_type, subject_id)
    if row is None:
        return STATE_NEW
    if subject_type in _REVIEW_SUBJECTS:
        return review_status_to_state(row.get("review_status"), row.get("confidence"))
    if subject_type in ("accepted_task", "accepted_commitment"):
        return accepted_status_to_state(
            row.get("status"), row.get("completed_utc"), row.get("accepted_utc"), now_utc
        )
    if subject_type == "follow_up_watch":
        return watch_status_to_state(row.get("watch_status"))
    return STATE_NEW  # daily_brief_action default


def _project_key(store: Any, subject_type: str, subject_id: str) -> Optional[str]:
    row = _row(store, subject_type, subject_id)
    return (row or {}).get("project_key")


def _is_suppressed(store: Any, subject_type: str, subject_id: str) -> bool:
    rules = store.list_suppression_rules(active_only=True)
    if not rules:
        return False
    group = _subject_group_key(store, subject_type, subject_id)
    for r in rules:
        if r.get("scope") == "candidate" and (
            r.get("subject_type") == subject_type and r.get("subject_id") == subject_id
        ):
            return True
        if r.get("scope") == "group" and group and r.get("duplicate_group_key") == group:
            return True
    return False


def _is_merged_source(store: Any, subject_type: str, subject_id: str) -> bool:
    for link in store.list_merge_links():
        if link.get("source_subject_type") == subject_type and (
            link.get("source_subject_id") == subject_id
        ):
            return True
    return False


def _subject_group_key(store: Any, subject_type: str, subject_id: str) -> Optional[str]:
    """Compute the duplicate group key for a subject from its safe fields + source refs."""
    row = _row(store, subject_type, subject_id)
    if row is None:
        return None
    resolved = source_ref_candidate_id(subject_type, subject_id)
    refs: list[dict[str, Any]] = []
    if resolved is not None:
        ctype, cid = resolved
        refs = store.list_candidate_source_refs(candidate_type=ctype, candidate_id=cid, limit=200)
    return duplicate_group_key(
        subject_type=subject_type,
        subject_id=subject_id,
        family=row.get("family") or row.get("section"),
        project_key=row.get("project_key"),
        title_redacted=row.get("title_redacted"),
        stable_key=row.get("stable_key"),
        source_refs=refs,
    )


# --- guard-sum proof for the V50 tables ------------------------------------

def lifecycle_guard_sum(store: Any) -> int:
    """Sum of all 13 guard columns across the 3 V50 lifecycle tables (must be 0)."""
    conn = store._db_path  # noqa: SLF001 - store exposes only a path; open read-only below
    import sqlite3

    total = 0
    db = sqlite3.connect(f"file:{conn}?mode=ro", uri=True)
    try:
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        for table in LIFECYCLE_TABLES:
            total += int(db.execute(f"SELECT {expr} FROM {table}").fetchone()[0])
    finally:
        db.close()
    return total


# --- disposition operations (local DB only, idempotent, raw-safe) ---------

def _validate_subject(subject_type: str) -> None:
    if subject_type not in SUBJECT_TYPES:
        raise ValueError(f"unknown subject_type: {subject_type!r}")


def _emit_event(
    store: Any,
    *,
    idempotency_key: str,
    subject_type: str,
    subject_id: str,
    event_type: str,
    new_state: Optional[str],
    prior_state: Optional[str],
    reason_code: Optional[str] = None,
    reason_redacted: Optional[str] = None,
    effective_until_utc: Optional[str] = None,
    target_subject_type: Optional[str] = None,
    target_subject_id: Optional[str] = None,
    duplicate_group_key_value: Optional[str] = None,
    reviewer: str = "operator",
) -> tuple[str, bool]:
    return store.insert_lifecycle_event(
        idempotency_key=idempotency_key,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        new_state=new_state,
        prior_state=prior_state,
        reason_code=reason_code,
        reason_redacted=reason_redacted,
        effective_until_utc=effective_until_utc,
        target_subject_type=target_subject_type,
        target_subject_id=target_subject_id,
        duplicate_group_key=duplicate_group_key_value,
        reviewer_ref=reviewer,
    )


def _result(
    *,
    op: str,
    subject_type: str,
    subject_id: str,
    status: str,
    prior_state: str,
    new_state: Optional[str],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "ok": status not in ("not_found", "invalid"),
        "op": op,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "status": status,
        "prior_state": prior_state,
        "new_state": new_state,
        **extra,
    }


def accept(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    reviewer: str = "operator",
    note: Optional[str] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Accept a candidate. Source-ref gated: a source-missing actionable subject is blocked."""
    _validate_subject(subject_type)
    ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id, now_utc=now_utc)
    prior = ctx["lifecycle_state"]
    if _row(store, subject_type, subject_id) is None:
        return _result(op="accept", subject_type=subject_type, subject_id=subject_id,
                       status="not_found", prior_state=prior, new_state=None)
    if ctx["source_missing"]:
        return _result(op="accept", subject_type=subject_type, subject_id=subject_id,
                       status="accept_blocked_source_missing", prior_state=prior, new_state=prior,
                       source_ref_count=ctx["source_ref_count"])
    if prior == STATE_ACCEPTED:
        return _result(op="accept", subject_type=subject_type, subject_id=subject_id,
                       status="already_accepted", prior_state=prior, new_state=STATE_ACCEPTED)
    note_red = scrub_note(note)
    # Task/commitment: keep review_status canonical via the existing service.
    if subject_type in _REVIEW_SUBJECTS:
        ctype = "task" if subject_type == "task_candidate" else "commitment"
        candidate_review.accept_candidate(
            store, candidate_id=subject_id, candidate_type=ctype, reviewer=reviewer, note=note_red
        )
    key = f"{subject_type}:{subject_id}:accept:{prior}"
    _, inserted = _emit_event(
        store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
        event_type=EVENT_ACCEPT, new_state=STATE_ACCEPTED, prior_state=prior,
        reason_redacted=note_red, reviewer=reviewer,
    )
    return _result(op="accept", subject_type=subject_type, subject_id=subject_id,
                   status="accepted" if inserted else "already_accepted",
                   prior_state=prior, new_state=STATE_ACCEPTED)


def reject(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    reason: str,
    reviewer: str = "operator",
    note: Optional[str] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Reject a candidate with a reason code (hidden from normal views)."""
    _validate_subject(subject_type)
    ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id, now_utc=now_utc)
    prior = ctx["lifecycle_state"]
    if _row(store, subject_type, subject_id) is None:
        return _result(op="reject", subject_type=subject_type, subject_id=subject_id,
                       status="not_found", prior_state=prior, new_state=None)
    if prior == STATE_REJECTED:
        return _result(op="reject", subject_type=subject_type, subject_id=subject_id,
                       status="already_rejected", prior_state=prior, new_state=STATE_REJECTED,
                       reason_code=reason)
    note_red = scrub_note(note)
    if subject_type in _REVIEW_SUBJECTS:
        ctype = "task" if subject_type == "task_candidate" else "commitment"
        candidate_review.reject_candidate(
            store, candidate_id=subject_id, candidate_type=ctype, reviewer=reviewer, note=note_red
        )
    key = f"{subject_type}:{subject_id}:reject:{prior}:{reason}"
    _, inserted = _emit_event(
        store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
        event_type=EVENT_REJECT, new_state=STATE_REJECTED, prior_state=prior,
        reason_code=reason, reason_redacted=note_red, reviewer=reviewer,
    )
    return _result(op="reject", subject_type=subject_type, subject_id=subject_id,
                   status="rejected" if inserted else "already_rejected",
                   prior_state=prior, new_state=STATE_REJECTED, reason_code=reason)


def snooze(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    until: str,
    reviewer: str = "operator",
    reason: Optional[str] = None,
    note: Optional[str] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Snooze a subject until an ISO date/timestamp (hidden until the return date)."""
    _validate_subject(subject_type)
    if _parse(until) is None:
        return _result(op="snooze", subject_type=subject_type, subject_id=subject_id,
                       status="invalid", prior_state="unknown", new_state=None,
                       error="invalid until (expected ISO-8601)")
    ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id, now_utc=now_utc)
    prior = ctx["lifecycle_state"]
    if _row(store, subject_type, subject_id) is None:
        return _result(op="snooze", subject_type=subject_type, subject_id=subject_id,
                       status="not_found", prior_state=prior, new_state=None)
    note_red = scrub_note(note)
    if subject_type in _REVIEW_SUBJECTS:
        ctype = "task" if subject_type == "task_candidate" else "commitment"
        candidate_review.snooze_candidate(
            store, candidate_id=subject_id, candidate_type=ctype, until=until,
            reviewer=reviewer, note=note_red,
        )
    key = f"{subject_type}:{subject_id}:snooze:{until}"
    _, inserted = _emit_event(
        store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
        event_type=EVENT_SNOOZE, new_state=STATE_SNOOZED, prior_state=prior,
        reason_code=reason, reason_redacted=note_red, effective_until_utc=until, reviewer=reviewer,
    )
    return _result(op="snooze", subject_type=subject_type, subject_id=subject_id,
                   status="snoozed" if inserted else "already_snoozed",
                   prior_state=prior, new_state=STATE_SNOOZED, effective_until_utc=until)


def close(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    reason: str = "completed",
    reviewer: str = "operator",
    note: Optional[str] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Close a subject as handled/completed/resolved."""
    _validate_subject(subject_type)
    ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id, now_utc=now_utc)
    prior = ctx["lifecycle_state"]
    if _row(store, subject_type, subject_id) is None:
        return _result(op="close", subject_type=subject_type, subject_id=subject_id,
                       status="not_found", prior_state=prior, new_state=None)
    if prior == STATE_CLOSED:
        return _result(op="close", subject_type=subject_type, subject_id=subject_id,
                       status="already_closed", prior_state=prior, new_state=STATE_CLOSED)
    key = f"{subject_type}:{subject_id}:close:{prior}:{reason}"
    _, inserted = _emit_event(
        store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
        event_type=EVENT_CLOSE, new_state=STATE_CLOSED, prior_state=prior,
        reason_code=reason, reason_redacted=scrub_note(note), reviewer=reviewer,
    )
    return _result(op="close", subject_type=subject_type, subject_id=subject_id,
                   status="closed" if inserted else "already_closed",
                   prior_state=prior, new_state=STATE_CLOSED, reason_code=reason)


def reopen(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    reason: str = "operator_reopened",
    reviewer: str = "operator",
    note: Optional[str] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Reopen a closed/rejected subject back into the review queue (needs_review)."""
    _validate_subject(subject_type)
    ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id, now_utc=now_utc)
    prior = ctx["lifecycle_state"]
    if _row(store, subject_type, subject_id) is None:
        return _result(op="reopen", subject_type=subject_type, subject_id=subject_id,
                       status="not_found", prior_state=prior, new_state=None)
    if prior in ACTIONABLE_STATES or prior == STATE_NEW:
        return _result(op="reopen", subject_type=subject_type, subject_id=subject_id,
                       status="already_open", prior_state=prior, new_state=prior)
    key = f"{subject_type}:{subject_id}:reopen:{prior}:{reason}"
    _, inserted = _emit_event(
        store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
        event_type=EVENT_REOPEN, new_state=STATE_NEEDS_REVIEW, prior_state=prior,
        reason_code=reason, reason_redacted=scrub_note(note), reviewer=reviewer,
    )
    return _result(op="reopen", subject_type=subject_type, subject_id=subject_id,
                   status="reopened" if inserted else "already_open",
                   prior_state=prior, new_state=STATE_NEEDS_REVIEW, reason_code=reason)


def merge(
    store: Any,
    *,
    source_subject_type: str,
    source_subject_id: str,
    target_subject_type: str,
    target_subject_id: str,
    reason: str = "manual_duplicate",
    reviewer: str = "operator",
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Merge a source subject into a canonical target. Source becomes ``merged``; refs preserved."""
    _validate_subject(source_subject_type)
    _validate_subject(target_subject_type)
    if (source_subject_type, source_subject_id) == (target_subject_type, target_subject_id):
        return _result(op="merge", subject_type=source_subject_type, subject_id=source_subject_id,
                       status="invalid", prior_state="unknown", new_state=None,
                       error="cannot merge a subject into itself")
    if _row(store, source_subject_type, source_subject_id) is None:
        return _result(op="merge", subject_type=source_subject_type, subject_id=source_subject_id,
                       status="not_found", prior_state="unknown", new_state=None)
    ctx = subject_context(
        store, subject_type=source_subject_type, subject_id=source_subject_id, now_utc=now_utc
    )
    prior = ctx["lifecycle_state"]
    group = _subject_group_key(store, source_subject_type, source_subject_id)
    link_key = (
        f"merge:{source_subject_type}:{source_subject_id}->"
        f"{target_subject_type}:{target_subject_id}"
    )
    _, link_inserted = store.upsert_merge_link(
        idempotency_key=link_key,
        source_subject_type=source_subject_type,
        source_subject_id=source_subject_id,
        target_subject_type=target_subject_type,
        target_subject_id=target_subject_id,
        merge_reason_code=reason,
        duplicate_group_key=group,
        reviewer_ref=reviewer,
    )
    _, ev_inserted = _emit_event(
        store, idempotency_key=link_key + ":event", subject_type=source_subject_type,
        subject_id=source_subject_id, event_type=EVENT_MERGE, new_state=STATE_MERGED,
        prior_state=prior, reason_code=reason, target_subject_type=target_subject_type,
        target_subject_id=target_subject_id, duplicate_group_key_value=group, reviewer=reviewer,
    )
    return _result(op="merge", subject_type=source_subject_type, subject_id=source_subject_id,
                   status="merged" if (link_inserted or ev_inserted) else "already_merged",
                   prior_state=prior, new_state=STATE_MERGED,
                   target_subject_type=target_subject_type, target_subject_id=target_subject_id,
                   duplicate_group_key=group, reason_code=reason)


def suppress(
    store: Any,
    *,
    scope: str,
    reason: str,
    subject_type: Optional[str] = None,
    subject_id: Optional[str] = None,
    duplicate_group_key_value: Optional[str] = None,
    reviewer: str = "operator",
    note: Optional[str] = None,
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Suppress a recurring false positive by candidate or group (never deletes the candidate)."""
    if scope not in ("candidate", "group"):
        return _result(op="suppress", subject_type=subject_type or "?", subject_id=subject_id or "?",
                       status="invalid", prior_state="unknown", new_state=None,
                       error="scope must be 'candidate' or 'group'")
    note_red = scrub_note(note)
    if scope == "candidate":
        if not subject_type or not subject_id:
            return _result(op="suppress", subject_type=subject_type or "?",
                           subject_id=subject_id or "?", status="invalid",
                           prior_state="unknown", new_state=None,
                           error="candidate scope requires subject_type + subject_id")
        _validate_subject(subject_type)
        if _row(store, subject_type, subject_id) is None:
            return _result(op="suppress", subject_type=subject_type, subject_id=subject_id,
                           status="not_found", prior_state="unknown", new_state=None)
        group = duplicate_group_key_value or _subject_group_key(store, subject_type, subject_id)
        ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id,
                              now_utc=now_utc)
        prior = ctx["lifecycle_state"]
        rule_key = f"suppress:candidate:{subject_type}:{subject_id}:{reason}"
        _, rule_inserted = store.upsert_suppression_rule(
            idempotency_key=rule_key, scope="candidate", reason_code=reason,
            subject_type=subject_type, subject_id=subject_id, duplicate_group_key=group,
            reason_redacted=note_red, active=True,
        )
        _, ev_inserted = _emit_event(
            store, idempotency_key=rule_key + ":event", subject_type=subject_type,
            subject_id=subject_id, event_type=EVENT_SUPPRESS, new_state=STATE_SUPPRESSED,
            prior_state=prior, reason_code=reason, reason_redacted=note_red,
            duplicate_group_key_value=group, reviewer=reviewer,
        )
        return _result(op="suppress", subject_type=subject_type, subject_id=subject_id,
                       status="suppressed" if (rule_inserted or ev_inserted) else "already_suppressed",
                       prior_state=prior, new_state=STATE_SUPPRESSED, scope="candidate",
                       reason_code=reason, duplicate_group_key=group)
    # group scope
    if not duplicate_group_key_value:
        return _result(op="suppress", subject_type="group", subject_id=duplicate_group_key_value or "?",
                       status="invalid", prior_state="unknown", new_state=None,
                       error="group scope requires duplicate_group_key")
    rule_key = f"suppress:group:{duplicate_group_key_value}:{reason}"
    _, rule_inserted = store.upsert_suppression_rule(
        idempotency_key=rule_key, scope="group", reason_code=reason,
        duplicate_group_key=duplicate_group_key_value, reason_redacted=note_red, active=True,
    )
    return _result(op="suppress", subject_type="group", subject_id=duplicate_group_key_value,
                   status="suppressed" if rule_inserted else "already_suppressed",
                   prior_state="n/a", new_state=STATE_SUPPRESSED, scope="group",
                   reason_code=reason, duplicate_group_key=duplicate_group_key_value)


# --- promotion to accepted actions (explicit, idempotent, source-ref gated) ---

def promote(
    store: Any,
    *,
    subject_type: str,
    subject_id: str,
    reviewer: str = "operator",
    now_utc: Optional[str] = None,
) -> dict[str, Any]:
    """Promote a candidate into an accepted action. Explicit + idempotent + source-ref gated.

    Returns a ``references/promotion_contract.md`` status code. Preserves the deterministic
    accepted id (``acc-task:{cid}`` / ``acc-commit:{cid}``), the project key, and source-ref
    traceability (accepted rows reference the candidate id; refs stay under that candidate id).
    Never copies raw content. daily-brief-only candidates have no domain mapping → lifecycle-only
    acceptance with ``promotion_skipped_unmapped``.
    """
    _validate_subject(subject_type)
    row = _row(store, subject_type, subject_id)
    base = {"op": "promote", "subject_type": subject_type, "subject_id": subject_id}
    if row is None:
        return {**base, "ok": False, "status": "promotion_not_applicable",
                "promotion_status": "promotion_not_applicable", "error": "not_found"}
    if subject_type in ("accepted_task", "accepted_commitment", "follow_up_watch"):
        return {**base, "ok": True, "status": "promotion_not_applicable",
                "promotion_status": "promotion_not_applicable"}

    refs = source_ref_count(store, subject_type, subject_id)
    if subject_type in SOURCE_REQUIRED_SUBJECTS and refs == 0:
        return {**base, "ok": False, "status": "promotion_blocked_source_missing",
                "promotion_status": "promotion_blocked_source_missing", "source_ref_count": refs}

    if subject_type == "daily_brief_action":
        # No domain mapping for a daily-brief-only candidate: accept it in the lifecycle overlay
        # only, recording that promotion to a domain accepted row was skipped.
        ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id,
                              now_utc=now_utc)
        key = f"{subject_type}:{subject_id}:accept:{ctx['lifecycle_state']}"
        _emit_event(store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
                    event_type=EVENT_ACCEPT, new_state=STATE_ACCEPTED,
                    prior_state=ctx["lifecycle_state"], reason_code="promotion_skipped_unmapped",
                    reviewer=reviewer)
        return {**base, "ok": True, "status": "promotion_skipped_unmapped",
                "promotion_status": "promotion_skipped_unmapped", "project_key": row.get("project_key")}

    # task / commitment candidate → accepted_tasks / accepted_commitments (idempotent insert).
    title = str(row.get("title_redacted") or "")
    waiting = str(row.get("waiting_state") or "unknown")
    safety = str(row.get("safety_category") or "normal")
    project = row.get("project_key")
    if subject_type == "task_candidate":
        inserted = store.insert_accepted_task(
            candidate_id=subject_id, title_redacted=title, waiting_state=waiting,
            safety_category=safety, project_key=project, due_at_utc=row.get("due_at_utc"),
        )
        accepted_id = store.accepted_task_id_for(subject_id)
    else:
        inserted = store.insert_accepted_commitment(
            candidate_id=subject_id, title_redacted=title, waiting_state=waiting,
            safety_category=safety, project_key=project, due_at_utc=row.get("due_at_utc"),
        )
        accepted_id = store.accepted_commitment_id_for(subject_id)

    ctype = "task" if subject_type == "task_candidate" else "commitment"
    # Keep review_status canonical + record acceptance in the lifecycle overlay.
    candidate_review.accept_candidate(
        store, candidate_id=subject_id, candidate_type=ctype, reviewer=reviewer
    )
    ctx = subject_context(store, subject_type=subject_type, subject_id=subject_id, now_utc=now_utc)
    key = f"{subject_type}:{subject_id}:promote"
    _emit_event(store, idempotency_key=key, subject_type=subject_type, subject_id=subject_id,
                event_type=EVENT_ACCEPT, new_state=STATE_ACCEPTED, prior_state=ctx["base_state"],
                reason_code="promoted", reviewer=reviewer)
    return {**base, "ok": True,
            "status": "promoted" if inserted else "already_promoted",
            "promotion_status": "promoted" if inserted else "already_promoted",
            "accepted_id": accepted_id, "project_key": project,
            "project_resolution_status": "resolved" if project else "project_review_required",
            "source_ref_count": refs}
