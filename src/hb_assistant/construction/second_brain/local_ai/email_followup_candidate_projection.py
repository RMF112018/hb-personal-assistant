"""Phase 10 — deterministic email follow-up candidate projection (structured-first, raw-safe).

Converts the V49 *structured* email message/thread substrate
(``email_raw_message_structured`` / ``email_raw_thread_structured``) into source-linked,
project-aware daily-brief follow-up / task / commitment candidates. This is the slice that
replaces the email/follow-up *data-gap card* (see ``email_followup_readiness``) with real
content once eligible candidates exist, and preserves the card honestly when none are produced.

Design guarantees (enforced here + by tests):

- **Structured-first, metadata-only.** Only safe structured fields are read — bounded subject,
  sender name/address/domain, sent/received timestamps, recipient/attachment/message/participant
  counts, body *availability flags* (never body text), ``project_key``, ``thread_ref``,
  ``message_id_hash``, ``source_quality``. Raw bodies are **never** loaded in this pass
  (``raw_access_used`` is always ``False``); ``load_body(...)`` is the audited exceptional path and
  is intentionally not used here.
- **Deterministic.** No clock read (``now_utc`` is passed in), no model, no randomness. A given
  (rows, now_utc, owner_identity) always yields the same candidates and the same ids — re-runnable
  and idempotent. Signal scoring reuses :func:`score_email_task_signals` (the existing deterministic
  email-task scorer) so classification is a single implementation.
- **Raw-safe output.** Titles/reasons are bounded and scrubbed of URLs, email addresses, and
  bearer-token-looking strings before truncation, so even a subject that embedded one cannot leak.
- **Honest project keys.** Resolution reuses :func:`resolve_project`; a project-like-but-unresolved
  candidate is marked ``review_required`` with ``project_key=None`` — keys are never invented.
- **Source-linked.** Every persisted daily-brief candidate is written through the central
  :func:`persist_candidate_with_refs` with a hashed source ref, so coverage is 100% by construction.

Domain persistence targets the existing idempotent candidate tables: ``task_candidates`` for
non-commitment families and ``commitment_candidates`` for the commitment families (which is what
flips the data-gap card to *populated*). ``follow_up_watch_items`` is intentionally NOT written here
— that table is the post-acceptance monitor keyed to ``accepted_*`` rows
(see ``follow_up_watch.run_follow_up_watch_scan``), not a projection target.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .daily_brief_candidate_writer import persist_candidate_with_refs
from .email_task_extraction import score_email_task_signals
from .project_aliases import candidate_tokens, resolve_project

# --------------------------------------------------------------------------------------------------
# Candidate families + routing.
# --------------------------------------------------------------------------------------------------
FAM_WAITING_ON_RESPONSE = "waiting_on_response"
FAM_RESPONSE_NEEDED = "response_needed"
FAM_STALE_THREAD_NUDGE = "stale_thread_nudge"
FAM_USER_COMMITMENT = "user_commitment"
FAM_THIRD_PARTY_COMMITMENT = "third_party_commitment"
FAM_PROJECT_ACTION_ITEM = "project_action_item"
FAM_TIME_SENSITIVE_FOLLOWUP = "time_sensitive_followup"

FAMILIES: tuple[str, ...] = (
    FAM_WAITING_ON_RESPONSE,
    FAM_RESPONSE_NEEDED,
    FAM_STALE_THREAD_NUDGE,
    FAM_USER_COMMITMENT,
    FAM_THIRD_PARTY_COMMITMENT,
    FAM_PROJECT_ACTION_ITEM,
    FAM_TIME_SENSITIVE_FOLLOWUP,
)

_COMMITMENT_FAMILIES = frozenset({FAM_USER_COMMITMENT, FAM_THIRD_PARTY_COMMITMENT})

# Daily-brief section per family (all are executive sections → 100% source-ref coverage required).
_SECTION_FOR_FAMILY: dict[str, str] = {
    FAM_WAITING_ON_RESPONSE: "waiting",
    FAM_RESPONSE_NEEDED: "follow_up",
    FAM_STALE_THREAD_NUDGE: "follow_up",
    FAM_USER_COMMITMENT: "actions",
    FAM_THIRD_PARTY_COMMITMENT: "waiting",
    FAM_PROJECT_ACTION_ITEM: "actions",
    FAM_TIME_SENSITIVE_FOLLOWUP: "follow_up",
}

# Project resolution statuses (honest: never invents a key).
RESOLUTION_RESOLVED = "resolved"
RESOLUTION_REVIEW_REQUIRED = "review_required"
RESOLUTION_NOT_PROJECT_RELATED = "not_project_related"

# Conservative deterministic thresholds (package contract). Confidence floors per family.
STALE_BUSINESS_DAYS = 3
_FLOOR_DAILY_BRIEF = 0.55
_FLOOR_BY_FAMILY: dict[str, float] = {
    FAM_WAITING_ON_RESPONSE: 0.55,
    FAM_RESPONSE_NEEDED: 0.65,
    FAM_STALE_THREAD_NUDGE: 0.55,
    FAM_USER_COMMITMENT: 0.70,
    FAM_THIRD_PARTY_COMMITMENT: 0.70,
    FAM_PROJECT_ACTION_ITEM: 0.55,
    FAM_TIME_SENSITIVE_FOLLOWUP: 0.55,
}

_MAX_TITLE = 120
_MAX_REASON = 240
_MAX_NEXT_ACTION = 160

# Deterministic per-family confidence base. The decisive signal (known sender direction + an
# explicit ask/promise/stale signal) carries the base; each corroborating fired signal adds a small
# increment. Bases are set so a family meeting its decisive condition clears its persistence floor —
# this is honest because direction-confirmed asks/promises are genuinely high-confidence
# deterministically, not a model guess. Direction-dependent families are only ever reached when the
# owner identity is known (see :func:`classify_message_followup`).
_CONFIDENCE_BASE: dict[str, float] = {
    FAM_RESPONSE_NEEDED: 0.66,
    FAM_USER_COMMITMENT: 0.72,
    FAM_THIRD_PARTY_COMMITMENT: 0.72,
    FAM_WAITING_ON_RESPONSE: 0.58,
    FAM_TIME_SENSITIVE_FOLLOWUP: 0.60,
    FAM_PROJECT_ACTION_ITEM: 0.58,
    FAM_STALE_THREAD_NUDGE: 0.56,
}


def _confidence_for(family: str, fired_count: int) -> float:
    """Deterministic confidence: family base + a bounded increment per corroborating signal."""
    base = _CONFIDENCE_BASE.get(family, _FLOOR_DAILY_BRIEF)
    return round(min(0.92, base + 0.04 * max(0, fired_count - 1)), 3)


# A first-person promise ("I/we will send/issue/provide ..."). On an OUTBOUND message this reads as
# Bobby's commitment; on an INBOUND message as the sender's (third-party) commitment.
_FIRST_PERSON_PROMISE = re.compile(
    r"\b(i('| wi)ll|we('| wi)ll|i'?ll|we'?ll)\s+(send|provide|issue|deliver|share|get you|"
    r"forward|submit|return|follow up)\b",
    re.IGNORECASE,
)

# Scrub patterns — strip anything that could carry private content out of a subject before it
# becomes a bounded title/reason (URLs, email addresses, bearer-token-looking strings).
_URL_RE = re.compile(r"https?://\S+|www\.\S+|\b\S+\.(?:com|net|org|io|gov|edu)/\S+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_TOKEN_RE = re.compile(r"\b(bearer|token|secret|authorization)\s*[:=]?\s*\S+", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _scrub(text: Optional[str]) -> str:
    """Remove URLs / email addresses / token-looking strings and collapse whitespace (raw-safe)."""
    if not text:
        return ""
    t = _URL_RE.sub("[link]", str(text))
    t = _EMAIL_RE.sub("[addr]", t)
    t = _TOKEN_RE.sub("[redacted]", t)
    return _WS_RE.sub(" ", t).strip()


def bounded_redacted_title(subject: Optional[str], family: str) -> str:
    """Bounded, scrubbed daily-brief title derived from the safe structured subject."""
    base = _scrub(subject) or "(no subject)"
    label = family.replace("_", " ")
    title = f"{label}: {base}"
    return title[:_MAX_TITLE].rstrip()


def bounded_redacted_reason(reason_codes: list[str], stale_bucket: Optional[str]) -> str:
    """Bounded reason string built only from safe reason codes / buckets (no private text)."""
    parts = list(reason_codes or [])
    if stale_bucket:
        parts.append(f"stale:{stale_bucket}")
    return (", ".join(parts))[:_MAX_REASON]


def candidate_key_for(family: str, source_ref: str) -> str:
    """Deterministic, stable candidate key for one (family, source_ref)."""
    digest = hashlib.sha256(f"{family}|{source_ref}".encode()).hexdigest()[:16]
    return f"email-followup:{family}:{digest}"


@dataclass(frozen=True)
class EmailFollowupCandidate:
    candidate_key: str
    family: str
    source_family: str  # "email_message" | "email_thread"
    source_table: str
    source_ref: str
    message_id_hash: Optional[str]
    thread_ref: Optional[str]
    project_key: Optional[str]
    project_resolution_status: str
    title_redacted: str
    reason_redacted: str
    recommended_next_action: str
    priority: int
    confidence: float
    due_bucket: Optional[str]
    stale_bucket: Optional[str]
    raw_access_used: bool = False


# --------------------------------------------------------------------------------------------------
# Owner identity (sender-direction) — deterministic, config/env driven, honest when unknown.
# --------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class OwnerIdentity:
    addresses: frozenset[str]
    domains: frozenset[str]

    @property
    def known(self) -> bool:
        return bool(self.addresses or self.domains)

    def sent_by_user(self, from_address: Optional[str]) -> Optional[bool]:
        """True/False when identity is known; None when it cannot be determined safely."""
        if not self.known:
            return None
        addr = (from_address or "").strip().lower()
        if not addr:
            return None
        if addr in self.addresses:
            return True
        domain = addr.split("@")[-1] if "@" in addr else ""
        return bool(domain and domain in self.domains)


def resolve_owner_identity(
    *, addresses: Optional[list[str]] = None, domains: Optional[list[str]] = None
) -> OwnerIdentity:
    """Resolve the mailbox owner's addresses/domains for sender-direction (env-overridable).

    Explicit args win (tests pass them directly); otherwise the comma-separated env vars
    ``HB_ASSISTANT_OWNER_ADDRESSES`` / ``HB_ASSISTANT_OWNER_DOMAINS`` are used. When neither is
    configured the identity is *unknown* and direction-dependent families degrade honestly rather
    than guess (see :func:`classify_message_followup`).
    """

    def _split(raw: Optional[str], explicit: Optional[list[str]]) -> frozenset[str]:
        if explicit is not None:
            return frozenset(a.strip().lower() for a in explicit if a and a.strip())
        return frozenset(a.strip().lower() for a in (raw or "").split(",") if a and a.strip())

    return OwnerIdentity(
        addresses=_split(os.environ.get("HB_ASSISTANT_OWNER_ADDRESSES"), addresses),
        domains=_split(os.environ.get("HB_ASSISTANT_OWNER_DOMAINS"), domains),
    )


# --------------------------------------------------------------------------------------------------
# Deterministic time helpers (no clock read).
# --------------------------------------------------------------------------------------------------
def _parse_dt(value: Any) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _business_days_between(then: Optional[datetime], now: Optional[datetime]) -> Optional[int]:
    """Whole business days (Mon–Fri) between ``then`` and ``now``; None if either is unparseable."""
    if then is None or now is None or now < then:
        return None if (then is None or now is None) else 0
    days = 0
    cur = then.date()
    end = now.date()
    while cur < end:
        cur = cur.fromordinal(cur.toordinal() + 1)
        if cur.weekday() < 5:
            days += 1
    return days


def _stale_bucket(business_days: Optional[int]) -> Optional[str]:
    if business_days is None:
        return None
    if business_days <= 1:
        return "fresh"
    if business_days < STALE_BUSINESS_DAYS:
        return "aging"
    if business_days < STALE_BUSINESS_DAYS * 3:
        return "stale"
    return "very_stale"


# --------------------------------------------------------------------------------------------------
# Classification.
# --------------------------------------------------------------------------------------------------
def _signal_summary(
    *,
    subject: str,
    project_key: Optional[str],
    from_domain: Optional[str],
    received_at: Optional[str],
    sent_by_user: Optional[bool],
    source_ref: str,
) -> dict[str, Any]:
    """Build the metadata-safe summary dict consumed by :func:`score_email_task_signals`."""
    return {
        "source_ref": source_ref,
        "project_key": project_key,
        "input_redacted": {
            "thread_subject_redacted": subject,
            "summary_redacted": subject,  # bounded subject is the only safe text signal in pass 1
            "sender_domain": from_domain,
            "received_at": received_at,
            "sent_by_user": bool(sent_by_user),
        },
    }


def _due_bucket(business_days_to_due: Optional[int], has_due_signal: bool) -> Optional[str]:
    if not has_due_signal:
        return None
    return "this_week"  # deterministic coarse bucket; exact dates are not parsed in pass 1


def classify_message_followup(
    row: dict[str, Any], *, now_utc: str, owner: OwnerIdentity
) -> Optional[tuple[str, dict[str, Any]]]:
    """Classify one structured message into (family, signal-context) or None (low signal).

    Direction-dependent families (user/third-party commitment, response-needed,
    waiting-on-response) are only emitted when the owner identity is known; otherwise they degrade
    to direction-agnostic families (time-sensitive / project-action / stale-nudge) or are dropped.
    """
    subject = _scrub(row.get("subject"))
    from_address = row.get("from_address")
    from_domain = (
        str(from_address).split("@")[-1].lower()
        if from_address and "@" in str(from_address)
        else None
    )
    ts = _parse_dt(row.get("received_at_utc") or row.get("sent_at_utc"))
    now = _parse_dt(now_utc)
    stale_days = _business_days_between(ts, now)
    stale_bucket = _stale_bucket(stale_days)
    is_stale = stale_days is not None and stale_days >= STALE_BUSINESS_DAYS

    message_id_hash = row.get("message_id_hash")
    thread_ref = row.get("thread_ref")
    source_ref = (
        f"message:{message_id_hash}"
        if message_id_hash
        else (f"thread:{thread_ref}" if thread_ref else None)
    )
    if not source_ref:
        return None  # cannot source-link → never persisted

    sent_by_user = owner.sent_by_user(from_address)
    sig = _signal_summary(
        subject=subject,
        project_key=row.get("project_key"),
        from_domain=from_domain,
        received_at=row.get("received_at_utc"),
        sent_by_user=sent_by_user,
        source_ref=source_ref,
    )
    scored = score_email_task_signals(sig)
    signals = scored["signals"]
    has_action = (
        signals["direct_ask"] or signals["unanswered_question"] or signals["follow_up_stale"]
    )
    has_due = signals["due_date"]
    has_project = bool(row.get("project_key"))

    promise = bool(_FIRST_PERSON_PROMISE.search(subject))
    asks_reply = signals["direct_ask"] or signals["unanswered_question"]
    # First-match priority (one primary family per message; highest operator value first).
    # A first-person *promise* is a commitment; an *ask* awaiting reply is waiting/response — the two
    # are kept distinct so routine sent mail (no promise, no ask) never becomes a follow-up.
    family: Optional[str] = None
    if sent_by_user is True and promise:
        family = FAM_USER_COMMITMENT
    elif sent_by_user is False and promise:
        family = FAM_THIRD_PARTY_COMMITMENT
    elif sent_by_user is False and asks_reply:
        family = FAM_RESPONSE_NEEDED
    elif sent_by_user is True and is_stale and (asks_reply or signals["follow_up_stale"]):
        family = FAM_WAITING_ON_RESPONSE
    elif has_due:
        family = FAM_TIME_SENSITIVE_FOLLOWUP
    elif has_project and has_action:
        family = FAM_PROJECT_ACTION_ITEM
    elif is_stale and (has_project or signals["follow_up_stale"]):
        family = FAM_STALE_THREAD_NUDGE
    if family is None:
        return None

    fired_count = sum(1 for v in signals.values() if v)
    ctx = {
        "source_family": "email_message",
        "source_table": "email_raw_message_structured",
        "source_ref": source_ref,
        "message_id_hash": message_id_hash,
        "thread_ref": thread_ref,
        "subject": subject,
        "reason_codes": scored["reason_codes"],
        "confidence": _confidence_for(family, fired_count),
        "stale_bucket": stale_bucket,
        "due_bucket": _due_bucket(None, has_due),
        "row_project_key": row.get("project_key"),
    }
    return family, ctx


def classify_thread_followup(
    row: dict[str, Any], *, latest_ts_by_thread: dict[str, Optional[datetime]], now_utc: str
) -> Optional[tuple[str, dict[str, Any]]]:
    """Classify one structured thread into a stale-nudge candidate (direction-agnostic) or None.

    Thread rows carry no timestamp, so recency comes from the latest structured *message* in the
    same thread; threads without a structured message (no recency signal) are skipped honestly.
    """
    thread_ref = row.get("thread_ref")
    if not thread_ref:
        return None
    message_count = int(row.get("message_count") or 0)
    if message_count < 2:
        return None  # single-message "thread" is not a nudge target
    now = _parse_dt(now_utc)
    latest = latest_ts_by_thread.get(str(thread_ref))
    stale_days = _business_days_between(latest, now)
    if stale_days is None or stale_days < STALE_BUSINESS_DAYS:
        return None
    has_project = bool(row.get("project_key"))
    subject = _scrub(row.get("thread_subject"))
    if not (has_project or subject):
        return None
    source_ref = f"thread:{thread_ref}"
    fired = 2 + (1 if has_project else 0)
    ctx = {
        "source_family": "email_thread",
        "source_table": "email_raw_thread_structured",
        "source_ref": source_ref,
        "message_id_hash": None,
        "thread_ref": thread_ref,
        "subject": subject,
        "reason_codes": ["follow_up_stale"]
        + (["project_source_confidence"] if has_project else []),
        "confidence": _confidence_for(FAM_STALE_THREAD_NUDGE, fired),
        "stale_bucket": _stale_bucket(stale_days),
        "due_bucket": None,
        "row_project_key": row.get("project_key"),
    }
    return FAM_STALE_THREAD_NUDGE, ctx


# --------------------------------------------------------------------------------------------------
# Project resolution (honest; never invents a key).
# --------------------------------------------------------------------------------------------------
def _resolve_project_for(ctx: dict[str, Any]) -> tuple[Optional[str], str]:
    explicit = ctx.get("row_project_key")
    if explicit and str(explicit).strip():
        return str(explicit).strip(), RESOLUTION_RESOLVED
    subject = ctx.get("subject") or ""
    resolved = resolve_project(subject)
    if resolved:
        return resolved, RESOLUTION_RESOLVED
    if candidate_tokens(subject):
        return None, RESOLUTION_REVIEW_REQUIRED
    return None, RESOLUTION_NOT_PROJECT_RELATED


def _next_action_for(family: str) -> str:
    actions = {
        FAM_WAITING_ON_RESPONSE: "Review whether to nudge the other party for a response",
        FAM_RESPONSE_NEEDED: "Draft a response (manually) — inbound request awaiting Bobby",
        FAM_STALE_THREAD_NUDGE: "Review stale thread; decide whether a nudge is warranted",
        FAM_USER_COMMITMENT: "Confirm Bobby's commitment is on track and follow through",
        FAM_THIRD_PARTY_COMMITMENT: "Track the third-party commitment; follow up if it slips",
        FAM_PROJECT_ACTION_ITEM: "Review the project action item and assign next step",
        FAM_TIME_SENSITIVE_FOLLOWUP: "Review the time-sensitive item before its deadline",
    }
    return actions.get(family, "Review")[:_MAX_NEXT_ACTION]


def _priority_for(family: str) -> int:
    order = {
        FAM_RESPONSE_NEEDED: 10,
        FAM_USER_COMMITMENT: 20,
        FAM_TIME_SENSITIVE_FOLLOWUP: 30,
        FAM_THIRD_PARTY_COMMITMENT: 40,
        FAM_PROJECT_ACTION_ITEM: 50,
        FAM_WAITING_ON_RESPONSE: 60,
        FAM_STALE_THREAD_NUDGE: 80,
    }
    return order.get(family, 100)


def extract_email_followup_candidates_from_structured(
    *,
    messages: list[dict[str, Any]],
    threads: list[dict[str, Any]],
    now_utc: str,
    owner: OwnerIdentity,
) -> list[EmailFollowupCandidate]:
    """Pure deterministic extractor: structured rows → bounded, source-linked candidates.

    One primary candidate per message (priority order) plus thread-level stale nudges; deduplicated
    by deterministic candidate key. Confidence below the per-family floor is dropped.
    """
    # Latest structured-message timestamp per thread (recency signal for thread nudges).
    latest_ts_by_thread: dict[str, Optional[datetime]] = {}
    for m in messages:
        tref = m.get("thread_ref")
        if not tref:
            continue
        ts = _parse_dt(m.get("received_at_utc") or m.get("sent_at_utc"))
        if ts is None:
            continue
        cur = latest_ts_by_thread.get(str(tref))
        if cur is None or ts > cur:
            latest_ts_by_thread[str(tref)] = ts

    # Message-level candidates that clear their per-family confidence floor.
    surviving_message_hits: list[tuple[str, dict[str, Any]]] = []
    for m in messages:
        hit = classify_message_followup(m, now_utc=now_utc, owner=owner)
        if not hit:
            continue
        family, ctx = hit
        if float(ctx["confidence"]) < _FLOOR_BY_FAMILY.get(family, _FLOOR_DAILY_BRIEF):
            continue
        surviving_message_hits.append(hit)
    threads_with_message_candidate = {
        ctx.get("thread_ref") for _fam, ctx in surviving_message_hits if ctx.get("thread_ref")
    }

    raw: list[tuple[str, dict[str, Any]]] = list(surviving_message_hits)
    for t in threads:
        # Avoid double-nudging a thread that already produced a surviving message-level candidate.
        if t.get("thread_ref") in threads_with_message_candidate:
            continue
        hit = classify_thread_followup(t, latest_ts_by_thread=latest_ts_by_thread, now_utc=now_utc)
        if hit:
            raw.append(hit)

    by_key: dict[str, EmailFollowupCandidate] = {}
    for family, ctx in raw:
        confidence = float(ctx["confidence"])
        if confidence < _FLOOR_BY_FAMILY.get(family, _FLOOR_DAILY_BRIEF):
            continue
        project_key, resolution = _resolve_project_for(ctx)
        key = candidate_key_for(family, ctx["source_ref"])
        if key in by_key:
            continue  # deterministic dedup (stable first-wins by input order)
        by_key[key] = EmailFollowupCandidate(
            candidate_key=key,
            family=family,
            source_family=ctx["source_family"],
            source_table=ctx["source_table"],
            source_ref=ctx["source_ref"],
            message_id_hash=ctx.get("message_id_hash"),
            thread_ref=ctx.get("thread_ref"),
            project_key=project_key,
            project_resolution_status=resolution,
            title_redacted=bounded_redacted_title(ctx.get("subject"), family),
            reason_redacted=bounded_redacted_reason(
                ctx.get("reason_codes", []), ctx.get("stale_bucket")
            ),
            recommended_next_action=_next_action_for(family),
            priority=_priority_for(family),
            confidence=confidence,
            due_bucket=ctx.get("due_bucket"),
            stale_bucket=ctx.get("stale_bucket"),
            raw_access_used=False,
        )
    # Deterministic ordering: priority then key.
    return sorted(by_key.values(), key=lambda c: (c.priority, c.candidate_key))


# --------------------------------------------------------------------------------------------------
# Persistence (idempotent) + stage builder.
# --------------------------------------------------------------------------------------------------
def _domain_candidate_id(stable_key: str) -> str:
    return f"efu-{hashlib.sha256(stable_key.encode()).hexdigest()[:28]}"


def _waiting_state_for(family: str) -> str:
    return {
        FAM_WAITING_ON_RESPONSE: "waiting_on_others",
        FAM_RESPONSE_NEEDED: "waiting_on_me",
        FAM_STALE_THREAD_NUDGE: "waiting_on_others",
        FAM_USER_COMMITMENT: "waiting_on_me",
        FAM_THIRD_PARTY_COMMITMENT: "waiting_on_others",
        FAM_PROJECT_ACTION_ITEM: "waiting_on_me",
        FAM_TIME_SENSITIVE_FOLLOWUP: "waiting_on_me",
    }.get(family, "unknown")


def _persist_one(store: Any, cand: EmailFollowupCandidate, *, brief_date: str) -> None:
    """Persist one candidate to its domain table + the daily-brief candidate/source-ref (idempotent)."""
    candidate_id = _domain_candidate_id(cand.candidate_key)
    source_ref_payload = [
        {
            "source_family": cand.source_family,
            "source_ref": cand.source_ref,
            "source_table": cand.source_table,
        }
    ]
    source_ref_hash = hashlib.sha256(cand.source_ref.encode()).hexdigest()
    domain_type = "commitment" if cand.family in _COMMITMENT_FAMILIES else "task"

    if cand.family in _COMMITMENT_FAMILIES:
        store.upsert_commitment_candidate(
            candidate_id=candidate_id,
            stable_key=cand.candidate_key,
            title_redacted=cand.title_redacted,
            project_key=cand.project_key,
            commitment_actor_class="user" if cand.family == FAM_USER_COMMITMENT else "other",
            waiting_state=_waiting_state_for(cand.family),
            confidence=cand.confidence,
            reason_redacted=cand.reason_redacted,
            recommended_next_action=cand.recommended_next_action,
        )
    else:
        store.upsert_task_candidate(
            candidate_id=candidate_id,
            stable_key=cand.candidate_key,
            title_redacted=cand.title_redacted,
            project_key=cand.project_key,
            assignee_class="user" if cand.family == FAM_RESPONSE_NEEDED else "unknown",
            waiting_state=_waiting_state_for(cand.family),
            confidence=cand.confidence,
            reason_redacted=cand.reason_redacted,
            recommended_next_action=cand.recommended_next_action,
        )
    # Link the domain candidate to its email source ref (hash-only).
    store.upsert_candidate_source_ref(
        source_ref_id=f"efu-src-{hashlib.sha256(f'{candidate_id}|{cand.source_ref}'.encode()).hexdigest()[:28]}",
        candidate_type=domain_type,
        candidate_id=candidate_id,
        source_family=cand.source_family,
        source_ref_hash=source_ref_hash,
        source_table=cand.source_table,
    )
    # Daily-brief candidate + hashed source ref (central writer → 100% coverage by construction).
    persist_candidate_with_refs(
        store,
        brief_date=brief_date,
        section=_SECTION_FOR_FAMILY[cand.family],
        title_redacted=cand.title_redacted,
        confidence=cand.confidence,
        group_key=cand.candidate_key,
        source_refs=source_ref_payload,
        project_key=cand.project_key,
        priority=cand.priority,
        reason_redacted=cand.reason_redacted,
        recommended_next_action=cand.recommended_next_action,
    )


def build_email_followup_candidates(
    *,
    store: Any,
    now_utc: str,
    limit: int = 200,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    db_path: Optional[str] = None,
    owner: Optional[OwnerIdentity] = None,
) -> dict[str, Any]:
    """Pipeline stage builder: project structured email → source-linked follow-up candidates.

    Dry-run (default) writes nothing and reports ``would_persist``. ``--apply`` (dry_run=False)
    requires ``max_persist`` and caps ACTUAL persists; remaining eligible candidates are counted but
    not written. Idempotent: deterministic ids mean a repeat apply on the same DB is a no-op. The
    receipt is raw-free (counts / reason codes / coverage only).
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual candidate persists)")

    brief_date = now_utc[:10]
    owner = owner or resolve_owner_identity()
    messages = store.list_email_message_structured(limit=limit)
    threads = store.list_thread_structured(limit=limit)

    candidates = extract_email_followup_candidates_from_structured(
        messages=messages, threads=threads, now_utc=now_utc, owner=owner
    )

    generated_by_family: dict[str, int] = dict.fromkeys(FAMILIES, 0)
    for c in candidates:
        generated_by_family[c.family] += 1

    resolved = sum(1 for c in candidates if c.project_resolution_status == RESOLUTION_RESOLVED)
    review_required = sum(
        1 for c in candidates if c.project_resolution_status == RESOLUTION_REVIEW_REQUIRED
    )
    not_project = sum(
        1 for c in candidates if c.project_resolution_status == RESOLUTION_NOT_PROJECT_RELATED
    )
    project_key_coverage = round(resolved / len(candidates), 4) if candidates else 1.0

    would_persist = len(candidates)
    persisted = 0
    persisted_by_family: dict[str, int] = dict.fromkeys(FAMILIES, 0)
    remaining = max_persist if (not dry_run and max_persist is not None) else None
    for c in candidates:
        if dry_run or (remaining is not None and remaining <= 0):
            continue
        _persist_one(store, c, brief_date=brief_date)
        persisted += 1
        persisted_by_family[c.family] += 1
        if remaining is not None:
            remaining -= 1

    structured_email_available = bool(messages) or bool(threads)
    summary = {
        "would_persist": would_persist,
        "persisted": persisted,
        "structured_messages_considered": len(messages),
        "structured_threads_considered": len(threads),
        "structured_email_available": structured_email_available,
        "generated": len(candidates),
        "generated_by_family": generated_by_family,
        "persisted_by_family": persisted_by_family,
        "project_key_resolved": resolved,
        "project_key_review_required": review_required,
        "project_key_not_project_related": not_project,
        "project_key_coverage": project_key_coverage,
        "review_required_count": review_required,
        "raw_access_count": 0,
        "owner_identity_known": owner.known,
        "reason_codes": ([] if owner.known else ["owner_identity_unknown"]),
    }
    return {
        "command": "second-brain email-followup-projection",
        "ok": True,
        "applied": not dry_run,
        "now_utc": now_utc,
        "limit": limit,
        "max_persist": max_persist,
        "summary": summary,
        "candidates": [
            {
                "candidate_key": c.candidate_key,
                "family": c.family,
                "section": _SECTION_FOR_FAMILY[c.family],
                "source_family": c.source_family,
                "project_resolution_status": c.project_resolution_status,
                "has_project_key": c.project_key is not None,
                "confidence": c.confidence,
                "priority": c.priority,
                "due_bucket": c.due_bucket,
                "stale_bucket": c.stale_bucket,
                "raw_access_used": c.raw_access_used,
            }
            for c in candidates
        ],
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "deterministic_no_clock": True,
            "deterministic_no_model": True,
            "structured_first": True,
            "no_raw_body_loaded": True,
            "source_linked_only": True,
            "no_invented_project_keys": True,
            "no_writeback": True,
        },
    }


__all__ = [
    "EmailFollowupCandidate",
    "FAMILIES",
    "OwnerIdentity",
    "RESOLUTION_NOT_PROJECT_RELATED",
    "RESOLUTION_RESOLVED",
    "RESOLUTION_REVIEW_REQUIRED",
    "bounded_redacted_reason",
    "bounded_redacted_title",
    "build_email_followup_candidates",
    "candidate_key_for",
    "classify_message_followup",
    "classify_thread_followup",
    "extract_email_followup_candidates_from_structured",
    "resolve_owner_identity",
]
