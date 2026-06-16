"""Phase 10 — user-facing daily-brief presentation (pure, deterministic, raw-safe).

The presentation layer that turns the already-redacted ranking/assembly overlay rows into polished,
operator-facing Markdown lines. Every function here is pure (no store, no I/O, no wall-clock): it
takes the safe fields the overlay already exposes and returns display strings that carry a readable
label, a project label or clear fallback, a plain-language source category, a concise reason, and a
concrete CTA — never an internal id, sentinel, hash label, table/column name, ``next:review``, or any
raw subject/body/URL/email.

Two invariants make this safe by construction:

- The render path supplies only the overlay's redacted fields (``title_redacted``, ``project_key``,
  ``reason_redacted``, ``section``). Calendar titles arrive as ``[redacted:<hash>]`` placeholders and
  project keys may be sentinels (``__needs_review__`` / ``__internal_*``); both are mapped to safe
  labels here and never rendered verbatim.
- :func:`assert_clean_display` is the output fence — the render path runs it over the final Markdown
  so a regression that leaks a forbidden token fails loudly instead of reaching the user.
"""

from __future__ import annotations

import re
from typing import Optional

# --- Output fence -----------------------------------------------------------------------------

#: Internal artifacts that must never appear in user-facing Markdown (audit P1 leaks + raw markers).
FORBIDDEN_DISPLAY_TOKENS: tuple[str, ...] = (
    "id:dbac",
    "id:rel",
    "dbac-",
    "rel-",
    "__needs_review__",
    "__internal_",
    "[redacted:",
    "next:review",
    "candidate_id",
    "daily_brief_action_candidates",
    "ranking_run_id",
    "assembly_run_id",
    "section_key",
)

#: Raw private-content patterns (mirror the second-brain forbidden-token scanners).
_FORBIDDEN_RAW_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Bearer\s+[A-Za-z0-9]"),
    re.compile(r"-----BEGIN"),
    re.compile(r"eyJ[A-Za-z0-9_-]{5,}"),
    re.compile(r"https?://"),
    re.compile(r"\bsig="),
    re.compile(r"token=[A-Za-z0-9]"),
    re.compile(r"access_token|refresh_token|client_secret"),
    re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    re.compile(r"Traceback \(most recent call last\)"),
)

#: A ``[redacted:<hash>]`` placeholder — never usable as a user-facing label.
_REDACTED_LABEL = re.compile(r"\[redacted:[0-9a-fA-F]+\]")


def assert_clean_display(markdown: str, *, where: str = "rendered brief") -> None:
    """Raise ``ValueError`` if ``markdown`` carries any internal artifact or raw private content."""
    for tok in FORBIDDEN_DISPLAY_TOKENS:
        if tok in markdown:
            raise ValueError(f"forbidden display token {tok!r} found in {where}")
    for pat in _FORBIDDEN_RAW_PATTERNS:
        if pat.search(markdown):
            raise ValueError(f"forbidden raw pattern {pat.pattern!r} found in {where}")


# --- Section model ----------------------------------------------------------------------------

#: Assembly section_key → user-facing display group (the README's required order).
ASSEMBLY_KEY_TO_GROUP: dict[str, str] = {
    "top_priorities": "Top Priorities",
    "review_needs_decision": "Needs Review / Decisions",
    "meeting_prep": "Calendar Prep",
    "project_procore_risk": "Procore Financial / Project Signals",
    "waiting_on_me": "Email / Follow-up",
    "waiting_on_others": "Email / Follow-up",
    "accepted_stale": "Email / Follow-up",
    "data_gaps_degraded": "Data Gaps / Degraded",
}

#: Deterministic display-group order (README §1).
DISPLAY_GROUP_ORDER: tuple[str, ...] = (
    "Top Priorities",
    "Needs Review / Decisions",
    "Calendar Prep",
    "Procore Financial / Project Signals",
    "Email / Follow-up",
    "Data Gaps / Degraded",
)

#: Candidate ``section`` (family) → user-facing display group, for the no-overlay fallback path.
FAMILY_TO_GROUP: dict[str, str] = {
    "calendar": "Calendar Prep",
    "procore": "Procore Financial / Project Signals",
    "actions": "Email / Follow-up",
    "waiting": "Email / Follow-up",
    "follow_up": "Email / Follow-up",
}


