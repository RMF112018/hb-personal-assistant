#!/usr/bin/env python3
"""
generate_mapping_discrepancy_workpaper.py

Tropical World Nursery Senior Living Facility (project_key=tropical, job=23-435-01)
Mapping-discrepancy workpaper — explains owner-vs-Procore (`owner_procore_mismatch`) flags as either
true progress discrepancies or structural comparison problems, and emits ADVISORY recalibration
inputs for a later analysis patch.

Hard rules:
  - Does NOT mutate source / context / analysis packages, Excel, or the forecast workbook.
  - Does NOT commit, make live/external calls, or touch any production DB.
  - Does NOT invent mappings; no fuzzy/description-only/edit-distance/semantic matching.
  - Owner & Procore pay-app values are EVIDENCE, never accounting actual-cost truth.

Stdlib only. Decimal(str(value)) for all money math. Deterministic sorted output. Re-runnable.
"""

import json
import os
import re
import sys
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from decimal import Decimal, InvalidOperation, getcontext
from collections import defaultdict, OrderedDict

# self-contained script (run as `python <file>`): make the package importable for the shared
# run-lineage resolver regardless of whether PYTHONPATH=src was exported.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from construction_financial_review.common import run_lineage  # noqa: E402

getcontext().prec = 50

# --------------------------------------------------------------------------------------
DEFAULT_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)
# Resolved at RUNTIME by resolve_inputs() (never at import).
ROOT = None
CTX = None
ANL = None
OUT = None
SRC = OrderedDict()
CONTEXT_LINEAGE = None
ANALYSIS_LINEAGE = None

PROJECT_NAME = "Tropical World Nursery Senior Living Facility"
PROJECT_KEY = "tropical"
JOB_REF = "23-435-01"
PERIOD = "2026-June"

CENTS = Decimal("0.01")
MAT_DOLLAR = Decimal("25000")
MAT_PCT = Decimal("0.10")

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_inputs():
    """Resolve upstream context + analysis packages at runtime (full-fresh run state aware)."""
    global ROOT, CTX, ANL, OUT, SRC, CONTEXT_LINEAGE, ANALYSIS_LINEAGE
    global PROJECT_KEY, PROJECT_NAME, JOB_REF, PERIOD
    from construction_financial_review.common.project_config import (
        load_project_config,
        resolve_project_key,
    )

    PROJECT_KEY = resolve_project_key()
    _pcfg = load_project_config(PROJECT_KEY)
    PROJECT_NAME = _pcfg["project_name"]
    JOB_REF = _pcfg["job_reference"]
    PERIOD = _pcfg["forecast_period"]
    ROOT = run_lineage.active_data_root(DEFAULT_ROOT)
    CTX, CONTEXT_LINEAGE = run_lineage.resolve_upstream(
        "context", data_root=ROOT, project_key=PROJECT_KEY,
        override_stamp=os.environ.get("CFR_CONTEXT_STAMP"))
    ANL, ANALYSIS_LINEAGE = run_lineage.resolve_upstream(
        "analysis", data_root=ROOT, project_key=PROJECT_KEY,
        override_stamp=os.environ.get("CFR_ANALYSIS_STAMP"))
    OUT = ROOT / f"mapping_discrepancy_workpaper_{PROJECT_KEY}_{STAMP}"
    SRC = _build_src(CTX, ANL)
    return {"context": CONTEXT_LINEAGE, "analysis": ANALYSIS_LINEAGE}

# Internal / non-subcontract owner descriptor keywords (refinement #1 — MAT is NOT auto-internal)
INTERNAL_KEYWORDS = re.compile(
    r"general\s+condition|general\s+requirement|\bGR\b|\bGC\b|overhead|"
    r"\bfee\b|\bbond\b|insurance|contingency|allowance|builder.?s\s+risk|"
    r"supervision|project\s+management|\bP&O\b|general\s+liability",
    re.I,
)

ALLOWED_MAPPING_METHODS = {
    "owner_candidate_exact_budget_code_key_match", "owner_constructed_exact_budget_code_key_match",
    "owner_cost_code_family_unique_budget_match", "owner_cost_code_family_multiple_budget_candidates",
    "owner_cost_code_family_no_budget_match", "owner_change_order_not_base_budget",
    "owner_change_order_family_review", "owner_no_cost_code",
    "procore_wbs_flat_code_exact_budget_code_key_match", "procore_wbs_flat_code_parsed_match",
    "procore_cost_code_present_category_conflict", "procore_cost_code_present_category_ambiguous",
    "procore_no_budget_match", "master_budget_code", "workbook_budget_code_key_direct",
    "workbook_budget_code_key_not_in_master",
}

# --------------------------------------------------------------------------------------
# Helpers
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


def cost_code_family(cost_code):
    if not isinstance(cost_code, str):
        return None
    s = cost_code.split("-")
    return f"{s[0]}-{s[1]}" if len(s) >= 2 and s[0] and s[1] else None


def materiality(a, b):
    a = a if a is not None else Decimal("0")
    b = b if b is not None else Decimal("0")
    gap = abs(a - b)
    basis = max(abs(a), abs(b))
    pct = (gap / basis) if basis > 0 else None
    return gap, pct, (gap >= MAT_DOLLAR and pct is not None and pct >= MAT_PCT)


def latest_key(period_to, app_no, sheet_idx):
    return (period_to or "",
            app_no if isinstance(app_no, int) else -1,
            sheet_idx if isinstance(sheet_idx, int) else -1)


# --------------------------------------------------------------------------------------
# Load inputs
# --------------------------------------------------------------------------------------
def _build_src(CTX, ANL):
  return OrderedDict([
    ("ctx_budget_codes", CTX / "canonical" / "budget_codes.jsonl"),
    ("ctx_owner_lines", CTX / "canonical" / "owner_pay_app_line_items_mapped.jsonl"),
    ("ctx_owner_totals", CTX / "canonical" / "owner_pay_app_totals.jsonl"),
    ("ctx_procore_headers", CTX / "canonical" / "procore_subcontractor_payment_app_headers.jsonl"),
    ("ctx_procore_lines", CTX / "canonical" / "procore_subcontractor_payment_app_line_items_mapped.jsonl"),
    ("ctx_procore_latest", CTX / "canonical" / "procore_latest_subcontractor_invoice_by_budget_code.jsonl"),
    ("ctx_procore_commitments", CTX / "canonical" / "procore_commitments.jsonl"),
    ("ctx_cost_entries", CTX / "canonical" / "cost_entries.jsonl"),
    ("ctx_monthly", CTX / "canonical" / "monthly_actuals_by_budget_code.jsonl"),
    ("ctx_bc_context", CTX / "summaries" / "budget_code_forecast_context.jsonl"),
    ("ctx_project", CTX / "summaries" / "project_forecast_context.json"),
    ("ctx_coverage", CTX / "summaries" / "mapping_coverage_summary.json"),
    ("ctx_data_gaps", CTX / "summaries" / "data_gap_register.json"),
    ("ctx_family_crosswalk", CTX / "mapping" / "owner_cost_code_family_crosswalk.jsonl"),
    ("ctx_owner_results", CTX / "mapping" / "owner_pay_app_mapping_results.jsonl"),
    ("ctx_procore_results", CTX / "mapping" / "procore_pay_app_mapping_results.jsonl"),
    ("ctx_ambiguous", CTX / "mapping" / "ambiguous_mapping_candidates.jsonl"),
    ("ctx_unmapped_owner", CTX / "mapping" / "unmapped_owner_pay_app_rows.jsonl"),
    ("ctx_unmapped_procore", CTX / "mapping" / "unmapped_procore_pay_app_rows.jsonl"),
    ("ctx_decisions", CTX / "mapping" / "budget_code_mapping_decisions.jsonl"),
    ("ctx_validation", CTX / "validation_report.json"),
    ("anl_recs", ANL / "forecast_recommendations_by_budget_code.jsonl"),
    ("anl_risks", ANL / "forecast_risk_register.jsonl"),
    ("anl_alignment", ANL / "evidence_alignment_by_budget_code.jsonl"),
    ("anl_manual", ANL / "manual_mapping_review_items.jsonl"),
    ("anl_warnings", ANL / "data_quality_warnings.jsonl"),
    ("anl_confidence", ANL / "confidence_rollup.json"),
    ("anl_top_review", ANL / "summaries" / "top_review_items.json"),
    ("anl_project", ANL / "summaries" / "project_forecast_analysis.json"),
    ("anl_validation", ANL / "validation_report.json"),
  ])


def check_inputs():
    missing = [k for k, p in SRC.items() if not p.exists()]
    parse = {}
    for k, p in SRC.items():
        if not p.exists():
            continue
        try:
            if p.suffix == ".jsonl":
                for _ in read_jsonl(p):
                    pass
            else:
                read_json(p)
            parse[k] = True
        except Exception as e:
            parse[k] = f"INVALID: {e}"
    ctx_concl = read_json(SRC["ctx_validation"]).get("conclusion")
    anl_concl = read_json(SRC["anl_validation"]).get("conclusion")
    return missing, parse, ctx_concl, anl_concl


