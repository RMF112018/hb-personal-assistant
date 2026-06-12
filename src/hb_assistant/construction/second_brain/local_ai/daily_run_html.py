"""Phase 10 — polished, self-contained browser brief for the daily run (local consumption).

Renders the already-grouped daily-brief sections (from ``render_daily_brief``) into a single
self-contained HTML file with **inline CSS only and zero network access**. Raw local content
(meeting subjects/locations, Procore titles) is allowed because the browser brief is a private
local consumption surface — but every dynamic value is first scrubbed of egress patterns (URLs,
join links, signed/SAS params, bearer/JWT tokens, emails) and then HTML-escaped (injection-safe),
and the whole document is scanned fail-closed for external-asset/network patterns before the
caller writes it.

This file never goes inside the repo; the caller writes it under Application Support. The renderer
itself is pure (no I/O) and deterministic given its inputs.
"""

from __future__ import annotations

import html
import re
from typing import Any

from ..daily_brief_html import _scan_html_for_external_assets

# Egress scrubbing applied to every dynamic value before escaping. Replaces (does not just detect)
# so a stray link/token in raw business content cannot reach the page.
_EMAIL_RE = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_JOIN_RE = re.compile(
    r"\b(?:teams\.microsoft\.com|zoom\.us|meet\.google\.com|webex\.com|[a-z0-9-]+\.zoom\.us)\S*",
    re.IGNORECASE,
)
_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|us|co|ms|gov|edu)\b(?:/\S*)?", re.IGNORECASE
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}\.?[A-Za-z0-9_-]*")
_TOKEN_RE = re.compile(
    r"\b(?:bearer\s+\S+|access_token\S*|refresh_token\S*|client_secret\S*)", re.IGNORECASE
)
_SAS_RE = re.compile(r"[?&](?:sig|sv|se|st|sp|sr)=[^&\s]+", re.IGNORECASE)

_STATUS_CLASS = {
    "success": "ok",
    "deterministic_success_synthesis_degraded": "ok",
    "partial": "warn",
    "degraded": "warn",
    "failure": "fail",
    "skipped_weekend": "skip",
}


def scrub_raw_text(text: Any) -> str:
    """Strip egress patterns from a raw value (replace with safe markers), collapse whitespace."""
    if text is None:
        return ""
    s = str(text)
    s = _JWT_RE.sub("[redacted-token]", s)
    s = _TOKEN_RE.sub("[redacted-token]", s)
    s = _SAS_RE.sub("[redacted-token]", s)
    s = _JOIN_RE.sub("[redacted-link]", s)
    s = _URL_RE.sub("[redacted-link]", s)
    s = _DOMAIN_RE.sub("[redacted-link]", s)
    s = _EMAIL_RE.sub("[redacted-email]", s)
    return re.sub(r"\s+", " ", s).strip()


def _esc(text: Any) -> str:
    """Scrub then HTML-escape — the only path dynamic content reaches the page."""
    return html.escape(scrub_raw_text(text), quote=True)


def scan_daily_run_html(rendered_html: str) -> list[str]:
    """Fail-closed whole-document scan; empty list = clean (no external-asset/network patterns)."""
    return _scan_html_for_external_assets(rendered_html)


