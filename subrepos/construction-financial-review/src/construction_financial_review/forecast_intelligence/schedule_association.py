"""Classify how each canonical budget code is tied to remaining schedule work.

Association ladder (strongest -> weakest):
    direct              unique deterministic mapped activity link for THIS exact budget code
    cost_code_family    no direct link, but the cost-code family has remaining schedule work
    vendor_or_commitment a vendor/commitment tie to scheduled work (unavailable in current data)
    owner_scope         same owner SOV scope (per the authoritative crosswalk) has remaining work
    division            same CSI division (cost-code first segment) has remaining work
    project_level       only project-level remaining work (CONTEXT ONLY — never drives ETC/EAC)
    none                schedule complete or no schedule evidence anywhere

``direct`` REQUIRES a deterministic unique mapped activity link (mapping_status == "mapped" with at
least one mapped activity id). Ambiguous (cost-code spans MAT&SUB) codes can never be ``direct``.
Each association carries a ``schedule_confidence`` multiplier that SCALES the schedule-ETC estimate's
reconciliation weight (never its value). ``project_level`` carries weight 0.0 by rule: it is recorded
for the reviewer but must not influence any budget-code-level remaining-cost estimate.
"""
from __future__ import annotations

from collections import OrderedDict, defaultdict
from decimal import Decimal
from typing import Optional

from ..common.budget_keys import cost_code_family
from ..common.money import D, money_str

ASSOC_DIRECT = "direct"
ASSOC_FAMILY = "cost_code_family"
ASSOC_VENDOR = "vendor_or_commitment"
ASSOC_OWNER = "owner_scope"
ASSOC_DIVISION = "division"
ASSOC_PROJECT = "project_level"
ASSOC_NONE = "none"

# schedule_confidence multipliers applied to the schedule-ETC estimate weight.
ASSOC_CONFIDENCE = {
    ASSOC_DIRECT: Decimal("1.0"),
    ASSOC_FAMILY: Decimal("0.6"),
    ASSOC_VENDOR: Decimal("0.5"),
    ASSOC_OWNER: Decimal("0.4"),
    ASSOC_DIVISION: Decimal("0.3"),
    ASSOC_PROJECT: Decimal("0.0"),   # context only — never drives code-level ETC/EAC
    ASSOC_NONE: Decimal("0.0"),
}

# Associations that may influence code-level remaining-cost estimates.
INFLUENCING = (ASSOC_DIRECT, ASSOC_FAMILY, ASSOC_VENDOR, ASSOC_OWNER, ASSOC_DIVISION)


def _division(cost_code: Optional[str]) -> Optional[str]:
    if not isinstance(cost_code, str):
        return None
    seg = cost_code.split("-")
    return seg[0] if seg and seg[0] else None


def _has_direct_work(rollup: Optional[dict]) -> bool:
    return bool(rollup and rollup.get("schedule_mapping_status") == "mapped"
                and (rollup.get("open_activity_count") or 0) > 0)


def build_group_indices(rollup_by_key: dict, code_meta: dict) -> dict:
    """Aggregate remaining schedule work by family / division / owner-scope across codes.

    ``code_meta[key]`` -> {cost_code, family, division, owner_sov_code, revised_budget}.
    Only codes with DIRECT remaining work (mapped + open activities) contribute remaining work; the
    group's revised-budget denominator spans every member code (so borrowed work is shared by budget
    weight). Returns {dim: {group_value: aggregate}}.
    """
    families: dict[str, dict] = defaultdict(lambda: _empty_group())
    divisions: dict[str, dict] = defaultdict(lambda: _empty_group())
    owners: dict[str, dict] = defaultdict(lambda: _empty_group())

    for key, meta in code_meta.items():
        rollup = rollup_by_key.get(key)
        budget = D(meta.get("revised_budget"))
        for dim_map, gv in ((families, meta.get("family")),
                            (divisions, meta.get("division")),
                            (owners, meta.get("owner_sov_code"))):
            if not gv:
                continue
            g = dim_map[gv]
            g["member_keys"].append(key)
            g["member_budget_total"] += budget
            if _has_direct_work(rollup):
                g["work_keys"].append(key)
                g["remaining_duration_days"] += D(rollup.get("remaining_duration_days"))
                g["open_activity_count"] += int(rollup.get("open_activity_count") or 0)
                lrf = rollup.get("latest_remaining_finish")
                if lrf and (g["latest_remaining_finish"] is None or lrf > g["latest_remaining_finish"]):
                    g["latest_remaining_finish"] = lrf
    return {"family": dict(families), "division": dict(divisions), "owner_scope": dict(owners)}


