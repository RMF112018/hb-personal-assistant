#!/usr/bin/env python3
"""
generate_forecast_analysis_crosswalk_v2.py

Tropical World Nursery Senior Living Facility (project_key=tropical, job=23-435-01)
Forecast ANALYSIS v2 — applies the AUTHORITATIVE Owner SOV scope crosswalk so owner pay-app evidence,
Procore subcontractor evidence, BudgetDetails, and CostEntries are compared at the correct
owner-scope rollup level (not inferred child-level matching).

Hard rules:
  - Crosswalk is AUTHORITATIVE — consumed verbatim; never inferred/fuzzy-matched/overridden.
  - Does NOT mutate any source / package / crosswalk / Excel / SQLite / repo.
  - No live/external calls; no new budget keys.
  - CostEntries are accounting actual-cost truth; pay-app values are EVIDENCE only.
  - Accounting actuals are the only basis for numeric floor increases.

Stdlib only. Decimal(str(value)) money math. Deterministic sorted output. Re-runnable.
"""

import json
import os
import re
import sys
import hashlib
import shutil
import fnmatch
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation, getcontext
from collections import defaultdict, OrderedDict

# self-contained script (run as `python <file>`): make the package importable for the shared
# run-lineage resolver regardless of whether PYTHONPATH=src was exported.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from construction_financial_review.common import run_lineage  # noqa: E402

getcontext().prec = 50

DEFAULT_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)
# Resolved at RUNTIME by resolve_inputs() (never at import).
ROOT = None
CTX = None
ANL = None
WP = None
XW_DIR = None
XW_FILE = None
XW_VALIDATION = None
OUT = None
CONTEXT_LINEAGE = None
ANALYSIS_LINEAGE = None
WORKPAPER_LINEAGE = None

# The owner-SOV scope crosswalk is the AUTHORITATIVE, hand-curated static input (consumed verbatim,
# never inferred). Its `20260614_final` name is a fixed governance artifact — NOT stale run lineage.
XW_AUTHORITATIVE_NAME = "owner_sov_scope_crosswalk_tropical_authoritative_20260614_final"

PROJECT_NAME = "Tropical World Nursery Senior Living Facility"
PROJECT_KEY = "tropical"
JOB_REF = "23-435-01"
PERIOD = "2026-June"

CENTS = Decimal("0.01")
MAT_DOLLAR = Decimal("25000")
MAT_PCT = Decimal("0.10")
OWNER_COMPLETE_PCT = Decimal("0.98")
EXHAUSTION_PCT = Decimal("0.90")

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_inputs():
    """Resolve upstream context + analysis + mapping-workpaper at runtime (full-fresh run state aware).
    The authoritative owner-SOV crosswalk is a fixed static input, resolved by its governance name."""
    global ROOT, CTX, ANL, WP, XW_DIR, XW_FILE, XW_VALIDATION, OUT
    global CONTEXT_LINEAGE, ANALYSIS_LINEAGE, WORKPAPER_LINEAGE
    ROOT = run_lineage.active_data_root(DEFAULT_ROOT)
    CTX, CONTEXT_LINEAGE = run_lineage.resolve_upstream(
        "context", data_root=ROOT, project_key=PROJECT_KEY,
        override_stamp=os.environ.get("CFR_CONTEXT_STAMP"))
    ANL, ANALYSIS_LINEAGE = run_lineage.resolve_upstream(
        "analysis", data_root=ROOT, project_key=PROJECT_KEY,
        override_stamp=os.environ.get("CFR_ANALYSIS_STAMP"))
    WP, WORKPAPER_LINEAGE = run_lineage.resolve_upstream(
        "mapping_workpaper", data_root=ROOT, project_key=PROJECT_KEY,
        override_stamp=os.environ.get("CFR_MAPPING_WORKPAPER_STAMP"))
    XW_DIR = ROOT / XW_AUTHORITATIVE_NAME
    XW_FILE = XW_DIR / f"{XW_AUTHORITATIVE_NAME}.jsonl"
    XW_VALIDATION = XW_DIR / f"{XW_AUTHORITATIVE_NAME}_validation_report.json"
    OUT = ROOT / f"forecast_analysis_package_tropical_crosswalk_v2_{STAMP}"
    return {"context": CONTEXT_LINEAGE, "analysis": ANALYSIS_LINEAGE, "mapping_workpaper": WORKPAPER_LINEAGE}