# --- Labels & projects ------------------------------------------------------------------------

_INTERNAL_TIME_OFF = "__internal_time_off__"
_NEEDS_REVIEW = "__needs_review__"


def _str_field(detail: dict[str, object], key: str) -> Optional[str]:
    """Read a string field from a candidate-detail dict, or ``None`` if absent/non-string."""
    value = detail.get(key)
    return value if isinstance(value, str) else None


def project_label(project_key: Optional[str]) -> Optional[str]:
    """Readable project *display name*, or ``None`` for sentinels/empty.

    Routes through the config-backed display resolver so neither the user-facing brief nor the
    collapsed diagnostics ever render a raw lowercase project key (e.g. ``tropical`` →
    ``Tropical``, ``alton-hilltop-pbg`` → ``Alton Hilltop at PBG``). Unknown keys are cleaned to a
    title-cased label rather than shown as a slug.
    """
    from .project_aliases import project_display_name

    return project_display_name(project_key)


def safe_calendar_label(project_key: Optional[str]) -> str:
    """Map a calendar candidate's project key to an actionable, raw-free label (README §3)."""
    pk = str(project_key or "").strip()
    if pk == _INTERNAL_TIME_OFF:
        return "Internal calendar block"
    if pk == _NEEDS_REVIEW:
        return "Calendar item needing project review"
    if pk.startswith("__internal"):
        return "Internal calendar block"
    label = project_label(pk)
    if label is not None:
        return f"Project meeting — {label}"
    return "Calendar item — project TBD"


def clean_title(title_redacted: Optional[str], *, fallback: str) -> str:
    """Return a readable title, replacing empty/hash-placeholder titles with ``fallback``."""
    title = str(title_redacted or "").strip()
    if not title or _REDACTED_LABEL.search(title):
        return fallback
    return title


# --- Procore signals --------------------------------------------------------------------------

#: signal_type → human phrase used in aggregated Procore lines.
SIGNAL_PHRASE: dict[str, str] = {
    "invoice_payment_due": "payment-due invoice",
    "invoice_approved_not_paid": "approved-not-paid invoice",
    "budget_variance_negative": "negative budget variance",
    "budget_forecast_exceeds_budget": "forecast-exceeds-budget",
    "commitment_change_order_unpaid": "unpaid commitment change-order",
    "prime_change_order_unpaid": "unpaid prime change-order",
    "rfi_cost_impact_flagged": "RFI cost-impact",
}

#: signal_type → deterministic CTA (README §5). The blanket ``next:review`` is never emitted.
CTA_BY_SIGNAL: dict[str, str] = {
    "invoice_payment_due": "Review payment status and confirm next payment action.",
    "invoice_approved_not_paid": "Confirm whether approved invoices are scheduled for payment.",
    "budget_variance_negative": "Review variance driver and forecast exposure.",
    "budget_forecast_exceeds_budget": "Check forecast-to-complete and escalation path.",
    "commitment_change_order_unpaid": "Confirm unpaid commitment change order status.",
    "prime_change_order_unpaid": "Confirm owner-side change order payment status.",
    "rfi_cost_impact_flagged": "Confirm pricing exposure and response owner.",
}

_CTA_PROCORE_DEFAULT = "Review the highest-value items and confirm the next action."
_CTA_CALENDAR_NEEDS_REVIEW = "Assign project/context and prepare meeting notes."
_CTA_CALENDAR_DEFAULT = "Review the meeting and prepare notes."
_CTA_FOLLOW_UP = "Confirm status and next response."
_CTA_EMAIL_GAP = "Review the email follow-up projection/watch eligibility inputs."
_CTA_REVIEW_DECISION = "Review and decide whether to act, snooze, or dismiss."


def parse_procore_signal(title_redacted: Optional[str]) -> tuple[str, str]:
    """Split a Procore candidate title ``"{why}: {signal_type}"`` → ``(why, signal_type)``.

    Falls back to ``("", <title>)`` when no ``": "`` separator is present.
    """
    title = str(title_redacted or "").strip()
    if ": " in title:
        why, signal_type = title.rsplit(": ", 1)
        return why.strip(), signal_type.strip()
    return "", title