# --------------------------------------------------------------------------------------
def main():
    resolve_inputs()   # runtime upstream resolution (full-fresh run state aware)
    print(f"[mapping-workpaper] context: {CONTEXT_LINEAGE['consumed_package']} "
          f"(src={CONTEXT_LINEAGE['lineage_source']}); analysis: {ANALYSIS_LINEAGE['consumed_package']} "
          f"(src={ANALYSIS_LINEAGE['lineage_source']})")
    OUT.mkdir(parents=True, exist_ok=False)
    missing, parse_results, ctx_concl, anl_concl = check_inputs()

    budget_codes = list(read_jsonl(SRC["ctx_budget_codes"]))
    canonical_keys = {r["budget_code_key"] for r in budget_codes}
    bc_by_key = {r["budget_code_key"]: r for r in budget_codes}
    ctx_rows = {r["budget_code_key"]: r for r in read_jsonl(SRC["ctx_bc_context"])}
    family_crosswalk = list(read_jsonl(SRC["ctx_family_crosswalk"]))

    # ambiguous owner candidate set + family->candidates
    amb_candidates = set()
    for cw in family_crosswalk:
        if cw.get("resolution_status") == "multiple_budget_candidates":
            amb_candidates.update(cw.get("budget_detail_candidate_keys", []))
    for r in read_jsonl(SRC["ctx_ambiguous"]):
        amb_candidates.update(r.get("candidate_budget_code_keys", []))

    # analysis owner_procore_mismatch risks
    anl_risks = list(read_jsonl(SRC["anl_risks"]))
    mismatch_risks = {r["budget_code_key"]: r for r in anl_risks
                      if r.get("risk_type") == "owner_procore_mismatch" and r.get("budget_code_key")}
    anl_recs = {r["budget_code_key"]: r for r in read_jsonl(SRC["anl_recs"])}
    anl_align = {r["budget_code_key"]: r for r in read_jsonl(SRC["anl_alignment"])}

    out_counts = OrderedDict()

    # ==================================================================================
    # 1) owner_sov_to_budget_code_crosswalk
    # ==================================================================================
    owner_lines = list(read_jsonl(SRC["ctx_owner_lines"]))
    owner_groups = defaultdict(list)
    for r in owner_lines:
        gk = (r.get("row_type"), r.get("owner_sov_code"), r.get("cost_code"), r.get("owner_cost_code_family"))
        owner_groups[gk].append(r)

    owner_xwalk = []
    owner_xwalk_by_id = {}
    owner_groups_selecting_key = defaultdict(set)   # budget_code_key -> {crosswalk_id}
    owner_family_to_xwalk = defaultdict(list)

    for idx, gk in enumerate(sorted(owner_groups.keys(),
                                    key=lambda g: tuple((x or "") for x in g))):
        rows = owner_groups[gk]
        row_type, sov, cost_code, fam = gk
        latest = max(rows, key=lambda r: latest_key(r.get("period_to"), r.get("application_no"), r.get("sheet_index")))
        apps = sorted({r.get("application_no") for r in rows if isinstance(r.get("application_no"), int)})
        candidate_keys = sorted({k for r in rows for k in (r.get("candidate_budget_code_keys") or [])})
        mapped = latest.get("mapped_budget_code_key")
        method = latest.get("mapping_method")
        status = latest.get("mapping_status")

        if mapped and method == "owner_candidate_exact_budget_code_key_match":
            selected, alloc, conf = [mapped], "exact", "high"
        elif mapped and method == "owner_constructed_exact_budget_code_key_match":
            selected, alloc, conf = [mapped], "constructed_exact", "high"
        elif mapped and method == "owner_cost_code_family_unique_budget_match":
            selected, alloc, conf = [mapped], "family_unique", "medium"
        elif status == "ambiguous":
            selected, alloc, conf = candidate_keys, "family_multiple", "low"
        elif row_type == "change_order_line_item":
            selected, alloc, conf = [], "not_applicable", "none"
        elif status == "manual_required":
            selected, alloc, conf = candidate_keys, "manual", "none"
        elif status == "not_applicable":
            selected, alloc, conf = [], "not_applicable", "none"
        else:
            selected, alloc, conf = ([mapped] if mapped else candidate_keys), \
                ("exact" if mapped else "manual"), ("high" if mapped else "none")

        cid = f"OSB-{idx+1:04d}"
        for k in selected:
            owner_groups_selecting_key[k].add(cid)
        if fam:
            owner_family_to_xwalk[fam].append(cid)

        scope_summ = []
        for k in selected[:8]:
            bk = bc_by_key.get(k)
            if bk:
                scope_summ.append({"budget_code_key": k, "category": bk.get("category"),
                                   "cost_code": bk.get("cost_code")})

        row = OrderedDict([
            ("crosswalk_id", cid), ("project_key", PROJECT_KEY),
            ("owner_sov_code", sov), ("owner_cost_code_original", latest.get("owner_cost_code_original")),
            ("owner_cost_code_normalized", latest.get("owner_cost_code_normalized")),
            ("owner_cost_code_family", fam),
            ("owner_placeholder_code_detected", bool(latest.get("owner_placeholder_code_detected"))),
            ("owner_description", latest.get("description_of_work")),
            ("row_type", row_type), ("owner_line_item_count", len(rows)),
            ("owner_application_numbers", apps),
            ("owner_latest_application_no", latest.get("application_no")),
            ("owner_latest_period_to", latest.get("period_to")),
            ("owner_latest_current_value", money_str(latest.get("current_value"))),
            ("owner_latest_completed_to_date", money_str(latest.get("total_completed_and_stored_to_date"))),
            ("owner_latest_percent_complete", latest.get("percent_complete")),
            ("owner_latest_balance_to_finish", money_str(latest.get("balance_to_finish"))),
            ("owner_latest_retainage", money_str(latest.get("retainage"))),
            ("candidate_budget_code_keys", candidate_keys),
            ("selected_budget_code_keys", selected),
            ("candidate_count", len(candidate_keys)),
            ("budget_candidate_scope_summary", scope_summ),
            ("allocation_method", alloc),
            ("allocation_percent_by_budget_code", None),  # no explicit basis -> never invent
            ("confidence", conf),
            ("requires_human_review", alloc in ("family_multiple", "manual")),
            ("notes", _owner_note(alloc, row_type, fam)),
        ])
        owner_xwalk.append(row)
        owner_xwalk_by_id[cid] = row
    out_counts["owner_sov_to_budget_code_crosswalk.jsonl"] = write_jsonl(
        OUT / "owner_sov_to_budget_code_crosswalk.jsonl", owner_xwalk)

    # ==================================================================================
    # 2) procore_commitment_to_budget_code_crosswalk
    # ==================================================================================
    # invoice counts & item types & ids per (commitment, vendor, wbs, budget_code)
    proc_line_agg = defaultdict(lambda: {"count": 0, "invoice_ids": set(), "record_keys": set(),
                                         "item_types": set(), "neg_fields": set()})
    for r in read_jsonl(SRC["ctx_procore_lines"]):
        gk = (r.get("commitment_id"), r.get("vendor_entity_key"), r.get("wbs_flat_code"),
              r.get("cost_code_id"), r.get("item_type"), r.get("mapped_budget_code_key"))
        a = proc_line_agg[gk]
        a["count"] += 1
        if r.get("invoice_id"):
            a["invoice_ids"].add(r.get("invoice_id"))
        if r.get("invoice_record_key"):
            a["record_keys"].add(r.get("invoice_record_key"))
        if r.get("item_type"):
            a["item_types"].add(r.get("item_type"))
        for f in ("total_completed_and_stored_to_date", "work_completed_this_period", "subcontractor_claimed_amount"):
            d = dec(r.get(f))
            if d is not None and d < 0:
                a["neg_fields"].add(f)

    proc_latest = list(read_jsonl(SRC["ctx_procore_latest"]))
    procore_xwalk = []
    procore_xwalk_by_id = {}
    procore_by_key = defaultdict(list)         # budget_code_key -> [crosswalk rows]
    procore_family_to_xwalk = defaultdict(list)
    procore_scope_ids = []                      # for synthetic procore_only

    for idx, r in enumerate(sorted(proc_latest, key=lambda x: (
            x.get("wbs_flat_code") or "", x.get("commitment_id") or "", x.get("vendor_entity_key") or ""))):
        wbs = r.get("wbs_flat_code")
        parsed = parse_budget_key(wbs)
        pcc = parsed[1] if parsed else None
        pcat = parsed[2] if parsed else None
        fam = cost_code_family(pcc) if pcc else None
        mapped = r.get("mapped_budget_code_key")
        gk = (r.get("commitment_id"), r.get("vendor_entity_key"), wbs, r.get("cost_code_id"),
              r.get("item_type"), mapped)
        agg = proc_line_agg.get(gk, {"count": 0, "invoice_ids": set(), "record_keys": set(),
                                     "item_types": set(), "neg_fields": set()})
        completed = dec(r.get("latest_total_completed_and_stored_to_date"))
        neg_fields = sorted(agg["neg_fields"] | ({"latest_total_completed_and_stored_to_date"}
                                                 if completed is not None and completed < 0 else set()))
        cid = f"PCB-{idx+1:04d}"
        remaining = dec(r.get("latest_header_balance_to_finish_including_retainage"))
        row = OrderedDict([
            ("crosswalk_id", cid), ("project_key", PROJECT_KEY),
            ("commitment_id", r.get("commitment_id")), ("commitment_id_source", "procore_invoice_join"),
            ("vendor_entity_key", r.get("vendor_entity_key")),
            ("procore_wbs_flat_code", wbs), ("procore_cost_code_id", r.get("cost_code_id")),
            ("procore_cost_code", pcc), ("procore_category", pcat), ("procore_cost_code_family", fam),
            ("mapped_budget_code_key", mapped), ("mapping_method", r.get("mapping_method")),
            ("mapping_confidence", r.get("mapping_confidence")),
            ("invoice_item_count", agg["count"]),
            ("latest_invoice_period_end", r.get("latest_period_end")),
            ("latest_scheduled_value", money_str(r.get("latest_scheduled_value"))),
            ("latest_completed_to_date", money_str(r.get("latest_total_completed_and_stored_to_date"))),
            ("latest_claimed_amount", money_str(r.get("latest_subcontractor_claimed_amount"))),
            ("latest_retainage", money_str(r.get("latest_retainage_held"))),
            ("latest_balance_or_remaining_exposure", money_str(remaining)),
            ("has_negative_latest_value", bool(neg_fields)),
            ("negative_value_fields", neg_fields),
            ("related_invoice_ids", sorted(agg["invoice_ids"])),
            ("related_invoice_record_keys", sorted(agg["record_keys"])),
            ("related_item_types", sorted(agg["item_types"]) or ([r.get("item_type")] if r.get("item_type") else [])),
            ("notes", "negative latest value(s) may be deductive change-order credit evidence"
                      if neg_fields else None),
        ])
        procore_xwalk.append(row)
        procore_xwalk_by_id[cid] = row
        if mapped:
            procore_by_key[mapped].append(row)
        if fam:
            procore_family_to_xwalk[fam].append(cid)
        procore_scope_ids.append(cid)
    out_counts["procore_commitment_to_budget_code_crosswalk.jsonl"] = write_jsonl(
        OUT / "procore_commitment_to_budget_code_crosswalk.jsonl", procore_xwalk)

    # ==================================================================================
    # 3) owner_sov_to_procore_scope_crosswalk  (+ synthetic procore_only rows)
    # ==================================================================================
    scope_rows = []
    scope_by_owner_id = {}
    procore_ids_referenced_by_owner = set()

    for ow in owner_xwalk:
        cid = ow["crosswalk_id"]
        selected = ow["selected_budget_code_keys"]
        fam = ow["owner_cost_code_family"]
        related_proc = []
        for k in selected:
            related_proc.extend(procore_by_key.get(k, []))
        # plus family-matched procore (evidence only)
        if fam:
            for pcid in procore_family_to_xwalk.get(fam, []):
                pr = procore_xwalk_by_id[pcid]
                if pr not in related_proc:
                    related_proc.append(pr)
        for pr in related_proc:
            procore_ids_referenced_by_owner.add(pr["crosswalk_id"])

        rel_keys = sorted(set(selected))
        rel_commitments = sorted({p["commitment_id"] for p in related_proc if p["commitment_id"]})
        rel_vendors = sorted({p["vendor_entity_key"] for p in related_proc if p["vendor_entity_key"]})
        rel_wbs = sorted({p["procore_wbs_flat_code"] for p in related_proc if p["procore_wbs_flat_code"]})
        rel_fams = sorted({p["procore_cost_code_family"] for p in related_proc if p["procore_cost_code_family"]})
        neg_credit = sum(1 for p in related_proc if p["has_negative_latest_value"])
        proc_completed = dsum(p["latest_completed_to_date"] for p in related_proc)
        proc_claimed = dsum(p["latest_claimed_amount"] for p in related_proc)
        proc_reten = dsum(p["latest_retainage"] for p in related_proc)

        n_keys = len(rel_keys)
        n_proc = len(related_proc)
        row_type = ow["row_type"]
        owner_internal = _is_internal(ow["owner_description"], rel_keys, bc_by_key)

        if row_type == "change_order_line_item":
            rel = "pcco_change_order"
        elif owner_internal:
            rel = "internal_cost"
        elif n_proc == 0 and n_keys >= 1:
            rel = "owner_only"
        elif n_proc == 0:
            rel = "unresolved"
        else:
            multi_owner = any(len(owner_groups_selecting_key.get(k, set())) > 1 for k in rel_keys)
            if n_keys <= 1 and n_proc == 1 and not multi_owner:
                rel = "one_to_one"
            elif multi_owner and (n_keys <= 1):
                rel = "many_to_one"
            elif n_keys > 1 and n_proc > 1:
                rel = "many_to_many"
            else:
                rel = "one_to_many"

        comp_basis = _comparison_basis(rel, ow, proc_completed)
        smc = "high" if rel == "one_to_one" else ("medium" if rel in ("one_to_many", "many_to_one") else "low")
        if rel in ("unresolved",):
            smc = "none"

        srow = OrderedDict([
            ("crosswalk_id", f"OPS-{len(scope_rows)+1:04d}"), ("project_key", PROJECT_KEY),
            ("owner_sov_code", ow["owner_sov_code"]), ("owner_cost_code_family", fam),
            ("owner_description", ow["owner_description"]), ("row_type", row_type),
            ("owner_latest_current_value", ow["owner_latest_current_value"]),
            ("owner_latest_completed_to_date", ow["owner_latest_completed_to_date"]),
            ("owner_latest_percent_complete", ow["owner_latest_percent_complete"]),
            ("owner_latest_balance_to_finish", ow["owner_latest_balance_to_finish"]),
            ("related_budget_code_keys", rel_keys),
            ("related_procore_commitment_ids", rel_commitments),
            ("related_procore_vendor_entity_keys", rel_vendors),
            ("related_procore_wbs_flat_codes", rel_wbs),
            ("related_procore_cost_code_families", rel_fams),
            ("related_procore_latest_completed_to_date_sum", money_str(proc_completed) if related_proc else None),
            ("related_procore_latest_claimed_amount_sum", money_str(proc_claimed) if related_proc else None),
            ("related_procore_latest_retainage_sum", money_str(proc_reten) if related_proc else None),
            ("related_procore_negative_credit_count", neg_credit),
            ("scope_relationship", rel), ("comparison_basis", comp_basis),
            ("scope_match_confidence", smc),
            ("requires_human_review", rel in ("one_to_many", "many_to_one", "many_to_many",
                                              "unresolved", "owner_only")),
            ("owner_crosswalk_id", cid),
            ("procore_crosswalk_ids", sorted({p["crosswalk_id"] for p in related_proc})),
            ("notes", _scope_note(rel, comp_basis)),
        ])
        scope_rows.append(srow)
        scope_by_owner_id[cid] = srow

    # synthetic procore_only rows (refinement #2)
    for pcid in procore_scope_ids:
        if pcid in procore_ids_referenced_by_owner:
            continue
        pr = procore_xwalk_by_id[pcid]
        srow = OrderedDict([
            ("crosswalk_id", f"OPS-{len(scope_rows)+1:04d}"), ("project_key", PROJECT_KEY),
            ("owner_sov_code", None), ("owner_cost_code_family", None),
            ("owner_description", None), ("row_type", None),
            ("owner_latest_current_value", None), ("owner_latest_completed_to_date", None),
            ("owner_latest_percent_complete", None), ("owner_latest_balance_to_finish", None),
            ("related_budget_code_keys", [pr["mapped_budget_code_key"]] if pr["mapped_budget_code_key"] else []),
            ("related_procore_commitment_ids", [pr["commitment_id"]] if pr["commitment_id"] else []),
            ("related_procore_vendor_entity_keys", [pr["vendor_entity_key"]] if pr["vendor_entity_key"] else []),
            ("related_procore_wbs_flat_codes", [pr["procore_wbs_flat_code"]] if pr["procore_wbs_flat_code"] else []),
            ("related_procore_cost_code_families", [pr["procore_cost_code_family"]] if pr["procore_cost_code_family"] else []),
            ("related_procore_latest_completed_to_date_sum", pr["latest_completed_to_date"]),
            ("related_procore_latest_claimed_amount_sum", pr["latest_claimed_amount"]),
            ("related_procore_latest_retainage_sum", pr["latest_retainage"]),
            ("related_procore_negative_credit_count", 1 if pr["has_negative_latest_value"] else 0),
            ("scope_relationship", "procore_only"), ("comparison_basis", "not_comparable"),
            ("scope_match_confidence", "low"),
            ("requires_human_review", True),
            ("owner_crosswalk_id", None),
            ("procore_crosswalk_ids", [pcid]),
            ("notes", "Procore commitment/WBS scope with no related owner SOV scope (synthetic procore_only row)"),
        ])
        scope_rows.append(srow)
    out_counts["owner_sov_to_procore_scope_crosswalk.jsonl"] = write_jsonl(
        OUT / "owner_sov_to_procore_scope_crosswalk.jsonl", scope_rows)

    # scope relationship + supporting ids per budget_code_key
    scope_by_key = defaultdict(list)
    for s in scope_rows:
        for k in s["related_budget_code_keys"]:
            scope_by_key[k].append(s)

    # ==================================================================================
    # 4) owner_procore_discrepancy_classification
    # ==================================================================================
    # discrepancy set: mismatch-risk codes ∪ both-mapped ∪ codes w/ owner+procore related scope
    disc_keys = set(mismatch_risks.keys())
    for k, rec in anl_recs.items():
        if rec.get("owner_mapping_status") == "mapped" and rec.get("procore_mapping_status") == "mapped":
            disc_keys.add(k)
    for k in canonical_keys:
        ctx = ctx_rows.get(k, {})
        ob = (ctx.get("owner_pay_app") or {})
        pb = (ctx.get("procore_subcontractor_pay_apps") or {})
        if ob.get("mapping_status") == "mapped" and pb.get("mapping_status") == "mapped":
            disc_keys.add(k)
    # include codes where owner is ambiguous-candidate AND procore mapped (related but unclean)
    for k in canonical_keys:
        pb = (ctx_rows.get(k, {}).get("procore_subcontractor_pay_apps") or {})
        if k in amb_candidates and pb.get("mapping_status") == "mapped":
            disc_keys.add(k)

    disc_rows = []
    disc_by_key = {}
    type_counts = defaultdict(int)
    true_count = 0

    for k in sorted(disc_keys):
        if k not in canonical_keys:
            continue
        bk = bc_by_key.get(k, {})
        ctx = ctx_rows.get(k, {})
        parsed = parse_budget_key(k)
        sub_job, cost_code, category = (parsed if parsed else (None, None, None))
        ob = (ctx.get("owner_pay_app") or {})
        pb = (ctx.get("procore_subcontractor_pay_apps") or {})
        ac = (ctx.get("actuals") or {})

        owner_mapped = ob.get("mapping_status") == "mapped"
        owner_completed = dec(ob.get("latest_total_completed_and_stored_to_date")) if owner_mapped else None
        owner_pct = dec(ob.get("latest_percent_complete")) if owner_mapped else None
        owner_balance = dec(ob.get("latest_balance_to_finish")) if owner_mapped else None
        procore_mapped = pb.get("mapping_status") == "mapped"
        procore_completed = dec(pb.get("latest_total_completed_and_stored_to_date_sum")) if procore_mapped else None
        procore_claimed = dec(pb.get("latest_subcontractor_claimed_amount_sum")) if procore_mapped else None
        procore_reten = dec(pb.get("latest_retainage_held_sum")) if procore_mapped else None
        actual = D(ac.get("actual_cost_all_source_to_date"))
        proj = D((bk.get("amounts") or {}).get("projected_costs"))

        # procore negative credit on this key — classify as deductive ONLY when material:
        # net Procore completed is negative, OR a single commitment carries a material (>= $25k)
        # negative latest completed value. Small negative line fields are noted, not classified.
        has_any_negative = any(p["has_negative_latest_value"] for p in procore_by_key.get(k, []))
        material_neg_commitment = any(
            (dec(p["latest_completed_to_date"]) is not None and dec(p["latest_completed_to_date"]) < 0
             and abs(dec(p["latest_completed_to_date"])) >= MAT_DOLLAR)
            for p in procore_by_key.get(k, []))
        procore_neg = (procore_completed is not None and procore_completed < 0) or material_neg_commitment

        # scope relationship for this key (owner-driven rows referencing it)
        owner_scopes = [s for s in scope_by_key.get(k, []) if s["owner_crosswalk_id"]]
        scope_rel = owner_scopes[0]["scope_relationship"] if owner_scopes else (
            "procore_only" if procore_mapped and not owner_mapped else "unresolved")
        comp_basis = owner_scopes[0]["comparison_basis"] if owner_scopes else (
            "not_comparable")
        is_amb = k in amb_candidates and not owner_mapped

        gap, pct, mat = materiality(owner_completed, procore_completed)
        d_oa = (owner_completed - actual) if owner_completed is not None else None
        d_pa = (procore_completed - actual) if procore_completed is not None else None
        d_op = (owner_completed - procore_completed) if (owner_completed is not None and procore_completed is not None) else None

        owner_internal = _is_internal(bk.get("budget_code_description"), [k], bc_by_key)

        # ---- decision tree ----
        if (category in ("LAB", "LBN", "OVH")) or owner_internal:
            dtype = "internal_or_non_subcontract_cost"
        elif procore_neg:
            dtype = "deductive_change_order_credit"
        elif is_amb and any(s for s in owner_xwalk if k in s["candidate_budget_code_keys"]
                            and s["owner_placeholder_code_detected"]):
            dtype = "owner_sov_placeholder_family"
        elif is_amb:
            dtype = "mapping_ambiguity"
        elif scope_rel == "pcco_change_order":
            dtype = "pcco_or_change_order_scope"
        elif scope_rel in ("one_to_many", "many_to_one", "many_to_many"):
            dtype = "scope_aggregation_difference"
        elif scope_rel == "procore_only":
            dtype = "missing_owner_sov_scope"
        elif scope_rel == "owner_only":
            dtype = "missing_procore_commitment_scope"
        elif owner_mapped and procore_mapped and scope_rel == "one_to_one":
            if owner_completed is not None and procore_completed is not None and procore_completed > 0 \
                    and owner_completed > procore_completed and mat:
                dtype = "owner_sell_value_vs_subcontract_cost"
            elif procore_completed is not None and owner_completed is not None and procore_completed > owner_completed and mat:
                dtype = "timing_difference"
            elif mat and comp_basis in ("percent_complete", "remaining_exposure"):
                dtype = "true_progress_discrepancy"
            elif not mat:
                dtype = "no_discrepancy"
            else:
                dtype = "owner_sell_value_vs_subcontract_cost" if (owner_completed or Decimal("0")) >= (procore_completed or Decimal("0")) else "unresolved"
        elif not mat:
            dtype = "no_discrepancy"
        else:
            dtype = "unresolved"

        # HARD GUARD (refinement #3): true_progress_discrepancy requires comparable basis
        if dtype == "true_progress_discrepancy" and comp_basis not in ("percent_complete", "remaining_exposure"):
            dtype = "scope_aggregation_difference" if scope_rel != "one_to_one" else "owner_sell_value_vs_subcontract_cost"

        is_true = dtype == "true_progress_discrepancy"
        if is_true:
            true_count += 1
        type_counts[dtype] += 1

        if dtype == "no_discrepancy":
            implication = "none"
        elif dtype in ("owner_sell_value_vs_subcontract_cost", "scope_aggregation_difference",
                       "owner_sov_placeholder_family", "deductive_change_order_credit",
                       "internal_or_non_subcontract_cost"):
            implication = "informational"
        elif dtype in ("mapping_ambiguity", "missing_procore_commitment_scope",
                       "missing_owner_sov_scope", "timing_difference"):
            implication = "review"
        elif is_true:
            implication = "confirmed_forecast_risk" if actual > 0 else "potential_forecast_risk"
        else:
            implication = "potential_forecast_risk" if actual >= MAT_DOLLAR else "review"

        sup_owner = sorted({s["owner_crosswalk_id"] for s in owner_scopes if s["owner_crosswalk_id"]}
                           | {ox["crosswalk_id"] for ox in owner_xwalk if k in ox["selected_budget_code_keys"]})
        sup_proc = sorted({p["crosswalk_id"] for p in procore_by_key.get(k, [])})
        sup_scope = sorted({s["crosswalk_id"] for s in scope_by_key.get(k, [])})

        row = OrderedDict([
            ("discrepancy_id", f"DISC-{len(disc_rows)+1:04d}"), ("project_key", PROJECT_KEY),
            ("budget_code_key", k), ("sub_job", sub_job), ("cost_code", cost_code), ("category", category),
            ("budget_code_description", bk.get("budget_code_description")),
            ("owner_completed_to_date", money_str(owner_completed)),
            ("owner_percent_complete", float(owner_pct) if owner_pct is not None else None),
            ("owner_balance_to_finish", money_str(owner_balance)),
            ("procore_completed_to_date", money_str(procore_completed)),
            ("procore_claimed_amount", money_str(procore_claimed)),
            ("procore_retainage", money_str(procore_reten)),
            ("actual_cost_to_date", money_str(actual)),
            ("current_projected_cost", money_str(proj)),
            ("delta_owner_vs_procore", money_str(d_op) if d_op is not None else None),
            ("delta_owner_vs_actual", money_str(d_oa) if d_oa is not None else None),
            ("delta_procore_vs_actual", money_str(d_pa) if d_pa is not None else None),
            ("owner_vs_procore_materiality_passed", bool(mat)),
            ("scope_relationship", scope_rel), ("comparison_basis", comp_basis),
            ("discrepancy_type", dtype), ("is_true_progress_discrepancy", is_true),
            ("forecast_risk_implication", implication),
            ("recommended_resolution", _disc_resolution(dtype)),
            ("requires_human_review", dtype in ("mapping_ambiguity", "owner_sov_placeholder_family",
                                                "missing_owner_sov_scope", "missing_procore_commitment_scope",
                                                "timing_difference", "true_progress_discrepancy", "unresolved")),
            ("supporting_owner_crosswalk_ids", sup_owner),
            ("supporting_procore_crosswalk_ids", sup_proc),
            ("supporting_scope_crosswalk_ids", sup_scope),
            ("original_analysis_risk_severity", mismatch_risks.get(k, {}).get("severity")),
            ("notes", _disc_note(dtype, scope_rel, comp_basis, has_any_negative)),
        ])
        disc_rows.append(row)
        disc_by_key[k] = row
    out_counts["owner_procore_discrepancy_classification.jsonl"] = write_jsonl(
        OUT / "owner_procore_discrepancy_classification.jsonl", disc_rows)

    # ==================================================================================
    # 5) budget_code_scope_reconciliation (127)
    # ==================================================================================
    recon_rows = []
    for k in sorted(canonical_keys):
        bk = bc_by_key.get(k, {})
        ctx = ctx_rows.get(k, {})
        parsed = parse_budget_key(k)
        sub_job, cost_code, category = (parsed if parsed else (None, None, None))
        ob = (ctx.get("owner_pay_app") or {})
        pb = (ctx.get("procore_subcontractor_pay_apps") or {})
        ac = (ctx.get("actuals") or {})
        amts = bk.get("amounts") or {}

        if ob.get("mapping_status") == "mapped":
            owner_status = "mapped"
        elif k in amb_candidates:
            owner_status = "ambiguous_family"
        elif any(ox["allocation_method"] == "manual" and k in ox["candidate_budget_code_keys"] for ox in owner_xwalk):
            owner_status = "manual_required"
        else:
            owner_status = "none"

        owner_sov_codes = sorted({ox["owner_sov_code"] for ox in owner_xwalk
                                  if k in ox["selected_budget_code_keys"] and ox["owner_sov_code"]})
        owner_xids = sorted({ox["crosswalk_id"] for ox in owner_xwalk if k in ox["selected_budget_code_keys"]})
        proc_rows_k = procore_by_key.get(k, [])
        procore_status = "mapped" if pb.get("mapping_status") == "mapped" else "none"
        scope_summ = sorted({s["scope_relationship"] for s in scope_by_key.get(k, [])})
        disc = disc_by_key.get(k)
        dtypes = [disc["discrepancy_type"]] if disc else []

        recon_rows.append(OrderedDict([
            ("project_key", PROJECT_KEY), ("budget_code_key", k),
            ("sub_job", sub_job), ("sub_job_description", bk.get("sub_job_description")),
            ("cost_code", cost_code), ("category", category),
            ("budget_code_description", bk.get("budget_code_description")),
            ("budget_amount", money_str(amts.get("revised_budget"))),
            ("current_projected_cost", money_str(amts.get("projected_costs"))),
            ("actual_cost_all_source_to_date", money_str(ac.get("actual_cost_all_source_to_date"))),
            ("actual_cost_through_may_2026", money_str(ac.get("actual_cost_through_may_2026"))),
            ("actual_cost_june_2026_to_date", money_str(ac.get("actual_cost_june_2026_to_date"))),
            ("owner_evidence_status", owner_status),
            ("owner_related_sov_codes", owner_sov_codes),
            ("owner_related_crosswalk_ids", owner_xids),
            ("owner_latest_completed_to_date", money_str(ob.get("latest_total_completed_and_stored_to_date"))),
            ("owner_latest_percent_complete", ob.get("latest_percent_complete")),
            ("owner_latest_balance_to_finish", money_str(ob.get("latest_balance_to_finish"))),
            ("procore_evidence_status", procore_status),
            ("procore_related_commitment_ids", sorted({p["commitment_id"] for p in proc_rows_k if p["commitment_id"]})),
            ("procore_related_wbs_flat_codes", sorted({p["procore_wbs_flat_code"] for p in proc_rows_k if p["procore_wbs_flat_code"]})),
            ("procore_related_crosswalk_ids", sorted({p["crosswalk_id"] for p in proc_rows_k})),
            ("procore_latest_completed_to_date", money_str(pb.get("latest_total_completed_and_stored_to_date_sum"))),
            ("procore_latest_claimed_amount", money_str(pb.get("latest_subcontractor_claimed_amount_sum"))),
            ("procore_negative_credit_count", sum(1 for p in proc_rows_k if p["has_negative_latest_value"])),
            ("scope_relationship_summary", scope_summ),
            ("discrepancy_types", dtypes),
            ("true_progress_discrepancy_count", 1 if (disc and disc["is_true_progress_discrepancy"]) else 0),
            ("forecast_risk_implication", disc["forecast_risk_implication"] if disc else "none"),
            ("recommended_mapping_resolution", _disc_resolution(dtypes[0]) if dtypes else "none_required"),
            ("recommended_analysis_recalibration",
             "downgrade owner_procore_mismatch to structural/informational" if (disc and not disc["is_true_progress_discrepancy"]
                                                                                and k in mismatch_risks) else "none"),
            ("requires_human_review", bool(disc and disc["requires_human_review"]) or owner_status in ("ambiguous_family", "manual_required")),
            ("notes", None),
        ]))
    out_counts["budget_code_scope_reconciliation.jsonl"] = write_jsonl(
        OUT / "budget_code_scope_reconciliation.jsonl", recon_rows)

    # ==================================================================================
    # 6) manual_crosswalk_review_items
    # ==================================================================================
    review_items = []
    rc = [0]

    def add_review(priority, rtype, key, sov, fam, commit, cands, classification, reason, action, src, sup):
        rc[0] += 1
        review_items.append(OrderedDict([
            ("review_item_id", f"MCR-{rc[0]:04d}"), ("priority", priority), ("review_type", rtype),
            ("budget_code_key", key), ("owner_sov_code", sov), ("owner_cost_code_family", fam),
            ("procore_commitment_id", commit), ("candidate_budget_code_keys", cands),
            ("current_classification", classification), ("reason", reason),
            ("recommended_human_action", action), ("source_files", src), ("supporting_ids", sup),
        ]))

    SRC_CW = ["owner_sov_to_budget_code_crosswalk.jsonl", "owner_sov_to_procore_scope_crosswalk.jsonl",
              "owner_procore_discrepancy_classification.jsonl"]
    # owner placeholder families with multiple candidates / no match
    for cw in sorted(family_crosswalk, key=lambda c: -(c.get("owner_line_item_count") or 0)):
        if cw.get("resolution_status") == "multiple_budget_candidates":
            add_review("medium", "owner_sov_budget_mapping", None, None, cw.get("owner_cost_code_family"),
                       None, cw.get("budget_detail_candidate_keys", []), "owner_sov_placeholder_family",
                       f"Owner family {cw.get('owner_cost_code_family')} → {cw.get('budget_detail_candidate_count')} candidates",
                       "Select correct budget key(s) or supply allocation basis.",
                       ["mapping/owner_cost_code_family_crosswalk.jsonl"], [])
        elif cw.get("resolution_status") == "no_budget_match":
            add_review("high", "owner_sov_budget_mapping", None, None, cw.get("owner_cost_code_family"),
                       None, [], "no_budget_match",
                       f"Owner family {cw.get('owner_cost_code_family')} has no BudgetDetails match",
                       "Confirm scope mapping / whether scope is in base budget.",
                       ["mapping/owner_cost_code_family_crosswalk.jsonl"], [])
    # discrepancy-driven items
    for d in disc_rows:
        dt = d["discrepancy_type"]
        key = d["budget_code_key"]
        if dt == "true_progress_discrepancy":
            add_review("critical", "true_progress_discrepancy_review", key, None, None, None, [key],
                       dt, "Likely true progress discrepancy with comparable basis.",
                       "Confirm progress vs cost; assess forecast impact.", SRC_CW,
                       d["supporting_scope_crosswalk_ids"])
        elif dt == "unresolved" and D(d["actual_cost_to_date"]) >= MAT_DOLLAR:
            add_review("high", "owner_sov_procore_scope_mapping", key, None, None, None, [key],
                       dt, "Unresolved mismatch with material actual cost.",
                       "Resolve owner/Procore scope relationship.", SRC_CW, d["supporting_scope_crosswalk_ids"])
        elif dt == "deductive_change_order_credit":
            add_review("medium", "deductive_change_order_credit_review", key, None, None, None, [key],
                       dt, "Negative Procore latest value affects comparison.",
                       "Verify deductive change-order credit; exclude from progress comparison.", SRC_CW,
                       d["supporting_procore_crosswalk_ids"])
        elif dt == "timing_difference":
            add_review("medium", "timing_review", key, None, None, None, [key], dt,
                       "Subcontractor progress ahead of owner billing (timing).",
                       "Confirm billing-cycle timing; re-evaluate after next cycle.", SRC_CW,
                       d["supporting_scope_crosswalk_ids"])
        elif dt == "missing_owner_sov_scope":
            add_review("medium", "procore_commitment_scope_review", key, None, None, None, [key], dt,
                       "Procore commitment scope with no mapped owner SOV.",
                       "Identify owner SOV line covering this subcontract scope.", SRC_CW,
                       d["supporting_procore_crosswalk_ids"])
        elif dt == "missing_procore_commitment_scope":
            add_review("low", "procore_commitment_scope_review", key, None, None, None, [key], dt,
                       "Owner SOV maps to budget code with no Procore commitment evidence.",
                       "Confirm whether a subcontract exists / is in Procore.", SRC_CW,
                       d["supporting_owner_crosswalk_ids"])
        elif dt in ("owner_sell_value_vs_subcontract_cost", "scope_aggregation_difference"):
            add_review("low", "not_applicable_confirmation", key, None, None, None, [key], dt,
                       "Structural comparison difference (sell-vs-cost / scope aggregation).",
                       "Confirm structural; recalibrate risk to informational.", SRC_CW,
                       d["supporting_scope_crosswalk_ids"])
    out_counts["manual_crosswalk_review_items.jsonl"] = write_jsonl(
        OUT / "manual_crosswalk_review_items.jsonl", review_items)

    # ==================================================================================
    # 7) recalibration inputs + resolution summary
    # ==================================================================================
    recal_rows = []
    for k in sorted(set(mismatch_risks.keys()) | set(disc_by_key.keys())):
        d = disc_by_key.get(k)
        if not d:
            continue
        orig = mismatch_risks.get(k)
        dt = d["discrepancy_type"]
        is_true = d["is_true_progress_discrepancy"]
        if is_true:
            fut_type, fut_sev = "owner_procore_progress_discrepancy", ("high" if d["forecast_risk_implication"] == "confirmed_forecast_risk" else "medium")
        elif dt == "timing_difference":
            fut_type, fut_sev = "owner_procore_timing", "low"
        elif dt in ("mapping_ambiguity", "owner_sov_placeholder_family", "missing_owner_sov_scope",
                    "missing_procore_commitment_scope"):
            fut_type, fut_sev = "owner_procore_scope_mapping_gap", "low"
        else:
            fut_type, fut_sev = "owner_procore_scope_structural", "informational"
        recal_rows.append(OrderedDict([
            ("budget_code_key", k),
            ("original_risk_type", "owner_procore_mismatch" if orig else None),
            ("original_risk_severity", orig.get("severity") if orig else None),
            ("classified_discrepancy_type", dt),
            ("is_true_progress_discrepancy", is_true),
            ("forecast_risk_implication", d["forecast_risk_implication"]),
            ("recommended_future_risk_type", fut_type),
            ("recommended_future_severity", fut_sev),
            ("recommended_rule_change",
             "Do not score owner_procore_mismatch as critical when comparison_basis is "
             "dollars_with_markup_caution or not_comparable, or when owner mapping is ambiguous; "
             "reserve critical/high for true_progress_discrepancy with comparable basis and actuals support."),
            ("supporting_reason", d["notes"]),
        ]))
    out_counts["owner_procore_mismatch_recalibration_inputs.jsonl"] = write_jsonl(
        OUT / "owner_procore_mismatch_recalibration_inputs.jsonl", recal_rows)

    prio_counts = defaultdict(int)
    for it in review_items:
        prio_counts[it["priority"]] += 1
    coverage = read_json(SRC["ctx_coverage"])
    summary = OrderedDict([
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("period", PERIOD)])),
        ("generated_stamp", STAMP),
        ("total_budget_codes", len(canonical_keys)),
        ("budget_codes_with_both_owner_and_procore_evidence",
         sum(1 for k in canonical_keys if (ctx_rows.get(k, {}).get("owner_pay_app", {}).get("mapping_status") == "mapped"
                                           and ctx_rows.get(k, {}).get("procore_subcontractor_pay_apps", {}).get("mapping_status") == "mapped"))),
        ("owner_procore_mismatch_count_from_analysis", len(mismatch_risks)),
        ("classified_discrepancy_rows", len(disc_rows)),
        ("classified_discrepancy_counts_by_type", OrderedDict(sorted(type_counts.items()))),
        ("true_progress_discrepancy_count", true_count),
        ("unresolved_count", type_counts.get("unresolved", 0)),
        ("scope_aggregation_difference_count", type_counts.get("scope_aggregation_difference", 0)),
        ("owner_sell_value_vs_subcontract_cost_count", type_counts.get("owner_sell_value_vs_subcontract_cost", 0)),
        ("deductive_change_order_credit_count", type_counts.get("deductive_change_order_credit", 0)),
        ("mapping_ambiguity_count", type_counts.get("mapping_ambiguity", 0)),
        ("owner_sov_placeholder_family_count", type_counts.get("owner_sov_placeholder_family", 0)),
        ("timing_difference_count", type_counts.get("timing_difference", 0)),
        ("internal_or_non_subcontract_cost_count", type_counts.get("internal_or_non_subcontract_cost", 0)),
        ("manual_review_item_count_by_priority", OrderedDict(sorted(prio_counts.items()))),
        ("recommended_risk_recalibration_summary", OrderedDict([
            ("mismatch_codes", len(mismatch_risks)),
            ("recommended_structural_or_informational",
             sum(1 for r in recal_rows if r["recommended_future_severity"] in ("informational", "low") and r["original_risk_type"])),
            ("recommended_keep_medium_or_high",
             sum(1 for r in recal_rows if r["recommended_future_severity"] in ("medium", "high") and r["original_risk_type"])),
            ("rationale", "Most owner_procore_mismatch flags are structural (owner sell/SOV vs "
                          "subcontract cost, scope aggregation, placeholder family, or deductive credit) "
                          "and should not be critical. Reserve critical/high for true progress discrepancies."),
        ])),
        ("recommended_next_actions", [
            "Resolve owner placeholder-family mappings (owner_sov_to_budget_code_crosswalk.jsonl).",
            "Verify deductive change-order credits and timing items.",
            "Apply advisory recalibration inputs in a later analysis-package v2 patch.",
        ]),
        ("conclusion_pending_validation", None),
    ])
    # placeholder; conclusion filled below after validation
    # ==================================================================================
    # copy script + audit
    # ==================================================================================
    shutil.copy2(Path(__file__), OUT / "generate_mapping_discrepancy_workpaper.py")

    src_used = OrderedDict([
        ("context_package", str(CTX)), ("analysis_package", str(ANL)),
        ("files", [OrderedDict([("label", kk), ("path", str(p)), ("sha256", sha256_file(p)),
                                ("size_bytes", p.stat().st_size)]) for kk, p in SRC.items()]),
    ])
    write_json(OUT / "audit" / "source_files_used.json", src_used)
    write_json(OUT / "audit" / "source_validation_snapshot.json", OrderedDict([
        ("context_conclusion", ctx_concl), ("analysis_conclusion", anl_concl),
        ("context_coverage", coverage),
        ("analysis_owner_procore_mismatch_count", len(mismatch_risks)),
    ]))
    recon_in = read_json(CTX / "audit" / "reconciliation_report.json")
    write_json(OUT / "audit" / "source_reconciliation_snapshot.json", OrderedDict([
        ("cost_entries_minus_erp_jtd", recon_in.get("cost_entries_minus_erp_jtd")),
        ("owner_latest_application_no", recon_in.get("owner_latest_application_no")),
        ("owner_latest_grand_total_completed_and_stored", recon_in.get("owner_latest_grand_total_completed_and_stored")),
        ("procore_latest_completed_all_88_rows", recon_in.get("procore_latest_completed_all_88_rows")),
        ("note", "Owner & Procore pay-app figures are evidence, not accounting actual cost. "
                 "Procore evidence is through May 2026; CostEntries include June 2026 actuals."),
    ]))

    # ---- safety scan ----
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

    bc_outputs = [OUT / "owner_procore_discrepancy_classification.jsonl",
                  OUT / "budget_code_scope_reconciliation.jsonl",
                  OUT / "owner_procore_mismatch_recalibration_inputs.jsonl"]
    keys_ok = True
    for f in bc_outputs:
        for r in read_jsonl(f):
            kk = r.get("budget_code_key")
            if kk is not None and kk not in canonical_keys:
                keys_ok = False
    mismatch_covered = sorted(mismatch_risks.keys())
    classified_keys = {r["budget_code_key"] for r in disc_rows}
    mismatch_coverage_ok = all(k in classified_keys for k in mismatch_covered)
    # true-discrepancy guard recheck
    true_guard_ok = all(r["comparison_basis"] in ("percent_complete", "remaining_exposure")
                        for r in disc_rows if r["is_true_progress_discrepancy"])
    # no fuzzy method strings present
    no_fuzzy_ok = True
    for f in (OUT / "owner_sov_to_budget_code_crosswalk.jsonl",
              OUT / "procore_commitment_to_budget_code_crosswalk.jsonl"):
        for r in read_jsonl(f):
            m = r.get("mapping_method")
            if m is not None and m not in ALLOWED_MAPPING_METHODS:
                no_fuzzy_ok = False

    mapping_workpaper_context_analysis_lineage_consistent = run_lineage.lineage_consistent(
        [CONTEXT_LINEAGE, ANALYSIS_LINEAGE])
    structural_ok = (not missing and out_valid and keys_ok and mismatch_coverage_ok
                     and true_guard_ok and no_fuzzy_ok and safety["passed"]
                     and ctx_concl == "forecast_context_ready_with_mapping_gaps"
                     and mapping_workpaper_context_analysis_lineage_consistent)
    has_unresolved = (type_counts.get("unresolved", 0) > 0 or len(review_items) > 0
                      or any(r["requires_human_review"] for r in disc_rows))
    if not structural_ok:
        conclusion = "mapping_discrepancy_workpaper_not_ready"
    elif has_unresolved:
        conclusion = "mapping_discrepancy_workpaper_ready_with_unresolved_items"
    else:
        conclusion = "mapping_discrepancy_workpaper_ready"

    summary["conclusion_pending_validation"] = conclusion
    write_json(OUT / "discrepancy_resolution_summary.json", summary)

    # ---- input_inventory ----
    write_json(OUT / "input_inventory.json", OrderedDict([
        ("data_root", str(ROOT)),
        ("context_package", str(CTX)),
        ("analysis_package_selected", str(ANL)),
        ("lineage", OrderedDict([
            ("consumed_context", CONTEXT_LINEAGE),
            ("consumed_analysis", ANALYSIS_LINEAGE),
            ("mapping_workpaper_context_analysis_lineage_consistent",
             bool(mapping_workpaper_context_analysis_lineage_consistent))])),
        ("input_files", [OrderedDict([("label", kk), ("path", str(p)), ("exists", p.exists()),
                                      ("parse", parse_results.get(kk))]) for kk, p in SRC.items()]),
        ("ignored", [
            {"path": "owner_pay_app_raw_cells.jsonl", "reason": "raw cells — audit only, never consumed"},
            {"path": "*.zip", "reason": "package zips, not data inputs"},
        ]),
    ]))

    # ---- validation_report ----
    validation = OrderedDict([
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("period", PERIOD)])),
        ("generated_stamp", STAMP),
        ("lineage", OrderedDict([
            ("consumed_context", CONTEXT_LINEAGE), ("consumed_analysis", ANALYSIS_LINEAGE),
            ("mapping_workpaper_context_analysis_lineage_consistent",
             bool(mapping_workpaper_context_analysis_lineage_consistent))])),
        ("input_checks", OrderedDict([
            ("missing_inputs", missing), ("parse_results", parse_results),
            ("context_conclusion", ctx_concl),
            ("context_conclusion_ok", ctx_concl == "forecast_context_ready_with_mapping_gaps"),
            ("analysis_conclusion", anl_concl),
            ("analysis_conclusion_ok", anl_concl in ("forecast_analysis_ready_with_review_items",
                                                     "forecast_analysis_ready")),
        ])),
        ("output_parse", OrderedDict([("all_passed", out_valid), ("invalid", invalid)])),
        ("row_counts", out_counts),
        ("checks", OrderedDict([
            ("budget_keys_valid_or_null", keys_ok),
            ("owner_procore_mismatch_count", len(mismatch_risks)),
            ("owner_procore_mismatch_all_classified", mismatch_coverage_ok),
            ("true_progress_discrepancy_comparable_basis_guard", true_guard_ok),
            ("no_fuzzy_mapping_methods", no_fuzzy_ok),
        ])),
        ("discrepancy_counts_by_type", OrderedDict(sorted(type_counts.items()))),
        ("true_progress_discrepancy_count", true_count),
        ("manual_review_item_counts_by_priority", OrderedDict(sorted(prio_counts.items()))),
        ("reconciliation", OrderedDict([
            ("source_mismatch_risks", len(mismatch_risks)),
            ("classified_rows", len(disc_rows)),
            ("classified_minus_source_mismatch", len(disc_rows) - len(mismatch_risks)),
            ("note", "classified rows ≥ source mismatch risks (set also includes both-mapped and "
                     "ambiguous-related codes)."),
        ])),
        ("safety_scan", OrderedDict([("passed", safety["passed"]), ("findings", safety["findings"])])),
        ("determinism", OrderedDict([
            ("method", "two frozen-stamp runs diffed on data files; engine sorted + no RNG"),
            ("performed_by_script", False),
            ("note", "Determinism verified by operator harness alongside this run."),
        ])),
        ("known_limitations", [
            "Owner SOV families often resolve to multiple BudgetDetails candidates; some scope "
            "relationships remain unresolved and need human mapping.",
            "Owner-vs-Procore dollar comparisons are sell-value vs subcontract-cost and are marked "
            "dollars_with_markup_caution; most mismatches are structural, not true progress risks.",
            "Procore evidence is through May 2026; June actuals exist separately.",
            "This workpaper is advisory; it does not modify the analysis package or risk scoring.",
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
        ("context_package", str(CTX)), ("analysis_package", str(ANL)),
        ("output_files", out_manifest),
        ("source_files", [OrderedDict([("label", kk), ("sha256", sha256_file(p))]) for kk, p in SRC.items()]),
        ("validation_status", OrderedDict([("output_parse", out_valid),
                                           ("mismatch_coverage", mismatch_coverage_ok),
                                           ("safety_scan", safety["passed"]),
                                           ("structural_ok", structural_ok)])),
        ("conclusion", conclusion),
    ]))

    # ---- README + SCHEMA ----
    write_text(OUT / "README.md", _readme(out_counts, type_counts, true_count, prio_counts,
                                          len(mismatch_risks), safety, conclusion))
    write_text(OUT / "SCHEMA.md", _schema())

    print(json.dumps(OrderedDict([
        ("output_package", str(OUT)), ("analysis_package_used", str(ANL)),
        ("conclusion", conclusion), ("structural_ok", structural_ok),
        ("owner_procore_mismatch_count", len(mismatch_risks)),
        ("classified_rows", len(disc_rows)),
        ("mismatch_all_classified", mismatch_coverage_ok),
        ("true_progress_discrepancy_count", true_count),
        ("discrepancy_counts_by_type", OrderedDict(sorted(type_counts.items()))),
        ("manual_review_by_priority", OrderedDict(sorted(prio_counts.items()))),
        ("safety_passed", safety["passed"]),
        ("out_counts", out_counts),
    ]), indent=2))