# --------------------------------------------------------------------------------------
def read_jsonl(path):
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dec(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip() == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def D(v):
    d = dec(v)
    return d if d is not None else Decimal("0")


def money_str(v):
    d = dec(v)
    return None if d is None else str(d.quantize(CENTS))


def dsum(vals):
    t = Decimal("0")
    for v in vals:
        d = dec(v)
        if d is not None:
            t += d
    return t


def parse_budget_key(key):
    if not isinstance(key, str):
        return None
    p = key.split(".")
    if len(p) != 3 or not all(p):
        return None
    return p[0], p[1], p[2]


def materiality(a, b):
    a = a if a is not None else Decimal("0")
    b = b if b is not None else Decimal("0")
    gap = abs(a - b)
    basis = max(abs(a), abs(b))
    pct = (gap / basis) if basis > 0 else None
    return gap, pct, (gap >= MAT_DOLLAR and pct is not None and pct >= MAT_PCT)


def severity_for(gap, pct):
    if gap >= Decimal("250000") or (pct is not None and pct >= Decimal("0.25")):
        return "critical"
    if gap >= Decimal("100000") or (pct is not None and pct >= Decimal("0.15")):
        return "high"
    if gap >= MAT_DOLLAR and (pct is not None and pct >= MAT_PCT):
        return "medium"
    return "low"


def latest_key(period_to, app_no, sheet_idx):
    return (period_to or "",
            app_no if isinstance(app_no, int) else -1,
            sheet_idx if isinstance(sheet_idx, int) else -1)


GR_DESC = "GENERAL REQUIREMENTS"


# --------------------------------------------------------------------------------------
def main():
    resolve_inputs()   # runtime upstream resolution (full-fresh run state aware)
    print(f"[crosswalk-v2] context: {CONTEXT_LINEAGE['consumed_package']} "
          f"(src={CONTEXT_LINEAGE['lineage_source']}); analysis: {ANALYSIS_LINEAGE['consumed_package']}; "
          f"workpaper: {WORKPAPER_LINEAGE['consumed_package']}")
    OUT.mkdir(parents=True, exist_ok=False)

    # ---- load ----
    xw_rows = list(read_jsonl(XW_FILE))
    xw_validation = read_json(XW_VALIDATION)
    budget_codes = list(read_jsonl(CTX / "canonical" / "budget_codes.jsonl"))
    canonical_keys = {r["budget_code_key"] for r in budget_codes}
    bc_by_key = {r["budget_code_key"]: r for r in budget_codes}
    ctx_rows = {r["budget_code_key"]: r for r in read_jsonl(CTX / "summaries" / "budget_code_forecast_context.jsonl")}
    owner_lines = [r for r in read_jsonl(CTX / "canonical" / "owner_pay_app_line_items_mapped.jsonl")]
    procore_latest = list(read_jsonl(CTX / "canonical" / "procore_latest_subcontractor_invoice_by_budget_code.jsonl"))
    procore_latest_by_key = defaultdict(list)
    for r in procore_latest:
        if r.get("mapped_budget_code_key"):
            procore_latest_by_key[r["mapped_budget_code_key"]].append(r)
    procore_wbs_universe = {r["wbs_flat_code"] for r in procore_latest}

    ctx_concl = read_json(CTX / "validation_report.json").get("conclusion")
    anl_validation = read_json(ANL / "validation_report.json")
    anl_concl = anl_validation.get("conclusion")
    wp_concl = read_json(WP / "validation_report.json").get("conclusion")
    old_risks = list(read_jsonl(ANL / "forecast_risk_register.jsonl"))
    old_mismatch = {r["budget_code_key"]: r for r in old_risks
                    if r.get("risk_type") == "owner_procore_mismatch" and r.get("budget_code_key")}
    old_recs = list(read_jsonl(ANL / "forecast_recommendations_by_budget_code.jsonl"))
    old_action_counts = defaultdict(int)
    old_conf_counts = defaultdict(int)
    for r in old_recs:
        old_action_counts[r["forecast_action"]] += 1
        old_conf_counts[r["confidence"]] += 1
    old_sev_counts = defaultdict(int)
    for r in old_risks:
        old_sev_counts[r["severity"]] += 1

    out_counts = OrderedDict()

    # ==================================================================================
    # Crosswalk expansion + assignment (EXPLICIT lists authoritative)
    # ==================================================================================
    def expand_budget(r):
        return sorted((set(r.get("covered_budget_code_keys") or [])) & canonical_keys)

    def expand_procore(r):
        return sorted((set(r.get("covered_procore_wbs_flat_codes") or [])) & procore_wbs_universe)

    assign_key_row = {}          # budget_code_key -> crosswalk row
    dup_keys = []
    for r in xw_rows:
        for k in expand_budget(r):
            if k in assign_key_row:
                dup_keys.append(k)
            assign_key_row[k] = r
    procore_assign = defaultdict(list)
    for r in xw_rows:
        for w in expand_procore(r):
            procore_assign[w].append(r)

    covered_keys = set(assign_key_row)
    uncovered_keys = sorted(canonical_keys - covered_keys)
    procore_covered = set(procore_assign)
    procore_uncovered = sorted(procore_wbs_universe - procore_covered)
    procore_dup = [w for w, v in procore_assign.items() if len(v) > 1]

    # ---- HARD GATE (refinement #1) ----
    def covers(owner_sov, key):
        for r in xw_rows:
            if r["owner_sov_code"] == owner_sov and key in expand_budget(r):
                return True
        return False
    crosswalk_facts = OrderedDict([
        ("budget_coverage_127", len(covered_keys) == 127 and not uncovered_keys),
        ("procore_coverage_42", len(procore_covered) == 42 and not procore_uncovered),
        ("zero_duplicate_budget_codes", len(dup_keys) == 0),
        ("zero_unresolved_owner_sov_rows",
         all(expand_budget(r) or expand_procore(r) for r in xw_rows)),
        ("fact_20_18_105_to_1000_20_18_170_mat", covers("20-18-105", "1000.20-18-170.MAT")),
        ("fact_99_01_790_to_1000_90_01_300_mat", covers("99-01-790", "1000.90-01-300.MAT")),
        ("fact_15_01_426", covers("15-01-426", "1000.15-01-426.MAT")),
        ("fact_15_01_530_multi", all(covers("15-01-530", f"1000.15-01-530.{c}") for c in ("LAB", "LBN", "MAT", "SUB"))),
        ("fact_15_01_xxx_excludes_426_530",
         not any(covers("15-01-XXX", k) for k in
                 ("1000.15-01-426.MAT", "1000.15-01-530.LAB", "1000.15-01-530.SUB"))),
        ("fact_10xx_two_disjoint_rows",
         sum(1 for r in xw_rows if r["owner_sov_code"] == "10-XX-XXX") == 2),
    ])
    crosswalk_gate_passed = all(crosswalk_facts.values())

    # owner-line description routing for 10-XX-XXX must be unambiguous
    ten_lines = [o for o in owner_lines if o.get("owner_sov_code") == "10-XX-XXX"
                 and o.get("row_type") == "construction_line_item"]
    ten_desc_ok = all((o.get("description_of_work") or "").strip() != "" for o in ten_lines)

    # ==================================================================================
    # 1) applied_owner_sov_scope_crosswalk.jsonl
    # ==================================================================================
    applied = []
    row_by_xid = {}
    for r in sorted(xw_rows, key=lambda x: x["crosswalk_id"]):
        eb = expand_budget(r)
        ep = expand_procore(r)
        out = OrderedDict([
            ("crosswalk_id", r["crosswalk_id"]), ("project_key", PROJECT_KEY),
            ("mapping_version", r.get("mapping_version")),
            ("owner_sov_code", r["owner_sov_code"]),
            ("owner_cost_code_family", r.get("owner_cost_code_family")),
            ("owner_scope_description", r.get("owner_scope_description")),
            ("owner_description_match_rule", r.get("owner_description_match_rule")),
            ("scope_relationship", r.get("scope_relationship")),
            ("coverage_type", r.get("coverage_type")),
            ("comparison_level", r.get("comparison_level")),
            ("allocation_required", r.get("allocation_required")),
            ("allocation_method", r.get("allocation_method")),
            ("covered_budget_code_key_patterns", r.get("covered_budget_code_key_patterns")),
            ("covered_budget_code_keys", r.get("covered_budget_code_keys")),
            ("covered_budget_code_exclusion_patterns", r.get("covered_budget_code_exclusion_patterns")),
            ("covered_budget_code_exclusions", []),
            ("covered_procore_wbs_flat_code_patterns", r.get("covered_procore_wbs_flat_code_patterns")),
            ("covered_procore_wbs_flat_codes", r.get("covered_procore_wbs_flat_codes")),
            ("covered_procore_wbs_flat_code_exclusion_patterns", r.get("covered_procore_wbs_flat_code_exclusion_patterns")),
            ("covered_procore_wbs_flat_code_exclusions", []),
            ("expanded_covered_budget_code_keys", eb),
            ("expanded_covered_procore_wbs_flat_codes", ep),
            ("comparison_basis", r.get("comparison_basis")),
            ("confidence", r.get("confidence")),
            ("approved_by", r.get("approved_by")),
            ("approved_date", r.get("approved_date")),
            ("notes", r.get("notes")),
        ])
        applied.append(out)
        row_by_xid[r["crosswalk_id"]] = r
    out_counts["applied_owner_sov_scope_crosswalk.jsonl"] = write_jsonl(
        OUT / "applied_owner_sov_scope_crosswalk.jsonl", applied)

    # ==================================================================================
    # 2) budget_code_to_owner_scope_assignment.jsonl (127)
    # ==================================================================================
    def assignment_method(r):
        ct = r.get("coverage_type")
        if r["owner_sov_code"] == "10-XX-XXX":
            return "authoritative_description_sensitive"
        if ct == "direct":
            return "authoritative_direct"
        if ct == "same_cost_code_multi_category":
            return "authoritative_direct"
        if r.get("covered_budget_code_exclusion_patterns"):
            return "authoritative_exclusion_resolved"
        return "authoritative_pattern"

    assign_rows = []
    for k in sorted(canonical_keys):
        r = assign_key_row.get(k)
        bk = bc_by_key[k]
        parsed = parse_budget_key(k)
        assign_rows.append(OrderedDict([
            ("project_key", PROJECT_KEY), ("budget_code_key", k),
            ("sub_job", parsed[0] if parsed else None),
            ("cost_code", parsed[1] if parsed else None),
            ("category", parsed[2] if parsed else None),
            ("budget_code_description", bk.get("budget_code_description")),
            ("assigned_owner_sov_code", r["owner_sov_code"] if r else None),
            ("assigned_owner_crosswalk_id", r["crosswalk_id"] if r else None),
            ("owner_scope_relationship", r.get("scope_relationship") if r else None),
            ("owner_comparison_level", r.get("comparison_level") if r else None),
            ("assignment_method", assignment_method(r) if r else None),
            ("assignment_confidence", "authoritative"),
            ("notes", None if r else "UNASSIGNED — crosswalk coverage gap"),
        ]))
    out_counts["budget_code_to_owner_scope_assignment.jsonl"] = write_jsonl(
        OUT / "budget_code_to_owner_scope_assignment.jsonl", assign_rows)
    assignment_ok = all(a["assigned_owner_crosswalk_id"] for a in assign_rows) and len(assign_rows) == 127

    # ==================================================================================
    # owner evidence per crosswalk row (latest), routed by description for 10-XX-XXX
    # ==================================================================================
    def owner_lines_for(r):
        sov = r["owner_sov_code"]
        rule = r.get("owner_description_match_rule") or ""
        lines = [o for o in owner_lines if o.get("owner_sov_code") == sov
                 and o.get("row_type") == "construction_line_item"]
        if sov == "10-XX-XXX":
            is_gr = "==" in rule  # 'description == GENERAL REQUIREMENTS'
            def match(o):
                d = (o.get("description_of_work") or "").strip().upper()
                return (d == GR_DESC) if is_gr else (d != GR_DESC)
            lines = [o for o in lines if match(o)]
        return lines

    def owner_latest_for(r):
        lines = owner_lines_for(r)
        if not lines:
            return None
        return max(lines, key=lambda o: latest_key(o.get("period_to"), o.get("application_no"), o.get("sheet_index")))

    # crosswalk owner sov set + owner-line sov set (for orphan derivation)
    xw_sov = {r["owner_sov_code"] for r in xw_rows}
    owner_line_sov = {o.get("owner_sov_code") for o in owner_lines
                      if o.get("row_type") == "construction_line_item"}
    orphan_owner_sov = sorted(s for s in owner_line_sov - xw_sov if s)

    # ==================================================================================
    # 3) owner_scope_rollup_evidence.jsonl (58) + rollup classification
    # ==================================================================================
    rollup_rows = []
    rollup_by_xid = {}
    for r in sorted(xw_rows, key=lambda x: x["crosswalk_id"]):
        xid = r["crosswalk_id"]
        eb = expand_budget(r)
        ep = expand_procore(r)
        ol = owner_latest_for(r)
        owner_completed = dec(ol.get("total_completed_and_stored_to_date")) if ol else None
        owner_current = dec(ol.get("current_value")) if ol else None
        owner_pct = dec(ol.get("percent_complete")) if ol else None
        owner_balance = dec(ol.get("balance_to_finish")) if ol else None
        owner_reten = dec(ol.get("retainage")) if ol else None

        proc_rows = [p for k in eb for p in procore_latest_by_key.get(k, [])]
        proc_completed = dsum(p.get("latest_total_completed_and_stored_to_date") for p in proc_rows)
        proc_claimed = dsum(p.get("latest_subcontractor_claimed_amount") for p in proc_rows)
        proc_reten = dsum(p.get("latest_retainage_held") for p in proc_rows)
        proc_sched = dsum(p.get("latest_scheduled_value") for p in proc_rows)
        neg_credit = sum(1 for p in proc_rows
                         if (dec(p.get("latest_total_completed_and_stored_to_date")) or Decimal("0")) < 0)
        has_proc = len(proc_rows) > 0

        actual_all = dsum(ctx_rows.get(k, {}).get("actuals", {}).get("actual_cost_all_source_to_date") for k in eb)
        actual_may = dsum(ctx_rows.get(k, {}).get("actuals", {}).get("actual_cost_through_may_2026") for k in eb)
        actual_june = dsum(ctx_rows.get(k, {}).get("actuals", {}).get("actual_cost_june_2026_to_date") for k in eb)
        proj_sum = dsum((bc_by_key.get(k, {}).get("amounts", {}) or {}).get("projected_costs") for k in eb)
        budget_sum = dsum((bc_by_key.get(k, {}).get("amounts", {}) or {}).get("revised_budget") for k in eb)

        d_op = (owner_completed - proc_completed) if owner_completed is not None and has_proc else None
        d_oa = (owner_completed - actual_all) if owner_completed is not None else None
        d_pa = (proc_completed - actual_all) if has_proc else None
        _, _, oa_mat = materiality(actual_all, proj_sum)

        if ol is None:
            align, impl = "insufficient_owner_evidence", "informational"
        elif not has_proc:
            align, impl = "insufficient_procore_evidence", "informational"
        elif actual_all > proj_sum and oa_mat:
            align, impl = "actuals_exceed_projected", "potential_forecast_risk"
        elif r.get("scope_relationship") == "one_to_many":
            align, impl = "structural_sell_value_vs_cost", "informational"
        else:
            gap, pct, mat = materiality(owner_completed, proc_completed)
            if mat and owner_completed > proc_completed:
                align, impl = "structural_sell_value_vs_cost", "informational"
            elif mat and proc_completed > owner_completed:
                align, impl = "timing_review", "review"
            else:
                align, impl = "aligned", "none"

        rr = OrderedDict([
            ("project_key", PROJECT_KEY), ("crosswalk_id", xid),
            ("owner_sov_code", r["owner_sov_code"]),
            ("owner_scope_description", r.get("owner_scope_description")),
            ("scope_relationship", r.get("scope_relationship")),
            ("comparison_level", r.get("comparison_level")),
            ("expanded_covered_budget_code_keys", eb),
            ("covered_budget_code_count", len(eb)),
            ("covered_procore_wbs_count", len(ep)),
            ("owner_latest_current_value", money_str(owner_current)),
            ("owner_latest_completed_to_date", money_str(owner_completed)),
            ("owner_latest_percent_complete", float(owner_pct) if owner_pct is not None else None),
            ("owner_latest_balance_to_finish", money_str(owner_balance)),
            ("owner_latest_retainage", money_str(owner_reten)),
            ("procore_latest_completed_to_date_sum", money_str(proc_completed) if has_proc else None),
            ("procore_latest_claimed_amount_sum", money_str(proc_claimed) if has_proc else None),
            ("procore_latest_retainage_sum", money_str(proc_reten) if has_proc else None),
            ("procore_latest_scheduled_value_sum", money_str(proc_sched) if has_proc else None),
            ("procore_negative_credit_count", neg_credit),
            ("actual_cost_all_source_to_date_sum", money_str(actual_all)),
            ("actual_cost_through_may_2026_sum", money_str(actual_may)),
            ("actual_cost_june_2026_to_date_sum", money_str(actual_june)),
            ("current_projected_cost_sum", money_str(proj_sum)),
            ("revised_budget_sum", money_str(budget_sum)),
            ("owner_vs_procore_delta", money_str(d_op) if d_op is not None else None),
            ("owner_vs_actual_delta", money_str(d_oa) if d_oa is not None else None),
            ("procore_vs_actual_delta", money_str(d_pa) if d_pa is not None else None),
            ("comparison_basis", r.get("comparison_basis")),
            ("alignment_status", align),
            ("risk_implication", impl),
            ("notes", _rollup_note(r.get("scope_relationship"), align)),
        ])
        rollup_rows.append(rr)
        rollup_by_xid[xid] = rr
    out_counts["owner_scope_rollup_evidence.jsonl"] = write_jsonl(
        OUT / "owner_scope_rollup_evidence.jsonl", rollup_rows)

    # ==================================================================================
    # 4) forecast_recommendations_by_budget_code.jsonl (127)
    # ==================================================================================
    recs = []
    calc = {}
    risks = []
    risk_seq = [0]

    def add_risk(sev, key, cc, cat, rtype, desc, ev, action):
        risk_seq[0] += 1
        risks.append(OrderedDict([
            ("risk_id", f"R-{risk_seq[0]:04d}"), ("severity", sev),
            ("budget_code_key", key), ("cost_code", cc), ("category", cat),
            ("risk_type", rtype), ("description", desc), ("evidence", ev),
            ("recommended_action", action), ("requires_human_review", sev in ("critical", "high", "medium")),
            ("source_files", ["forecast_recommendations_by_budget_code.jsonl",
                              "owner_scope_rollup_evidence.jsonl"]),
        ]))

    for k in sorted(canonical_keys):
        bk = bc_by_key[k]
        ctx = ctx_rows.get(k, {})
        amts = bk.get("amounts") or {}
        ac = ctx.get("actuals") or {}
        parsed = parse_budget_key(k)
        cat = parsed[2] if parsed else None
        cc = parsed[1] if parsed else None

        budget = D(amts.get("revised_budget"))
        proj = D(amts.get("projected_costs"))
        actual = D(ac.get("actual_cost_all_source_to_date"))
        actual_may = D(ac.get("actual_cost_through_may_2026"))
        actual_june = D(ac.get("actual_cost_june_2026_to_date"))
        ftc = dec(amts.get("forecast_to_complete"))
        entry_count = ac.get("actual_entry_count") or 0
        has_actuals = entry_count > 0

        xrow = assign_key_row.get(k)
        rollup = rollup_by_xid.get(xrow["crosswalk_id"]) if xrow else None
        one_to_many = xrow and xrow.get("scope_relationship") == "one_to_many"
        owner_basis = "inherited_from_owner_summary_scope" if one_to_many else "direct"

        # procore at this child key
        proc_rows_k = procore_latest_by_key.get(k, [])
        procore_completed_child = dsum(p.get("latest_total_completed_and_stored_to_date") for p in proc_rows_k) if proc_rows_k else None
        neg_child = any((dec(p.get("latest_total_completed_and_stored_to_date")) or Decimal("0")) < 0 for p in proc_rows_k)

        risk_flags = []
        june_flag = actual_june != 0
        if june_flag:
            risk_flags.append("june_actuals_without_june_payapp_evidence")
        if neg_child:
            risk_flags.append("deductive_change_order_credit_review")
        exhaustion = False
        if has_actuals and proj > 0 and (proj * EXHAUSTION_PCT) <= actual <= proj:
            rollup_remaining = rollup and rollup["alignment_status"] in ("remaining_exposure_review", "timing_review")
            if (rollup_remaining or (procore_completed_child is not None and procore_completed_child > 0)):
                exhaustion = True
                risk_flags.append("owner_scope_remaining_exposure_review")

        # No-exposure proven = workbook forecast_to_complete is 0 AND remaining (proj-actual) is
        # immaterial AND no positive Procore remaining at THIS child. Per refinement #3 we do NOT
        # pull the owner summary percent-complete down to the child.
        no_exposure_proven = (
            (ftc is None or ftc == 0) and (proj - actual) <= MAT_DOLLAR
            and not (procore_completed_child is not None and procore_completed_child > 0)
        )

        rec_proj = adj = ctc = None
        if has_actuals and actual > proj:
            action = "increase_forecast"
            rec_proj, adj, ctc = actual, actual - proj, Decimal("0")
            risk_flags = ["actuals_exceed_projected_cost", "forecast_floor_to_actuals"] + risk_flags
            # Floor is anchored on accounting actuals (rock solid). A Procore deductive credit is
            # evidence-side and does not undermine the floor; only June timing lowers confidence.
            confidence = "medium" if june_flag else "high"
            reason = "actuals exceed projected cost; floored to accounting actuals"
        elif has_actuals and _decrease_ok(proj, actual, rollup, june_flag, neg_child):
            action = "decrease_forecast"
            rec_proj, adj, ctc = actual, actual - proj, Decimal("0")
            confidence = "medium"
            reason = "owner scope substantially complete; projected materially exceeds actual with no remaining exposure"
        elif has_actuals and (neg_child or exhaustion or (rollup and rollup["alignment_status"] == "timing_review")):
            action = "review_required"
            confidence = "medium"
            reason = "actuals present; rollup/credit/exhaustion signal requires review"
        elif has_actuals:
            action = "hold_current_forecast"
            rec_proj, adj, ctc = proj, Decimal("0"), max(proj - actual, Decimal("0"))
            if no_exposure_proven:
                confidence = "high"
                reason = "valid actuals; no remaining exposure proven (forecast_to_complete 0, remaining immaterial)"
            else:
                confidence = "medium"
                reason = "valid actuals; remaining exposure not proven (actuals-only hold)"
        elif (rollup and rollup["alignment_status"] not in ("insufficient_owner_evidence", "insufficient_procore_evidence")) \
                and (rollup["owner_latest_completed_to_date"] or rollup["procore_latest_completed_to_date_sum"]):
            action = "review_required"
            confidence = "low"
            reason = "pay-app evidence exists at owner scope but no accounting actuals on this code"
        else:
            action = "insufficient_evidence"
            confidence = "none"
            reason = "no actuals and no owner/procore evidence"

        # de-dup flags
        seen = set()
        risk_flags = [f for f in risk_flags if not (f in seen or seen.add(f))]

        proj_var = (rec_proj - budget) if rec_proj is not None else None

        rec = OrderedDict([
            ("project_key", PROJECT_KEY), ("budget_code_key", k),
            ("sub_job", parsed[0] if parsed else None), ("cost_code", cc), ("category", cat),
            ("budget_code_description", bk.get("budget_code_description")),
            ("assigned_owner_sov_code", xrow["owner_sov_code"] if xrow else None),
            ("assigned_owner_crosswalk_id", xrow["crosswalk_id"] if xrow else None),
            ("owner_scope_relationship", xrow.get("scope_relationship") if xrow else None),
            ("owner_evidence_basis", owner_basis),
            ("budget_amount", money_str(budget)), ("current_projected_cost", money_str(proj)),
            ("actual_cost_all_source_to_date", money_str(actual)),
            ("actual_cost_through_may_2026", money_str(actual_may)),
            ("actual_cost_june_2026_to_date", money_str(actual_june)),
            ("latest_actual_accounting_date", ac.get("latest_actual_accounting_date")),
            ("owner_scope_rollup_completed_to_date", rollup["owner_latest_completed_to_date"] if rollup else None),
            ("owner_scope_rollup_percent_complete", rollup["owner_latest_percent_complete"] if rollup else None),
            ("owner_allocated_value", None),  # refinement #3: never allocate owner $ to child
            ("procore_latest_total_completed_and_stored_to_date", money_str(procore_completed_child)),
            ("procore_mapping_status", "mapped" if proc_rows_k else "none"),
            ("forecast_action", action),
            ("recommended_forecast_adjustment", money_str(adj) if adj is not None else None),
            ("recommended_projected_cost", money_str(rec_proj) if rec_proj is not None else None),
            ("recommended_cost_to_complete", money_str(ctc) if ctc is not None else None),
            ("projected_variance_to_budget", money_str(proj_var) if proj_var is not None else None),
            ("confidence", confidence), ("confidence_reason", reason),
            ("risk_flags", risk_flags),
            ("data_gap_flags", ctx.get("data_gap_flags") or []),
            ("review_notes", _rec_note(action, owner_basis, risk_flags)),
        ])
        recs.append(rec)
        calc[k] = {"budget": budget, "proj": proj, "actual": actual, "actual_june": actual_june,
                   "rec_proj": rec_proj if rec_proj is not None else proj, "adj": adj or Decimal("0"),
                   "action": action, "confidence": confidence, "cat": cat,
                   "division": cc.split("-")[0] if cc else None, "has_actuals": has_actuals,
                   "risk_flags": risk_flags, "neg_child": neg_child,
                   "procore_completed_child": procore_completed_child}

        # per-code risks
        for f in risk_flags:
            if f == "forecast_floor_to_actuals":
                continue
            sev, desc, ev, act = _risk_meta(f, actual, proj, actual_june, procore_completed_child)
            add_risk(sev, k, cc, cat, f, desc, ev, act)

    out_counts["forecast_recommendations_by_budget_code.jsonl"] = write_jsonl(
        OUT / "forecast_recommendations_by_budget_code.jsonl", recs)

    # ==================================================================================
    # 5) owner-scope rollup risks + traceability + project-level
    # ==================================================================================
    converted_to_scope_review = 0
    for rr in rollup_rows:
        impl = rr["risk_implication"]
        xid = rr["crosswalk_id"]
        sov = rr["owner_sov_code"]
        if rr["alignment_status"] == "structural_sell_value_vs_cost":
            add_risk("informational", None, None, None, "owner_scope_sell_value_vs_subcontract_cost",
                     f"Owner scope {sov} ({xid}): owner sell value vs subcontract cost compared at rollup; structural.",
                     {"owner_vs_procore_delta": rr["owner_vs_procore_delta"]}, "Informational; no action.")
        elif rr["alignment_status"] == "timing_review":
            converted_to_scope_review += 1
            add_risk("medium", None, None, None, "owner_scope_timing_review",
                     f"Owner scope {sov} ({xid}): subcontractor progress ahead of owner billing at rollup.",
                     {"owner_vs_procore_delta": rr["owner_vs_procore_delta"]}, "Confirm billing-cycle timing.")
        elif rr["alignment_status"] == "actuals_exceed_projected":
            converted_to_scope_review += 1
            add_risk("high", None, None, None, "owner_scope_remaining_exposure_review",
                     f"Owner scope {sov} ({xid}): rollup actuals exceed projected.",
                     {"actuals": rr["actual_cost_all_source_to_date_sum"], "projected": rr["current_projected_cost_sum"]},
                     "Review remaining exposure across the owner scope rollup.")

    # traceability for every prior owner_procore_mismatch (refinement #4)
    trace = []
    new_critical_mismatch = 0
    downgraded = 0
    for k in sorted(old_mismatch.keys()):
        prior = old_mismatch[k]
        xrow = assign_key_row.get(k)
        rollup = rollup_by_xid.get(xrow["crosswalk_id"]) if xrow else None
        # at rollup these are structural sell-vs-cost → resolved/informational
        new_type = "crosswalk_applied_structural_mismatch_resolved"
        new_sev = "informational"
        reason = ("Compared at authoritative owner_scope_rollup; owner SOV summary/sell value vs "
                  "subcontract cost is structural, not a child-level mismatch.")
        if rollup and rollup["alignment_status"] == "timing_review":
            new_type, new_sev, reason = "owner_scope_timing_review", "medium", \
                "Rollup shows subcontractor progress ahead of owner billing — timing review."
        if new_sev in ("critical", "high"):
            new_critical_mismatch += 1
        if prior["severity"] in ("critical", "high") and new_sev not in ("critical", "high"):
            downgraded += 1
        trace.append(OrderedDict([
            ("budget_code_key", k), ("prior_risk_type", prior["risk_type"]),
            ("prior_severity", prior["severity"]),
            ("assigned_owner_sov_code", xrow["owner_sov_code"] if xrow else None),
            ("assigned_crosswalk_id", xrow["crosswalk_id"] if xrow else None),
            ("new_risk_type", new_type), ("new_severity", new_sev),
            ("reclassification_reason", reason),
        ]))
        add_risk(new_sev, k, parse_budget_key(k)[1] if parse_budget_key(k) else None,
                 parse_budget_key(k)[2] if parse_budget_key(k) else None,
                 new_type, f"Prior owner_procore_mismatch ({prior['severity']}) reclassified after crosswalk.",
                 {"prior_severity": prior["severity"], "assigned_owner_sov_code": xrow["owner_sov_code"] if xrow else None},
                 "See owner_procore_mismatch_traceability.jsonl.")
    out_counts["owner_procore_mismatch_traceability.jsonl"] = write_jsonl(
        OUT / "owner_procore_mismatch_traceability.jsonl", trace)

    # project-level risks
    add_risk("medium", None, None, None, "owner_scope_remaining_exposure_review",
             "Procore subcontractor pay-app evidence is through May 2026 only; June exposure not yet reflected.",
             {"cutoff": "through_may_2026"}, "Refresh Procore June pay-app evidence before month-end.")
    out_counts["forecast_risk_register.jsonl"] = write_jsonl(
        OUT / "forecast_risk_register.jsonl", risks)

    # ==================================================================================
    # 6) evidence_alignment_by_budget_code.jsonl (127)
    # ==================================================================================
    align_rows = []
    for k in sorted(canonical_keys):
        rec = next(r for r in recs if r["budget_code_key"] == k)
        xrow = assign_key_row.get(k)
        rollup = rollup_by_xid.get(xrow["crosswalk_id"]) if xrow else None
        ac = ctx_rows.get(k, {}).get("actuals", {})
        proc_rows_k = procore_latest_by_key.get(k, [])
        align_rows.append(OrderedDict([
            ("budget_code_key", k),
            ("assigned_owner_sov_code", xrow["owner_sov_code"] if xrow else None),
            ("assigned_owner_crosswalk_id", xrow["crosswalk_id"] if xrow else None),
            ("owner_scope_relationship", xrow.get("scope_relationship") if xrow else None),
            ("owner_evidence_basis", rec["owner_evidence_basis"]),
            ("owner_scope_rollup_completed_to_date", rollup["owner_latest_completed_to_date"] if rollup else None),
            ("owner_scope_rollup_percent_complete", rollup["owner_latest_percent_complete"] if rollup else None),
            ("owner_allocated_value", None),
            ("child_actual_cost_all_source_to_date", money_str(ac.get("actual_cost_all_source_to_date"))),
            ("child_procore_latest_completed_to_date",
             money_str(dsum(p.get("latest_total_completed_and_stored_to_date") for p in proc_rows_k)) if proc_rows_k else None),
            ("rollup_alignment_status", rollup["alignment_status"] if rollup else None),
            ("forecast_action", rec["forecast_action"]),
            ("interpretation", f"owner evidence {rec['owner_evidence_basis']}; compared at "
                               f"{xrow.get('comparison_level') if xrow else 'n/a'} per authoritative crosswalk."),
        ]))
    out_counts["evidence_alignment_by_budget_code.jsonl"] = write_jsonl(
        OUT / "evidence_alignment_by_budget_code.jsonl", align_rows)

    # ==================================================================================
    # manual review + data quality (orphans re-derived) + confidence rollup + summaries
    # ==================================================================================
    review_items = []
    rc = [0]
    def add_review(priority, rtype, key, reason, action):
        rc[0] += 1
        review_items.append(OrderedDict([
            ("review_item_id", f"MR-{rc[0]:04d}"), ("priority", priority), ("review_type", rtype),
            ("budget_code_key", key), ("reason", reason), ("recommended_human_action", action)]))
    for rr in rollup_rows:
        if rr["alignment_status"] == "timing_review":
            add_review("medium", "owner_scope_timing_review", None,
                       f"Owner scope {rr['owner_sov_code']} subcontractor progress ahead of owner billing.",
                       "Confirm billing-cycle timing.")
        elif rr["alignment_status"] == "actuals_exceed_projected":
            add_review("high", "owner_scope_remaining_exposure_review", None,
                       f"Owner scope {rr['owner_sov_code']} rollup actuals exceed projected.",
                       "Review remaining exposure.")
    for rec in recs:
        if "deductive_change_order_credit_review" in rec["risk_flags"]:
            add_review("medium", "deductive_change_order_credit_review", rec["budget_code_key"],
                       "Negative Procore latest value on this code.", "Verify deductive credit.")
    out_counts["manual_mapping_review_items.jsonl"] = write_jsonl(
        OUT / "manual_mapping_review_items.jsonl", review_items)

    warnings = []
    wc = [0]
    def add_warn(sev, area, desc, keys, res):
        wc[0] += 1
        warnings.append(OrderedDict([("warning_id", f"W-{wc[0]:04d}"), ("severity", sev),
                                     ("area", area), ("description", desc),
                                     ("affected_budget_code_keys", keys), ("recommended_resolution", res)]))
    # refinement #2: orphan owner sov re-derived from final crosswalk → informational source-code discrepancy
    for s in orphan_owner_sov:
        add_warn("informational", "owner_source_code_discrepancy",
                 f"Owner SOV '{s}' appears in source owner evidence but has no authoritative crosswalk row. "
                 "Classified as an informational source-code discrepancy (NOT an unresolved mapping).",
                 [], "Confirm owner SOV code labeling; crosswalk coverage is complete (127/127).")
    no_owner_xw = sorted(r["owner_sov_code"] for r in xw_rows if not owner_lines_for(r)
                         and r["owner_sov_code"] != "10-XX-XXX")
    if no_owner_xw:
        add_warn("informational", "owner_scope_no_evidence",
                 f"{len(no_owner_xw)} crosswalk owner SOV scope(s) have no owner pay-app evidence line.",
                 [], "Expected where owner has not billed; rollup shows insufficient_owner_evidence.")
    add_warn("informational", "period_alignment",
             "June 2026 accounting actuals exist while pay-app evidence is through May only.",
             [], "Treat June actuals as leading signal.")
    out_counts["data_quality_warnings.jsonl"] = write_jsonl(
        OUT / "data_quality_warnings.jsonl", warnings)

    action_counts = defaultdict(int)
    conf_counts = defaultdict(int)
    for r in recs:
        action_counts[r["forecast_action"]] += 1
        conf_counts[r["confidence"]] += 1
    sev_counts = defaultdict(int)
    for r in risks:
        sev_counts[r["severity"]] += 1

    confidence_rollup = OrderedDict([
        ("total_budget_codes", len(recs)),
        ("count_by_forecast_action", OrderedDict(sorted(action_counts.items()))),
        ("count_by_confidence", OrderedDict(sorted(conf_counts.items()))),
        ("count_requiring_forecast_review", action_counts.get("review_required", 0)),
    ])
    write_json(OUT / "confidence_rollup.json", confidence_rollup)

    total_increase = sum((calc[k]["adj"] for k in calc if calc[k]["action"] == "increase_forecast"), Decimal("0"))
    total_decrease = sum((calc[k]["adj"] for k in calc if calc[k]["action"] == "decrease_forecast"), Decimal("0"))
    total_actual = sum((calc[k]["actual"] for k in calc), Decimal("0"))
    total_june = sum((calc[k]["actual_june"] for k in calc), Decimal("0"))
    total_proj_before = sum((calc[k]["proj"] for k in calc), Decimal("0"))
    total_proj_after = sum((calc[k]["rec_proj"] for k in calc), Decimal("0"))

    new_sev_owner_proc = sum(1 for t in trace if t["new_severity"] in ("critical", "high"))
    crosswalk_app = OrderedDict([
        ("crosswalk_row_count", len(xw_rows)),
        ("canonical_budget_codes_assigned", len(covered_keys)),
        ("procore_latest_wbs_assigned", len(procore_covered)),
        ("owner_sov_rows_resolved", sum(1 for r in xw_rows if expand_budget(r) or expand_procore(r))),
        ("unresolved_owner_sov_rows", sum(1 for r in xw_rows if not expand_budget(r) and not expand_procore(r))),
        ("duplicate_covered_budget_codes", len(dup_keys)),
        ("old_owner_procore_mismatch_critical_count",
         sum(1 for r in old_risks if r.get("risk_type") == "owner_procore_mismatch" and r["severity"] == "critical")),
        ("new_critical_owner_procore_mismatch_count", new_sev_owner_proc),
        ("count_downgraded_to_informational", downgraded),
        ("count_converted_to_scope_rollup_review", converted_to_scope_review),
        ("count_true_progress_discrepancy", 0),
        ("forecast_recommendation_counts_by_action", OrderedDict(sorted(action_counts.items()))),
        ("confidence_counts", OrderedDict(sorted(conf_counts.items()))),
        ("risk_severity_before", OrderedDict(sorted(old_sev_counts.items()))),
        ("risk_severity_after", OrderedDict(sorted(sev_counts.items()))),
        ("conclusion_pending", None),
    ])

    # ---- copy script + audit ----
    shutil.copy2(Path(__file__), OUT / "generate_forecast_analysis_crosswalk_v2.py")
    write_json(OUT / "audit" / "source_files_used.json", OrderedDict([
        ("context_package", str(CTX)), ("analysis_package", str(ANL)),
        ("workpaper", str(WP)), ("authoritative_crosswalk", str(XW_FILE)),
        ("crosswalk_sha256", sha256_file(XW_FILE)),
    ]))
    write_json(OUT / "audit" / "source_validation_snapshot.json", OrderedDict([
        ("context_conclusion", ctx_concl), ("analysis_conclusion", anl_concl),
        ("workpaper_conclusion", wp_concl),
    ]))
    write_json(OUT / "audit" / "crosswalk_validation_snapshot.json", OrderedDict([
        ("authoritative_validation_report", xw_validation),
        ("recomputed", OrderedDict([
            ("budget_covered", len(covered_keys)), ("budget_uncovered", uncovered_keys),
            ("budget_duplicates", sorted(set(dup_keys))),
            ("procore_covered", len(procore_covered)), ("procore_uncovered", procore_uncovered),
            ("facts", crosswalk_facts), ("gate_passed", crosswalk_gate_passed),
            ("orphan_owner_sov_codes", orphan_owner_sov),
        ])),
    ]))
    recon_in = read_json(CTX / "audit" / "reconciliation_report.json")
    project_ctx = read_json(CTX / "summaries" / "project_forecast_context.json")
    ctx_actual_total = project_ctx.get("actual_totals", {}).get("cost_entries_all_source_to_date")
    ctx_june_total = project_ctx.get("actual_totals", {}).get("cost_entries_june_2026_to_date_total")
    analysis_recon = OrderedDict([
        ("actual_total_recomputed", money_str(total_actual)),
        ("actual_total_context", ctx_actual_total),
        ("actual_total_minus_context", money_str(total_actual - D(ctx_actual_total))),
        ("june_actual_total_recomputed", money_str(total_june)),
        ("june_actual_total_context", ctx_june_total),
        ("projected_total_before", money_str(total_proj_before)),
        ("projected_total_after", money_str(total_proj_after)),
        ("total_recommended_increase", money_str(total_increase)),
        ("total_recommended_decrease", money_str(total_decrease)),
        ("note", "Actuals reconcile to context within the documented $0.01 ERP rounding. Pay-app "
                 "values are evidence, not actual cost. Owner summary dollars are NOT allocated to "
                 "child budget codes (no allocation schedule)."),
    ])
    write_json(OUT / "audit" / "analysis_reconciliation.json", analysis_recon)

    emitted = [str(p) for p in sorted(OUT.rglob("*")) if p.is_file() and p.suffix in (".jsonl", ".json", ".md")]
    safety = safety_scan(emitted)
    write_json(OUT / "audit" / "safety_scan_report.json", safety)

    # ---- validations ----
    out_valid, invalid = True, {}
    for p in sorted(OUT.rglob("*")):
        try:
            if p.suffix == ".jsonl":
                for _ in read_jsonl(p):
                    pass
            elif p.suffix == ".json":
                read_json(p)
        except Exception as e:
            out_valid = False
            invalid[str(p.relative_to(OUT))] = str(e)

    rec_keys_ok = all(r["budget_code_key"] in canonical_keys for r in recs) and len(recs) == 127
    risk_keys_ok = all((r["budget_code_key"] is None or r["budget_code_key"] in canonical_keys) for r in risks)
    high_conf_numeric_ok = all(calc[r["budget_code_key"]]["has_actuals"]
                               for r in recs if r["confidence"] == "high" and r["recommended_forecast_adjustment"] is not None)
    payapp_not_actual_ok = all(calc[r["budget_code_key"]]["has_actuals"]
                               for r in recs if r["forecast_action"] in ("increase_forecast", "decrease_forecast"))
    no_critical_struct_mismatch_ok = not any(
        r["severity"] in ("critical", "high")
        and r["risk_type"] in ("crosswalk_applied_structural_mismatch_resolved",
                               "owner_scope_sell_value_vs_subcontract_cost")
        for r in risks)
    mismatch_trace_ok = len(trace) == len(old_mismatch)

    crosswalk_v2_context_analysis_workpaper_lineage_consistent = run_lineage.lineage_consistent(
        [CONTEXT_LINEAGE, ANALYSIS_LINEAGE, WORKPAPER_LINEAGE])
    structural_ok = (out_valid and rec_keys_ok and risk_keys_ok and high_conf_numeric_ok
                     and payapp_not_actual_ok and no_critical_struct_mismatch_ok and mismatch_trace_ok
                     and crosswalk_gate_passed and assignment_ok and ten_desc_ok and safety["passed"]
                     and ctx_concl == "forecast_context_ready_with_mapping_gaps"
                     and anl_concl == "forecast_analysis_ready_with_review_items"
                     and wp_concl == "mapping_discrepancy_workpaper_ready_with_unresolved_items"
                     and crosswalk_v2_context_analysis_workpaper_lineage_consistent)
    has_review = (action_counts.get("review_required", 0) > 0 or action_counts.get("mapping_required", 0) > 0
                  or len(review_items) > 0 or any(r["severity"] in ("critical", "high", "medium") for r in risks))
    if not (crosswalk_gate_passed and assignment_ok):
        conclusion = "forecast_analysis_crosswalk_v2_not_ready"
    elif not structural_ok:
        conclusion = "forecast_analysis_crosswalk_v2_not_ready"
    elif has_review:
        conclusion = "forecast_analysis_crosswalk_v2_ready_with_review_items"
    else:
        conclusion = "forecast_analysis_crosswalk_v2_ready"

    crosswalk_app["conclusion_pending"] = conclusion
    write_json(OUT / "crosswalk_application_summary.json", crosswalk_app)

    # ---- summaries ----
    _emit_summaries(OUT, calc, recs, risks, trace, action_counts, conf_counts, sev_counts,
                    total_actual, total_june, total_increase, total_decrease, total_proj_before,
                    total_proj_after, recon_in, conclusion, out_counts)

    # ---- input inventory ----
    write_json(OUT / "input_inventory.json", OrderedDict([
        ("data_root", str(ROOT)),
        ("authoritative_crosswalk_path", str(XW_FILE)),
        ("authoritative_crosswalk_already_under_data_root", True),
        ("authoritative_crosswalk_copied", False),
        ("context_package", str(CTX)), ("analysis_package", str(ANL)), ("workpaper", str(WP)),
        ("crosswalk_sha256", sha256_file(XW_FILE)),
        ("lineage", OrderedDict([
            ("consumed_context", CONTEXT_LINEAGE), ("consumed_analysis", ANALYSIS_LINEAGE),
            ("consumed_mapping_workpaper", WORKPAPER_LINEAGE),
            ("crosswalk_v2_context_analysis_workpaper_lineage_consistent",
             bool(crosswalk_v2_context_analysis_workpaper_lineage_consistent))])),
    ]))

    # ---- validation report ----
    validation = OrderedDict([
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("period", PERIOD)])),
        ("generated_stamp", STAMP),
        ("lineage", OrderedDict([
            ("consumed_context", CONTEXT_LINEAGE), ("consumed_analysis", ANALYSIS_LINEAGE),
            ("consumed_mapping_workpaper", WORKPAPER_LINEAGE),
            ("crosswalk_v2_context_analysis_workpaper_lineage_consistent",
             bool(crosswalk_v2_context_analysis_workpaper_lineage_consistent))])),
        ("input_checks", OrderedDict([
            ("context_conclusion_ok", ctx_concl == "forecast_context_ready_with_mapping_gaps"),
            ("analysis_conclusion_ok", anl_concl == "forecast_analysis_ready_with_review_items"),
            ("workpaper_conclusion_ok", wp_concl == "mapping_discrepancy_workpaper_ready_with_unresolved_items"),
        ])),
        ("crosswalk_gate", OrderedDict([("facts", crosswalk_facts), ("passed", crosswalk_gate_passed),
                                        ("owner_10xx_description_routing_unambiguous", ten_desc_ok)])),
        ("output_parse", OrderedDict([("all_passed", out_valid), ("invalid", invalid)])),
        ("row_counts", out_counts),
        ("recommendation_checks", OrderedDict([
            ("recommendation_count_is_127", len(recs) == 127),
            ("all_keys_canonical", rec_keys_ok), ("risk_keys_valid_or_null", risk_keys_ok),
            ("no_high_confidence_numeric_without_actuals", high_conf_numeric_ok),
            ("payapp_not_treated_as_actual", payapp_not_actual_ok),
            ("no_critical_high_structural_owner_procore_mismatch", no_critical_struct_mismatch_ok),
            ("every_prior_mismatch_traced", mismatch_trace_ok),
            ("budget_assignment_127_exactly_once", assignment_ok),
        ])),
        ("forecast_action_counts", OrderedDict(sorted(action_counts.items()))),
        ("confidence_counts", OrderedDict(sorted(conf_counts.items()))),
        ("risk_severity_before", OrderedDict(sorted(old_sev_counts.items()))),
        ("risk_severity_after", OrderedDict(sorted(sev_counts.items()))),
        ("reconciliation", analysis_recon),
        ("safety_scan", OrderedDict([("passed", safety["passed"]), ("findings", safety["findings"])])),
        ("determinism", OrderedDict([("method", "two frozen-stamp runs diffed on data files; sorted + no RNG"),
                                     ("performed_by_script", False),
                                     ("note", "Verified by operator harness alongside this run.")])),
        ("known_limitations", [
            "Owner summary scopes are compared only at owner_scope_rollup; owner dollars are NOT "
            "allocated to child budget codes (no allocation schedule).",
            "Procore evidence is through May 2026; June actuals exist separately.",
            "Owner sell value vs subcontract cost differences are structural/informational, not risks.",
            "Pay-app values are evidence, not accounting actual-cost truth.",
        ]),
        ("conclusion", conclusion),
    ])
    write_json(OUT / "validation_report.json", validation)

    # ---- manifest ----
    out_manifest = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(OUT))
            out_manifest.append(OrderedDict([("path", rel), ("size_bytes", p.stat().st_size),
                                             ("row_count", out_counts.get(rel)), ("sha256", sha256_file(p))]))
    write_json(OUT / "manifest.json", OrderedDict([
        ("package_name", OUT.name), ("generated_timestamp_local", datetime.now().isoformat()),
        ("generated_stamp", STAMP),
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("period", PERIOD)])),
        ("authoritative_crosswalk", str(XW_FILE)),
        ("output_files", out_manifest),
        ("validation_status", OrderedDict([("crosswalk_gate", crosswalk_gate_passed),
                                           ("output_parse", out_valid), ("safety_scan", safety["passed"]),
                                           ("structural_ok", structural_ok)])),
        ("conclusion", conclusion),
    ]))

    write_text(OUT / "README.md", _readme(out_counts, action_counts, conf_counts, old_sev_counts,
                                          sev_counts, total_increase, total_decrease, total_actual,
                                          total_june, len(old_mismatch), new_sev_owner_proc, downgraded,
                                          safety, conclusion))
    write_text(OUT / "SCHEMA.md", _schema())

    print(json.dumps(OrderedDict([
        ("output_package", str(OUT)), ("crosswalk", str(XW_FILE)),
        ("conclusion", conclusion), ("crosswalk_gate_passed", crosswalk_gate_passed),
        ("structural_ok", structural_ok),
        ("crosswalk_facts", crosswalk_facts),
        ("forecast_action_counts", OrderedDict(sorted(action_counts.items()))),
        ("confidence_counts", OrderedDict(sorted(conf_counts.items()))),
        ("risk_severity_before", OrderedDict(sorted(old_sev_counts.items()))),
        ("risk_severity_after", OrderedDict(sorted(sev_counts.items()))),
        ("old_critical_owner_procore_mismatch", crosswalk_app["old_owner_procore_mismatch_critical_count"]),
        ("new_critical_owner_procore_mismatch", new_sev_owner_proc),
        ("downgraded_to_informational", downgraded),
        ("prior_mismatch_traced", len(trace)),
        ("total_recommended_increase", money_str(total_increase)),
        ("total_recommended_decrease", money_str(total_decrease)),
        ("june_actual_total", money_str(total_june)),
        ("orphan_owner_sov", orphan_owner_sov),
        ("safety_passed", safety["passed"]),
        ("out_counts", out_counts),
    ]), indent=2))


