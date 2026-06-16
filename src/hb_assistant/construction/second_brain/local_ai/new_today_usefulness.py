"""Phase 10 (253) — New Today usefulness/status gate (pure, deterministic).

The daily brief's user-facing product status. *New Today is the daily brief; everything else is
diagnostics.* This gate derives the additive ``daily_brief.status`` from the New Today digest and the
substrate that feeds it — never from legacy synthesis / model-enriched-intelligence health.

Status contract (per the 253 simplification):
  - ``daily_brief.status == "degraded"`` is reserved for **product-relevant** New Today degradation:
    email substrate present but zero actionable follow-up; the email/calendar projection failed or is
    coverage-degraded; the New Today raw-safety fence dropped every built event.
  - Legacy/diagnostic degradation (degraded LLM synthesis, MEI withheld, optional local-model/Ollama
    unavailability) is NOT product degradation — it never sets ``degraded`` and never surfaces an
    above-the-fold warning when deterministic New Today is useful.
  - A genuinely empty refresh window (nothing changed overnight, no source/extraction failure) stays
    ``success`` — "No notable business changes" is a valid brief.
  - ``failed`` is reserved for the case where New Today could not be built/rendered at all (handled by
    the caller's guard, not this function).

Pure: no store, no I/O, no wall-clock.
"""

from __future__ import annotations

from typing import Any, Optional

#: Stable degraded-reason codes (machine-testable; safe for the status JSON and evidence bundle).
REASON_EMAIL_FOLLOWUP_DEGRADED = "email_followup_degraded"
REASON_PROJECTION_DEGRADED = "projection_degraded"
REASON_PROJECTION_COVERAGE_DEGRADED = "projection_coverage_degraded"
REASON_ALL_EVENTS_DROPPED_RAW_SAFETY = "all_events_dropped_raw_safety"


def evaluate_new_today_status(
    *,
    digest: dict[str, Any],
    rendered_total_items: int,
    projection_receipt: Optional[dict[str, Any]] = None,
    model_enrichment_status: str = "not_requested",
) -> dict[str, Any]:
    """Derive the product-facing New Today status from the digest + its substrate.

    ``digest`` is :func:`new_today_digest.build_new_today_digest` output. ``rendered_total_items`` is
    the post-fence item count from :func:`new_today_presentation.build_render_model` (so a fence that
    drops every built event is caught). ``projection_receipt`` is the ``email_calendar_projection``
    stage detail. ``model_enrichment_status`` describes New Today's OWN optional Ollama overlay
    (``used|withheld|unavailable|not_requested``) — distinct from legacy MEI, and never a degraded
    trigger by itself.

    Returns a dict carrying ``status`` (``success|degraded``), ``operator_usable``,
    ``degraded_reasons`` (stable codes), ``visible_warning`` (whether the surfaces should render an
    above-the-fold warning), ``model_enrichment_status``, and ``deterministic_fallback_used``.
    """
    gates = dict(digest.get("gates") or {})
    reasons: list[str] = []

    # Product-relevant: email substrate present but no actionable follow-up could be derived.
    if gates.get("email_degraded"):
        reasons.append(REASON_EMAIL_FOLLOWUP_DEGRADED)

    # Product-relevant: the substrate projection that feeds New Today failed or is coverage-degraded.
    if projection_receipt:
        pstatus = str(projection_receipt.get("status") or "").strip().lower()
        pcoverage = str(projection_receipt.get("projection_coverage_status") or "").strip().lower()
        if pstatus and pstatus not in ("ok", "success", "completed"):
            reasons.append(REASON_PROJECTION_DEGRADED)
        elif pcoverage and pcoverage not in ("ok", "success", ""):
            reasons.append(REASON_PROJECTION_COVERAGE_DEGRADED)

    # Product-relevant: events were built but the raw-safety fence dropped all of them.
    built_events = int(gates.get("total_events") or 0)
    if built_events > 0 and int(rendered_total_items) == 0:
        reasons.append(REASON_ALL_EVENTS_DROPPED_RAW_SAFETY)

    status = "degraded" if reasons else "success"

    # New Today rendered (this function is only reached on a built digest), so the brief is
    # operator-usable even when degraded — the surfaces render a concise above-the-fold warning so the
    # operator knows the trust caveat. Pure diagnostic degradation produces no warning and no reasons.
    return {
        "status": status,
        "operator_usable": True,
        "degraded_reasons": reasons,
        "visible_warning": bool(reasons),
        "model_enrichment_status": model_enrichment_status,
        "deterministic_fallback_used": model_enrichment_status in ("withheld", "unavailable"),
    }