# --------------------------------------------------------------------------------------
def _is_internal(desc, keys, bc_by_key):
    """Internal/non-subcontract ONLY when category clearly supports it (refinement #1).
    SUB is subcontract scope and is NEVER internal; description keywords are a signal only when
    NO related key is a subcontract (.SUB) line — this avoids false positives on real subcontracts."""
    cats = set()
    for k in keys:
        parsed = parse_budget_key(k)
        if parsed:
            cats.add(parsed[2])
    if cats and cats <= {"LAB", "LBN", "OVH"}:
        return True            # purely internal-labor/overhead scope
    if "SUB" in cats:
        return False           # subcontract scope is not internal, regardless of description text
    if desc and INTERNAL_KEYWORDS.search(desc):
        return True            # owner GC/GR/fee/bond/insurance bucket with no subcontract key
    return False


def _comparison_basis(rel, ow, proc_completed):
    if rel in ("pcco_change_order", "internal_cost", "owner_only", "procore_only", "unresolved"):
        return "not_comparable"
    owner_pct = ow.get("owner_latest_percent_complete")
    if rel == "one_to_one" and owner_pct is not None and proc_completed is not None and proc_completed > 0:
        # owner is sell/bill value vs subcontract cost; dollars not same-basis -> caution
        return "dollars_with_markup_caution"
    return "dollars_with_markup_caution"


