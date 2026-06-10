"""Phase 10 — local model routing diagnostics (operator-facing, raw-free, fail-closed).

A single consolidated surface that sweeps **every** routed task family and reports, per family: the
selected profile, the ordered candidate model chain, availability/probe status, the fallback reason
(when a non-primary profile is chosen), the fail-closed reason (when blocked), and the declared output
safety category. Deterministic given ``present_models``; never persists or echoes raw prompts/
responses; never routes to cloud. Built on the existing :func:`route_task_family` decision.
"""

from __future__ import annotations

from typing import Any, Optional

from .contracts import load_local_model_profiles
from .model_router import load_local_model_task_routing, route_task_family

#: Declared output safety posture per task family (all advisory; redacted output; no raw persistence).
TASK_SAFETY_CATEGORY: dict[str, str] = {
    "email_action_extraction_json": "metadata_only_advisory",
    "daily_brief_synthesis_quality": "redacted_advisory",
    "short_operator_catchup": "redacted_advisory",
    "calendar_prep_summary": "redacted_advisory",
    "procore_digest_summary": "metadata_only_advisory",
    "relationship_scoring": "metadata_only_advisory",
    "email_followup_raw_enrichment": "bounded_raw_input_redacted_output",
}
_DEFAULT_SAFETY_CATEGORY = "redacted_advisory"


def build_routing_diagnostics(
    *,
    present_models: Optional[set[str]],
    daemon_reachable: bool,
    heavy_enabled: bool = False,
) -> dict[str, Any]:
    """Build consolidated routing diagnostics across all routed task families (raw-free).

    ``present_models`` is the set of installed local model names; ``daemon_reachable`` False (or
    ``present_models`` None) means availability is unknown → every family reports fail-closed rather
    than substituting cloud. Returns a structured, operator-inspectable dict.
    """
    try:
        routing = load_local_model_task_routing()
        profiles = load_local_model_profiles()
    except Exception as exc:  # config error → fail closed, deterministically
        return {
            "command": "second-brain local-model diagnostics",
            "ok": False,
            "error": f"config_error:{str(exc)[:80]}",
            "diagnostics": [],
            "guardrails": _GUARDRAILS,
        }

    probe_models = present_models if daemon_reachable else None
    diagnostics: list[dict[str, Any]] = []
    for family in sorted(routing.routes.keys()):
        rr = route_task_family(
            family,
            profiles=profiles,
            routing=routing,
            present_models=probe_models,
            heavy_enabled=heavy_enabled,
        )
        considered = rr.considered or []
        fallback_reason = None
        fallback_from = None
        if rr.reason_code == "selected_fallback" and considered:
            fallback_from = considered[0].get("profile_id")
            fallback_reason = considered[0].get("reason")
        diagnostics.append(
            {
                "task_family": family,
                "selected_profile": rr.selected_profile,
                "model_name": rr.model_name,
                "available": rr.available,
                "blocked": rr.blocked,
                "reason_code": rr.reason_code,
                "candidate_model_chain": [
                    {
                        "profile_id": c.get("profile_id"),
                        "model_name": c.get("model_name"),
                        "available": c.get("available"),
                        "reason": c.get("reason"),
                    }
                    for c in considered
                ],
                "fallback_from": fallback_from,
                "fallback_reason": fallback_reason,
                "fail_closed_reason": rr.reason_code if rr.blocked else None,
                "blockers": rr.blockers,
                "safety_category": TASK_SAFETY_CATEGORY.get(family, _DEFAULT_SAFETY_CATEGORY),
                "no_cloud": rr.no_cloud,
            }
        )

    counts = {
        "total": len(diagnostics),
        "available": sum(1 for d in diagnostics if d["available"]),
        "blocked": sum(1 for d in diagnostics if d["blocked"]),
        "fallback_selected": sum(1 for d in diagnostics if d["reason_code"] == "selected_fallback"),
    }
    return {
        "command": "second-brain local-model diagnostics",
        "ok": True,
        "daemon_reachable": daemon_reachable,
        "present_models": sorted(present_models) if present_models else [],
        "heavy_enabled": heavy_enabled,
        "counts": counts,
        "diagnostics": diagnostics,
        "guardrails": _GUARDRAILS,
    }


_GUARDRAILS = {
    "local_only": True,
    "no_cloud": True,
    "no_raw_persistence": True,
    "no_raw_prompts_or_responses_in_output": True,
    "deterministic_fallback": True,
    "fail_closed_on_unavailable": True,
}


def render_routing_diagnostics_markdown(diag: dict[str, Any]) -> str:
    """Render routing diagnostics as legible, raw-free operator markdown."""
    if not diag.get("ok"):
        return f"# Local Model Routing Diagnostics\n\n_Unavailable: {diag.get('error')}_\n"
    counts = diag.get("counts", {})
    lines = [
        "# Local Model Routing Diagnostics",
        "",
        f"_daemon reachable: {diag.get('daemon_reachable')} · present models: "
        f"{', '.join(diag.get('present_models') or []) or '(none probed)'} · "
        f"heavy enabled: {diag.get('heavy_enabled')}_",
        "",
        "## Summary",
        f"- task families: {counts.get('total', 0)} · available: {counts.get('available', 0)} · "
        f"blocked (fail-closed): {counts.get('blocked', 0)} · "
        f"fallback-selected: {counts.get('fallback_selected', 0)}",
        "",
        "## Per task family",
    ]
    for d in diag.get("diagnostics", []):
        chain = " → ".join(
            f"{c['profile_id']}({c['model_name']}):{c['reason']}"
            for c in d.get("candidate_model_chain", [])
        ) or "(none)"
        status = (
            f"selected `{d['selected_profile']}` ({d['model_name']})"
            if d["available"]
            else f"BLOCKED ({d['fail_closed_reason']})"
        )
        lines.append(
            f"- **{d['task_family']}** → {status} · reason `{d['reason_code']}` · "
            f"safety `{d['safety_category']}` · no-cloud {d['no_cloud']}"
        )
        lines.append(f"  - chain: {chain}")
        if d.get("fallback_reason"):
            lines.append(
                f"  - fallback: primary `{d['fallback_from']}` unavailable ({d['fallback_reason']})"
            )
    return "\n".join(lines) + "\n"