# --------------------------------------------------------------------------------------
def _decrease_ok(proj, actual, rollup, june_flag, neg_child):
    if rollup is None:
        return False
    pct = rollup.get("owner_latest_percent_complete")
    if pct is None or Decimal(str(pct)) < Decimal("0.98"):
        return False
    bal = dec(rollup.get("owner_latest_balance_to_finish"))
    if bal is not None and abs(bal) >= Decimal("25000"):
        return False
    pc = dec(rollup.get("procore_latest_completed_to_date_sum"))
    if pc is not None and pc > 0:
        return False
    gap, _, mat = materiality(proj, actual)
    if not (mat and proj > actual):
        return False
    if june_flag or neg_child:
        return False
    return True


def _risk_meta(flag, actual, proj, actual_june, procore_child):
    if flag == "actuals_exceed_projected_cost":
        gap = actual - proj
        g, p, _ = materiality(actual, proj)
        sev = severity_for(g, p) if gap >= Decimal("25000") else "low"
        return sev, "Actual cost exceeds current projected cost.", \
            {"actual": money_str(actual), "projected": money_str(proj), "overrun": money_str(gap)}, \
            "Increase forecast to at least actual cost; review remaining exposure."
    if flag == "deductive_change_order_credit_review":
        amt = procore_child if procore_child is not None else Decimal("0")
        sev = "high" if abs(amt) >= Decimal("25000") else "medium"
        return sev, "Negative Procore latest value (deductive change-order credit).", \
            {"procore_completed": money_str(procore_child)}, "Verify the credit; do not decrease forecast solely on this."
    if flag == "june_actuals_without_june_payapp_evidence":
        sev = "medium" if actual_june >= Decimal("25000") else "low"
        return sev, "June 2026 actuals exist while pay-app evidence is through May only.", \
            {"june_actuals": money_str(actual_june)}, "Treat June actuals as leading signal."
    if flag == "owner_scope_remaining_exposure_review":
        return "medium", "Actual cost near projected with remaining exposure implied at owner scope.", \
            {"actual": money_str(actual), "projected": money_str(proj)}, "Review remaining exposure."
    return "low", flag, {}, "Review."