_CSS = """
:root{--bg:#0f1220;--card:#1a1f35;--ink:#e7eaf3;--muted:#9aa3bd;--line:#2a3150;
--ok:#2f9e63;--warn:#c9952b;--fail:#c5453f;--skip:#5a6b8c;--accent:#4d7cfe;}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:28px 20px 64px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 18px}
.banner{padding:12px 16px;border-radius:10px;font-weight:600;margin:0 0 18px}
.banner.ok{background:rgba(47,158,99,.15);border:1px solid var(--ok)}
.banner.warn{background:rgba(201,149,43,.15);border:1px solid var(--warn)}
.banner.fail{background:rgba(197,69,63,.15);border:1px solid var(--fail)}
.banner.skip{background:rgba(154,163,189,.12);border:1px solid var(--muted)}
.policy{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 18px}
.policy .lbl{display:inline-block;background:var(--accent);color:#fff;border-radius:999px;
padding:2px 10px;font-size:12px;font-weight:700;margin-bottom:8px}
.policy dl{display:grid;grid-template-columns:max-content 1fr;gap:4px 14px;margin:6px 0 0}
.policy dt{color:var(--muted)}.policy dd{margin:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:0 0 14px}
.card h2{font-size:17px;margin:0 0 10px;display:flex;justify-content:space-between;align-items:center}
.count{color:var(--muted);font-size:13px;font-weight:500}
.item{padding:10px 0;border-top:1px solid var(--line)}.item:first-of-type{border-top:0}
.item .ttl{font-weight:600}.item .meta{color:var(--muted);font-size:13px;margin-top:2px}
.item .cid{color:#6b7a99;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.foot{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}
.empty{color:var(--muted);font-style:italic}
"""


def _bullet_card(title: str, items: list[str], *, count: int | None = None, empty: str) -> str:
    n = count if count is not None else len(items)
    parts = [f"<div class='card'><h2>{_esc(title)}<span class='count'>{n}</span></h2>"]
    if items:
        parts += [f"<div class='item'><div class='ttl'>{i}</div></div>" for i in items]
    else:
        parts.append(f"<p class='empty'>{_esc(empty)}</p>")
    parts.append("</div>")
    return "".join(parts)


def _fmt_bullet(b: dict[str, Any]) -> str:
    text = _esc(b.get("text"))
    tail: list[str] = []
    if b.get("project") and b.get("project") not in {"", "Needs Project Review"}:
        tail.append("project: " + _esc(b.get("project")))
    if b.get("source_id"):
        tail.append("id: " + _esc(b.get("source_id")))
    suffix = f" <span class='cid'>{' · '.join(tail)}</span>" if tail else ""
    return text + suffix


def _render_synthesis_cards(synthesis: dict[str, Any]) -> str:
    """Render the nine synthesized operator sections as cards (each with an empty state)."""
    out: list[str] = []
    out.append(
        _bullet_card(
            "Executive Summary",
            [_esc(x) for x in synthesis.get("executive_summary") or []],
            empty="No high-level summary generated.",
        )
    )
    out.append(
        _bullet_card(
            "What Changed Since Last Brief",
            [_fmt_bullet(b) for b in synthesis.get("what_changed_since_last_brief") or []],
            empty="No notable changes since the last working-period brief.",
        )
    )
    out.append(
        _bullet_card(
            "Critical / Due Today",
            [_fmt_bullet(b) for b in synthesis.get("critical_due_today") or []],
            empty="No critical due-today actions found.",
        )
    )
    out.append(
        _bullet_card(
            "Open Commitments & Follow-Ups",
            [_fmt_bullet(b) for b in synthesis.get("open_commitments_follow_ups") or []],
            empty="No open commitments or follow-up items found for this run.",
        )
    )

    # Today's Meetings — richer item layout (time, project, why, prep, questions).
    meetings = synthesis.get("todays_meetings") or []
    mparts = [
        f"<div class='card'><h2>Today's Meetings<span class='count'>{len(meetings)}</span></h2>"
    ]
    if meetings:
        for m in meetings:
            head = " — ".join(_esc(p) for p in (m.get("local_time"), m.get("title")) if p)
            mparts.append("<div class='item'>")
            mparts.append(
                f"<div class='ttl'>{head} <span class='cid'>({_esc(m.get('project'))})</span></div>"
            )
            meta: list[str] = []
            if m.get("why_it_matters"):
                meta.append("Why: " + _esc(m.get("why_it_matters")))
            if m.get("prep"):
                meta.append("Prep: " + _esc(m.get("prep")))
            if m.get("open_questions"):
                meta.append("Q: " + "; ".join(_esc(q) for q in m.get("open_questions")))
            if m.get("recommended_next_action"):
                meta.append("Next: " + _esc(m.get("recommended_next_action")))
            if meta:
                mparts.append(f"<div class='meta'>{' · '.join(meta)}</div>")
            if m.get("source_id"):
                mparts.append(f"<div class='cid'>id: {_esc(m.get('source_id'))}</div>")
            mparts.append("</div>")
    else:
        mparts.append("<p class='empty'>No meeting-prep items required attention.</p>")
    mparts.append("</div>")
    out.append("".join(mparts))

    # Project / Procore Signals — grouped.
    signals = synthesis.get("project_signals") or []
    sparts = [
        f"<div class='card'><h2>Project / Procore Signals<span class='count'>{len(signals)}</span></h2>"
    ]
    if signals:
        for g in signals:
            sparts.append(f"<div class='item'><div class='ttl'>{_esc(g.get('project'))}</div>")
            if g.get("summary"):
                sparts.append(f"<div class='meta'>{_esc(g.get('summary'))}</div>")
            for it in g.get("items") or []:
                sparts.append(f"<div class='meta'>· {_fmt_bullet(it)}</div>")
            sparts.append("</div>")
    else:
        sparts.append("<p class='empty'>No Procore project signals were generated in this run.</p>")
    sparts.append("</div>")
    out.append("".join(sparts))

    out.append(
        _bullet_card(
            "Recommended Next Actions",
            [_esc(x) for x in synthesis.get("recommended_next_actions") or []],
            empty="No prioritized next actions generated.",
        )
    )
    out.append(
        _bullet_card(
            "FYI / Low Priority",
            [_esc(x) for x in synthesis.get("fyi_low_priority") or []],
            empty="None.",
        )
    )
    out.append(
        _bullet_card(
            "Needs Review / Data Gaps",
            [_esc(x) for x in synthesis.get("needs_review_data_gaps") or []],
            empty="No data gaps flagged.",
        )
    )
    return "".join(out)


