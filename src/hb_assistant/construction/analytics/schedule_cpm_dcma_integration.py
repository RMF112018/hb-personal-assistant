"""DCMA critical-path metric integration: eligibility of the application-computed CPM chain.

PHASE 7 SCOPE — EVALUATION ONLY (READ-ONLY UPSTREAM). Decides whether the existing DCMA
critical-path quality metric can be measured from the application-computed CPM chain
(Phases 1-6). It is a pure function: it takes the latest CPM run metadata plus the longest-
path rows and the criticality classification rows for one ``schedule_version_key`` and
returns a typed evaluation. It executes NO SQL and performs NO computation of prior phases.

The metric becomes measurable ONLY when every dependency run is present and successful, the
longest path passes integrity checks, and every longest-path activity is computed_critical
by the Phase 6 classification. It NEVER reads source-export criticality/driving-path/float or
``is_critical`` — measurability derives solely from application-computed CPM results. Any
missing, blocked, or inconsistent dependency keeps the metric not measurable with an explicit
reason (conservative).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DCMA_BASIS_APP_CPM = "application_computed_cpm"
_TOL = 1e-6

# Dependency success statuses (per repo convention).
_FORWARD_OK = "forward_pass_only"
_BACKWARD_OK = "backward_pass_only"
_FLOAT_OK = "forward_backward_float_only"
_LONGEST_PATH_OK = "longest_path_only"
_CRITICALITY_OK = "criticality_classification_only"

# Reason codes (not measurable).
REASON_MISSING_FORWARD = "missing_forward_run"
REASON_MISSING_BACKWARD = "missing_backward_run"
REASON_MISSING_FLOAT = "missing_float_run"
REASON_MISSING_LONGEST_PATH = "missing_longest_path_run"
REASON_MISSING_CRITICALITY = "missing_criticality_run"
REASON_GRAPH_FATAL = "graph_fatal_diagnostic"
REASON_NO_LONGEST_PATH_ROW = "no_longest_path_row"
REASON_PATH_STATUS_NOT_COMPUTED = "longest_path_status_not_computed"
REASON_MISSING_PATH_ACTIVITIES = "longest_path_missing_activities"
REASON_SEQUENCE_NOT_CONTIGUOUS = "longest_path_sequence_not_contiguous"
REASON_MISSING_RELATIONSHIP = "longest_path_missing_relationship"
REASON_FINISH_OFFSET_MISMATCH = "path_finish_offset_mismatch"
REASON_DURATION_INCONSISTENT = "path_duration_inconsistent"
REASON_MEMBER_MISSING_CRITICALITY = "longest_path_member_missing_criticality"
REASON_MEMBER_MISSING_TOTAL_FLOAT = "longest_path_member_missing_total_float"
REASON_MEMBER_UNCLASSIFIED = "longest_path_member_unclassified"
REASON_NOT_COMPUTED_CRITICAL = "longest_path_not_computed_critical"

# Caveat codes (do not fail).
CAVEAT_CRITICAL_OUTSIDE_PATH = "computed_critical_outside_longest_path"

CLASS_CRITICAL = "computed_critical"


@dataclass
class DcmaCriticalPathEvaluation:
    measurable: bool
    basis: str | None
    reason_codes: list[str]
    caveats: list[str]
    dependency_run_ids: dict[str, str | None]
    path_id: str | None
    path_activity_count: int
    computed_critical_activity_count: int
    longest_path_critical_activity_count: int
    evidence: dict[str, Any] = field(default_factory=dict)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _run_id(run: dict[str, Any] | None) -> str | None:
    return str(run.get("cpm_run_id")) if run else None


def evaluate_dcma_critical_path_eligibility(
    *,
    graph_has_fatal: bool,
    forward_run: dict[str, Any] | None,
    backward_run: dict[str, Any] | None,
    float_run: dict[str, Any] | None,
    longest_path_run: dict[str, Any] | None,
    criticality_run: dict[str, Any] | None,
    path_rows: list[dict[str, Any]],
    path_activity_rows: list[dict[str, Any]],
    criticality_activity_rows: list[dict[str, Any]],
    tolerance: float = _TOL,
) -> DcmaCriticalPathEvaluation:
    """Decide DCMA critical-path measurability from the application-computed CPM chain."""
    reasons: list[str] = []
    caveats: list[str] = []
    dependency_run_ids = {
        "forward": _run_id(forward_run),
        "backward": _run_id(backward_run),
        "float": _run_id(float_run),
        "longest_path": _run_id(longest_path_run),
        "criticality": _run_id(criticality_run),
    }

    # --- Dependency presence + success -------------------------------------------------
    for run, ok_status, reason in (
        (forward_run, _FORWARD_OK, REASON_MISSING_FORWARD),
        (backward_run, _BACKWARD_OK, REASON_MISSING_BACKWARD),
        (float_run, _FLOAT_OK, REASON_MISSING_FLOAT),
        (longest_path_run, _LONGEST_PATH_OK, REASON_MISSING_LONGEST_PATH),
        (criticality_run, _CRITICALITY_OK, REASON_MISSING_CRITICALITY),
    ):
        if run is None or run.get("cpm_recalculation_status") != ok_status:
            reasons.append(reason)
    if graph_has_fatal:
        reasons.append(REASON_GRAPH_FATAL)

    path_id: str | None = None
    path_activity_count = 0
    longest_path_critical = 0
    # Total computed_critical across ALL classified activities (context for caveats).
    computed_critical_total = sum(
        1
        for r in criticality_activity_rows
        if str(r.get("computed_criticality_class")) == CLASS_CRITICAL
    )

    # --- Path integrity (only when the longest-path run itself succeeded) --------------
    ordered: list[dict[str, Any]] = []
    if REASON_MISSING_LONGEST_PATH not in reasons:
        primary = [
            p
            for p in path_rows
            if str(p.get("path_type")) == "longest_path" and p.get("path_rank") == 1
        ]
        if not primary:
            reasons.append(REASON_NO_LONGEST_PATH_ROW)
        else:
            path = primary[0]
            path_id = str(path.get("path_id"))
            if str(path.get("path_status")) != "computed":
                reasons.append(REASON_PATH_STATUS_NOT_COMPUTED)
            ordered = sorted(
                (a for a in path_activity_rows if str(a.get("path_id")) == path_id),
                key=lambda a: (a.get("path_sequence") or 0),
            )
            path_activity_count = len(ordered)
            if not ordered:
                reasons.append(REASON_MISSING_PATH_ACTIVITIES)
            else:
                seqs = [a.get("path_sequence") for a in ordered]
                if seqs != list(range(1, len(ordered) + 1)):
                    reasons.append(REASON_SEQUENCE_NOT_CONTIGUOUS)
                if any(
                    a.get("relationship_from_previous_ref") in (None, "")
                    for a in ordered[1:]
                ):
                    reasons.append(REASON_MISSING_RELATIONSHIP)
                start_off = _as_float(ordered[0].get("early_start_offset_days"))
                end_finish = _as_float(ordered[-1].get("early_finish_offset_days"))
                path_finish = _as_float(path.get("path_finish_offset_days"))
                path_duration = _as_float(path.get("path_duration"))
                if (
                    end_finish is not None
                    and path_finish is not None
                    and abs(end_finish - path_finish) > tolerance
                ):
                    reasons.append(REASON_FINISH_OFFSET_MISMATCH)
                if (
                    path_finish is not None
                    and start_off is not None
                    and path_duration is not None
                    and abs(path_duration - (path_finish - start_off)) > tolerance
                ):
                    reasons.append(REASON_DURATION_INCONSISTENT)

    # --- Criticality consistency over the longest-path members -------------------------
    if ordered and REASON_MISSING_CRITICALITY not in reasons:
        crit_by_id = {str(r.get("activity_id")): r for r in criticality_activity_rows}
        member_ids = {str(a.get("activity_id")) for a in ordered}
        all_critical = True
        for a in ordered:
            aid = str(a.get("activity_id"))
            row = crit_by_id.get(aid)
            if row is None:
                reasons.append(REASON_MEMBER_MISSING_CRITICALITY)
                all_critical = False
                continue
            if _as_float(row.get("computed_total_float")) is None:
                reasons.append(REASON_MEMBER_MISSING_TOTAL_FLOAT)
                all_critical = False
                continue
            cls = str(row.get("computed_criticality_class") or "")
            if cls in ("", "unclassified"):
                reasons.append(REASON_MEMBER_UNCLASSIFIED)
                all_critical = False
                continue
            if cls == CLASS_CRITICAL:
                longest_path_critical += 1
            else:
                all_critical = False
        # Flag the not-critical reason only when membership/classification existed but an
        # activity classified as something other than computed_critical.
        if (
            not all_critical
            and REASON_NOT_COMPUTED_CRITICAL not in reasons
            and longest_path_critical < len(ordered)
            and all(
                r not in reasons
                for r in (
                    REASON_MEMBER_MISSING_CRITICALITY,
                    REASON_MEMBER_MISSING_TOTAL_FLOAT,
                    REASON_MEMBER_UNCLASSIFIED,
                )
            )
        ):
            reasons.append(REASON_NOT_COMPUTED_CRITICAL)
        # Computed-critical activities OUTSIDE the longest path are a caveat, not a failure.
        if any(
            str(r.get("activity_id")) not in member_ids
            and str(r.get("computed_criticality_class")) == CLASS_CRITICAL
            for r in criticality_activity_rows
        ):
            caveats.append(CAVEAT_CRITICAL_OUTSIDE_PATH)

    # De-duplicate reasons preserving order.
    seen: set[str] = set()
    reason_codes = [r for r in reasons if not (r in seen or seen.add(r))]

    measurable = not reason_codes
    evidence = {
        "basis": DCMA_BASIS_APP_CPM if measurable else "attempted",
        "dependency_run_ids": dependency_run_ids,
        "path_id": path_id,
        "path_activity_count": path_activity_count,
        "longest_path_critical_activity_count": longest_path_critical,
        "computed_critical_activity_count": computed_critical_total,
        "reason_codes": reason_codes,
        "caveats": caveats,
        # Explicit provenance: source-export criticality was NOT a computation input.
        "source_critical_flags_used": False,
        "source_export_evidence": "separate",
    }
    return DcmaCriticalPathEvaluation(
        measurable=measurable,
        basis=DCMA_BASIS_APP_CPM if measurable else None,
        reason_codes=reason_codes,
        caveats=caveats,
        dependency_run_ids=dependency_run_ids,
        path_id=path_id,
        path_activity_count=path_activity_count,
        computed_critical_activity_count=computed_critical_total,
        longest_path_critical_activity_count=longest_path_critical,
        evidence=evidence,
    )


__all__ = [
    "DcmaCriticalPathEvaluation",
    "evaluate_dcma_critical_path_eligibility",
    "DCMA_BASIS_APP_CPM",
    "REASON_MISSING_FORWARD",
    "REASON_MISSING_BACKWARD",
    "REASON_MISSING_FLOAT",
    "REASON_MISSING_LONGEST_PATH",
    "REASON_MISSING_CRITICALITY",
    "REASON_GRAPH_FATAL",
    "REASON_NOT_COMPUTED_CRITICAL",
    "REASON_SEQUENCE_NOT_CONTIGUOUS",
    "REASON_MISSING_PATH_ACTIVITIES",
    "REASON_MEMBER_UNCLASSIFIED",
    "REASON_MEMBER_MISSING_TOTAL_FLOAT",
    "CAVEAT_CRITICAL_OUTSIDE_PATH",
]