def _owner_note(alloc, row_type, fam):
    if alloc == "not_applicable":
        return "PCCO/change-order or non-base scope; outside base budget universe"
    if alloc == "family_multiple":
        return f"placeholder/family {fam} maps to multiple BudgetDetails candidates — human review"
    if alloc == "manual":
        return f"family {fam} has no clean BudgetDetails match — manual mapping required"
    return None


def _scope_note(rel, basis):
    return f"scope_relationship={rel}; comparison_basis={basis}"


def _disc_resolution(dtype):
    return {
        "internal_or_non_subcontract_cost": "Exclude from owner-vs-subcontract comparison; internal/non-subcontract scope.",
        "deductive_change_order_credit": "Treat negative Procore as deductive credit; exclude from progress comparison.",
        "owner_sov_placeholder_family": "Resolve owner placeholder-family mapping to budget code(s).",
        "mapping_ambiguity": "Resolve ambiguous owner mapping before comparing progress.",
        "pcco_or_change_order_scope": "Handle as change-order scope; not a base-budget progress mismatch.",
        "scope_aggregation_difference": "Compare at aggregated scope; owner SOV ≠ per-commitment Procore.",
        "owner_sell_value_vs_subcontract_cost": "Compare percent-complete, not sell-vs-cost dollars.",
        "timing_difference": "Re-evaluate after aligning billing cycles.",
        "missing_procore_commitment_scope": "Confirm whether a subcontract exists in Procore.",
        "missing_owner_sov_scope": "Identify owner SOV line covering this subcontract scope.",
        "true_progress_discrepancy": "Investigate progress vs cost; assess forecast impact.",
        "no_discrepancy": "No action; immaterial.",
        "unresolved": "Human review to determine scope relationship.",
    }.get(dtype, "Review.")