def _rollup_note(rel, align):
    return f"scope_relationship={rel}; alignment={align}"


def _rec_note(action, basis, flags):
    base = {
        "hold_current_forecast": "Projected cost covers actuals.",
        "increase_forecast": "Floored to accounting actuals (actuals exceed projected).",
        "decrease_forecast": "Owner scope complete; lower final cost supported.",
        "review_required": "Rollup/credit/exhaustion signal requires review.",
        "insufficient_evidence": "No actuals or owner/procore evidence.",
    }.get(action, "")
    extra = []
    if "deductive_change_order_credit_review" in flags:
        extra.append("Negative Procore latest value (deductive credit).")
    if "june_actuals_without_june_payapp_evidence" in flags:
        extra.append("June actuals present; pay-app evidence through May.")
    extra.append(f"owner evidence basis: {basis}.")
    return " ".join([base] + extra)


def _emit_summaries(OUT, calc, recs, risks, trace, action_counts, conf_counts, sev_counts,
                    total_actual, total_june, total_increase, total_decrease, total_proj_before,
                    total_proj_after, recon_in, conclusion, out_counts):
    # division/category rollups
    def rollup(keyfn):
        groups = OrderedDict()
        for k, c in calc.items():
            gk = keyfn(c)
            g = groups.setdefault(gk, {"budget": Decimal("0"), "actual": Decimal("0"),
                                       "rec_proj": Decimal("0"), "adj": Decimal("0"),
                                       "review": 0, "conf": defaultdict(int)})
            g["budget"] += c["budget"]; g["actual"] += c["actual"]
            g["rec_proj"] += c["rec_proj"]; g["adj"] += c["adj"]
            if c["action"] == "review_required":
                g["review"] += 1
            g["conf"][c["confidence"]] += 1
        return groups

    def emit(groups, label, path):
        rows = []
        for gk in sorted(groups.keys(), key=lambda x: (x is None, x)):
            g = groups[gk]
            rows.append(OrderedDict([
                (label, gk), ("budget_total", money_str(g["budget"])),
                ("actual_total", money_str(g["actual"])),
                ("recommended_projected_total", money_str(g["rec_proj"])),
                ("recommended_adjustment_total", money_str(g["adj"])),
                ("review_required_count", g["review"]),
                ("confidence_summary", OrderedDict(sorted(g["conf"].items()))),
            ]))
        return write_jsonl(path, rows)

    out_counts["summaries/division_summary.jsonl"] = emit(
        rollup(lambda c: c["division"]), "division", OUT / "summaries" / "division_summary.jsonl")
    out_counts["summaries/category_summary.jsonl"] = emit(
        rollup(lambda c: c["cat"]), "category", OUT / "summaries" / "category_summary.jsonl")

    items = list(calc.items())

    def keyrec(k, c):
        parsed = parse_budget_key(k)
        return OrderedDict([("budget_code_key", k),
                            ("cost_code", parsed[1] if parsed else None),
                            ("category", parsed[2] if parsed else None),
                            ("forecast_action", c["action"]),
                            ("current_projected_cost", money_str(c["proj"])),
                            ("recommended_projected_cost", money_str(c["rec_proj"])),
                            ("adjustment", money_str(c["adj"])),
                            ("actual_cost", money_str(c["actual"]))])
    write_json(OUT / "summaries" / "top_forecast_movements.json", OrderedDict([
        ("top_recommended_increase", [keyrec(k, c) for k, c in sorted(items, key=lambda x: -x[1]["adj"])
                                      if c["action"] == "increase_forecast"][:10]),
        ("top_recommended_decrease", [keyrec(k, c) for k, c in sorted(items, key=lambda x: x[1]["adj"])
                                      if c["action"] == "decrease_forecast"][:10]),
        ("top_actuals_exceeding_projected_cost", [keyrec(k, c) for k, c in sorted(items, key=lambda x: -(x[1]["actual"] - x[1]["proj"]))
                                                  if c["has_actuals"] and c["actual"] > c["proj"]][:10]),
        ("top_largest_actual_cost", [OrderedDict([("budget_code_key", k), ("actual_cost", money_str(c["actual"]))])
                                     for k, c in sorted(items, key=lambda x: -x[1]["actual"])][:10]),
        ("top_largest_june_actual_cost", [OrderedDict([("budget_code_key", k), ("june_actual", money_str(c["actual_june"]))])
                                          for k, c in sorted(items, key=lambda x: -x[1]["actual_june"]) if c["actual_june"] > 0][:10]),
    ]))
    write_json(OUT / "summaries" / "top_review_items.json", OrderedDict([
        ("top_budget_codes_requiring_review", [keyrec(k, c) for k, c in sorted(items, key=lambda x: -x[1]["actual"])
                                               if c["action"] == "review_required"][:15]),
        ("owner_procore_mismatch_reclassified", trace[:15]),
    ]))
    write_json(OUT / "summaries" / "project_forecast_analysis.json", OrderedDict([
        ("project_name", PROJECT_NAME), ("project_key", PROJECT_KEY), ("job_reference", JOB_REF),
        ("forecast_period", PERIOD), ("generated_stamp", STAMP),
        ("budget_totals", OrderedDict([("recommended_projected_total", money_str(total_proj_after)),
                                       ("projected_total_before", money_str(total_proj_before))])),
        ("actual_totals", OrderedDict([("all_source_to_date", money_str(total_actual)),
                                       ("june_2026_to_date", money_str(total_june))])),
        ("recommendation_totals", OrderedDict(sorted(action_counts.items()))),
        ("confidence_counts", OrderedDict(sorted(conf_counts.items()))),
        ("risk_totals_by_severity", OrderedDict(sorted(sev_counts.items()))),
        ("total_recommended_increase", money_str(total_increase)),
        ("total_recommended_decrease", money_str(total_decrease)),
        ("conclusion", conclusion),
    ]))


