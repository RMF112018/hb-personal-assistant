"""Phase 10 convergence — the unified **Model Enriched Intelligence** section (default-on, raw-safe).

Converges the two existing, tested local-model surfaces into ONE operator-facing section without
merging their upstream model calls:

* the source-linked advisory **daily-brief intelligence adapter**
  (:func:`daily_brief_intelligence.build_daily_brief_intelligence`), and
* the review-safe **V45 pending email follow-up enrichments**
  (:func:`daily_brief.email_followup_pending.build_pending_email_enrichment_section`).

Convergence happens at the render/status contract layer (this module + the render surfaces), NOT by
forcing a single model call — the narrative synthesis brief body stays unchanged. The two model calls
(synthesis for the body, the adapter for these bullets) are intentional and documented; see
``docs/evidence/phase-10-top3-local-model-agent-convergence/04-unified-design-contract.md``.

Hard rules (inherited from the two composed paths):
* Every advisory bullet cites ≥1 real candidate id (the adapter drops unsourced bullets; zero
  survivors ⇒ the body is withheld and the deterministic brief is preserved).
* Pending rows are raw-free, source-linked, clearly labeled advisory — never accepted fact.
* The model being unavailable yields a deterministic, explicitly-degraded/withheld section; the
  pending rows (deterministic) still surface.
* No raw prompt/response/body, full URL, token, email, or unsafe HTML is ever produced here.

The rendered section label is EXACTLY ``Model Enriched Intelligence`` (operator-facing requirement).
"""

from __future__ import annotations

from typing import Any, Optional

from ..daily_brief.email_followup_pending import (
    SECTION_KEY as _PENDING_SECTION_KEY,
)
from ..daily_brief.email_followup_pending import (
    build_pending_email_enrichment_section,
    render_pending_enrichment_markdown,
)
from .daily_brief_intelligence import (
    DailyBriefIntelligenceResult,
    build_daily_brief_intelligence,
)

#: The single, exact, operator-facing section label (must not change).
MODEL_ENRICHED_INTELLIGENCE_LABEL = "Model Enriched Intelligence"

#: The adapter bullet sections, in display order, with human headings.
_DISPLAY_SECTIONS: tuple[tuple[str, str], ...] = (
    ("top_priorities", "Top Priorities"),
    ("open_loops", "Open Loops"),
    ("waiting_on_me", "Waiting on Me"),
    ("waiting_on_others", "Waiting on Others"),
    ("meeting_prep", "Meeting Prep"),
    ("project_risk", "Project / Procore Risk"),
)

_GUARDRAILS = {
    "label_exact": True,
    "advisory_only": True,
    "source_linked": True,
    "no_raw_persistence": True,
    "no_cloud": True,
    "deterministic_fallback_preserved": True,
}


def _short_id(value: Any) -> str:
    """Short, stable trace indicator (candidate ids are deterministic hashes, not private)."""
    s = str(value or "")
    return s[:18] if s else ""


def _source_link_count(intelligence: Optional[dict[str, Any]]) -> int:
    """Distinct candidate ids cited across all kept advisory bullets (0 when withheld/empty)."""
    if not intelligence:
        return 0
    cited: set[str] = set()
    for section, _heading in _DISPLAY_SECTIONS:
        for bullet in intelligence.get(section) or []:
            for sid in bullet.get("source_ids") or []:
                if sid:
                    cited.add(str(sid))
    return len(cited)


def _pending_block(pending_section: dict[str, Any]) -> dict[str, Any]:
    """Compact, raw-free pending-enrichment block for the unified object/status."""
    return {
        "count": int(pending_section.get("count") or 0),
        "items": list(pending_section.get("items") or []),
        "omitted_low_confidence": int(pending_section.get("omitted_low_confidence") or 0),
        "dropped_leak": int(pending_section.get("dropped_leak") or 0),
        "available": bool(pending_section.get("available")),
        "degraded_reason": pending_section.get("degraded_reason"),
    }


