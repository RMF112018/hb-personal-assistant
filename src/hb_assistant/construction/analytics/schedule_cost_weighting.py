"""Advisory schedule-informed forecast weighting (approved mappings only)."""

from __future__ import annotations

import json
from typing import Any


def compute_weighting_results(
    *,
    mapping_run_id: str,
    project_key: str,
    schedule_version_key: str,
    approved_candidates: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    approved: bool,
) -> list[dict[str, Any]]:
    if not approved:
        return []

    mapped_ids = {str(c["activity_id"]) for c in approved_candidates}
    total = len(activities)
    unmapped = total - len(mapped_ids & {str(a["activity_id"]) for a in activities})

    by_code: dict[str, int] = {}
    for cand in approved_candidates:
        code = str(cand.get("candidate_cost_code") or "unmapped")
        by_code[code] = by_code.get(code, 0) + 1

    out: list[dict[str, Any]] = []
    for code, count in by_code.items():
        confidence = min(0.95, 0.5 + 0.05 * count)
        modifier = f"{confidence:.2f}"
        out.append(
            {
                "project_key": project_key,
                "schedule_version_key": schedule_version_key,
                "mapping_run_id": mapping_run_id,
                "budget_code_key": code,
                "schedule_risk_score": "0.0",
                "mapping_confidence": f"{confidence:.2f}",
                "forecast_confidence_modifier": modifier,
                "risk_reasons_json": json.dumps(["advisory_schedule_mapping"]),
                "supporting_activity_count": count,
                "unmapped_activity_count": unmapped,
                "operator_review_required": 1,
            }
        )
    return out