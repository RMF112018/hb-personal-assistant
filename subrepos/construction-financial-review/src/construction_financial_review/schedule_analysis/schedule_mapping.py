"""Deterministic schedule-activity -> BudgetDetails ``budget_code_key`` mapping.

Authority rule (approved refinement): the canonical BudgetDetails universe is the SOLE mapping
authority. The schedule extractor's ``candidate_budget_code_keys`` are recorded as *supporting
evidence only* and can never independently create a ``mapped`` budget_code_key. No fuzzy matching,
no description matching, never force ``.SUB`` when a cost code spans multiple categories.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from ..common.budget_keys import cost_code_family, parse_budget_key
from . import schedule_io

# mapping_status values
STATUS_MAPPED = "mapped"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_MANUAL = "manual_required"
STATUS_NA = "not_applicable"
STATUS_INVALID = "invalid"

# mapping_method values
METHOD_EXACT_KEY = "exact_budget_code_key"
METHOD_CONSTRUCTED_EXACT = "constructed_exact_budget_code_key"
METHOD_CC_UNIQUE = "cost_code_unique_budget_match"
METHOD_CC_CATEGORY = "cost_code_category_match"
METHOD_FAMILY_CANDIDATE = "family_candidate_only"
METHOD_MANUAL = "manual_required"
METHOD_NA = "not_applicable"


def build_canonical_index(budget_codes: list[dict]) -> dict:
    """Index the canonical 127 budget codes for deterministic resolution.

    Returns ``{"keys": set, "by_cost_code": {cost_code: sorted[keys]},
    "by_cost_code_category": {(cost_code, category): key}, "by_family": {family: sorted[keys]}}``.
    """
    keys: set[str] = set()
    by_cost_code: dict[str, list[str]] = defaultdict(list)
    by_cc_cat: dict[tuple, str] = {}
    by_family: dict[str, set] = defaultdict(set)
    for row in budget_codes:
        key = row.get("budget_code_key")
        cc = row.get("cost_code")
        cat = row.get("category")
        if not key:
            continue
        keys.add(key)
        if cc:
            by_cost_code[cc].append(key)
            if cat:
                by_cc_cat[(cc, cat)] = key
            fam = cost_code_family(cc)
            if fam:
                by_family[fam].add(key)
    return {
        "keys": keys,
        "by_cost_code": {cc: sorted(v) for cc, v in by_cost_code.items()},
        "by_cost_code_category": by_cc_cat,
        "by_family": {f: sorted(v) for f, v in by_family.items()},
    }


def resolve_activity(activity: dict, index: dict) -> dict:
    """Resolve one activity to a budget mapping decision against the canonical index.

    Schedule activities provide a cost code but not a budget category, so a cost code that spans
    multiple canonical categories (e.g. ``15-16-110`` -> ``.MAT`` and ``.SUB``) is **ambiguous**,
    never force-mapped. The extractor candidates are surfaced as supporting evidence only.
    """
    codes = activity.get("activity_codes") or {}
    cost_code = schedule_io.activity_cost_code(activity)
    family = cost_code_family(cost_code) if cost_code else None
    extractor_candidates = list(codes.get("candidate_budget_code_keys")
                                or activity.get("candidate_budget_code_keys") or [])
    extractor_conf = (codes.get("budget_code_mapping_confidence")
                      or activity.get("budget_code_mapping_confidence"))

    decision = {
        "schedule_cost_code": cost_code,
        "schedule_cost_code_family": family,
        "extractor_candidate_budget_code_keys": sorted(extractor_candidates),
        "extractor_mapping_confidence": extractor_conf,
        "candidate_budget_code_keys": [],
        "mapped_budget_code_key": None,
        "mapping_status": STATUS_NA,
        "mapping_method": METHOD_NA,
        "mapping_confidence": "none",
        "requires_human_review": False,
        "notes": None,
    }

    if not cost_code:
        decision["notes"] = "Activity has no cost code; not financially mappable."
        return decision

    by_cc = index["by_cost_code"]
    matches = by_cc.get(cost_code)
    if not matches:
        # Cost code present but absent from the canonical BudgetDetails universe.
        decision["mapping_status"] = STATUS_INVALID
        decision["mapping_method"] = METHOD_MANUAL
        decision["requires_human_review"] = True
        decision["candidate_budget_code_keys"] = (
            index["by_family"].get(family, []) if family else []
        )
        decision["notes"] = (
            f"Schedule cost code {cost_code} not found in canonical BudgetDetails universe."
        )
        return decision

    if len(matches) == 1:
        decision["mapped_budget_code_key"] = matches[0]
        decision["candidate_budget_code_keys"] = matches
        decision["mapping_status"] = STATUS_MAPPED
        decision["mapping_method"] = METHOD_CC_UNIQUE
        decision["mapping_confidence"] = "high"
        # The extractor candidate, when it agrees, is corroborating evidence only.
        if matches[0] not in extractor_candidates and extractor_candidates:
            decision["notes"] = (
                "Canonical unique match; extractor candidate "
                f"{extractor_candidates} differs (supporting evidence only)."
            )
        return decision

    # Multiple canonical keys for one cost code -> ambiguous (category unknown from schedule).
    decision["candidate_budget_code_keys"] = matches
    decision["mapping_status"] = STATUS_AMBIGUOUS
    decision["mapping_method"] = METHOD_FAMILY_CANDIDATE
    decision["mapping_confidence"] = "low"
    decision["requires_human_review"] = True
    cats = sorted({parse_budget_key(k)[2] for k in matches if parse_budget_key(k)})
    decision["notes"] = (
        f"Cost code {cost_code} spans {len(matches)} canonical categories ({', '.join(cats)}); "
        "schedule supplies no category, so no single budget_code_key is assigned. "
        "Extractor candidate is supporting evidence only."
    )
    return decision


def map_activities(activities: list[dict], index: dict) -> list[dict]:
    """Resolve every activity; return enriched mapping decisions keyed by activity identity."""
    out = []
    for a in activities:
        d = resolve_activity(a, index)
        d["activity_id"] = a.get("activity_id")
        d["activity_object_id"] = a.get("activity_object_id")
        d["activity_name"] = a.get("activity_name")
        out.append(d)
    return out


def aggregate_crosswalk(decisions: list[dict]) -> list[dict]:
    """Roll activity decisions up to one crosswalk row per (cost_code, mapping outcome)."""
    groups: dict[tuple, dict] = {}
    for d in decisions:
        cc = d["schedule_cost_code"]
        key = (cc, d["mapping_status"], d.get("mapped_budget_code_key"))
        g = groups.get(key)
        if g is None:
            g = {
                "schedule_cost_code": cc,
                "schedule_cost_code_family": d["schedule_cost_code_family"],
                "mapped_budget_code_key": d.get("mapped_budget_code_key"),
                "candidate_budget_code_keys": d["candidate_budget_code_keys"],
                "mapping_status": d["mapping_status"],
                "mapping_method": d["mapping_method"],
                "mapping_confidence": d["mapping_confidence"],
                "extractor_candidate_budget_code_keys": d["extractor_candidate_budget_code_keys"],
                "extractor_mapping_confidence": d["extractor_mapping_confidence"],
                "requires_human_review": d["requires_human_review"],
                "activity_ids": [],
                "activity_names_sample": [],
                "notes": d["notes"],
            }
            groups[key] = g
        if d.get("activity_id"):
            g["activity_ids"].append(d["activity_id"])
        if d.get("activity_name") and len(g["activity_names_sample"]) < 5:
            g["activity_names_sample"].append(d["activity_name"])
    rows = []
    for g in groups.values():
        g["activity_ids"] = sorted(g["activity_ids"])
        g["activity_count"] = len(g["activity_ids"])
        rows.append(g)
    rows.sort(key=lambda r: (r["schedule_cost_code"] or "", r["mapping_status"],
                             r.get("mapped_budget_code_key") or ""))
    return rows