def _render_pending_followup_card(pending: dict[str, Any]) -> str:
    """Render the raw-free V45 pending email follow-up section as a card.

    Deterministic + source-linked + clearly labeled; appears whenever pending review-safe rows
    exist (independent of model synthesis). Returns "" when the section is unavailable/empty so the
    brief is unchanged when there is nothing to surface. Every dynamic value is scrubbed + escaped.
    """
    if not pending or not pending.get("available") or not pending.get("items"):
        return ""
    items = pending.get("items") or []
    label = pending.get("label") or "Model-enriched / pending review"
    out = [f"<div class='card'><h2>{_esc(label)}<span class='count'>{len(items)}</span></h2>"]
    out.append(
        "<p class='meta'>Pending V45 email follow-up enrichments — model-enriched, raw-free, "
        "source-linked; awaiting your review (advisory, not accepted fact).</p>"
    )
    for it in items:
        title = _esc(it.get("enriched_title") or "(untitled)")
        out.append("<div class='item'>")
        out.append(
            f"<div class='ttl'>{title} <span class='cid'>({_esc(it.get('label'))})</span></div>"
        )
        meta = [
            "waiting: " + _esc(it.get("waiting_state")),
            "assignee: " + _esc(it.get("assignee_type")),
            f"confidence: {_esc(it.get('confidence_band'))} ({float(it.get('confidence') or 0.0):.2f})",
        ]
        if it.get("suggested_next_action"):
            meta.append("next: " + _esc(it.get("suggested_next_action")))
        if it.get("due_at_utc"):
            meta.append("due: " + _esc(it.get("due_at_utc")))
        out.append(f"<div class='meta'>{' · '.join(meta)}</div>")
        refs = ", ".join(_esc(s) for s in (it.get("source_refs") or [])) or "(none)"
        out.append(
            f"<div class='cid'>enrichment: {_esc(it.get('enrichment_id'))} · "
            f"candidate: {_esc(it.get('candidate_id'))} · "
            f"watch: {_esc(it.get('watch_item_id') or '(none)')} · refs: [{refs}]</div></div>"
        )
    if pending.get("omitted_low_confidence"):
        out.append(
            f"<p class='meta'>{int(pending['omitted_low_confidence'])} "
            "low-confidence item(s) omitted.</p>"
        )
    out.append("</div>")
    return "".join(out)