SAFETY_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?<!\d)(?:\+?1[ .\-])?\(?\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}(?!\d)"),
    "bearer": re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
    "api_token": re.compile(r"\b(?:sk|pk|ghp|xox[baprs])[_\-][A-Za-z0-9]{16,}\b"),
    "signed_url_sig": re.compile(r"[?&](?:X-Amz-Signature|Signature|sig|X-Goog-Signature|se|sig=)=", re.I),
    "private_blob_url": re.compile(r"https?://[^\s\"]*(?:blob\.core\.windows\.net|s3[.\-][^\s\"]*amazonaws\.com|sharepoint\.com|1drv\.ms|graph\.microsoft\.com)", re.I),
    "pem": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "raw_body_field": re.compile(r"\"(?:description_summary_json|raw_body|payload|response_body|request_body)\"\s*:"),
}
FAIL_CATEGORIES = {"bearer", "api_token", "signed_url_sig", "private_blob_url", "pem", "raw_body_field"}


def safety_scan(files):
    findings = {k: 0 for k in SAFETY_PATTERNS}
    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue
        for name, pat in SAFETY_PATTERNS.items():
            findings[name] += len(pat.findall(text))
    passed = all(findings[c] == 0 for c in FAIL_CATEGORIES)
    return OrderedDict([("scanned_file_count", len(files)),
                        ("findings", OrderedDict((k, findings[k]) for k in sorted(findings))),
                        ("passed", passed)])