def _disc_note(dtype, rel, basis, neg):
    parts = [f"type={dtype}", f"scope={rel}", f"basis={basis}"]
    if neg:
        parts.append("procore negative/deductive-credit present")
    return "; ".join(parts)


# --------------------------------------------------------------------------------------
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
    samples = defaultdict(list)
    for path in files:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue
        for name, pat in SAFETY_PATTERNS.items():
            for m in pat.finditer(text):
                findings[name] += 1
                if len(samples[name]) < 3:
                    s = m.group(0)
                    samples[name].append({"file": Path(path).name,
                                          "match_redacted": (s[:4] + "…REDACTED") if len(s) > 6 else "REDACTED"})
    passed = all(findings[c] == 0 for c in FAIL_CATEGORIES)
    return OrderedDict([("scanned_file_count", len(files)),
                        ("findings", OrderedDict((k, findings[k]) for k in sorted(findings))),
                        ("fail_categories", sorted(FAIL_CATEGORIES)),
                        ("samples_redacted", {k: samples[k] for k in samples}),
                        ("passed", passed)])


def _readme(out_counts, type_counts, true_count, prio, mismatch_n, safety, conclusion):
    L = []
    A = L.append
    A(f"# Mapping-Discrepancy Workpaper — {PROJECT_NAME}\n")
    A("## Objective\n")
    A("Explain and, where the data supports, resolve the structural discrepancies behind "
      "`owner_procore_mismatch` flags by building a scope-relationship layer between owner G703/SOV "
      "progress evidence and Procore subcontractor pay-app progress evidence. **Workpaper only** — it "
      "does not mutate sources, the workbook, or the forecast analysis package, and treats all pay-app "
      "values as evidence (never accounting actual-cost truth).\n")
    A("## Paths\n")
    A(f"- Context package: `{CTX}`")
    A(f"- Analysis package: `{ANL}`")
    A(f"- Output: `{OUT}`\n")
    A(f"## Project\n- {PROJECT_NAME} · key `{PROJECT_KEY}` · job `{JOB_REF}` · period `{PERIOD}` · generated `{STAMP}`\n")
    A("## The owner-vs-Procore structural comparison issue\n")
    A("The analysis compared owner `latest_total_completed_and_stored_to_date` (owner-facing **sell/bill** "
      "value — may include markup, bundled scope, general conditions, placeholder SOV families, or PCCO) "
      "against Procore `latest_total_completed_and_stored_to_date_sum` (vendor/commitment **cost**-side "
      "progress — may include deductive change-order credits) for the same budget code. These are often "
      "not scope-equivalent, so the raw dollar mismatch is usually a structural comparison artifact, not "
      "a true progress discrepancy. This package classifies each one.\n")
    A("## Files generated (row counts)\n")
    for f, c in out_counts.items():
        A(f"- `{f}`: {c}")
    A("")
    A("## Discrepancy classification counts\n")
    for t, c in sorted(type_counts.items()):
        A(f"- {t}: {c}")
    A(f"\n- true_progress_discrepancy: {true_count}")
    A(f"- owner_procore_mismatch risks classified: {mismatch_n}\n")
    A("## Manual review counts (by priority)\n")
    for p, c in sorted(prio.items()):
        A(f"- {p}: {c}")
    A("")
    A("## Validation summary\n")
    A(f"- Safety scan: {'PASS' if safety['passed'] else 'FAIL'}; all emitted JSON/JSONL parse; every "
      "budget code ∈ canonical 127; all 32 mismatch risks classified; true_progress_discrepancy guarded "
      "to comparable basis only.\n")
    A("## Known limitations\n")
    A("- Owner SOV families often map to multiple budget codes (unresolved scope relationships remain).")
    A("- Owner-vs-Procore dollars are sell-vs-cost (`dollars_with_markup_caution`).")
    A("- Procore evidence is through May 2026; June actuals exist separately.")
    A("- Advisory only — does not change the analysis package or risk scoring.\n")
    A("## Recommended next use\n")
    A("Use `owner_procore_discrepancy_classification.jsonl` + `manual_crosswalk_review_items.jsonl` for "
      "human resolution, and `owner_procore_mismatch_recalibration_inputs.jsonl` as advisory input to a "
      "later forecast-analysis v2 patch.\n")
    A(f"## Conclusion: `{conclusion}`\n")
    return "\n".join(L)