_MEI_DISPLAY_SECTIONS: tuple[tuple[str, str], ...] = (
    ("top_priorities", "Top Priorities"),
    ("open_loops", "Open Loops"),
    ("waiting_on_me", "Waiting on Me"),
    ("waiting_on_others", "Waiting on Others"),
    ("meeting_prep", "Meeting Prep"),
    ("project_risk", "Project / Procore Risk"),
)


def _render_pending_items(items: list[dict[str, Any]]) -> list[str]:
    """Raw-free pending V45 follow-up item markup (scrubbed + escaped). Shared by the MEI card."""
    out: list[str] = []
    for it in items:
        title = _esc(it.get("enriched_title") or "(untitled)")
        out.append("<div class='item'>")
        out.append(
            f"<div class='ttl'>{title} <span class='cid'>({_esc(it.get('label'))})</span></div>"
        )
        meta = [
            "waiting: " + _esc(it.get("waiting_state")),
            "assignee: " + _esc(it.get("assignee_type")),
            f"confidence: {_esc(it.get('confidence_band'))} ({float(it.get('confidence') or 0.0):.2f})",
        ]
        if it.get("suggested_next_action"):
            meta.append("next: " + _esc(it.get("suggested_next_action")))
        if it.get("due_at_utc"):
            meta.append("due: " + _esc(it.get("due_at_utc")))
        out.append(f"<div class='meta'>{' · '.join(meta)}</div>")
        refs = ", ".join(_esc(s) for s in (it.get("source_refs") or [])) or "(none)"
        out.append(
            f"<div class='cid'>enrichment: {_esc(it.get('enrichment_id'))} · "
            f"candidate: {_esc(it.get('candidate_id'))} · "
            f"watch: {_esc(it.get('watch_item_id') or '(none)')} · refs: [{refs}]</div></div>"
        )
    return out


def _render_model_enriched_card(mei: dict[str, Any]) -> str:
    """Render the single converged **Model Enriched Intelligence** card (advisory + pending V45).

    Exact-label section combining the source-linked advisory bullets and the raw-free pending email
    follow-up enrichments. Withheld/degraded → honest banner, no advisory body; pending rows (which
    are deterministic) still render so the section survives the degraded path. Every dynamic value is
    scrubbed + escaped.
    """
    label = str(mei.get("label") or "Model Enriched Intelligence")
    available = bool(mei.get("available"))
    intel = mei.get("intelligence") if available else None
    pending = mei.get("pending_followup") or {}
    pending_items = pending.get("items") or []
    kept = int(mei.get("bullets_kept") or 0)
    count = kept + len(pending_items)
    out = [f"<div class='card'><h2>{_esc(label)}<span class='count'>{count}</span></h2>"]
    out.append(
        "<p class='meta'>Advisory, source-linked, local-model enrichment of the deterministic "
        "brief. Not accepted fact.</p>"
    )
    if not available:
        reason = mei.get("withheld_reason") or ("disabled" if not mei.get("enabled") else "withheld")
        out.append(
            f"<div class='meta'>⚠ Model-enriched advisory withheld (reason: {_esc(reason)}). "
            "The deterministic brief is authoritative.</div>"
        )
    else:
        catchup = (intel or {}).get("executive_catchup") or []
        if catchup:
            out.append("<div class='item'><div class='ttl'>Executive Catch-Up</div>")
            out.append(
                "<div class='meta'>" + " · ".join(_esc(c) for c in catchup) + "</div></div>"
            )
        for section, heading in _MEI_DISPLAY_SECTIONS:
            bullets = (intel or {}).get(section) or []
            if not bullets:
                continue
            out.append(f"<div class='item'><div class='ttl'>{_esc(heading)}</div>")
            for b in bullets:
                refs = ", ".join(_esc(str(s)[:18]) for s in (b.get("source_ids") or []) if s)
                tail = f" <span class='cid'>sources: {refs}</span>" if refs else ""
                out.append(f"<div class='meta'>· {_esc(b.get('text'))}{tail}</div>")
            out.append("</div>")
    if pending_items:
        out.append(
            "<div class='item'><div class='ttl'>Pending Email Follow-Up Enrichments"
            f" <span class='count'>{len(pending_items)}</span></div>"
            "<div class='meta'>Model-enriched, raw-free, source-linked; awaiting review "
            "(advisory, not accepted fact).</div></div>"
        )
        out.extend(_render_pending_items(pending_items))
        if pending.get("omitted_low_confidence"):
            out.append(
                f"<p class='meta'>{int(pending['omitted_low_confidence'])} "
                "low-confidence item(s) omitted.</p>"
            )
    out.append("</div>")
    return "".join(out)