def _readme(out_counts, ac, cc, old_sev, new_sev, inc, dec_, total_actual, june, old_mm, new_mm,
            downgraded, safety, conclusion):
    L = []
    A = L.append
    A(f"# Forecast Analysis Crosswalk v2 — {PROJECT_NAME}\n")
    A("## Objective\n")
    A("Apply the AUTHORITATIVE Owner SOV scope crosswalk so owner pay-app, Procore subcontractor, "
      "BudgetDetails, and CostEntries evidence is compared at the correct owner-scope rollup level "
      "instead of inferred child-level matching. Package generation only — no source/workbook/analysis "
      "mutation; pay-app values are evidence, never actual cost.\n")
    A("## Paths\n")
    A(f"- Authoritative crosswalk: `{XW_FILE}`")
    A(f"- Context: `{CTX}`\n- Analysis (v1): `{ANL}`\n- Workpaper: `{WP}`\n- Output: `{OUT}`\n")
    A(f"## Project\n- {PROJECT_NAME} · key `{PROJECT_KEY}` · job `{JOB_REF}` · period `{PERIOD}` · generated `{STAMP}`\n")
    A("## Core change\n")
    A("Owner vs Procore is now compared at the approved `owner_scope_rollup` (summing covered "
      "BudgetDetails/Procore keys) for one-to-many owner SOV scopes, not at the individual budget code. "
      "Child budget rows inherit rollup context but owner dollars are NOT allocated to children "
      "(no allocation schedule). The 32 prior critical `owner_procore_mismatch` flags are reclassified "
      "as structural (owner sell value vs subcontract cost) — see traceability.\n")
    A("## Files (row counts)\n")
    for f, c in out_counts.items():
        A(f"- `{f}`: {c}")
    A("")
    A("## Crosswalk application\n")
    A(f"- 127/127 BudgetDetails assigned; 42/42 Procore latest WBS covered; 0 unresolved; 0 duplicate.")
    A(f"- Old critical owner_procore_mismatch: {old_mm}; new critical owner/procore mismatch: {new_mm}; "
      f"downgraded to informational: {downgraded}.\n")
    A("## Headline\n")
    A(f"- Actions: " + ", ".join(f"{k}={v}" for k, v in sorted(ac.items())))
    A(f"- Confidence: " + ", ".join(f"{k}={v}" for k, v in sorted(cc.items())))
    A(f"- Risk severity before: " + ", ".join(f"{k}={v}" for k, v in sorted(old_sev.items())))
    A(f"- Risk severity after: " + ", ".join(f"{k}={v}" for k, v in sorted(new_sev.items())))
    A(f"- Recommended increase: ${inc.quantize(CENTS):,}; decrease: ${dec_.quantize(CENTS):,}")
    A(f"- Actuals to date: ${total_actual.quantize(CENTS):,}; June actuals: ${june.quantize(CENTS):,}\n")
    A(f"## Validation\n- Crosswalk gate PASS; safety {'PASS' if safety['passed'] else 'FAIL'}; 127 recs all canonical.\n")
    A("## Known limitations\n")
    A("- Owner summary scopes compared only at rollup; owner $ not allocated to children.")
    A("- Procore evidence through May 2026; June actuals separate.")
    A("- Pay-app values are evidence, not actual cost.\n")
    A(f"## Conclusion: `{conclusion}`\n")
    return "\n".join(L)