def _disabled_envelope(
    *, pending_section: dict[str, Any], generated_utc: str
) -> dict[str, Any]:
    pending = _pending_block(pending_section)
    return {
        "enabled": False,
        "available": False,
        "label": MODEL_ENRICHED_INTELLIGENCE_LABEL,
        "generated_utc": generated_utc,
        "degraded": False,
        "withheld_reason": "disabled",
        "candidate_count": 0,
        "candidate_freshness": "",
        "source_link_count": 0,
        "source_link_coverage": 0.0,
        "bullets_seen": 0,
        "bullets_kept": 0,
        "bullets_dropped": 0,
        "unknown_source_ids_count": 0,
        "pending_followup_count": pending["count"],
        "route_selected_profile": "",
        "route_model_name": "",
        "terminal_profile_id": "",
        "generation_profile_id": "",
        "fallback_chain": [],
        "warnings": [],
        "guardrails": dict(_GUARDRAILS),
        "intelligence": None,
        "pending_followup": pending,
    }


def build_model_enriched_intelligence(
    *,
    store: Any,
    brief_date: Optional[str],
    enabled: bool = True,
    dry_run: bool = True,
    generation_mode: str = "pipeline_apply",
    present_models: set[str] | None = None,
    profiles: Optional[Any] = None,
    backend: Optional[Any] = None,
    candidates: Optional[list[dict[str, Any]]] = None,
    intelligence_result: Optional[DailyBriefIntelligenceResult] = None,
    pending_section: Optional[dict[str, Any]] = None,
    generated_utc: str = "",
    probe_models: bool = True,
) -> dict[str, Any]:
    """Build the unified ``Model Enriched Intelligence`` object (raw-safe, fail-closed, default-on).

    Composes the source-linked intelligence-adapter result with the V45 pending follow-up rows. The
    pending section is always built (deterministic) so it survives a disabled/degraded model. When
    ``enabled`` is False the adapter is not run. ``intelligence_result``/``pending_section``/
    ``candidates`` may be injected for offline tests; otherwise they are resolved here. ``backend``
    (an injected ``GenerationBackend``) bypasses the live model probe. Returns the status/render dict
    documented in ``04-unified-design-contract.md``.
    """
    # Pending rows are deterministic — always available regardless of model state / enable flag.
    if pending_section is None:
        try:
            pending_section = build_pending_email_enrichment_section(store)
        except Exception as exc:  # advisory only — never raise into the daily run
            pending_section = {
                "section": _PENDING_SECTION_KEY,
                "label": MODEL_ENRICHED_INTELLIGENCE_LABEL,
                "available": False,
                "degraded_reason": f"pending_error:{str(exc)[:80]}",
                "count": 0,
                "items": [],
            }

    if not enabled:
        return _disabled_envelope(pending_section=pending_section, generated_utc=generated_utc)

    # Resolve the advisory intelligence adapter result (the source-linked bullets).
    if intelligence_result is None:
        if candidates is None:
            try:
                candidates = (
                    store.list_daily_brief_action_candidates(brief_date=brief_date, limit=200)
                    if brief_date
                    else []
                )
            except Exception:
                candidates = []
        if profiles is None:
            from .contracts import load_local_model_profiles

            profiles = load_local_model_profiles()
        # Probe installed local models (read-only) unless a backend is injected or probing is off.
        if present_models is None and backend is None and probe_models:
            try:
                from .provider import build_local_model_status

                status = build_local_model_status(provider_name="ollama")
                present_models = (
                    {str(m) for m in (status.get("present_models") or [])}
                    if status.get("daemon_reachable")
                    else None
                )
            except Exception:
                present_models = None
        intelligence_result = build_daily_brief_intelligence(
            candidates=candidates or [],
            profiles=profiles,
            present_models=present_models,
            backend=backend,
            dry_run=dry_run,
            store=store,
            brief_date=brief_date,
            generation_mode=generation_mode,
        )

    r = intelligence_result
    metrics = r.metrics or {}
    intel = r.intelligence if r.enriched else None
    available = bool(r.enriched)
    pending = _pending_block(pending_section)

    return {
        "enabled": True,
        "available": available,
        "label": MODEL_ENRICHED_INTELLIGENCE_LABEL,
        "generated_utc": generated_utc,
        "degraded": not available,
        "withheld_reason": r.withheld_reason,
        "candidate_count": int(r.candidate_count or 0),
        "candidate_freshness": r.candidate_freshness or "",
        "source_link_count": _source_link_count(intel),
        "source_link_coverage": float(metrics.get("source_link_coverage") or 0.0),
        "bullets_seen": int(metrics.get("model_bullets_seen") or 0),
        "bullets_kept": int(metrics.get("bullets_kept") or 0),
        "bullets_dropped": int(metrics.get("bullets_dropped") or 0),
        "unknown_source_ids_count": int(metrics.get("unknown_source_ids_count") or 0),
        "pending_followup_count": pending["count"],
        "route_selected_profile": r.route_selected_profile or "",
        "route_model_name": r.route_model_name or "",
        "terminal_profile_id": r.terminal_profile_id or "",
        "generation_profile_id": r.generation_profile_id or "",
        "fallback_chain": list(r.fallback_chain or []),
        "warnings": list(r.warnings or []),
        "guardrails": dict(_GUARDRAILS),
        "intelligence": intel,
        "pending_followup": pending,
    }