def _render_section_cards(sections: list[dict[str, Any]], *, heading_prefix: str = "") -> str:
    """Render the deterministic candidate sections (used as audit appendix / degraded fallback)."""
    out: list[str] = []
    if not sections:
        out.append("<div class='card'><p class='empty'>No candidates for this date.</p></div>")
    for sec in sections:
        disp = _esc(heading_prefix + str(sec.get("display", "")))
        count = int(sec.get("item_count", sec.get("section_count", 0)) or 0)
        out.append(f"<div class='card'><h2>{disp}<span class='count'>{count}</span></h2>")
        items = sec.get("items") or []
        if not items:
            out.append("<p class='empty'>None.</p>")
        for it in items:
            # Real subject (LOCAL --raw only) takes precedence; else the sanitized display line.
            title = _esc(it.get("raw_title") or it.get("display") or "(untitled)")
            meta_bits: list[str] = []
            if it.get("raw_detail"):
                meta_bits.append(_esc(it.get("raw_detail")))
            cid = _esc(it.get("candidate_id") or "")
            out.append("<div class='item'>")
            out.append(f"<div class='ttl'>{title}</div>")
            if meta_bits:
                out.append(f"<div class='meta'>{' · '.join(meta_bits)}</div>")
            out.append(f"<div class='cid'>id: {cid}</div></div>")
        out.append("</div>")
    return "".join(out)


