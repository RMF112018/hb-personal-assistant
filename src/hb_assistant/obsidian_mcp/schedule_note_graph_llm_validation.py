"""Report-only LLM suggestion validation for schedule graph links (Phase 20)."""

from __future__ import annotations

import json
import re
from typing import Any

from hb_assistant.obsidian_mcp.schedule_note_graph import ScheduleGraphCandidate

_FORBIDDEN_PATH = re.compile(
    r"(/Users/|/Volumes/|/home/|[A-Za-z]:\\|\.\./)",
    re.IGNORECASE,
)

_ALLOWED_RELATIONSHIPS = frozenset(
    {
        "same_project_schedule_note",
        "prior_schedule_update",
        "baseline_comparison_related",
        "controls_to_review_summary",
        "portfolio_to_project_schedule",
        "schedule_note_to_safe_source_card",
        "trust_status_related",
    }
)


def build_suggestion_prompt(
    candidates: list[ScheduleGraphCandidate],
    *,
    max_items: int = 12,
) -> str:
    rows = []
    for cand in candidates[:max_items]:
        rows.append(
            {
                "candidate_key": cand.candidate_key,
                "source_note": cand.source_note,
                "target_note": cand.target_note,
                "relationship_type": cand.relationship_type,
                "confidence": cand.confidence,
                "label": cand.pm_safe_label,
            }
        )
    return (
        "You are reviewing schedule-note graph link candidates for a PM-safe vault. "
        "Pick zero or more candidate_key values that deserve human attention. "
        "Return JSON only: {\"selected_keys\": [\"...\"], \"rationale\": \"...\"}. "
        "Do not invent paths, titles, or relationship types.\n\n"
        f"Candidates:\n{json.dumps(rows, indent=2)}"
    )


def validate_llm_suggestions(
    raw_response: str,
    candidates: list[ScheduleGraphCandidate],
) -> dict[str, Any]:
    violations: list[str] = []
    selected: list[str] = []
    rationale = ""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError:
        return {"passed": False, "violations": ["invalid_json"], "selected_keys": [], "rationale": ""}
    if not isinstance(payload, dict):
        violations.append("not_object")
    else:
        keys = payload.get("selected_keys")
        rationale = str(payload.get("rationale") or "")[:500]
        if keys is None:
            violations.append("missing_selected_keys")
        elif not isinstance(keys, list):
            violations.append("selected_keys_not_list")
        else:
            allowed = {c.candidate_key for c in candidates}
            for key in keys:
                sk = str(key)
                if sk not in allowed:
                    violations.append(f"unknown_candidate_key:{sk}")
                else:
                    selected.append(sk)
    blob = raw_response + rationale
    if _FORBIDDEN_PATH.search(blob):
        violations.append("forbidden_path_leak")
    for cand in candidates:
        if cand.candidate_key in selected and cand.relationship_type not in _ALLOWED_RELATIONSHIPS:
            violations.append(f"disallowed_relationship:{cand.relationship_type}")
    return {
        "passed": not violations,
        "violations": violations,
        "selected_keys": sorted(set(selected)),
        "rationale": rationale,
        "report_only": True,
    }
