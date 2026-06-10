"""Phase 10 — relationship / entity normalization review report (read-only, review-safe).

Consolidates the unified V25 ``cross_source_relationship_candidates`` substrate into ONE operator
review surface, grouped by what Bobby does with each item: alias / project matches, person / company /
project relationships, likely-duplicate entities, low-confidence needs-review, and rejected /
not-actionable. Deterministic-first: grouping is decided by stable enums (relationship_type /
confidence_class / promotion_status / review_required), never by model inference. Read-only — it
persists nothing and promotes nothing; unreviewed inferences stay advisory. Raw-free: only candidate
ids, family/type enums, stable record refs, confidence, reason signal-types, and source-ref counts.
"""

from __future__ import annotations

from typing import Any, Optional

# Operator-review categories (stable order for the report).
CAT_ALIAS_PROJECT = "alias_project_matches"
CAT_RELATIONSHIPS = "entity_relationships"
CAT_DUPLICATES = "likely_duplicate_entities"
CAT_NEEDS_REVIEW = "low_confidence_needs_review"
CAT_REJECTED = "rejected_not_actionable"

_CATEGORIES: tuple[str, ...] = (
    CAT_ALIAS_PROJECT,
    CAT_RELATIONSHIPS,
    CAT_DUPLICATES,
    CAT_NEEDS_REVIEW,
    CAT_REJECTED,
)

_CATEGORY_HEADINGS = {
    CAT_ALIAS_PROJECT: "Alias / project matches",
    CAT_RELATIONSHIPS: "Person / company / project relationships",
    CAT_DUPLICATES: "Likely duplicate entities",
    CAT_NEEDS_REVIEW: "Low-confidence / needs review",
    CAT_REJECTED: "Rejected / not actionable",
}

_REJECTED_PROMOTIONS = {"rejected"}
_NEEDS_REVIEW_PROMOTIONS = {"needs_review", "stale", "stale_or_unresolved"}
_WEAK_CLASSES = {"weak_heuristic", "stale_or_unresolved"}
#: Explicit same-entity relationship types (duplicates), distinct from generic relatedness.
_DUP_TYPES = {"duplicate", "same_entity", "alias_of", "merge_candidate"}


def classify_relationship_candidate(cand: dict[str, Any]) -> str:
    """Deterministically map one V25 candidate to an operator-review category (enum-driven)."""
    promo = str(cand.get("promotion_status") or "").lower()
    conf_class = str(cand.get("confidence_class") or "").lower()
    if promo in _REJECTED_PROMOTIONS or conf_class == "rejected":
        return CAT_REJECTED
    if (
        bool(cand.get("review_required"))
        or promo in _NEEDS_REVIEW_PROMOTIONS
        or conf_class in _WEAK_CLASSES
    ):
        return CAT_NEEDS_REVIEW
    rtype = str(cand.get("relationship_type") or "").lower()
    sfam = str(cand.get("source_family") or "").lower()
    tfam = str(cand.get("target_family") or "").lower()
    if "project" in rtype or "project" in sfam or "project" in tfam:
        return CAT_ALIAS_PROJECT
    src_type = cand.get("source_record_type")
    if (
        rtype in _DUP_TYPES
        and sfam == tfam
        and bool(src_type)
        and src_type == cand.get("target_record_type")
    ):
        return CAT_DUPLICATES
    return CAT_RELATIONSHIPS


def _signal_types(cand: dict[str, Any]) -> list[str]:
    """Extract bounded, raw-free signal-type labels from signals_json (already decoded to a list/dict)."""
    sig = cand.get("signals_json")
    out: list[str] = []
    if isinstance(sig, list):
        for s in sig[:8]:
            if isinstance(s, str):
                out.append(s[:40])
            elif isinstance(s, dict):
                label = s.get("type") or s.get("signal") or s.get("code")
                if label:
                    out.append(str(label)[:40])
    elif isinstance(sig, dict):
        out = [str(k)[:40] for k in list(sig.keys())[:8]]
    return out


def _safe_view(cand: dict[str, Any]) -> dict[str, Any]:
    refs = cand.get("source_reference_json")
    ref_count = len(refs) if isinstance(refs, (list, dict)) else 0
    return {
        "candidate_id": cand.get("candidate_id"),
        "relationship_type": cand.get("relationship_type"),
        "source_family": cand.get("source_family"),
        "source_record_type": cand.get("source_record_type"),
        "target_family": cand.get("target_family"),
        "target_record_type": cand.get("target_record_type"),
        "project_key": cand.get("project_key"),
        "confidence_score": cand.get("confidence_score"),
        "confidence_class": cand.get("confidence_class"),
        "deterministic": bool(cand.get("deterministic")),
        "model_proposed": bool(cand.get("model_proposed")),
        "review_required": bool(cand.get("review_required")),
        "promotion_status": cand.get("promotion_status"),
        "reason_signal_types": _signal_types(cand),
        "source_ref_count": ref_count,
    }