def render_daily_run_html(
    *,
    brief_date: str,
    status: str,
    sections: list[dict[str, Any]],
    summary: dict[str, Any],
    warnings: list[str],
    generated_label: str,
    date_policy: dict[str, Any] | None = None,
    extra_section_label: str | None = None,
    synthesis: dict[str, Any] | None = None,
    model_metadata: dict[str, Any] | None = None,
    degraded: bool = False,
    deterministic_fallback: bool = False,
    pending_followup: dict[str, Any] | None = None,
    model_enriched: dict[str, Any] | None = None,
) -> str:
    """Build the self-contained browser brief HTML. All dynamic content is scrubbed + escaped.

    When ``synthesis`` (a validated :class:`DailyBriefSynthesis` dump) is supplied and not
    ``degraded``, the nine synthesized operator sections are the primary content and the deterministic
    ``sections`` render as a collapsed "Source-Linked Candidates (audit)" appendix. When ``degraded``
    (or no synthesis), a degraded banner is shown and the deterministic sections are the fallback body.

    ``pending_followup`` (the raw-free V45 pending email follow-up section) is rendered as its own
    deterministic card before the brief body whenever pending review-safe rows exist — independent of
    model synthesis, so it survives the degraded path.
    """
    status_cls = _STATUS_CLASS.get(status, "warn")
    status_text = {
        "success": "Success — fresh local-model brief generated this run",
        "deterministic_success_synthesis_degraded": (
            "Deterministic brief published — model synthesis degraded; operator-usable "
            "(usefulness gate passed)"
        ),
        "partial": "Partial — a pipeline stage failed; see warnings",
        "degraded": "Degraded — deterministic usefulness gate failed; last good is preserved",
        "failure": "Failure — brief not generated this run; last good is preserved",
        "skipped_weekend": "Skipped — weekend run, no fresh brief generated",
    }.get(status, status)

    parts: list[str] = []
    parts.append("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append(f"<title>Daily Brief — {_esc(brief_date)}</title>")
    parts.append(f"<style>{_CSS}</style></head><body><div class='wrap'>")
    parts.append(f"<h1>Daily Brief — {_esc(brief_date)}</h1>")
    model_sub = ""
    if model_metadata:
        model_sub = (
            f" · model {_esc(model_metadata.get('model_name'))} "
            f"(profile {_esc(model_metadata.get('profile_id'))}, {_esc(model_metadata.get('status'))})"
        )
    parts.append(
        f"<p class='sub'>Local-agent family · advisory · generated {_esc(generated_label)}{model_sub}</p>"
    )
    parts.append(f"<div class='banner {status_cls}'>{_esc(status_text)}</div>")

    if degraded:
        reason = (model_metadata or {}).get("degraded_reason") or (model_metadata or {}).get(
            "status"
        )
        if deterministic_fallback:
            # Operator-usable: the usefulness gate passed; the deterministic source-linked brief is
            # published as a safe fallback (NOT the same class as an unusable/degraded brief).
            parts.append(
                "<div class='banner ok'>✓ Deterministic source-linked brief published. "
                f"Local-model synthesis was degraded: {_esc(reason)}. This brief is operator-usable "
                "because the deterministic usefulness gate passed.</div>"
            )
        else:
            parts.append(
                "<div class='banner fail'>⚠ DEGRADED — local-model synthesis unavailable "
                f"(reason: {_esc(reason)}). Showing deterministic source-linked candidates; "
                "this run is NOT counted as successful.</div>"
            )

    if extra_section_label:
        parts.append(f"<div class='banner ok'>{_esc(extra_section_label)}</div>")

    if date_policy:
        parts.append("<div class='policy'>")
        parts.append(f"<span class='lbl'>{_esc(date_policy.get('label', ''))}</span>")
        parts.append(f"<div>{_esc(date_policy.get('explanation', ''))}</div><dl>")
        for k in (
            "run_date",
            "run_weekday",
            "previous_business_day",
            "next_business_day",
            "lookback_start",
            "lookback_end",
            "lookahead_start",
            "lookahead_end",
            "calendar_prep_start",
            "calendar_prep_end",
        ):
            if k in date_policy:
                parts.append(f"<dt>{_esc(k)}</dt><dd>{_esc(date_policy.get(k))}</dd>")
        parts.append("</dl></div>")

    if warnings:
        parts.append("<div class='policy'><span class='lbl'>warnings</span><dl>")
        for w in warnings:
            parts.append(f"<dt>·</dt><dd>{_esc(w)}</dd>")
        parts.append("</dl></div>")

    # Converged Model Enriched Intelligence section (advisory bullets + pending V45 rows under one
    # exact label). When supplied it replaces the standalone pending card so the operator sees ONE
    # coherent section. Legacy callers (no model_enriched) keep the standalone pending card.
    if model_enriched is not None:
        parts.append(_render_model_enriched_card(model_enriched))
    else:
        # V45 pending email follow-up enrichments — deterministic, raw-free, surfaced regardless of
        # synthesis state (so the degraded path keeps it too).
        pending_card = _render_pending_followup_card(pending_followup or {})
        if pending_card:
            parts.append(pending_card)

    if synthesis and not degraded:
        parts.append(_render_synthesis_cards(synthesis))
        parts.append(
            "<div class='card'><h2>Appendix: Source-Linked Candidates (audit)"
            f"<span class='count'>{sum(int(s.get('section_count', 0) or 0) for s in sections)}</span></h2>"
            "<p class='meta'>Deterministic, redacted source rows backing the synthesized brief above.</p></div>"
        )
        parts.append(_render_section_cards(sections))
    else:
        parts.append(_render_section_cards(sections))

    rendered = int(summary.get("rendered", 0) or 0)
    parts.append(
        f"<div class='foot'>{rendered} candidate(s) · brief {_esc(brief_date)} · "
        f"generated {_esc(generated_label)} · local consumption only</div>"
    )
    parts.append("</div></body></html>")
    return "".join(parts)
