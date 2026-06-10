"""Phase 10 — MCP context packet hardening (safe, bounded, source-linked, fail-closed).

Wraps the existing deterministic ``build_daily_brief_context_packet`` (the single context source — no
second contradictory packet path) in an explicit, inspectable **MCP packet contract**: purpose,
generated_at, source window, source-ref summary, candidate summaries, caps applied, the raw categories
that are deliberately omitted, redaction flags, and freshness/quality warnings. A final forbidden-
content gate scans the actual context payload (regex patterns, not the contract's category labels); on
any match the packet **fails closed** — the context is withheld and the redaction trigger is reported,
so a leaking packet is never emitted. Read-only; no external writeback.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from .daily_brief_context_packet import build_daily_brief_context_packet
from .daily_brief_window import compute_daily_brief_window

PACKET_CONTRACT_VERSION = "phase10-mcp-1.0"

#: Raw categories that are NEVER included in the packet (documented for the consumer).
OMITTED_RAW_CATEGORIES: tuple[str, ...] = (
    "raw_email_bodies",
    "raw_document_text",
    "raw_calendar_payloads",
    "raw_procore_payloads",
    "raw_model_prompts",
    "raw_model_responses",
    "html_bodies",
    "signed_urls",
    "download_urls",
    "join_links",
    "bearer_tokens",
    "attendee_arrays",
    "email_address_dumps",
)

# Forbidden CONTENT patterns (scanned over the real payload only — never the category labels above).
_FORBIDDEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "url": re.compile(r"\bhttps?://", re.IGNORECASE),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    "bearer": re.compile(r"\bBearer\s+[A-Za-z0-9._\-+/=]{16,}"),
    "oauth_field": re.compile(r"\b(access_token|refresh_token|client_secret)\b\s*[:=]", re.IGNORECASE),
    "sas": re.compile(r"[?&](sig|sv|se|st|sp|sr)=[^&\s]+", re.IGNORECASE),
    "pem": re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    "email": re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),
}


def _parse_dt(now_utc: str) -> datetime:
    return datetime.fromisoformat(now_utc.replace("Z", "+00:00"))


def scan_for_forbidden_content(payload: Any) -> list[str]:
    """Return the list of forbidden-content categories found in ``payload`` (empty = clean)."""
    blob = json.dumps(payload, default=str)
    return sorted(name for name, rx in _FORBIDDEN_PATTERNS.items() if rx.search(blob))


def _collect_source_ref_summary(context: dict[str, Any]) -> dict[str, Any]:
    """Summarize source refs across the packet (counts only — never the raw refs)."""
    families: dict[str, int] = {}
    total = 0
    blob = json.dumps(context, default=str)
    # Count occurrences of the safe ref-hash keys the context builder emits.
    for key in ("source_ref_hash", "source_ref_hashes", "source_refs", "ref_hash"):
        total += blob.count(f'"{key}"')
    for fam in ("email", "calendar", "document", "procore", "task", "commitment"):
        c = blob.count(f'"{fam}"')
        if c:
            families[fam] = c
    return {"approx_source_ref_mentions": total, "family_mentions": families}


def build_hardened_mcp_packet(
    *,
    store: Any,
    now_utc: str,
    timezone: str = "America/New_York",
    brief_date: Optional[str] = None,
    db_path: Optional[str] = None,
    purpose: str = "daily_brief_local_agent_context",
) -> dict[str, Any]:
    """Build the hardened MCP context packet (contract envelope + fail-closed forbidden-content gate)."""
    window = compute_daily_brief_window(_parse_dt(now_utc), timezone)
    bd = brief_date or window.run_date
    try:
        context = build_daily_brief_context_packet(
            store=store, brief_date=bd, window=window, now_utc=now_utc, db_path=db_path
        )
    except Exception as exc:  # degrade deterministically — never emit a partial/raw packet
        return {
            "packet_contract_version": PACKET_CONTRACT_VERSION,
            "ok": False,
            "purpose": purpose,
            "generated_at": now_utc,
            "brief_date": bd,
            "withheld_reason": f"context_unavailable:{str(exc)[:80]}",
            "redaction_triggered": False,
            "context": None,
            "guardrails": _GUARDRAILS,
        }

    open_c = context.get("open_commitments") or {}
    candidate_summaries = {
        "open_commitments": {k: len(v or []) for k, v in open_c.items()},
        "candidates_by_section": {
            sec: len(items or [])
            for sec, items in (context.get("candidates_by_section") or {}).items()
        },
        "relationships": len(context.get("relationships") or []),
        "procore_signals": len(context.get("procore_signals") or []),
        "calendar": len(context.get("calendar") or []),
    }

    envelope: dict[str, Any] = {
        "packet_contract_version": PACKET_CONTRACT_VERSION,
        "ok": True,
        "purpose": purpose,
        "generated_at": now_utc,
        "brief_date": bd,
        "source_window": context.get("date_window"),
        "candidate_summaries": candidate_summaries,
        "source_ref_summary": _collect_source_ref_summary(context),
        "caps_applied": context.get("caps"),
        "omitted_raw_categories": list(OMITTED_RAW_CATEGORIES),
        "redaction_flags": {
            "titles_redacted": True,
            "refs_hashed": True,
            "raw_bodies_excluded": True,
            "attendees_reduced_to_counts": True,
        },
        "freshness_quality_warnings": context.get("data_gaps") or [],
        "guardrails": _GUARDRAILS,
    }

    # Fail-closed forbidden-content gate over the REAL payload only (not the contract labels).
    leak = scan_for_forbidden_content(context)
    if leak:
        envelope["ok"] = False
        envelope["redaction_triggered"] = True
        envelope["withheld_reason"] = "forbidden_content_detected"
        envelope["leak_categories"] = leak
        envelope["context"] = None
        return envelope

    envelope["redaction_triggered"] = False
    envelope["context"] = context
    return envelope


_GUARDRAILS = {
    "read_only": True,
    "metadata_only_summaries": True,
    "source_refs_hashed": True,
    "no_raw_content": True,
    "no_external_writeback": True,
    "fail_closed_on_forbidden_content": True,
    "deterministic": True,
}


def render_hardened_mcp_packet_markdown(packet: dict[str, Any]) -> str:
    """Render the hardened MCP packet contract as legible, raw-free operator markdown."""
    lines = [
        "# MCP Context Packet",
        "",
        f"_Contract {packet.get('packet_contract_version')} · purpose "
        f"`{packet.get('purpose')}` · generated {packet.get('generated_at')} · "
        f"brief {packet.get('brief_date')}_",
        "",
    ]
    if not packet.get("ok"):
        lines += [
            "## Status: WITHHELD (fail-closed)",
            f"- reason: **{packet.get('withheld_reason')}**",
            f"- redaction triggered: {packet.get('redaction_triggered')}",
        ]
        if packet.get("leak_categories"):
            lines.append(f"- leak categories: {', '.join(packet['leak_categories'])}")
        return "\n".join(lines) + "\n"

    cs = packet.get("candidate_summaries", {})
    lines += [
        "## Candidate summaries (counts only)",
        f"- open commitments: {cs.get('open_commitments')}",
        f"- candidates by section: {cs.get('candidates_by_section')}",
        f"- relationships: {cs.get('relationships')} · procore signals: "
        f"{cs.get('procore_signals')} · calendar: {cs.get('calendar')}",
        "",
        "## Caps applied",
        f"- {packet.get('caps_applied')}",
        "",
        "## Omitted raw categories",
        f"- {', '.join(packet.get('omitted_raw_categories') or [])}",
        "",
        "## Freshness / quality warnings",
    ]
    warnings = packet.get("freshness_quality_warnings") or []
    lines += [f"- {w}" for w in warnings] if warnings else ["- (none)"]
    lines += [
        "",
        "## Safety",
        f"- {packet.get('guardrails')}",
    ]
    return "\n".join(lines) + "\n"