def signal_phrase(signal_type: str) -> str:
    """Human phrase for a signal type (mapped, else a de-snaked fallback)."""
    st = str(signal_type or "").strip()
    return SIGNAL_PHRASE.get(st, st.replace("_", " ").strip() or "project")


def cta_for_signal(signal_type: str) -> str:
    """Deterministic CTA for a Procore signal type."""
    return CTA_BY_SIGNAL.get(str(signal_type or "").strip(), _CTA_PROCORE_DEFAULT)


def aggregate_procore_lines(
    items: list[dict[str, object]],
    *,
    max_signal_types_per_project: int = 4,
    max_project_lines: int = 8,
) -> list[str]:
    """Aggregate per-signal Procore candidates into one readable line per project (README §4).

    ``items`` are candidate-detail dicts with ``project_key`` + ``title_redacted``. Groups by
    project, counts distinct signal types, dedupes, caps per-project signal types and total project
    lines, and emits ``"<project> — N <phrase> signals, …. <CTA>"``. Deterministic order: most
    signals first, then project label.
    """
    by_project: dict[str, dict[str, int]] = {}
    for it in items:
        proj_key = project_label(_str_field(it, "project_key")) or "Project TBD"
        _why, signal_type = parse_procore_signal(_str_field(it, "title_redacted"))
        counts = by_project.setdefault(proj_key, {})
        counts[signal_type] = counts.get(signal_type, 0) + 1

    ranked_projects = sorted(
        by_project.items(),
        key=lambda kv: (-sum(kv[1].values()), kv[0]),
    )[:max_project_lines]

    lines: list[str] = []
    for proj, counts in ranked_projects:
        top_signals = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[
            :max_signal_types_per_project
        ]
        phrases = ", ".join(
            f"{cnt} {signal_phrase(st)} signal{'' if cnt == 1 else 's'}" for st, cnt in top_signals
        )
        cta = cta_for_signal(top_signals[0][0]) if top_signals else _CTA_PROCORE_DEFAULT
        lines.append(f"- {proj} — {phrases}. {cta}")
    return lines


# --- Calendar metadata ------------------------------------------------------------------------

_LOCATION_PHRASE = {
    "online": "online",
    "in_person_or_unspecified": "in person / TBD",
}


def calendar_metadata(reason_redacted: Optional[str]) -> str:
    """Reformat the calendar candidate's safe reason ("N attendees · M domains · class") for display.

    The reason is built raw-free at write time; we only normalize separators and the location class.
    Returns an empty string when no reason is present.
    """
    reason = str(reason_redacted or "").strip()
    if not reason:
        return ""
    parts = [p.strip() for p in reason.split("·") if p.strip()]
    normalized = [_LOCATION_PHRASE.get(p, p) for p in parts]
    return " / ".join(normalized)


# --- Per-item lines ---------------------------------------------------------------------------


def render_calendar_line(detail: dict[str, object]) -> str:
    """One sanitized Calendar-Prep bullet (safe label + metadata + prep CTA)."""
    pk = _str_field(detail, "project_key")
    label = safe_calendar_label(pk)
    meta = calendar_metadata(_str_field(detail, "reason_redacted"))
    cta = _CTA_CALENDAR_NEEDS_REVIEW if pk == _NEEDS_REVIEW else _CTA_CALENDAR_DEFAULT
    suffix = f" — {meta}. {cta}" if meta else f" — {cta}"
    return f"- {label}{suffix}"


def render_procore_line(detail: dict[str, object]) -> str:
    """One sanitized Procore bullet (single-signal form, used inside Top Priorities)."""
    proj = project_label(_str_field(detail, "project_key")) or "Project TBD"
    _why, signal_type = parse_procore_signal(_str_field(detail, "title_redacted"))
    return f"- {proj} — {signal_phrase(signal_type)} signal. {cta_for_signal(signal_type)}"


