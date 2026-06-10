"""Phase 10 — Procore monitoring read-model (read-only, degraded-honest, no writeback).

Composes the existing Procore read-models into ONE operator-facing monitoring surface that makes
daily-brief Procore intelligence trustworthy: the endpoint contract status (live-verified vs
degraded/unverified), per-project source-refresh health (current/stale/never), the next operator
action for stale endpoints, and an explicit per-project + overall verdict (healthy / partial_stale /
stale / no_data). Read-only over the persisted ``procore_live_*`` tables + the static endpoint
registry — no live HTTP call, no writeback, no raw values (counts / statuses / timestamps / ids only).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from hb_assistant.procore import endpoints as _ep
from hb_assistant.store.procore_freshness import build_freshness_report

_REFRESH_KEYS = ("current", "stale", "never_synced", "unknown", "operational_total")

# Verdict order (best → worst) for rolling project verdicts up to an overall verdict.
_VERDICT_RANK = {"healthy": 0, "partial_stale": 1, "stale": 2, "no_data": 3, "error": 4}


def _project_verdict(current: int, stale: int, never: int) -> str:
    """Roll per-endpoint freshness counts into one honest project verdict.

    ``no_data`` means nothing has ever synced (all operational endpoints ``never``); ``healthy`` means
    all current; ``partial_stale`` means some current + some stale/never; ``stale`` means none current
    but it is not the all-never case.
    """
    operational_total = current + stale + never
    if operational_total == 0 or never == operational_total:
        return "no_data"
    if stale == 0 and never == 0:
        return "healthy"
    if current > 0:
        return "partial_stale"
    return "stale"


def _degraded_reason(verdict: str, current: int, stale: int, never: int) -> Optional[str]:
    if verdict == "no_data":
        return "no persisted procore_live_* rows for this project (never synced or unmapped)"
    if verdict == "partial_stale":
        return f"{stale + never} endpoint(s) stale/never-synced; {current} fresh"
    if verdict == "stale":
        return "no current endpoints; operational data is stale (some never synced)"
    return None


def build_procore_monitoring_report(
    *,
    now_utc: str,
    project_keys: list[str],
    db_path: Optional[str] = None,
    stale_days: int = 7,
) -> dict[str, Any]:
    """Build the consolidated, degraded-honest Procore monitoring report (read-only)."""
    all_eps = _ep.list_all()
    verified = _ep.list_verified()
    degraded_eps = [e for e in all_eps if not e.live_verified]
    contract = {
        "total_endpoints": len(all_eps),
        "live_verified": len(verified),
        "degraded_or_unverified": len(degraded_eps),
        "degraded_endpoints": sorted(e.endpoint_id for e in degraded_eps),
    }

    dbp = Path(db_path) if db_path else None
    projects: list[dict[str, Any]] = []
    for pk in project_keys:
        try:
            fresh = build_freshness_report(pk, now_utc=now_utc, stale_days=stale_days, db_path=dbp)
        except Exception as exc:  # read-model must never raise → degrade honestly
            projects.append(
                {"project_key": pk, "verdict": "error", "error": str(exc)[:80]}
            )
            continue
        summary = fresh.get("summary", {})
        stale = fresh.get("stale_endpoints", []) or []
        current = int(summary.get("current", 0) or 0)
        stale_n = int(summary.get("stale", 0) or 0)
        never_n = int(summary.get("never_synced", 0) or 0)
        verdict = _project_verdict(current, stale_n, never_n)
        projects.append(
            {
                "project_key": pk,
                "refresh_summary": {k: summary.get(k) for k in _REFRESH_KEYS},
                "stale_endpoint_count": len(stale),
                "stale_endpoints": [
                    {
                        "endpoint_id": s.get("endpoint_id"),
                        "status": s.get("status"),
                        "age_days": s.get("age_days"),
                        "next_action": s.get("recommended_sync_command"),
                    }
                    for s in stale[:20]
                ],
                "verdict": verdict,
                "degraded_reason": _degraded_reason(verdict, current, stale_n, never_n),
            }
        )

    overall = "healthy"
    if projects:
        overall = max(
            (p.get("verdict", "error") for p in projects),
            key=lambda v: _VERDICT_RANK.get(v, 9),
        )
    counts = {
        "projects": len(projects),
        "healthy": sum(1 for p in projects if p.get("verdict") == "healthy"),
        "partial_stale": sum(1 for p in projects if p.get("verdict") == "partial_stale"),
        "stale": sum(1 for p in projects if p.get("verdict") == "stale"),
        "no_data": sum(1 for p in projects if p.get("verdict") == "no_data"),
    }
    return {
        "command": "procore live monitor",
        "ok": True,
        "generated_utc": now_utc,
        "stale_threshold_days": stale_days,
        "endpoint_contract": contract,
        "counts": counts,
        "overall_verdict": overall,
        "projects": projects,
        "guardrails": {
            "read_only": True,
            "no_live_call_performed": True,
            "no_writeback": True,
            "no_raw_values": True,
            "degraded_honest": True,
        },
    }


def render_procore_monitoring_markdown(report: dict[str, Any]) -> str:
    """Render the Procore monitoring report as legible, raw-free operator markdown."""
    if not report.get("ok"):
        return f"# Procore Monitoring Report\n\n_Unavailable: {report.get('error')}_\n"
    c = report.get("endpoint_contract", {})
    counts = report.get("counts", {})
    lines = [
        "# Procore Monitoring Report",
        "",
        f"_Generated {report.get('generated_utc')} · stale threshold "
        f"{report.get('stale_threshold_days')}d · read-only, no live call._",
        "",
        "## Endpoint contract",
        f"- endpoints: {c.get('total_endpoints', 0)} · live-verified: {c.get('live_verified', 0)} · "
        f"degraded/unverified: {c.get('degraded_or_unverified', 0)}",
        f"- degraded endpoints: {', '.join(c.get('degraded_endpoints') or []) or '(none)'}",
        "",
        "## Overall",
        f"- verdict: **{report.get('overall_verdict')}** · projects: {counts.get('projects', 0)} "
        f"(healthy {counts.get('healthy', 0)} · partial_stale {counts.get('partial_stale', 0)} · "
        f"stale {counts.get('stale', 0)} · no_data {counts.get('no_data', 0)})",
        "",
        "## Per project",
    ]
    for p in report.get("projects", []):
        if p.get("verdict") == "error":
            lines.append(f"- **{p.get('project_key')}** → error ({p.get('error')})")
            continue
        rs = p.get("refresh_summary", {})
        lines.append(
            f"- **{p.get('project_key')}** → verdict **{p.get('verdict')}** · "
            f"current {rs.get('current')} · stale {rs.get('stale')} · "
            f"never {rs.get('never_synced')}"
        )
        if p.get("degraded_reason"):
            lines.append(f"  - {p['degraded_reason']}")
        for s in p.get("stale_endpoints", [])[:5]:
            lines.append(
                f"  - stale `{s.get('endpoint_id')}` ({s.get('status')}, age {s.get('age_days')}d) "
                f"→ {s.get('next_action') or '(no action)'}"
            )
    return "\n".join(lines) + "\n"