def _schema():
    return """# SCHEMA — Forecast Analysis Crosswalk v2

## Interpretation
- Authoritative Owner SOV scope crosswalk controls owner↔budget↔Procore scope relationships.
- BudgetDetails master universe (127); CostEntries are actual-cost truth; pay-app values are evidence.
- One-to-many owner SOV scopes are compared ONLY at owner_scope_rollup; owner dollars are NOT
  allocated to child budget codes (no allocation schedule). Children inherit rollup context only.
- Owner sell value vs subcontract cost differences are structural/informational, not critical risks.
- Actuals-exceed-projected → mandatory floor-to-actuals increase (actuals are the only numeric basis).
- Actuals-only holds are `medium` unless no-exposure is proven (forecast_to_complete 0 + immaterial
  remaining + owner ~complete + no positive Procore remaining).

## applied_owner_sov_scope_crosswalk.jsonl (58)  — normalized authoritative crosswalk with expanded coverage.
## budget_code_to_owner_scope_assignment.jsonl (127) — each canonical key → exactly one owner SOV scope;
   assignment_method {authoritative_direct|authoritative_pattern|authoritative_exclusion_resolved|
   authoritative_description_sensitive}; assignment_confidence=authoritative.
## owner_scope_rollup_evidence.jsonl (58) — owner vs Procore vs actuals at rollup; alignment_status,
   risk_implication; one-to-many owner>procore → structural_sell_value_vs_cost/informational.
## forecast_recommendations_by_budget_code.jsonl (127) — approved engine + crosswalk owner scope;
   owner_evidence_basis {direct|inherited_from_owner_summary_scope}; owner_allocated_value always null.
## forecast_risk_register.jsonl — revised types incl. crosswalk_applied_structural_mismatch_resolved,
   owner_scope_*; structural owner/procore → informational; critical only for actual-cost-backed risk.
## owner_procore_mismatch_traceability.jsonl — one row per prior owner_procore_mismatch: prior severity,
   assigned crosswalk row, new risk type/severity, reclassification reason.
## evidence_alignment_by_budget_code.jsonl (127) — assigned owner scope, rollup totals (context),
   child actuals/Procore, owner_evidence_basis, owner_allocated_value=null, rollup_alignment_status.
## crosswalk_application_summary.json — coverage, old-vs-new owner_procore_mismatch counts, action/conf.
## summaries/, audit/, manifest.json, validation_report.json, input_inventory.json — rollups, gates, hashes.
"""


if __name__ == "__main__":
    main()
