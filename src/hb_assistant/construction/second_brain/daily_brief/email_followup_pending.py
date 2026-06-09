"""Phase 10 V45 — daily-brief consumption of pending email follow-up enrichments (raw-free).

Surfaces ``review_status='pending'`` V45 enrichment rows in the daily brief as clearly-labeled,
source-linked, structured items. Never includes raw excerpts, prompts, responses, URLs, tokens,
HTML, or email dumps — only structured/redacted fields + hashes + source/candidate/watch references.

Labeling (authoritative): every pending item is labeled "Model-enriched / pending review". Low-
confidence items are either labeled "low confidence / needs review" or omitted, per the configured
``low_confidence_policy`` + thresholds. Fail-closed/clean degradation: a missing table or no rows
yields an empty, available=False section rather than an error, so the deterministic brief continues.
"""

from __future__ import annotations

from typing import Any

from ..local_ai.email_followup_models import (
    DEFAULT_HIGH_CONFIDENCE,
    DEFAULT_MEDIUM_CONFIDENCE,
    confidence_band_for,
)
from ..local_ai.email_followup_route import find_raw_leak

#: Authoritative labels.
PENDING_LABEL = "Model-enriched / pending review"
LOW_CONFIDENCE_LABEL = "low confidence / needs review"

SECTION_KEY = "email_followup_pending_enrichment"


def build_pending_email_enrichment_section(
    store: Any,
    *,
    limit: int = 50,
    high_confidence: float = DEFAULT_HIGH_CONFIDENCE,
    medium_confidence: float = DEFAULT_MEDIUM_CONFIDENCE,
    low_confidence_policy: str = "label",
    include_reviewed: bool = False,
) -> dict[str, Any]:
    """Build the raw-free pending-enrichment daily-brief section (clean-degrading).

    ``low_confidence_policy`` is ``"label"`` (default; append the low-confidence label) or ``"omit"``
    (drop low-confidence items, counted in ``omitted_low_confidence``). With ``include_reviewed`` the
    section also surfaces accepted rows (without the pending label). A final per-field raw-leak sweep
    drops any item that would leak (defense-in-depth; persisted rows are already guarded).
    """
    try:
        rows = store.list_email_followup_enrichments(
            review_status=None if include_reviewed else "pending", limit=limit
        )
    except Exception as exc:  # missing table / store error → degrade cleanly
        return {
            "section": SECTION_KEY,
            "label": PENDING_LABEL,
            "available": False,
            "degraded_reason": f"enrichment_unavailable:{str(exc)[:80]}",
            "count": 0,
            "omitted_low_confidence": 0,
            "items": [],
            "guardrails": _GUARDRAILS,
        }

    items: list[dict[str, Any]] = []
    omitted_low = 0
    dropped_leak = 0
    for r in rows:
        review_status = str(r.get("review_status") or "pending")
        confidence = float(r.get("confidence") or 0.0)
        band = r.get("confidence_band") or confidence_band_for(
            confidence, high=high_confidence, medium=medium_confidence
        )
        is_low = band == "low"
        if is_low and low_confidence_policy == "omit":
            omitted_low += 1
            continue

        enriched_title = str(r.get("enriched_title") or "")
        suggested = r.get("suggested_next_action")
        assignee_display = r.get("assignee_display")
        reason_codes = list(r.get("reason_codes") or [])
        source_refs = list(r.get("source_refs") or [])
        # Defense-in-depth: never surface a row whose any field leaks raw content.
        if any(
            find_raw_leak(v)
            for v in [enriched_title, str(suggested or ""), str(assignee_display or "")]
            + reason_codes
            + source_refs
        ):
            dropped_leak += 1
            continue

        label = PENDING_LABEL if review_status == "pending" else f"reviewed:{review_status}"
        if is_low:
            label = f"{label} — {LOW_CONFIDENCE_LABEL}"
        items.append(
            {
                "label": label,
                "review_status": review_status,
                "enriched_title": enriched_title,
                "waiting_state": r.get("waiting_state"),
                "assignee_type": r.get("assignee_type"),
                "assignee_display": assignee_display,
                "suggested_next_action": suggested,
                "due_at_utc": r.get("due_at_utc"),
                "confidence": confidence,
                "confidence_band": band,
                "reason_codes": reason_codes,
                # Source-linking (raw-free references only).
                "enrichment_id": r.get("enrichment_id"),
                "candidate_id": r.get("source_candidate_id"),
                "candidate_type": r.get("source_candidate_type"),
                "watch_item_id": r.get("watch_item_id"),
                "source_refs": source_refs,
                "raw_excerpt_hash": r.get("raw_excerpt_hash"),
            }
        )

    return {
        "section": SECTION_KEY,
        "label": PENDING_LABEL,
        "available": True,
        "count": len(items),
        "omitted_low_confidence": omitted_low,
        "dropped_leak": dropped_leak,
        "items": items,
        "guardrails": _GUARDRAILS,
    }


_GUARDRAILS = {
    "raw_excerpts_in_brief": False,
    "model_enriched_labeled": True,
    "source_linked": True,
    "low_confidence_handled": True,
    "clean_degradation": True,
}


def render_pending_enrichment_markdown(section: dict[str, Any]) -> str:
    """Render the pending-enrichment section as raw-free markdown (label + structured fields only).

    Returns an empty string when the section is unavailable / empty, so the deterministic brief is
    unchanged when there is nothing to add.
    """
    if not section.get("available") or not section.get("items"):
        return ""
    lines = [f"### {section['label']}", ""]
    for it in section["items"]:
        title = it.get("enriched_title") or "(untitled)"
        lines.append(f"- **{title}** _({it.get('label')})_")
        lines.append(
            f"  - waiting: {it.get('waiting_state')} · assignee: {it.get('assignee_type')} · "
            f"confidence: {it.get('confidence_band')} ({it.get('confidence'):.2f})"
        )
        if it.get("suggested_next_action"):
            lines.append(f"  - next: {it['suggested_next_action']}")
        if it.get("due_at_utc"):
            lines.append(f"  - due: {it['due_at_utc']}")
        refs = ", ".join(str(s) for s in (it.get("source_refs") or [])) or "(none)"
        lines.append(
            f"  - source: enrichment={it.get('enrichment_id')} candidate={it.get('candidate_id')}"
            f" watch={it.get('watch_item_id') or '(none)'} refs=[{refs}]"
        )
    if section.get("omitted_low_confidence"):
        lines.append("")
        lines.append(
            f"_({section['omitted_low_confidence']} low-confidence item(s) omitted)_"
        )
    return "\n".join(lines)