def build_relationship_entity_report(
    *,
    store: Any,
    project_key: Optional[str] = None,
    limit: int = 2000,
) -> dict[str, Any]:
    """Build the consolidated, review-safe relationship/entity candidate report (read-only)."""
    try:
        rows = store.list_cross_source_relationship_candidates(
            project_key=project_key, limit=limit
        )
    except Exception as exc:  # missing table / store error → degrade cleanly
        return {
            "command": "second-brain relationship-candidates report",
            "ok": False,
            "error": f"unavailable:{str(exc)[:80]}",
            "groups": {c: [] for c in _CATEGORIES},
            "guardrails": _GUARDRAILS,
        }

    groups: dict[str, list[dict[str, Any]]] = {c: [] for c in _CATEGORIES}
    for cand in rows:
        groups[classify_relationship_candidate(cand)].append(_safe_view(cand))

    counts = {c: len(v) for c, v in groups.items()}
    counts["total"] = len(rows)
    # Promotion-safety: anything model-proposed or review-required must not be in an accepted state.
    unreviewed_as_fact = sum(
        1
        for cand in rows
        if (bool(cand.get("model_proposed")) or bool(cand.get("review_required")))
        and str(cand.get("promotion_status") or "") == "promoted"
    )
    return {
        "command": "second-brain relationship-candidates report",
        "ok": True,
        "project_key": project_key,
        "counts": counts,
        "groups": groups,
        "promotion_safety": {
            "unreviewed_inferences_promoted_as_fact": unreviewed_as_fact,
            "ok": unreviewed_as_fact == 0,
        },
        "guardrails": _GUARDRAILS,
    }


_GUARDRAILS = {
    "read_only": True,
    "dry_run": True,
    "deterministic_grouping_no_model": True,
    "source_linked": True,
    "no_raw_content": True,
    "no_writeback": True,
    "no_promotion": True,
    "advisory_only": True,
}


def render_relationship_entity_report_markdown(report: dict[str, Any]) -> str:
    """Render the relationship/entity report as legible, review-safe operator markdown."""
    if not report.get("ok"):
        return f"# Relationship / Entity Report\n\n_Unavailable: {report.get('error')}_\n"
    counts = report.get("counts", {})
    lines = [
        "# Relationship / Entity Normalization Report",
        "",
        f"_Project: {report.get('project_key') or '(all)'} · read-only / dry-run / deterministic "
        "grouping._",
        "",
        "## Summary",
        f"- total: {counts.get('total', 0)} · alias/project: {counts.get('alias_project_matches', 0)} "
        f"· relationships: {counts.get('entity_relationships', 0)} · duplicates: "
        f"{counts.get('likely_duplicate_entities', 0)} · needs-review: "
        f"{counts.get('low_confidence_needs_review', 0)} · rejected: "
        f"{counts.get('rejected_not_actionable', 0)}",
        f"- promotion-safety (unreviewed promoted as fact): "
        f"{report.get('promotion_safety', {}).get('unreviewed_inferences_promoted_as_fact', 0)}",
    ]
    groups = report.get("groups", {})
    for cat in _CATEGORIES:
        items = groups.get(cat) or []
        lines += ["", f"## {_CATEGORY_HEADINGS[cat]} ({len(items)})"]
        if not items:
            lines.append("_None._")
            continue
        for it in items:
            conf = it.get("confidence_score")
            conf_s = f"{float(conf):.2f}" if isinstance(conf, (int, float)) else "n/a"
            reasons = ", ".join(it.get("reason_signal_types") or []) or "(none)"
            lines.append(
                f"- **{it.get('source_family')}:{it.get('source_record_type')}** → "
                f"**{it.get('target_family')}:{it.get('target_record_type')}** "
                f"_({it.get('relationship_type')} · {it.get('confidence_class')} {conf_s} · "
                f"{it.get('promotion_status')})_"
            )
            lines.append(
                f"  - id: {it.get('candidate_id')} · project: {it.get('project_key') or '(none)'} · "
                f"deterministic: {it.get('deterministic')} · refs: {it.get('source_ref_count')} · "
                f"signals: [{reasons}]"
            )
    return "\n".join(lines) + "\n"
