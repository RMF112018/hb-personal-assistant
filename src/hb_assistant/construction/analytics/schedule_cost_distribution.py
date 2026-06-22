"""Simplified duration-based cost distribution (analytical only)."""

from __future__ import annotations

from typing import Any


def compute_duration_distribution(
    *,
    mapping_run_id: str,
    project_key: str,
    schedule_version_key: str,
    approved_candidates: list[dict[str, Any]],
    activities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Allocate by duration weight within each cost code. Labeled analytical_distribution."""
    act_by_id = {str(a["activity_id"]): a for a in activities}
    by_code: dict[str, list[dict[str, Any]]] = {}
    for cand in approved_candidates:
        code = str(cand.get("candidate_cost_code") or "")
        if code:
            by_code.setdefault(code, []).append(cand)

    out: list[dict[str, Any]] = []
    for code, cands in by_code.items():
        durations: list[tuple[str, float]] = []
        for cand in cands:
            act = act_by_id.get(str(cand["activity_id"]), {})
            try:
                dur = float(act.get("duration_original") or 0)
            except (TypeError, ValueError):
                dur = 0.0
            if dur > 0:
                durations.append((str(cand["activity_id"]), dur))
        total = sum(d for _, d in durations) or 0.0
        if total <= 0:
            continue
        for act_id, dur in durations:
            pct = dur / total
            out.append(
                {
                    "mapping_run_id": mapping_run_id,
                    "project_key": project_key,
                    "schedule_version_key": schedule_version_key,
                    "activity_id": act_id,
                    "budget_code_key": code,
                    "cost_code": code,
                    "allocation_method": "analytical_distribution",
                    "source_financial_record_type": None,
                    "source_financial_record_id": None,
                    "source_value": None,
                    "allocation_percent": f"{pct:.6f}",
                    "allocated_value": None,
                    "operator_approved": 1,
                    "reconciliation_status": "analytical_only",
                }
            )
    return out