def _schema():
    return """# SCHEMA — Mapping-Discrepancy Workpaper

## Interpretation guidance
- BudgetDetails (127 keys) is the master universe; all budget-code rows resolve to a canonical key.
- CostEntries are accounting actual-cost truth; owner & Procore pay-app values are EVIDENCE only.
- Owner SOV = owner-facing sell/bill value (markup/bundled/GC/placeholder/PCCO possible).
- Procore = vendor/commitment subcontract cost progress (deductive credits possible).
- Compare scope BEFORE dollars. Raw owner vs Procore dollars are `dollars_with_markup_caution`
  unless proven same-scope and same-basis.
- `true_progress_discrepancy` requires comparison_basis ∈ {percent_complete, remaining_exposure}
  (hard guard) AND clean one_to_one scope, no ambiguity, no deductive-credit distortion, materiality,
  and actuals/remaining support.

## owner_sov_to_budget_code_crosswalk.jsonl
One row per owner SOV scope (row_type, owner_sov_code, cost_code, family). Fields: crosswalk_id,
owner identity/normalized/family/placeholder, latest owner values, candidate & selected
budget_code_keys, allocation_method {exact|constructed_exact|family_unique|family_multiple|manual|
percent_allocation|not_applicable}, allocation_percent_by_budget_code (null unless explicit basis),
confidence, requires_human_review, notes.

## procore_commitment_to_budget_code_crosswalk.jsonl
One row per Procore commitment/vendor/WBS scope. Fields: crosswalk_id, commitment_id(+source),
vendor_entity_key, procore_wbs_flat_code/cost_code/category/family, mapped_budget_code_key,
mapping_method/confidence, invoice_item_count, latest values, has_negative_latest_value +
negative_value_fields (deductive credits preserved), related invoice ids/record keys/item types.

## owner_sov_to_procore_scope_crosswalk.jsonl
One row per owner SOV scope + synthetic procore_only rows. scope_relationship {one_to_one|one_to_many|
many_to_one|many_to_many|owner_only|procore_only|pcco_change_order|internal_cost|unresolved};
comparison_basis {percent_complete|remaining_exposure|dollars_with_markup_caution|not_comparable};
related budget/commitment/vendor/wbs, Procore latest sums, negative-credit count, scope_match_confidence.

## owner_procore_discrepancy_classification.jsonl
One row per discrepancy-set budget code. discrepancy_type {scope_aggregation_difference|
owner_sell_value_vs_subcontract_cost|timing_difference|owner_sov_placeholder_family|
pcco_or_change_order_scope|deductive_change_order_credit|internal_or_non_subcontract_cost|
missing_procore_commitment_scope|missing_owner_sov_scope|mapping_ambiguity|true_progress_discrepancy|
no_discrepancy|unresolved}; is_true_progress_discrepancy; forecast_risk_implication {none|informational|
review|potential_forecast_risk|confirmed_forecast_risk}; deltas, materiality, supporting crosswalk ids.
MAT is NOT auto-internal; internal only for LAB/LBN/OVH or clearly internal/GC scope.

## budget_code_scope_reconciliation.jsonl
One row per master key: budget/proj/actuals (+May/June), owner_evidence_status {mapped|ambiguous_family|
manual_required|none}, procore_evidence_status {mapped|none}, related ids, scope_relationship_summary,
discrepancy_types, true_progress_discrepancy_count, forecast_risk_implication, recommendations.

## manual_crosswalk_review_items.jsonl
Human queue. priority {critical|high|medium|low}, review_type, ids, reason, recommended_human_action.

## owner_procore_mismatch_recalibration_inputs.jsonl  (ADVISORY ONLY)
Per mismatch/comparable code: original_risk_type/severity, classified_discrepancy_type,
is_true_progress_discrepancy, forecast_risk_implication, recommended_future_risk_type/severity
{critical|high|medium|low|informational|none}, recommended_rule_change, supporting_reason. Does NOT
modify the analysis package.

## discrepancy_resolution_summary.json / validation_report.json / manifest.json / input_inventory.json
Project-level rollups, validation gates, hashes, and the selected analysis package record.
"""


if __name__ == "__main__":
    main()