def status_block(mei: dict[str, Any]) -> dict[str, Any]:
    """Compact, raw-safe status block for the status file / run JSON (counts + metadata only)."""
    return {
        "enabled": bool(mei.get("enabled")),
        "available": bool(mei.get("available")),
        "label": mei.get("label") or MODEL_ENRICHED_INTELLIGENCE_LABEL,
        "degraded": bool(mei.get("degraded")),
        "withheld_reason": mei.get("withheld_reason"),
        "candidate_count": int(mei.get("candidate_count") or 0),
        "source_link_count": int(mei.get("source_link_count") or 0),
        "source_link_coverage": float(mei.get("source_link_coverage") or 0.0),
        "bullets_seen": int(mei.get("bullets_seen") or 0),
        "bullets_kept": int(mei.get("bullets_kept") or 0),
        "bullets_dropped": int(mei.get("bullets_dropped") or 0),
        "unknown_source_ids_count": int(mei.get("unknown_source_ids_count") or 0),
        "pending_followup_count": int(mei.get("pending_followup_count") or 0),
        "route_selected_profile": mei.get("route_selected_profile") or "",
        "route_model_name": mei.get("route_model_name") or "",
        "terminal_profile_id": mei.get("terminal_profile_id") or "",
        "generation_profile_id": mei.get("generation_profile_id") or "",
        "fallback_chain": list(mei.get("fallback_chain") or []),
        "warnings": list(mei.get("warnings") or []),
    }


def render_model_enriched_markdown(mei: dict[str, Any]) -> str:
    """Render the unified section as raw-free markdown under the exact label (Obsidian/audit surface).

    Always emits the ``## Model Enriched Intelligence`` heading. When the advisory body is withheld
    (model unavailable / no source-linked bullets / disabled), it renders an honest banner and still
    surfaces the deterministic pending follow-up subsection when present. Returns the section text
    (never empty — the heading always renders so the operator sees the section exists).
    """
    lines: list[str] = [f"## {MODEL_ENRICHED_INTELLIGENCE_LABEL}", ""]
    lines.append(
        "_Advisory, source-linked, local-model enrichment of the deterministic brief. "
        "Not accepted fact._"
    )
    lines.append("")

    intel = mei.get("intelligence") if mei.get("available") else None
    if not mei.get("available"):
        reason = mei.get("withheld_reason") or ("disabled" if not mei.get("enabled") else "withheld")
        lines.append(
            f"> ⚠ Model-enriched advisory withheld (reason: {reason}). "
            "The deterministic brief above is authoritative."
        )
        lines.append("")
    else:
        catchup = (intel or {}).get("executive_catchup") or []
        if catchup:
            lines.append("### Executive Catch-Up")
            lines.extend(f"- {str(c)}" for c in catchup)
            lines.append("")
        for section, heading in _DISPLAY_SECTIONS:
            bullets = (intel or {}).get(section) or []
            if not bullets:
                continue
            lines.append(f"### {heading}")
            for b in bullets:
                refs = ", ".join(_short_id(s) for s in (b.get("source_ids") or []) if s)
                tail = f" · sources: {refs}" if refs else ""
                lines.append(f"- {str(b.get('text') or '').strip()}{tail}")
            lines.append("")

    # Deterministic pending V45 follow-up rows (raw-free) — survive the degraded/withheld path.
    pending = mei.get("pending_followup") or {}
    if pending.get("count"):
        pending_md = render_pending_enrichment_markdown(
            {
                "available": True,
                "label": f"Pending Email Follow-Up Enrichments ({int(pending['count'])})",
                "items": pending.get("items") or [],
                "omitted_low_confidence": pending.get("omitted_low_confidence") or 0,
            }
        )
        if pending_md:
            lines.append(pending_md)
            lines.append("")

    return "\n".join(lines).strip() + "\n"


__all__ = [
    "MODEL_ENRICHED_INTELLIGENCE_LABEL",
    "build_model_enriched_intelligence",
    "status_block",
    "render_model_enriched_markdown",
]
