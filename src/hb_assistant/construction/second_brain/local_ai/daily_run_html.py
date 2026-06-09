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

_STATUS_CLASS = {"success": "ok", "partial": "warn", "failure": "fail", "skipped_weekend": "skip"}


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
) -> str:
    """Build the self-contained browser brief HTML. All dynamic content is scrubbed + escaped."""
    status_cls = _STATUS_CLASS.get(status, "warn")
    status_text = {
        "success": "Success — fresh brief generated this run",
        "partial": "Partial — some stages failed; items may be stale or missing",
        "failure": "Failure — brief not generated this run; showing last good is preserved",
        "skipped_weekend": "Skipped — weekend run, no fresh brief generated",
    }.get(status, status)

    parts: list[str] = []
    parts.append("<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>")
    parts.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    parts.append(f"<title>Daily Brief — {_esc(brief_date)}</title>")
    parts.append(f"<style>{_CSS}</style></head><body><div class='wrap'>")
    parts.append(f"<h1>Daily Brief — {_esc(brief_date)}</h1>")
    parts.append(
        f"<p class='sub'>Local-agent family · advisory · generated {_esc(generated_label)}</p>"
    )
    parts.append(f"<div class='banner {status_cls}'>{_esc(status_text)}</div>")

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

    if not sections:
        parts.append("<div class='card'><p class='empty'>No candidates for this date.</p></div>")
    for sec in sections:
        disp = _esc(sec.get("display", ""))
        count = int(sec.get("section_count", 0) or 0)
        parts.append(f"<div class='card'><h2>{disp}<span class='count'>{count}</span></h2>")
        items = sec.get("items") or []
        if not items:
            parts.append("<p class='empty'>None.</p>")
        for it in items:
            title = _esc(it.get("display_title") or it.get("title_redacted") or "(untitled)")
            meta_bits: list[str] = []
            if it.get("reason_redacted"):
                meta_bits.append(_esc(it.get("reason_redacted")))
            if it.get("raw_detail"):
                meta_bits.append(_esc(it.get("raw_detail")))
            if it.get("project_key"):
                meta_bits.append("project: " + _esc(it.get("project_key")))
            if it.get("recommended_next_action"):
                meta_bits.append("next: " + _esc(it.get("recommended_next_action")))
            cid = _esc(it.get("candidate_id") or "")
            parts.append("<div class='item'>")
            parts.append(f"<div class='ttl'>{title}</div>")
            if meta_bits:
                parts.append(f"<div class='meta'>{' · '.join(meta_bits)}</div>")
            parts.append(f"<div class='cid'>id: {cid}</div></div>")
        parts.append("</div>")

    rendered = int(summary.get("rendered", 0) or 0)
    parts.append(
        f"<div class='foot'>{rendered} candidate(s) · brief {_esc(brief_date)} · "
        f"generated {_esc(generated_label)} · local consumption only</div>"
    )
    parts.append("</div></body></html>")
    return "".join(parts)