def _empty_group() -> dict:
    return {"member_keys": [], "work_keys": [], "member_budget_total": Decimal("0"),
            "remaining_duration_days": Decimal("0"), "open_activity_count": 0,
            "latest_remaining_finish": None}


def _group_has_work(group: Optional[dict]) -> bool:
    return bool(group and group["work_keys"] and group["remaining_duration_days"] > 0)


def _prorated_remaining(group: dict, my_budget: Decimal) -> Decimal:
    """Share of the group's remaining duration attributable to this code by revised-budget weight."""
    denom = group["member_budget_total"]
    if denom <= 0:
        # Even split across members lacking direct work.
        n = max(1, len(group["member_keys"]))
        return (group["remaining_duration_days"] / Decimal(n))
    share = (my_budget / denom)
    return group["remaining_duration_days"] * share


def classify(budget_code_key: str, meta: dict, rollup_by_key: dict,
             direct_activity_ids_by_key: dict, indices: dict,
             project_has_remaining_work: bool, project_key: str) -> OrderedDict:
    """Return the schedule-association + remaining-work-evidence row for one budget code."""
    rollup = rollup_by_key.get(budget_code_key)
    my_budget = D(meta.get("revised_budget"))
    direct_ids = sorted(direct_activity_ids_by_key.get(budget_code_key, []))

    assoc = ASSOC_NONE
    open_count = 0
    remaining_days = Decimal("0")
    latest_finish = None
    activity_refs: list = []
    status = (rollup.get("schedule_remaining_work_status") if rollup else None) or "no_schedule_evidence"
    basis = "no schedule evidence at any level"
    group_value = None

    if rollup and rollup.get("schedule_mapping_status") == "mapped" and direct_ids:
        # Deterministic unique mapped link for this exact code.
        assoc = ASSOC_DIRECT
        open_count = int(rollup.get("open_activity_count") or 0)
        remaining_days = D(rollup.get("remaining_duration_days"))
        latest_finish = rollup.get("latest_remaining_finish")
        activity_refs = direct_ids[:25]
        basis = (f"{rollup.get('mapped_activity_count')} mapped activities "
                 f"({open_count} open) on this budget code")
    else:
        fam = indices["family"].get(meta.get("family"))
        own = indices["owner_scope"].get(meta.get("owner_sov_code"))
        div = indices["division"].get(meta.get("division"))
        # vendor/commitment association is unavailable in current data (no per-code vendor link).
        if _group_has_work(fam):
            assoc, group, group_value = ASSOC_FAMILY, fam, meta.get("family")
        elif _group_has_work(own):
            assoc, group, group_value = ASSOC_OWNER, own, meta.get("owner_sov_code")
        elif _group_has_work(div):
            assoc, group, group_value = ASSOC_DIVISION, div, meta.get("division")
        elif project_has_remaining_work:
            assoc, group, group_value = ASSOC_PROJECT, None, "project"
        else:
            assoc, group, group_value = ASSOC_NONE, None, None

        if assoc in (ASSOC_FAMILY, ASSOC_OWNER, ASSOC_DIVISION):
            open_count = group["open_activity_count"]
            remaining_days = _prorated_remaining(group, my_budget)
            latest_finish = group["latest_remaining_finish"]
            status = "material_remaining_work" if remaining_days > 0 else status
            basis = (f"borrowed from {assoc} '{group_value}': {len(group['work_keys'])} code(s) with "
                     f"remaining work, prorated by revised-budget share")
        elif assoc == ASSOC_PROJECT:
            basis = "project has remaining schedule work; context only (does not drive code ETC/EAC)"

    confidence = ASSOC_CONFIDENCE[assoc]
    influences = assoc in INFLUENCING

    return OrderedDict([
        ("project_key", project_key),
        ("budget_code_key", budget_code_key),
        ("schedule_association", assoc),
        ("schedule_association_group", group_value),
        ("schedule_confidence", str(confidence)),
        ("influences_code_estimate", influences),
        ("open_activity_count", open_count),
        ("remaining_duration_days",
         str(remaining_days.quantize(Decimal("0.01"))) if remaining_days else "0.00"),
        ("latest_schedule_finish", latest_finish),
        ("schedule_remaining_work_status", status),
        ("direct_mapped_activity_count", len(direct_ids)),
        ("activity_refs", activity_refs),
        ("association_basis", basis),
    ])