def render_followup_line(detail: dict[str, object], *, needs_decision: bool = False) -> str:
    """One sanitized Email/Follow-up or Needs-Review bullet (readable title + project + CTA)."""
    fallback = "Review item" if needs_decision else "Follow-up item"
    title = clean_title(_str_field(detail, "title_redacted"), fallback=fallback)
    proj = project_label(_str_field(detail, "project_key"))
    head = f"{proj} — {title}" if proj else title
    cta = _CTA_REVIEW_DECISION if needs_decision else _CTA_FOLLOW_UP
    return f"- {head}. {cta}"


def render_item_line(detail: dict[str, object], *, group: str) -> str:
    """Dispatch a candidate detail to the right per-family renderer for ``group``."""
    section = str(detail.get("section") or "")
    if section == "calendar" or group == "Calendar Prep":
        return render_calendar_line(detail)
    if section == "procore" or group == "Procore Financial / Project Signals":
        return render_procore_line(detail)
    needs_decision = group == "Needs Review / Decisions"
    return render_followup_line(detail, needs_decision=needs_decision)


# --- Email / follow-up data-gap card ----------------------------------------------------------


def email_followup_gap_card(thread_summary_count: int) -> list[str]:
    """Polished data-gap card when email summaries exist but no follow-ups are eligible (README §6)."""
    if thread_summary_count <= 0:
        return ["- No email follow-up candidates and no email summaries available for this date."]
    if thread_summary_count == 1:
        noun, verb, none_clause = "summary", "exists", "it is not eligible"
    else:
        noun, verb, none_clause = "summaries", "exist", "none are eligible"
    return [
        f"- Email follow-up unavailable — {thread_summary_count} email thread {noun} {verb}, but "
        f"{none_clause} for follow-up watch. {_CTA_EMAIL_GAP}"
    ]


def collapse_duplicate_lines(lines: list[str]) -> list[str]:
    """Collapse exact-duplicate bullet lines into a single line with a ``(×N)`` count (order-stable).

    Keeps per-item sections readable when ranking surfaces several identical signals (e.g. five
    identical payment-due lines in Top Priorities) without dropping information.
    """
    counts: dict[str, int] = {}
    order: list[str] = []
    for ln in lines:
        if ln not in counts:
            order.append(ln)
        counts[ln] = counts.get(ln, 0) + 1
    out: list[str] = []
    for ln in order:
        n = counts[ln]
        out.append(f"{ln} (×{n})" if n > 1 else ln)
    return out


#: Max calendar lines shown in the brief before an explicit overflow summary (no silent truncation).
CALENDAR_MAX_LINES = 12


def cap_lines(lines: list[str], *, max_lines: int, more_noun: str) -> list[str]:
    """Cap ``lines`` to ``max_lines`` and append an explicit ``"+N more …"`` line (never silent)."""
    if max_lines <= 0 or len(lines) <= max_lines:
        return lines
    kept = lines[:max_lines]
    dropped = len(lines) - max_lines
    kept.append(f"- +{dropped} more {more_noun} (open the full review queue to see them all).")
    return kept


# --- Data gaps / degraded ---------------------------------------------------------------------


def render_data_gap_lines(degraded_reason: Optional[str]) -> list[str]:
    """Polished rendering of an assembly ``data_gaps_degraded`` reason (raw-free key=value string)."""
    reason = str(degraded_reason or "").strip()
    withheld = 0
    model_layer = "ok"
    for chunk in reason.split(";"):
        chunk = chunk.strip()
        if chunk.startswith("source_missing_withheld="):
            try:
                withheld = int(chunk.split("=", 1)[1])
            except ValueError:
                withheld = 0
        elif chunk.startswith("model_layer="):
            model_layer = chunk.split("=", 1)[1].strip() or "ok"

    lines: list[str] = []
    if withheld > 0:
        lines.append(
            f"- {withheld} item(s) withheld this run because required source links were missing. "
            "These are intentionally not surfaced; confirm the upstream projection populated refs."
        )
    if model_layer not in ("ok", "model_enriched"):
        lines.append(
            "- Advisory model layer unavailable; deterministic ranking is authoritative for this "
            "brief. No action needed — the priorities above are complete."
        )
    if not lines:
        lines.append("- No data gaps detected for this date.")
    return lines
