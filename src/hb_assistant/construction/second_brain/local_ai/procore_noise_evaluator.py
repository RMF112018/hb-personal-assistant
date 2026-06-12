"""Phase 10 V52 — Procore noise + source-family evaluator (advisory only).

Identifies whether Procore-derived candidates are over-prioritized or generating clutter, and scores
usefulness per source/candidate family. Output is a tuning/review recommendation only — it never
suppresses, re-thresholds, or writes back anything. Small samples are marked insufficient. Reads
only safe metadata (source/candidate family, section, project key, rank, lifecycle outcome); never
reads a raw Procore payload.
"""

from __future__ import annotations

from typing import Any, Optional

from . import daily_brief_effectiveness_metrics as M
from .daily_brief_effectiveness_packets import normalize_dim

#: A candidate is "top-rank" (extra noise penalty when noisy) at or above this position.
TOP_RANK_THRESHOLD = 5
#: Minimum exposed candidates in a group before its usefulness/noise score is trusted.
MIN_GROUP_SAMPLE = 5

_NOISE_OUTCOMES = frozenset({M.REJECTED, M.IGNORED, M.SUPPRESSED})
_PROGRESS_OUTCOMES = frozenset({M.ACCEPTED, M.CLOSED, M.REOPENED})


def _counts(items: list[dict[str, Any]]) -> dict[str, int]:
    c = {
        "exposed": len(items),
        "accepted": 0,
        "rejected": 0,
        "snoozed": 0,
        "ignored": 0,
        "suppressed": 0,
        "merged": 0,
        "closed": 0,
        "top_rank_noisy": 0,
    }
    for it in items:
        outcome = it.get("outcome_type")
        if outcome in c:
            c[outcome] += 1
        if outcome in _NOISE_OUTCOMES and int(it.get("rank_position") or 99) <= TOP_RANK_THRESHOLD:
            c["top_rank_noisy"] += 1
    return c


def evaluate_procore_noise(packet: dict[str, Any]) -> dict[str, Any]:
    """Compute the Procore noise score + top noisy groups + safe tuning recommendations."""
    items = packet.get("items", [])
    procore_items = [it for it in items if it.get("is_procore")]
    counts = _counts(procore_items)
    noise = M.procore_noise_score(
        exposed_procore=counts["exposed"],
        rejected=counts["rejected"],
        ignored=counts["ignored"],
        suppressed=counts["suppressed"],
        top_rank_noisy=counts["top_rank_noisy"],
    )

    # Group by (source_family, candidate_family, section_key, project_key) — all normalized.
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for it in procore_items:
        key = (
            normalize_dim(it.get("source_family")),
            normalize_dim(it.get("candidate_family")),
            normalize_dim(it.get("section_key")),
            normalize_dim(it.get("project_key")),
        )
        groups.setdefault(key, []).append(it)

    group_rows: list[dict[str, Any]] = []
    for (sfam, cfam, section, project), g in sorted(groups.items()):
        gc = _counts(g)
        g_noise = M.procore_noise_score(
            exposed_procore=gc["exposed"],
            rejected=gc["rejected"],
            ignored=gc["ignored"],
            suppressed=gc["suppressed"],
            top_rank_noisy=gc["top_rank_noisy"],
        )
        group_rows.append(
            {
                "source_family": sfam,
                "candidate_family": cfam,
                "section_key": section,
                "project_key": project,
                "exposed": gc["exposed"],
                "noise_score": g_noise,
                "insufficient_sample": gc["exposed"] < MIN_GROUP_SAMPLE,
            }
        )
    top_noisy = sorted(
        (r for r in group_rows if r["noise_score"] is not None),
        key=lambda r: (-(r["noise_score"] or 0.0), r["section_key"]),
    )[:5]

    recommendations = _recommendations(noise, top_noisy)
    return {
        "exposed_procore_candidates": counts["exposed"],
        "counts": counts,
        "procore_noise_score": noise,
        "insufficient_sample": counts["exposed"] < MIN_GROUP_SAMPLE,
        "groups": group_rows,
        "top_noisy_groups": top_noisy,
        "recommendations": recommendations,
        "advisory": True,
        "no_suppression": True,
    }


def evaluate_source_families(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-source-family usefulness scores (advisory), normalized dimensions, small-sample flagged."""
    items = packet.get("items", [])
    by_family: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        by_family.setdefault(normalize_dim(it.get("source_family")), []).append(it)

    rows: list[dict[str, Any]] = []
    for family, g in sorted(by_family.items()):
        outs = [it["outcome_type"] for it in g if it.get("outcome_type")]
        progressed = sum(1 for o in outs if o in _PROGRESS_OUTCOMES)
        usefulness = M.source_family_usefulness_score(
            accepted_rate_value=M.accepted_rate(outs),
            source_ref_coverage_value=M.source_ref_coverage(g),
            closed_or_progressed_rate=M._rate(progressed, len(outs)) if outs else 0.0,
            rejected_rate_value=M.rejected_rate(outs),
            ignored_rate_value=M.ignored_rate(outs),
        )
        rows.append(
            {
                "source_family": family,
                "exposed": len(g),
                "outcome_count": len(outs),
                "usefulness_score": usefulness,
                "insufficient_sample": len(outs) < M.MIN_OUTCOME_SAMPLE,
            }
        )
    return rows


def _recommendations(noise: Optional[float], top_noisy: list[dict[str, Any]]) -> list[str]:
    """Raw-free tuning recommendations (section keys + scores only; never raw titles)."""
    recs: list[str] = []
    if noise is None:
        recs.append("insufficient_procore_sample: no tuning recommended yet")
        return recs
    if noise >= 0.5:
        recs.append(f"review_procore_prioritization: noise_score={noise} (high clutter signal)")
    for row in top_noisy:
        if (
            row["noise_score"] is not None
            and row["noise_score"] >= 0.5
            and not row["insufficient_sample"]
        ):
            recs.append(
                "review_noisy_group: "
                f"section={row['section_key']} family={row['candidate_family']} "
                f"noise_score={row['noise_score']}"
            )
    if not recs:
        recs.append(f"procore_noise_within_normal_range: noise_score={noise}")
    return recs
