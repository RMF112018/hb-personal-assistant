"""Phase 10 — daily-run usefulness gate (daily-brief usefulness repair).

The capstone gate: after deterministic projection + model synthesis, decide whether a run is allowed
to be `success`. The audit showed a run reporting `success` while the brief was operator-useless
(empty deterministic sections, 0.0 calendar resolution, 0.0 source-ref coverage, Procore aggregate
sludge). This gate computes those metrics from the PERSISTED candidates + source refs and fails a
would-be `success` that cannot meet the usefulness bar — forcing `partial`/`degraded`, preserving the
last successful brief, and explaining which gate failed.

Read-only: no writeback, no model call. All inputs are already-redacted candidate rows + hashed refs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .daily_brief_candidate_writer import candidate_source_ref_coverage
from .source_ref_gate import EXECUTIVE_SECTIONS, gate_model_candidate_context

# Sections that count as an "operator-useful deterministic section" when non-empty.
_USEFUL_SECTIONS = EXECUTIVE_SECTIONS

# A calendar candidate is "project-like" (should map to a project) when resolved OR flagged for
# review — internal (PTO/training/company) and unknown events are deliberately NOT project-like.
_PROJECT_LIKE_CAL_KEYS_PREFIXLESS = True  # resolved real keys
_NEEDS_REVIEW = "__needs_review__"


@dataclass(frozen=True)
class UsefulnessGateResult:
    passed: bool
    verdict: str  # "useful" | "degraded"
    failed_reasons: list[str]
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "verdict": self.verdict,
            "failed_reasons": self.failed_reasons,
            "metrics": self.metrics,
        }


def evaluate_usefulness_gate(
    *,
    store: Any,
    brief_date: str,
    synthesis_present: bool,
    synthesis_degraded: bool,
    egress_clean: bool = True,
) -> UsefulnessGateResult:
    """Evaluate whether the run meets the usefulness bar for `success` (deterministic + read-only)."""
    candidates = store.list_daily_brief_action_candidates(brief_date=brief_date, limit=100000)

    by_section: dict[str, int] = {}
    for c in candidates:
        sec = str(c.get("section") or "__unassigned__")
        by_section[sec] = by_section.get(sec, 0) + 1
    deterministic_section_count = sum(1 for s in _USEFUL_SECTIONS if by_section.get(s, 0) > 0)

    # Calendar project resolution.
    cal = [c for c in candidates if str(c.get("section")) == "calendar"]
    cal_resolved = [
        c for c in cal if (c.get("project_key") and not str(c.get("project_key")).startswith("__"))
    ]
    cal_project_like = cal_resolved + [
        c for c in cal if str(c.get("project_key")) == _NEEDS_REVIEW
    ]
    calendar_project_resolution_rate = (
        round(len(cal_resolved) / len(cal_project_like), 4) if cal_project_like else 1.0
    )
    unresolved_project_like = len(cal_project_like) - len(cal_resolved)

    # Procore: persisted procore candidates are PROMOTED/ranked rows (aggregate sludge is demoted to
    # diagnostics and never persisted), so executive sludge is 0 by construction.
    procore_executive = sum(1 for c in candidates if str(c.get("section")) == "procore")

    # Source-ref coverage (overall + executive).
    cov = candidate_source_ref_coverage(store, brief_date=brief_date)
    _, gate_report = gate_model_candidate_context(store, brief_date)
    executive_coverage = float(gate_report.get("executive_coverage", 1.0))
    executive_total = int(gate_report.get("executive_total", 0))

    # Contradiction: model synthesis present/usable but deterministic candidates are empty.
    contradiction = bool(synthesis_present and not synthesis_degraded and len(candidates) == 0)

    metrics = {
        "total_candidates": len(candidates),
        "section_counts": by_section,
        "deterministic_section_count": deterministic_section_count,
        "calendar_project_resolution_rate": calendar_project_resolution_rate,
        "calendar_project_like_count": len(cal_project_like),
        "calendar_unresolved_project_like_count": unresolved_project_like,
        "procore_executive_count": procore_executive,
        "procore_aggregate_sludge_selected": 0,
        "source_ref_coverage": cov.get("coverage"),
        "executive_source_ref_coverage": round(executive_coverage, 4),
        "executive_candidate_count": executive_total,
        "synthesis_present": bool(synthesis_present),
        "synthesis_degraded": bool(synthesis_degraded),
        "contradiction_synthesis_without_candidates": contradiction,
        "egress_clean": bool(egress_clean),
    }

    failed: list[str] = []
    if deterministic_section_count < 1:
        failed.append("no_useful_deterministic_section")
    if contradiction:
        failed.append("synthesis_without_deterministic_candidates")
    if executive_total > 0 and executive_coverage < 1.0:
        failed.append("executive_source_ref_coverage_below_100")
    if cal_project_like and len(cal_resolved) == 0:
        failed.append("calendar_project_like_all_unresolved")
    if not egress_clean:
        failed.append("egress_not_clean")

    passed = not failed
    return UsefulnessGateResult(
        passed=passed,
        verdict="useful" if passed else "degraded",
        failed_reasons=failed,
        metrics=metrics,
    )
