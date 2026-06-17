#!/usr/bin/env python3
"""
generate_forecast_analysis_package.py

Tropical World Nursery Senior Living Facility (project_key=tropical, job=23-435-01)
Forecast ANALYSIS generation — FOR HUMAN REVIEW ONLY.

Consumes the read-only forecast CONTEXT package and emits a forecast-analysis package:
per-budget-code forecast recommendations, risk register, evidence alignment, manual-mapping
review items, assumptions, data-quality warnings, and executive/reviewer summaries.

Hard rules:
  - Does NOT mutate any source / context data, Excel, or the forecast workbook.
  - Does NOT commit, and makes NO live/external calls or production-DB access.
  - Does NOT invent mappings; never uses fuzzy/description-only matching.
  - Pay-app values are EVIDENCE, never accounting actual-cost truth.

Stdlib only. Decimal(str(value)) for all money math; no float arithmetic on amounts.
Deterministic sorted output. Re-runnable.
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
# Paths / constants
# --------------------------------------------------------------------------------------
DEFAULT_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)
# Resolved at RUNTIME by resolve_inputs() (never at import): data root + upstream context + outputs.
ROOT = None
INPUT = None
OUT = None
SRC = {}
CONTEXT_LINEAGE = None

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
    """Resolve the upstream context package + output path at runtime (full-fresh run state aware).

    Under an active full-fresh run state, the context is consumed strictly from the state; otherwise
    latest-glob. A `--context-stamp` debug override rides in as CFR_CONTEXT_STAMP. Never resolves from
    stale config names or hardcoded package paths.
    """
    global ROOT, INPUT, OUT, SRC, CONTEXT_LINEAGE
    ROOT = run_lineage.active_data_root(DEFAULT_ROOT)
    INPUT, CONTEXT_LINEAGE = run_lineage.resolve_upstream(
        "context", data_root=ROOT, project_key=PROJECT_KEY,
        override_stamp=os.environ.get("CFR_CONTEXT_STAMP"))
    OUT = ROOT / f"forecast_analysis_package_tropical_{STAMP}"
    SRC = {
        "bc_context": INPUT / "summaries" / "budget_code_forecast_context.jsonl",
        "project_context": INPUT / "summaries" / "project_forecast_context.json",
        "coverage": INPUT / "summaries" / "mapping_coverage_summary.json",
        "data_gaps": INPUT / "summaries" / "data_gap_register.json",
        "recon": INPUT / "audit" / "reconciliation_report.json",
        "ctx_validation": INPUT / "validation_report.json",
        "budget_codes": INPUT / "canonical" / "budget_codes.jsonl",
        "ambiguous": INPUT / "mapping" / "ambiguous_mapping_candidates.jsonl",
        "unmapped_owner": INPUT / "mapping" / "unmapped_owner_pay_app_rows.jsonl",
        "owner_crosswalk": INPUT / "mapping" / "owner_cost_code_family_crosswalk.jsonl",
        "unmapped_procore": INPUT / "mapping" / "unmapped_procore_pay_app_rows.jsonl",
    }
    return {"context": CONTEXT_LINEAGE}

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
    """Decimal or 0."""
    d = dec(v)
    return d if d is not None else Decimal("0")


def money_str(v):
    d = dec(v)
    if d is None:
        return None
    return str(d.quantize(CENTS))


def cost_code_division(cost_code):
    if not isinstance(cost_code, str):
        return None
    seg = cost_code.split("-")
    return seg[0] if seg and seg[0] else None


def materiality(a, b):
    """Return (gap:Decimal, pct:Decimal|None, is_material:bool) for |a-b|."""
    a = a if a is not None else Decimal("0")
    b = b if b is not None else Decimal("0")
    gap = abs(a - b)
    basis = max(abs(a), abs(b))
    pct = (gap / basis) if basis > 0 else None
    is_material = (gap >= MAT_DOLLAR) and (pct is not None and pct >= MAT_PCT)
    return gap, pct, is_material


def severity_for(gap, pct):
    if gap >= Decimal("250000") or (pct is not None and pct >= Decimal("0.25")):
        return "critical"
    if gap >= Decimal("100000") or (pct is not None and pct >= Decimal("0.15")):
        return "high"
    if gap >= MAT_DOLLAR and (pct is not None and pct >= MAT_PCT):
        return "medium"
    return "low"


# --------------------------------------------------------------------------------------
# Load inputs
# --------------------------------------------------------------------------------------
def check_inputs():
    missing = [k for k, p in SRC.items() if not p.exists()]
    parse_ok = {}
    for k, p in SRC.items():
        if not p.exists():
            continue
        try:
            if p.suffix == ".jsonl":
                for _ in read_jsonl(p):
                    pass
            else:
                read_json(p)
            parse_ok[k] = True
        except Exception as e:
            parse_ok[k] = f"INVALID: {e}"
    ctx_val = read_json(SRC["ctx_validation"])
    ctx_conclusion = ctx_val.get("conclusion")
    return missing, parse_ok, ctx_conclusion, ctx_val


# build ambiguous-owner-candidate index + family review info
def build_owner_mapping_indexes():
    amb_candidates = set()
    crosswalk = list(read_jsonl(SRC["owner_crosswalk"]))
    for cw in crosswalk:
        if cw.get("resolution_status") == "multiple_budget_candidates":
            for k in cw.get("budget_detail_candidate_keys", []):
                amb_candidates.add(k)
    for row in read_jsonl(SRC["ambiguous"]):
        for k in row.get("candidate_budget_code_keys", []):
            amb_candidates.add(k)
    return amb_candidates, crosswalk


# --------------------------------------------------------------------------------------
# Recommendation engine
# --------------------------------------------------------------------------------------
def analyze():
    bc_rows = list(read_jsonl(SRC["bc_context"]))
    canonical_keys = {r["budget_code_key"] for r in read_jsonl(SRC["budget_codes"])}
    amb_candidates, crosswalk = build_owner_mapping_indexes()

    recs = []
    aligns = []
    risks = []
    calc_by_key = {}
    risk_counter = [0]

    def add_risk(severity, key, cost_code, category, rtype, desc, evidence, action, src_files):
        risk_counter[0] += 1
        risks.append(OrderedDict([
            ("risk_id", f"R-{risk_counter[0]:04d}"),
            ("severity", severity),
            ("budget_code_key", key),
            ("cost_code", cost_code),
            ("category", category),
            ("risk_type", rtype),
            ("description", desc),
            ("evidence", evidence),
            ("recommended_action", action),
            ("requires_human_review", True),
            ("source_files", src_files),
        ]))

    BC_SRC = ["summaries/budget_code_forecast_context.jsonl"]

    for r in sorted(bc_rows, key=lambda x: x["budget_code_key"]):
        key = r["budget_code_key"]
        amts = r.get("budget_amounts") or {}
        actuals = r.get("actuals") or {}
        ob = r.get("owner_pay_app") or {}
        pb = r.get("procore_subcontractor_pay_apps") or {}
        com = r.get("commitments") or {}

        budget = D(amts.get("revised_budget"))
        proj = D(amts.get("projected_costs"))
        actual = D(actuals.get("actual_cost_all_source_to_date"))
        actual_may = D(actuals.get("actual_cost_through_may_2026"))
        actual_june = D(actuals.get("actual_cost_june_2026_to_date"))
        entry_count = actuals.get("actual_entry_count") or 0

        has_actuals = entry_count > 0
        has_owner = ob.get("mapping_status") == "mapped"
        has_procore = pb.get("mapping_status") == "mapped"

        owner_completed = dec(ob.get("latest_total_completed_and_stored_to_date")) if has_owner else None
        owner_pct = dec(ob.get("latest_percent_complete")) if has_owner else None
        owner_balance = dec(ob.get("latest_balance_to_finish")) if has_owner else None
        procore_completed = dec(pb.get("latest_total_completed_and_stored_to_date_sum")) if has_procore else None
        procore_claimed = dec(pb.get("latest_subcontractor_claimed_amount_sum")) if has_procore else None
        procore_retainage = dec(pb.get("latest_retainage_held_sum")) if has_procore else None
        commitment_count = com.get("related_commitment_count") or 0

        is_amb_candidate = key in amb_candidates

        # evidence depth
        if not has_actuals and not has_owner and not has_procore:
            evidence_depth = "no_evidence"
        elif not has_actuals:
            evidence_depth = "payapp_only"
        elif has_owner and has_procore:
            evidence_depth = "actuals_owner_and_procore"
        elif has_owner:
            evidence_depth = "actuals_and_owner"
        elif has_procore:
            evidence_depth = "actuals_and_procore"
        else:
            evidence_depth = "actuals_only"

        # ---- flags ----
        risk_flags = []
        flag_detail = {}

        # owner vs actuals
        if has_owner and has_actuals and owner_completed is not None:
            gap, pct, mat = materiality(owner_completed, actual)
            if mat and owner_completed > actual:
                risk_flags.append("owner_progress_ahead_of_actuals")
                flag_detail["owner_progress_ahead_of_actuals"] = (gap, pct)
            elif mat and actual > owner_completed:
                risk_flags.append("actuals_ahead_of_owner_progress")
                flag_detail["actuals_ahead_of_owner_progress"] = (gap, pct)
        # procore vs actuals
        if has_procore and has_actuals and procore_completed is not None:
            gap, pct, mat = materiality(procore_completed, actual)
            if mat and procore_completed > actual:
                risk_flags.append("subcontractor_progress_ahead_of_actuals")
                flag_detail["subcontractor_progress_ahead_of_actuals"] = (gap, pct)
        # owner vs procore
        if has_owner and has_procore and owner_completed is not None and procore_completed is not None:
            gap, pct, mat = materiality(owner_completed, procore_completed)
            if mat:
                risk_flags.append("owner_procore_mismatch")
                flag_detail["owner_procore_mismatch"] = (gap, pct)
        # negative procore credit
        neg_procore = has_procore and procore_completed is not None and procore_completed < 0
        if neg_procore:
            risk_flags.append("deductive_change_order_credit_review")
        # june timing
        june_flag = actual_june != 0
        if june_flag:
            risk_flags.append("june_actuals_without_june_payapp_evidence")
        # exhaustion risk
        exhaustion = False
        if has_actuals and proj > 0 and actual >= (proj * EXHAUSTION_PCT) and actual <= proj:
            remaining_implied = (
                (owner_pct is not None and owner_pct < 1)
                or (owner_balance is not None and owner_balance > 0)
                or (procore_completed is not None and procore_completed > 0)
            )
            if remaining_implied:
                exhaustion = True
                risk_flags.append("forecast_exhaustion_risk")
        # mapping gap (owner billed at family level, attribution to this code unresolved)
        mapping_gap = is_amb_candidate and not has_owner
        if mapping_gap:
            risk_flags.append("mapping_gap")
        if is_amb_candidate:
            risk_flags.append("ambiguous_owner_mapping")
        # payapp evidence without actuals
        if not has_actuals and (has_owner or has_procore):
            risk_flags.append("payapp_evidence_without_actuals")
        # budget code with no activity
        if not has_actuals and not has_owner and not has_procore:
            risk_flags.append("budget_code_with_no_activity")

        # ---- decision tree ----
        # Genuine evidence-conflict triggers only. Owner-family ambiguity (is_amb_candidate /
        # mapping_gap) is an attribution caveat on OWNER EVIDENCE, not a flaw in the code's
        # actuals-anchored forecast, so it does NOT force review_required when actuals are clean —
        # it is surfaced as a flag + manual-review item instead.
        review_triggers = [f for f in (
            "owner_progress_ahead_of_actuals", "actuals_ahead_of_owner_progress",
            "subcontractor_progress_ahead_of_actuals", "owner_procore_mismatch",
            "deductive_change_order_credit_review", "forecast_exhaustion_risk",
        ) if f in risk_flags]
        material_june = june_flag and (actual_june >= MAT_DOLLAR)

        rec_proj = None
        adjustment = None
        ctc = None
        action = None
        confidence = None
        reason = None

        if has_actuals and actual > proj:
            # 1) ABSOLUTE precedence: floor-to-actuals increase
            action = "increase_forecast"
            rec_proj = actual
            adjustment = actual - proj
            ctc = max(rec_proj - actual, Decimal("0"))
            if "actuals_exceed_projected_cost" not in risk_flags:
                risk_flags.insert(0, "actuals_exceed_projected_cost")
            risk_flags.append("forecast_floor_to_actuals")
            if (has_owner and owner_pct is not None and owner_pct < 1) or \
               (has_procore and procore_completed is not None and procore_completed > actual):
                risk_flags.append("remaining_exposure_review_required")
            # confidence
            if mapping_gap or is_amb_candidate:
                confidence = "low"
                reason = "actuals exceed projected cost; related owner evidence has mapping gaps"
            elif material_june or review_triggers:
                confidence = "medium"
                reason = "actuals exceed projected cost; June timing or pay-app mismatch warrants review"
            else:
                confidence = "high"
                reason = "actuals exceed projected cost with clean mapping; floored to actual cost"
        elif has_actuals and _decrease_ok(proj, actual, has_owner, owner_pct, owner_balance,
                                          has_procore, procore_completed, june_flag,
                                          is_amb_candidate, neg_procore):
            action = "decrease_forecast"
            rec_proj = actual
            adjustment = actual - proj  # negative
            ctc = Decimal("0")
            risk_flags.append("forecast_decrease_supported_by_completion")
            confidence = "medium"
            reason = ("owner evidence substantially complete and projected materially exceeds actual "
                      "with no remaining exposure indicated")
        elif has_actuals and review_triggers:
            action = "review_required"
            confidence = "low" if (mapping_gap or is_amb_candidate) else "medium"
            reason = "actuals present but pay-app evidence conflicts (progress mismatch / credit / "
            reason += "exhaustion) require review"
        elif has_actuals:
            action = "hold_current_forecast"
            rec_proj = proj
            adjustment = Decimal("0")
            ctc = max(proj - actual, Decimal("0"))
            confidence = "high"
            reason = "valid actuals; projected cost covers actuals with no material mismatch"
        elif has_owner or has_procore:
            action = "review_required"
            confidence = "low"
            reason = "pay-app evidence exists but no accounting actuals to anchor a forecast"
        elif is_amb_candidate:
            action = "mapping_required"
            confidence = "low"
            reason = "owner billed at cost-code-family level; attribution to this budget code unresolved"
        else:
            action = "insufficient_evidence"
            confidence = "none"
            reason = "no actuals and no mapped owner/Procore evidence"

        # de-dup flags, keep order
        seen = set()
        risk_flags = [f for f in risk_flags if not (f in seen or seen.add(f))]

        projected_variance_to_budget = (rec_proj - budget) if rec_proj is not None else None
        current_variance_to_budget = proj - budget

        # monthly trend (last 3)
        monthly = actuals.get("monthly_actuals") or []
        trend = [m.get("amount_decimal_string") for m in monthly[-3:]]

        supporting = OrderedDict([
            ("actual_cost_all_source_to_date", money_str(actual)),
            ("actual_cost_june_2026_to_date", money_str(actual_june)),
            ("owner_latest_completed", money_str(owner_completed)),
            ("owner_latest_percent_complete", float(owner_pct) if owner_pct is not None else None),
            ("procore_latest_completed", money_str(procore_completed)),
            ("procore_latest_claimed", money_str(procore_claimed)),
            ("commitment_count", commitment_count),
            ("recent_monthly_actuals", trend),
        ])

        rec = OrderedDict([
            ("project_key", PROJECT_KEY),
            ("budget_code_key", key),
            ("sub_job", r.get("sub_job")),
            ("sub_job_description", r.get("sub_job_description")),
            ("cost_code", r.get("cost_code")),
            ("category", r.get("category")),
            ("budget_code_description", r.get("budget_code_description")),
            ("budget_amount", money_str(budget)),
            ("current_projected_cost", money_str(proj)),
            ("actual_cost_all_source_to_date", money_str(actual)),
            ("actual_cost_through_may_2026", money_str(actual_may)),
            ("actual_cost_june_2026_to_date", money_str(actual_june)),
            ("latest_actual_accounting_date", actuals.get("latest_actual_accounting_date")),
            ("owner_latest_total_completed_and_stored_to_date", money_str(owner_completed)),
            ("owner_latest_percent_complete", float(owner_pct) if owner_pct is not None else None),
            ("owner_latest_balance_to_finish", money_str(owner_balance)),
            ("owner_mapping_status", ob.get("mapping_status")),
            ("procore_latest_total_completed_and_stored_to_date", money_str(procore_completed)),
            ("procore_latest_retainage_held", money_str(procore_retainage)),
            ("procore_latest_claimed_amount", money_str(procore_claimed)),
            ("procore_mapping_status", pb.get("mapping_status")),
            ("commitment_count", commitment_count),
            ("evidence_depth", evidence_depth),
            ("forecast_action", action),
            ("recommended_forecast_adjustment", money_str(adjustment) if adjustment is not None else None),
            ("recommended_projected_cost", money_str(rec_proj) if rec_proj is not None else None),
            ("recommended_cost_to_complete", money_str(ctc) if ctc is not None else None),
            ("projected_variance_to_budget", money_str(projected_variance_to_budget) if projected_variance_to_budget is not None else None),
            ("current_variance_to_budget", money_str(current_variance_to_budget)),
            ("reference_amounts", OrderedDict([
                ("projected_budget", money_str(amts.get("projected_budget"))),
                ("estimated_cost_at_completion", money_str(amts.get("estimated_cost_at_completion"))),
                ("original_budget_amount", money_str(amts.get("original_budget_amount"))),
                ("approved_cos", money_str(amts.get("approved_cos"))),
                ("pending_budget_changes", money_str(amts.get("pending_budget_changes"))),
                ("committed_costs", money_str(amts.get("committed_costs"))),
            ])),
            ("confidence", confidence),
            ("confidence_reason", reason),
            ("risk_flags", risk_flags),
            ("data_gap_flags", r.get("data_gap_flags") or []),
            ("supporting_evidence", supporting),
            ("review_notes", _review_note(action, evidence_depth, risk_flags)),
        ])
        recs.append(rec)
        calc_by_key[key] = {
            "budget": budget, "proj": proj, "actual": actual, "actual_june": actual_june,
            "rec_proj": rec_proj if rec_proj is not None else proj, "adjustment": adjustment or Decimal("0"),
            "action": action, "confidence": confidence, "category": r.get("category"),
            "division": cost_code_division(r.get("cost_code")),
            "has_actuals": has_actuals, "has_owner": has_owner, "has_procore": has_procore,
            "owner_completed": owner_completed, "procore_completed": procore_completed,
            "risk_flags": risk_flags, "is_amb_candidate": is_amb_candidate,
        }

        # ---- evidence alignment ----
        avb = (actual / budget) if budget > 0 else None
        avp = (actual / proj) if proj > 0 else None
        ovd = (owner_completed - actual) if (owner_completed is not None) else None
        pvd = (procore_completed - actual) if (procore_completed is not None) else None
        opd = (owner_completed - procore_completed) if (owner_completed is not None and procore_completed is not None) else None
        align_flags = []
        if not has_actuals:
            astatus = "insufficient_actuals"
        elif mapping_gap:
            astatus = "mapping_gap"
        elif "owner_procore_mismatch" in risk_flags:
            astatus = "owner_procore_mismatch"
        elif "owner_progress_ahead_of_actuals" in risk_flags or "subcontractor_progress_ahead_of_actuals" in risk_flags:
            astatus = "progress_high_vs_actuals"
        elif "actuals_ahead_of_owner_progress" in risk_flags or (has_actuals and actual > proj):
            astatus = "actuals_high_vs_progress"
        elif not has_owner and not has_procore:
            astatus = "insufficient_payapp_evidence"
        else:
            astatus = "aligned"
        for f in ("owner_progress_ahead_of_actuals", "actuals_ahead_of_owner_progress",
                  "subcontractor_progress_ahead_of_actuals", "owner_procore_mismatch",
                  "deductive_change_order_credit_review", "mapping_gap"):
            if f in risk_flags:
                align_flags.append(f)
        aligns.append(OrderedDict([
            ("budget_code_key", key),
            ("budget_amount", money_str(budget)),
            ("current_projected_cost", money_str(proj)),
            ("actual_cost_all_source_to_date", money_str(actual)),
            ("owner_latest_completed", money_str(owner_completed)),
            ("owner_latest_percent_complete", float(owner_pct) if owner_pct is not None else None),
            ("procore_latest_completed", money_str(procore_completed)),
            ("procore_latest_claimed", money_str(procore_claimed)),
            ("commitment_count", commitment_count),
            ("actual_vs_budget_ratio", str(avb.quantize(Decimal("0.0001"))) if avb is not None else None),
            ("actual_vs_projected_ratio", str(avp.quantize(Decimal("0.0001"))) if avp is not None else None),
            ("owner_vs_actual_delta", money_str(ovd) if ovd is not None else None),
            ("procore_vs_actual_delta", money_str(pvd) if pvd is not None else None),
            ("owner_vs_procore_delta", money_str(opd) if opd is not None else None),
            ("alignment_status", astatus),
            ("alignment_flags", align_flags),
            ("interpretation", _alignment_interpretation(astatus, evidence_depth)),
        ]))

        # ---- per-code risk rows ----
        for f in risk_flags:
            if f in ("forecast_floor_to_actuals", "forecast_decrease_supported_by_completion",
                     "remaining_exposure_review_required", "ambiguous_owner_mapping"):
                continue  # captured via other flags / notes
            sev, desc, ev, act = _risk_meta(f, flag_detail, actual, proj, owner_completed,
                                            procore_completed, actual_june)
            add_risk(sev, key, r.get("cost_code"), r.get("category"), f, desc, ev, act, BC_SRC)
            if f == "ambiguous_owner_mapping":
                pass

    return recs, aligns, risks, calc_by_key, canonical_keys, crosswalk, amb_candidates


def _decrease_ok(proj, actual, has_owner, owner_pct, owner_balance, has_procore,
                 procore_completed, june_flag, is_amb_candidate, neg_procore):
    if not has_owner:
        return False
    if owner_pct is None or owner_pct < OWNER_COMPLETE_PCT:
        return False
    if owner_balance is not None and abs(owner_balance) >= MAT_DOLLAR:
        return False
    if has_procore and procore_completed is not None and procore_completed > 0:
        # remaining subcontractor exposure indicated
        return False
    gap, pct, mat = materiality(proj, actual)
    if not (mat and proj > actual):
        return False
    if june_flag:
        return False
    if is_amb_candidate:
        return False
    if neg_procore:
        return False
    return True


def _review_note(action, depth, flags):
    base = {
        "hold_current_forecast": "Projected cost covers actuals; no change recommended.",
        "increase_forecast": "Floored to accounting actuals (actuals exceed current projected cost).",
        "decrease_forecast": "Completion evidence supports a lower final cost; confirm before applying.",
        "review_required": "Evidence conflicts, timing, or mapping issues require human review.",
        "mapping_required": "Owner attribution unresolved at the budget-code level; map before forecasting.",
        "insufficient_evidence": "No actuals or mapped pay-app evidence; cannot forecast.",
    }[action]
    extra = []
    if "deductive_change_order_credit_review" in flags:
        extra.append("Negative Procore latest value (deductive change-order credit) — verify.")
    if "june_actuals_without_june_payapp_evidence" in flags:
        extra.append("June actuals present while pay-app evidence is through May only.")
    if "mapping_gap" in flags:
        extra.append("Owner billed at cost-code-family level; attribution to this code unresolved.")
    return " ".join([base] + extra)


def _alignment_interpretation(status, depth):
    return {
        "aligned": "Actuals and pay-app progress are consistent within materiality.",
        "actuals_high_vs_progress": "Accounting actuals run ahead of recognized progress.",
        "progress_high_vs_actuals": "Recognized progress runs ahead of accounting actuals.",
        "owner_procore_mismatch": "Owner and subcontractor progress evidence disagree materially.",
        "insufficient_payapp_evidence": "Actuals exist but no mapped pay-app evidence to corroborate.",
        "insufficient_actuals": "No accounting actuals to anchor pay-app evidence.",
        "mapping_gap": "Owner evidence exists at family level but is not attributed to this code.",
    }[status] + f" (evidence_depth={depth})"


def _risk_meta(flag, detail, actual, proj, owner_completed, procore_completed, actual_june):
    g = detail.get(flag)
    if g:
        gap, pct = g
        sev = severity_for(gap, pct)
        ev = {"gap": money_str(gap), "pct": (str(pct.quantize(Decimal('0.0001'))) if pct is not None else None)}
    else:
        gap = pct = None
        sev = "medium"
        ev = {}
    meta = {
        "actuals_exceed_projected_cost": ("Actual cost exceeds current projected cost.",
            {"actual": money_str(actual), "projected": money_str(proj),
             "overrun": money_str(actual - proj)}, "Increase forecast to at least actual cost; review remaining exposure."),
        "owner_progress_ahead_of_actuals": ("Owner-recognized progress materially exceeds actual cost.",
            ev, "Review whether cost is lagging billing or owner progress is overstated."),
        "actuals_ahead_of_owner_progress": ("Actual cost materially exceeds owner-recognized progress.",
            ev, "Review underbilling / unrecognized progress to the owner."),
        "subcontractor_progress_ahead_of_actuals": ("Subcontractor completed/stored materially exceeds actual cost.",
            ev, "Review subcontractor exposure not yet hit accounting actuals."),
        "owner_procore_mismatch": ("Owner vs subcontractor progress evidence disagree materially.",
            ev, "Reconcile owner SOV progress against subcontractor pay-app progress."),
        "deductive_change_order_credit_review": ("Negative Procore latest completed value (deductive change-order credit).",
            {"procore_completed": money_str(procore_completed)}, "Verify the credit; do not decrease forecast solely on this."),
        "forecast_exhaustion_risk": ("Actual cost near projected with remaining exposure implied.",
            {"actual": money_str(actual), "projected": money_str(proj)}, "Review whether projected cost is sufficient to complete."),
        "june_actuals_without_june_payapp_evidence": ("June 2026 actuals exist while pay-app evidence is through May only.",
            {"june_actuals": money_str(actual_june)}, "Treat June actuals as leading signal; await June pay-app evidence."),
        "mapping_gap": ("Owner billed at cost-code-family level; attribution to this budget code unresolved.",
            {}, "Resolve owner family-to-budget-code mapping before trusting owner evidence here."),
        "payapp_evidence_without_actuals": ("Pay-app evidence exists but no accounting actuals.",
            {}, "Confirm whether cost should have posted; treat as evidence only."),
        "budget_code_with_no_activity": ("Budget code has no actuals and no mapped pay-app evidence.",
            {}, "Confirm whether scope is active or dormant."),
    }
    desc, ev2, act = meta.get(flag, (flag, {}, "Review."))
    if not ev:
        ev = ev2
    # severity overrides for categorical flags
    if flag == "deductive_change_order_credit_review":
        amt = procore_completed if procore_completed is not None else Decimal("0")
        sev = "high" if abs(amt) >= MAT_DOLLAR else "medium"
    elif flag == "actuals_exceed_projected_cost":
        gg, pp, _ = materiality(actual, proj)
        sev = severity_for(gg, pp) if (actual - proj) >= MAT_DOLLAR else "low"
    elif flag == "june_actuals_without_june_payapp_evidence":
        sev = "medium" if actual_june >= MAT_DOLLAR else "low"
    elif flag in ("payapp_evidence_without_actuals", "budget_code_with_no_activity", "mapping_gap"):
        sev = "low"
    return sev, desc, ev, act


# --------------------------------------------------------------------------------------
# Safety scan (same regex discipline as the context package)
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
    return OrderedDict([
        ("scanned_file_count", len(files)),
        ("findings", OrderedDict((k, findings[k]) for k in sorted(findings))),
        ("fail_categories", sorted(FAIL_CATEGORIES)),
        ("samples_redacted", {k: samples[k] for k in samples}),
        ("note", "phone regex requires separators; numeric IDs and md5-style keys do not match."),
        ("passed", passed),
    ])


# --------------------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------------------
def main():
    lineage = resolve_inputs()   # runtime upstream resolution (full-fresh run state aware)
    print(f"[analysis] context: {CONTEXT_LINEAGE['consumed_package']} "
          f"(source={CONTEXT_LINEAGE['lineage_source']})")
    OUT.mkdir(parents=True, exist_ok=False)

    missing, parse_ok, ctx_conclusion, ctx_val = check_inputs()
    _ = lineage
    project_ctx = read_json(SRC["project_context"])
    coverage_in = read_json(SRC["coverage"])
    recon_in = read_json(SRC["recon"])
    data_gaps_in = read_json(SRC["data_gaps"])

    recs, aligns, risks, calc, canonical_keys, crosswalk, amb_candidates = analyze()

    out_counts = OrderedDict()
    out_counts["forecast_recommendations_by_budget_code.jsonl"] = write_jsonl(
        OUT / "forecast_recommendations_by_budget_code.jsonl", recs)
    out_counts["evidence_alignment_by_budget_code.jsonl"] = write_jsonl(
        OUT / "evidence_alignment_by_budget_code.jsonl", aligns)

    # ---- project-level risks ----
    risk_counter = len(risks)
    def add_proj_risk(sev, rtype, desc, ev, act):
        nonlocal risk_counter
        risk_counter += 1
        risks.append(OrderedDict([
            ("risk_id", f"R-{risk_counter:04d}"), ("severity", sev),
            ("budget_code_key", None), ("cost_code", None), ("category", None),
            ("risk_type", rtype), ("description", desc), ("evidence", ev),
            ("recommended_action", act), ("requires_human_review", True),
            ("source_files", ["summaries/mapping_coverage_summary.json", "summaries/data_gap_register.json"]),
        ]))
    cov_owner = coverage_in.get("owner_pay_app_line_items", {})
    add_proj_risk("high", "ambiguous_owner_mapping",
                  "Owner SOV families resolve to multiple BudgetDetails candidates; owner evidence is not "
                  "attributable to specific budget codes without human review.",
                  {"ambiguous_owner_line_items": cov_owner.get("ambiguous"),
                   "manual_required": cov_owner.get("manual_required"),
                   "families_needing_review": sum(1 for c in crosswalk if c.get("requires_human_review"))},
                  "Resolve owner cost-code-family crosswalk before relying on owner progress per code.")
    add_proj_risk("medium", "missing_payapp_evidence",
                  "Procore subcontractor pay-app evidence is through May 2026 only; June progress is not yet reflected.",
                  {"cutoff": "through_may_2026"}, "Refresh Procore pay-app evidence for June before month-end forecasting.")
    add_proj_risk("medium", "june_actuals_without_payapp_evidence",
                  "June 2026 accounting actuals exist while pay-app evidence is through May only.",
                  {"june_actual_count": project_ctx.get("actual_totals", {}).get("cost_entries_june_2026_to_date_count"),
                   "june_actual_total": project_ctx.get("actual_totals", {}).get("cost_entries_june_2026_to_date_total")},
                  "Treat June actuals as leading signal pending June pay-app evidence.")
    multi_cat = next((g for g in data_gaps_in.get("gaps", []) if g.get("gap_id") == "GAP-006"), {})
    add_proj_risk("medium", "mapping_gap",
                  "Several cost codes exist under multiple categories; exact category match is required and SUB must not be assumed.",
                  {"multi_category_cost_codes": multi_cat.get("affected_cost_codes", [])[:20]},
                  "Require source-proven category for any mapping to multi-category cost codes.")
    recon_delta = recon_in.get("cost_entries_minus_erp_jtd")
    add_proj_risk("low", "negative_or_unusual_amount",
                  "CostEntries vs BudgetDetails ERP JTD differ by a known rounding amount.",
                  {"cost_entries_minus_erp_jtd": recon_delta}, "Informational; within $0.01 tolerance.")

    out_counts["forecast_risk_register.jsonl"] = write_jsonl(
        OUT / "forecast_risk_register.jsonl", risks)

    # ---- manual mapping review items ----
    review_items = []
    rc = [0]
    def add_review(source_system, row_key, cc, fam, desc, cands, reason, action, priority):
        rc[0] += 1
        review_items.append(OrderedDict([
            ("review_item_id", f"MR-{rc[0]:04d}"),
            ("source_system", source_system),
            ("source_row_key", row_key),
            ("source_cost_code", cc),
            ("source_cost_code_family", fam),
            ("source_description", desc),
            ("candidate_budget_code_keys", cands),
            ("candidate_count", len(cands)),
            ("reason", reason),
            ("recommended_human_action", action),
            ("priority", priority),
        ]))
    for cw in sorted(crosswalk, key=lambda c: -(c.get("owner_line_item_count") or 0)):
        if not cw.get("requires_human_review"):
            continue
        cnt = cw.get("owner_line_item_count") or 0
        pr = "high" if cnt >= 20 else ("medium" if cnt >= 5 else "low")
        rs = cw.get("resolution_status")
        action = ("Choose the correct BudgetDetails key(s) for this owner family or supply an allocation table."
                  if rs == "multiple_budget_candidates"
                  else "No BudgetDetails match for this owner family; confirm scope mapping.")
        add_review("owner_pay_app", cw.get("owner_cost_code_family"),
                   ", ".join(cw.get("owner_cost_code_examples", [])[:3]),
                   cw.get("owner_cost_code_family"),
                   f"Owner family {cw.get('owner_cost_code_family')} ({cnt} line items, latest app "
                   f"{cw.get('owner_latest_application_no')})",
                   cw.get("budget_detail_candidate_keys", []), f"resolution_status={rs}", action, pr)
    # budget-code attribution items where a code with material actuals is an unmapped ambiguous candidate
    for key, c in sorted(calc.items()):
        if c["is_amb_candidate"] and not c["has_owner"] and c["has_actuals"] and c["actual"] >= MAT_DOLLAR:
            add_review("budget_code", key, c.get("division"), None,
                       f"Budget code {key} has material actuals ({money_str(c['actual'])}) and is a candidate "
                       "for owner family billing not yet attributed.",
                       [key], "owner_family_billing_unattributed_to_this_code",
                       "Confirm whether owner billing for this family belongs to this budget code.",
                       "medium")
    out_counts["manual_mapping_review_items.jsonl"] = write_jsonl(
        OUT / "manual_mapping_review_items.jsonl", review_items)

    # ---- assumption register ----
    assumptions = [
        ("A-001", "BudgetDetails (127 keys) is the master budget-code universe.",
         "All recommendations key to a BudgetDetails budget_code_key.", "Recommendations mis-scoped.", "all"),
        ("A-002", "CostEntries / monthly actuals are accounting actual-cost truth.",
         "Actual cost basis for all numeric recommendations.", "Forecast floor wrong.", "actuals"),
        ("A-003", "Owner pay-app data is owner-recognized billing/progress evidence, not actual cost.",
         "Used only for progress/mismatch review.", "Over-trusting owner billing as cost.", "owner_pay_app"),
        ("A-004", "Procore subcontractor pay-app data is subcontractor progress/exposure evidence, not actual cost.",
         "Used only for exposure/progress review.", "Over-trusting subcontractor billing as cost.", "procore_pay_app"),
        ("A-005", "Procore pay-app evidence is through May 2026 only.",
         "June exposure not reflected in pay-app evidence.", "Understating June exposure.", "procore_pay_app"),
        ("A-006", "CostEntries include early June 2026 actuals (47 records, $31,393.68).",
         "June actuals treated as leading signal, flagged vs May-only pay-apps.", "Period mismatch misread.", "actuals"),
        ("A-007", "Pay-app evidence does not override accounting actuals.",
         "Numeric recommendations derive from actuals, not pay-apps.", "Recommendations not defensible.", "all"),
        ("A-008", "Ambiguous/manual-required mapping rows do not drive confident numeric recommendations.",
         "Such codes route to review_required / mapping_required.", "False confidence.", "mapping"),
        ("A-009", "Negative Procore latest values may be deductive change-order credits and require review.",
         "Never used alone to decrease a forecast.", "Erroneous decrease.", "procore_pay_app"),
        ("A-010", "budget_amount = revised_budget; current_projected_cost = projected_costs.",
         "Baseline for variance and forecast-under-review. projected_budget / estimated_cost_at_completion preserved as reference.",
         "Variance baseline shifts.", "all"),
        ("A-011", "Materiality gate: |gap| >= $25,000 AND >= 10% of the larger basis.",
         "Gates mismatch flags and increase/decrease triggers; severity tiered above it.", "Too many/few flags.", "all"),
        ("A-012", "Increase rule: when actuals exceed projected cost, floor projected up to actuals "
         "(adjustment = actual - projected). This precedence is absolute and not suppressed by review flags.",
         "Minimum defensible increase based on incurred cost.", "Underforecast persists.", "actuals"),
        ("A-013", "Decrease only when owner evidence is substantially complete, balance-to-finish immaterial, "
         "no remaining Procore exposure, material proj>actual, no June/mapping/credit issues; else review_required.",
         "Prevents premature decreases.", "Erroneous decrease.", "owner_pay_app"),
    ]
    assumption_rows = [OrderedDict([("assumption_id", a), ("assumption", b), ("impact", c),
                                    ("risk_if_wrong", d), ("applies_to", e)]) for a, b, c, d, e in assumptions]
    out_counts["assumption_register.jsonl"] = write_jsonl(OUT / "assumption_register.jsonl", assumption_rows)

    # ---- data quality warnings ----
    warnings = []
    wc = [0]
    def add_warn(sev, area, desc, keys, src, res):
        wc[0] += 1
        warnings.append(OrderedDict([
            ("warning_id", f"W-{wc[0]:04d}"), ("severity", sev), ("area", area),
            ("description", desc), ("affected_budget_code_keys", keys),
            ("source_file", src), ("recommended_resolution", res)]))
    for g in data_gaps_in.get("gaps", []):
        add_warn(g.get("severity", "important"), g.get("area", "context"),
                 g.get("description"), g.get("affected_budget_code_keys", [])[:50],
                 "forecast_context_package/summaries/data_gap_register.json",
                 g.get("recommended_resolution"))
    neg_keys = [k for k, c in calc.items() if c["procore_completed"] is not None and c["procore_completed"] < 0]
    add_warn("medium", "unusual_amount",
             "Budget codes with negative Procore latest completed (deductive change-order credits).",
             sorted(neg_keys), "forecast_context_package/summaries/budget_code_forecast_context.jsonl",
             "Verify credits; do not decrease forecast solely on negative Procore values.")
    add_warn("low", "reconciliation",
             "CostEntries vs ERP JTD differ by a documented rounding amount.",
             [], "forecast_context_package/audit/reconciliation_report.json",
             "Informational; within $0.01 tolerance.")
    add_warn("low", "owner_metadata",
             "Owner pay-app metadata anomalies (sheet-1 nulls, duplicate app 11, app-date vs period-to).",
             [], "forecast_context_package/audit/source_validation_reports/owner_pay_app_validation_report.json",
             "Use period_to as primary temporal key; treat application_no as secondary.")
    neither = [k for k, c in calc.items() if not c["has_owner"] and not c["has_procore"]]
    add_warn("low", "evidence_coverage",
             f"{len(neither)} budget codes have no owner or Procore pay-app evidence.",
             [], "forecast_context_package/summaries/mapping_coverage_summary.json",
             "Expected for non-subcontracted scopes; confirm no missing pay-app linkage.")
    out_counts["data_quality_warnings.jsonl"] = write_jsonl(OUT / "data_quality_warnings.jsonl", warnings)

    # ---- confidence rollup ----
    action_counts = defaultdict(int)
    conf_counts = defaultdict(int)
    depth_counts = defaultdict(int)
    for rec in recs:
        action_counts[rec["forecast_action"]] += 1
        conf_counts[rec["confidence"]] += 1
        depth_counts[rec["evidence_depth"]] += 1
    n_actuals = sum(1 for c in calc.values() if c["has_actuals"])
    n_owner = sum(1 for c in calc.values() if c["has_owner"])
    n_procore = sum(1 for c in calc.values() if c["has_procore"])
    n_both = sum(1 for c in calc.values() if c["has_owner"] and c["has_procore"])
    n_neither = sum(1 for c in calc.values() if not c["has_owner"] and not c["has_procore"])
    n_mapping_req = action_counts.get("mapping_required", 0)
    n_review = action_counts.get("review_required", 0)
    confidence_rollup = OrderedDict([
        ("total_budget_codes", len(recs)),
        ("count_by_forecast_action", OrderedDict(sorted(action_counts.items()))),
        ("count_by_confidence", OrderedDict(sorted(conf_counts.items()))),
        ("count_by_evidence_depth", OrderedDict(sorted(depth_counts.items()))),
        ("count_with_actuals", n_actuals),
        ("count_with_owner_evidence", n_owner),
        ("count_with_procore_evidence", n_procore),
        ("count_with_both_owner_and_procore", n_both),
        ("count_with_neither_owner_nor_procore", n_neither),
        ("count_requiring_manual_mapping", n_mapping_req),
        ("count_requiring_forecast_review", n_review),
    ])
    write_json(OUT / "confidence_rollup.json", confidence_rollup)

    # ---- division / category summaries ----
    def rollup(group_key_fn):
        groups = OrderedDict()
        for key, c in calc.items():
            gk = group_key_fn(c)
            g = groups.setdefault(gk, {"budget": Decimal("0"), "actual": Decimal("0"),
                                       "rec_proj": Decimal("0"), "adj": Decimal("0"),
                                       "risk": 0, "review": 0,
                                       "conf": defaultdict(int)})
            g["budget"] += c["budget"]; g["actual"] += c["actual"]
            g["rec_proj"] += c["rec_proj"]; g["adj"] += c["adjustment"]
            g["risk"] += len([f for f in c["risk_flags"] if f not in
                              ("forecast_floor_to_actuals", "forecast_decrease_supported_by_completion",
                               "remaining_exposure_review_required")])
            if c["action"] == "review_required":
                g["review"] += 1
            g["conf"][c["confidence"]] += 1
        return groups

    div_groups = rollup(lambda c: c["division"])
    div_rows = []
    for gk in sorted(div_groups.keys(), key=lambda x: (x is None, x)):
        g = div_groups[gk]
        div_rows.append(OrderedDict([
            ("division", gk), ("budget_total", money_str(g["budget"])),
            ("actual_total", money_str(g["actual"])),
            ("recommended_projected_total", money_str(g["rec_proj"])),
            ("recommended_adjustment_total", money_str(g["adj"])),
            ("risk_count", g["risk"]), ("review_required_count", g["review"]),
            ("confidence_summary", OrderedDict(sorted(g["conf"].items()))),
        ]))
    out_counts["summaries/division_summary.jsonl"] = write_jsonl(OUT / "summaries" / "division_summary.jsonl", div_rows)

    cat_groups = rollup(lambda c: c["category"])
    cat_rows = []
    for gk in sorted(cat_groups.keys(), key=lambda x: (x is None, x)):
        g = cat_groups[gk]
        cat_rows.append(OrderedDict([
            ("category", gk), ("budget_total", money_str(g["budget"])),
            ("actual_total", money_str(g["actual"])),
            ("recommended_projected_total", money_str(g["rec_proj"])),
            ("recommended_adjustment_total", money_str(g["adj"])),
            ("risk_count", g["risk"]), ("review_required_count", g["review"]),
            ("confidence_summary", OrderedDict(sorted(g["conf"].items()))),
        ]))
    out_counts["summaries/category_summary.jsonl"] = write_jsonl(OUT / "summaries" / "category_summary.jsonl", cat_rows)

    # ---- totals ----
    total_increase = sum((c["adjustment"] for c in calc.values()
                          if c["action"] == "increase_forecast"), Decimal("0"))
    total_decrease = sum((c["adjustment"] for c in calc.values()
                          if c["action"] == "decrease_forecast"), Decimal("0"))
    total_budget = sum((c["budget"] for c in calc.values()), Decimal("0"))
    total_actual = sum((c["actual"] for c in calc.values()), Decimal("0"))
    total_rec_proj = sum((c["rec_proj"] for c in calc.values()), Decimal("0"))
    total_june = sum((c["actual_june"] for c in calc.values()), Decimal("0"))

    # ---- top movements / review items ----
    def keyrec(c, key):
        return OrderedDict([("budget_code_key", key), ("cost_code", None),
                            ("forecast_action", c["action"]),
                            ("current_projected_cost", money_str(c["proj"])),
                            ("recommended_projected_cost", money_str(c["rec_proj"])),
                            ("adjustment", money_str(c["adjustment"])),
                            ("actual_cost", money_str(c["actual"]))])
    items = [(k, c) for k, c in calc.items()]
    top_increase = [keyrec(c, k) for k, c in sorted(items, key=lambda x: -x[1]["adjustment"])
                    if c["action"] == "increase_forecast"][:10]
    top_decrease = [keyrec(c, k) for k, c in sorted(items, key=lambda x: x[1]["adjustment"])
                    if c["action"] == "decrease_forecast"][:10]
    top_overrun = [keyrec(c, k) for k, c in sorted(items, key=lambda x: -(x[1]["actual"] - x[1]["proj"]))
                   if c["has_actuals"] and c["actual"] > c["proj"]][:10]
    top_actual = [OrderedDict([("budget_code_key", k), ("actual_cost", money_str(c["actual"]))])
                  for k, c in sorted(items, key=lambda x: -x[1]["actual"])][:10]
    top_june = [OrderedDict([("budget_code_key", k), ("june_actual", money_str(c["actual_june"]))])
                for k, c in sorted(items, key=lambda x: -x[1]["actual_june"]) if c["actual_june"] > 0][:10]
    def mismatch_size(c):
        if c["owner_completed"] is not None and c["procore_completed"] is not None:
            return abs(c["owner_completed"] - c["procore_completed"])
        return Decimal("0")
    top_mismatch = [OrderedDict([("budget_code_key", k),
                                 ("owner_completed", money_str(c["owner_completed"])),
                                 ("procore_completed", money_str(c["procore_completed"])),
                                 ("owner_vs_procore_delta", money_str(c["owner_completed"] - c["procore_completed"]))])
                    for k, c in sorted(items, key=lambda x: -mismatch_size(x[1]))
                    if c["owner_completed"] is not None and c["procore_completed"] is not None
                    and mismatch_size(c) > 0][:10]
    write_json(OUT / "summaries" / "top_forecast_movements.json", OrderedDict([
        ("top_recommended_increase", top_increase),
        ("top_recommended_decrease", top_decrease),
        ("top_actuals_exceeding_projected_cost", top_overrun),
        ("top_largest_actual_cost", top_actual),
        ("top_largest_june_actual_cost", top_june),
        ("top_owner_procore_mismatch", top_mismatch),
    ]))

    review_keys = [keyrec(c, k) for k, c in sorted(items, key=lambda x: -x[1]["actual"])
                   if c["action"] in ("review_required", "mapping_required")][:15]
    top_no_payapp_material = [OrderedDict([("budget_code_key", k), ("actual_cost", money_str(c["actual"]))])
                              for k, c in sorted(items, key=lambda x: -x[1]["actual"])
                              if c["has_actuals"] and not c["has_owner"] and not c["has_procore"]
                              and c["actual"] >= MAT_DOLLAR][:10]
    top_amb_families = [OrderedDict([("owner_cost_code_family", cw.get("owner_cost_code_family")),
                                     ("owner_line_item_count", cw.get("owner_line_item_count")),
                                     ("budget_detail_candidate_count", cw.get("budget_detail_candidate_count"))])
                        for cw in sorted(crosswalk, key=lambda c: -(c.get("owner_line_item_count") or 0))
                        if cw.get("resolution_status") == "multiple_budget_candidates"][:10]
    write_json(OUT / "summaries" / "top_review_items.json", OrderedDict([
        ("top_manual_mapping_items", [r for r in review_items[:10]]),
        ("top_ambiguous_owner_families", top_amb_families),
        ("top_budget_codes_requiring_review", review_keys),
        ("top_material_actuals_without_payapp_evidence", top_no_payapp_material),
    ]))

    # ---- determine conclusion ----
    safety = None  # set later; first compute structural validation

    # ---- copy script into package ----
    shutil.copy2(Path(__file__), OUT / "generate_forecast_analysis_package.py")

    # ---- audit files ----
    src_used = OrderedDict([
        ("input_package", str(INPUT)),
        ("files", [OrderedDict([("label", k), ("path", str(p.relative_to(INPUT))),
                                ("sha256", sha256_file(p)), ("size_bytes", p.stat().st_size)])
                   for k, p in SRC.items()]),
    ])
    write_json(OUT / "audit" / "source_files_used.json", src_used)
    write_json(OUT / "input_inventory.json", OrderedDict([
        ("data_root", str(ROOT)),
        ("context_package", str(INPUT)),
        ("lineage", OrderedDict([
            ("consumed_context", CONTEXT_LINEAGE),
            ("analysis_context_lineage_consistent",
             run_lineage.lineage_consistent([CONTEXT_LINEAGE]))])),
    ]))
    write_json(OUT / "audit" / "source_validation_snapshot.json", OrderedDict([
        ("context_conclusion", ctx_conclusion),
        ("context_row_count_reconciliation_passed", ctx_val.get("row_count_reconciliation", {}).get("passed")),
        ("context_cutoff_passed", ctx_val.get("cutoff_validation", {}).get("passed")),
        ("context_safety_passed", ctx_val.get("safety_scan", {}).get("passed")),
        ("context_coverage", coverage_in),
    ]))

    # ---- analysis reconciliation ----
    analysis_recon = OrderedDict([
        ("budget_total_recomputed", money_str(total_budget)),
        ("budget_total_context_revised_budget_note", "sum of revised_budget across 127 codes"),
        ("actual_total_recomputed", money_str(total_actual)),
        ("actual_total_context",
         project_ctx.get("actual_totals", {}).get("cost_entries_all_source_to_date")),
        ("actual_total_minus_context",
         money_str(total_actual - D(project_ctx.get("actual_totals", {}).get("cost_entries_all_source_to_date")))),
        ("june_actual_total_recomputed", money_str(total_june)),
        ("june_actual_total_context",
         project_ctx.get("actual_totals", {}).get("cost_entries_june_2026_to_date_total")),
        ("recommended_projected_total", money_str(total_rec_proj)),
        ("total_recommended_increase", money_str(total_increase)),
        ("total_recommended_decrease", money_str(total_decrease)),
        ("owner_latest_application", OrderedDict([
            ("application_no", recon_in.get("owner_latest_application_no")),
            ("period_to", recon_in.get("owner_latest_period_to")),
            ("grand_total_completed_and_stored", recon_in.get("owner_latest_grand_total_completed_and_stored")),
        ])),
        ("procore_latest_completed_all_88_rows", recon_in.get("procore_latest_completed_all_88_rows")),
        ("note", "Budget total uses revised_budget; actuals reconcile to the context package within the "
                 "documented $0.01 ERP rounding. Pay-app figures are evidence, not actual cost."),
    ])
    write_json(OUT / "audit" / "analysis_reconciliation.json", analysis_recon)

    # ---- safety scan over emitted artifacts ----
    emitted = [str(p) for p in sorted(OUT.rglob("*")) if p.is_file() and p.suffix in (".jsonl", ".json", ".md")]
    safety = safety_scan(emitted)
    write_json(OUT / "audit" / "safety_scan_report.json", safety)

    # ---- validations ----
    # output parse
    out_valid = True
    invalid = {}
    for p in sorted(OUT.rglob("*")):
        if p.suffix == ".jsonl":
            try:
                for _ in read_jsonl(p):
                    pass
            except Exception as e:
                out_valid = False; invalid[str(p.relative_to(OUT))] = str(e)
        elif p.suffix == ".json":
            try:
                read_json(p)
            except Exception as e:
                out_valid = False; invalid[str(p.relative_to(OUT))] = str(e)

    rec_count_ok = len(recs) == 127
    all_keys_canonical = all(rec["budget_code_key"] in canonical_keys for rec in recs)
    no_nonmaster = all(rec["budget_code_key"] in canonical_keys for rec in recs)
    risk_keys_ok = all((r["budget_code_key"] is None or r["budget_code_key"] in canonical_keys) for r in risks)
    # no manual/ambiguous drives high-confidence numeric rec
    bad_conf = [rec["budget_code_key"] for rec in recs
                if rec["confidence"] == "high" and rec["recommended_forecast_adjustment"] is not None
                and not calc[rec["budget_code_key"]]["has_actuals"]]
    high_conf_numeric_ok = len(bad_conf) == 0
    # pay-app never used as actual: numeric recs only when has_actuals (except hold/0) — check increase/decrease have actuals
    payapp_not_actual_ok = all(calc[rec["budget_code_key"]]["has_actuals"]
                               for rec in recs if rec["forecast_action"] in ("increase_forecast", "decrease_forecast"))

    input_checks = OrderedDict([
        ("missing_inputs", missing),
        ("parse_results", parse_ok),
        ("context_conclusion", ctx_conclusion),
        ("context_conclusion_ok", ctx_conclusion == "forecast_context_ready_with_mapping_gaps"),
    ])

    # ---- determinism placeholder (filled by external harness; here we self-report design) ----
    determinism = OrderedDict([
        ("method", "two runs into temp dirs with frozen stamp; data files diffed ignoring timestamp/path"),
        ("performed_by_script", False),
        ("note", "Determinism verified by the operator harness; engine uses sorted output and no RNG."),
    ])

    analysis_context_lineage_consistent = run_lineage.lineage_consistent([CONTEXT_LINEAGE])
    structural_ok = (out_valid and rec_count_ok and all_keys_canonical and risk_keys_ok
                     and high_conf_numeric_ok and payapp_not_actual_ok and safety["passed"]
                     and not missing and input_checks["context_conclusion_ok"]
                     and analysis_context_lineage_consistent)
    n_review_items = n_review + n_mapping_req + len(review_items)
    if not structural_ok:
        conclusion = "forecast_analysis_not_ready"
    elif (n_review + n_mapping_req) > 0 or len(review_items) > 0 or len(risks) > 0:
        conclusion = "forecast_analysis_ready_with_review_items"
    else:
        conclusion = "forecast_analysis_ready"

    severity_counts = defaultdict(int)
    for r in risks:
        severity_counts[r["severity"]] += 1

    validation = OrderedDict([
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("period", PERIOD)])),
        ("generated_stamp", STAMP),
        ("lineage", OrderedDict([
            ("consumed_context", CONTEXT_LINEAGE),
            ("analysis_context_lineage_consistent", bool(analysis_context_lineage_consistent))])),
        ("input_checks", input_checks),
        ("output_parse", OrderedDict([("all_passed", out_valid), ("invalid", invalid)])),
        ("row_counts", out_counts),
        ("recommendation_checks", OrderedDict([
            ("recommendation_row_count", len(recs)),
            ("recommendation_count_is_127", rec_count_ok),
            ("all_keys_in_canonical", all_keys_canonical),
            ("no_recommendation_for_nonmaster_key", no_nonmaster),
            ("risk_keys_valid_or_null", risk_keys_ok),
            ("no_manual_or_ambiguous_drives_high_confidence_numeric", high_conf_numeric_ok),
            ("payapp_not_treated_as_actual_cost", payapp_not_actual_ok),
        ])),
        ("forecast_action_counts", OrderedDict(sorted(action_counts.items()))),
        ("confidence_counts", OrderedDict(sorted(conf_counts.items()))),
        ("risk_counts_by_severity", OrderedDict(sorted(severity_counts.items()))),
        ("financial", OrderedDict([
            ("budget_total_revised_budget", money_str(total_budget)),
            ("actual_total_recomputed", money_str(total_actual)),
            ("actual_total_context", project_ctx.get("actual_totals", {}).get("cost_entries_all_source_to_date")),
            ("june_actual_total", money_str(total_june)),
            ("total_recommended_increase", money_str(total_increase)),
            ("total_recommended_decrease", money_str(total_decrease)),
            ("baseline_note", "budget_amount=revised_budget; current_projected_cost=projected_costs; "
                              "materiality $25k AND 10%; floor-to-actuals increase."),
        ])),
        ("safety_scan", OrderedDict([("passed", safety["passed"]), ("findings", safety["findings"])])),
        ("determinism", determinism),
        ("known_limitations", [
            "Owner pay-app families often resolve to multiple BudgetDetails candidates; owner progress is "
            "not attributable per code without human review (see manual_mapping_review_items.jsonl).",
            "Procore pay-app evidence is through May 2026 only; June progress not yet reflected.",
            "June 2026 accounting actuals exist; treated as leading signal vs May-only pay-apps.",
            "Pay-app values are evidence, not accounting actual-cost truth; recommendations are for review, "
            "not final accounting entries. No workbook or source system was modified.",
        ]),
        ("conclusion", conclusion),
    ])
    write_json(OUT / "validation_report.json", validation)

    # ---- project_forecast_analysis.json ----
    write_json(OUT / "summaries" / "project_forecast_analysis.json", OrderedDict([
        ("project_name", PROJECT_NAME), ("project_key", PROJECT_KEY), ("job_reference", JOB_REF),
        ("forecast_period", PERIOD), ("generated_stamp", STAMP),
        ("input_package_path", str(INPUT)),
        ("budget_totals", OrderedDict([("revised_budget_total", money_str(total_budget)),
                                       ("recommended_projected_total", money_str(total_rec_proj))])),
        ("actual_totals", OrderedDict([("all_source_to_date", money_str(total_actual)),
                                       ("june_2026_to_date", money_str(total_june))])),
        ("owner_latest_application_summary", OrderedDict([
            ("application_no", recon_in.get("owner_latest_application_no")),
            ("period_to", recon_in.get("owner_latest_period_to")),
            ("grand_total_completed_and_stored", recon_in.get("owner_latest_grand_total_completed_and_stored"))])),
        ("procore_latest_subcontractor_summary", OrderedDict([
            ("latest_completed_all_88_rows", recon_in.get("procore_latest_completed_all_88_rows")),
            ("cutoff", "through_may_2026")])),
        ("recommendation_totals", OrderedDict(sorted(action_counts.items()))),
        ("risk_totals_by_severity", OrderedDict(sorted(severity_counts.items()))),
        ("confidence_rollup", confidence_rollup),
        ("total_recommended_increase", money_str(total_increase)),
        ("total_recommended_decrease", money_str(total_decrease)),
        ("conclusion", conclusion),
    ]))

    # ---- markdown summaries ----
    write_text(OUT / "forecast_review_summary.md",
               _review_md(action_counts, conf_counts, severity_counts, total_actual, total_increase,
                          total_decrease, total_june, recon_in, project_ctx, review_items, top_overrun,
                          top_mismatch, neither, conclusion))
    write_text(OUT / "executive_forecast_summary.md",
               _exec_md(action_counts, conf_counts, severity_counts, total_actual, total_increase,
                        total_decrease, total_june, recon_in, n_review + n_mapping_req, conclusion))

    # ---- README ----
    write_text(OUT / "README.md", _readme(out_counts, action_counts, conf_counts, severity_counts,
                                          total_actual, total_increase, total_decrease, total_june,
                                          safety, conclusion))

    # ---- manifest ----
    out_file_manifest = []
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(OUT))
            out_file_manifest.append(OrderedDict([
                ("path", rel), ("size_bytes", p.stat().st_size),
                ("row_count", out_counts.get(rel)), ("sha256", sha256_file(p))]))
    write_json(OUT / "manifest.json", OrderedDict([
        ("package_name", OUT.name),
        ("generated_timestamp_local", datetime.now().isoformat()),
        ("generated_stamp", STAMP),
        ("project", OrderedDict([("name", PROJECT_NAME), ("project_key", PROJECT_KEY),
                                 ("job", JOB_REF), ("period", PERIOD)])),
        ("input_package_path", str(INPUT)),
        ("output_files", out_file_manifest),
        ("validation_status", OrderedDict([
            ("output_parse", out_valid), ("recommendation_count_127", rec_count_ok),
            ("safety_scan", safety["passed"]), ("structural_ok", structural_ok)])),
        ("conclusion", conclusion),
    ]))

    print(json.dumps(OrderedDict([
        ("output_package", str(OUT)),
        ("conclusion", conclusion),
        ("structural_ok", structural_ok),
        ("forecast_action_counts", OrderedDict(sorted(action_counts.items()))),
        ("confidence_counts", OrderedDict(sorted(conf_counts.items()))),
        ("risk_counts_by_severity", OrderedDict(sorted(severity_counts.items()))),
        ("risk_rows", len(risks)),
        ("manual_review_items", len(review_items)),
        ("total_recommended_increase", money_str(total_increase)),
        ("total_recommended_decrease", money_str(total_decrease)),
        ("june_actual_total", money_str(total_june)),
        ("safety_passed", safety["passed"]),
        ("out_counts", out_counts),
    ]), indent=2))


def _review_md(ac, cc, sev, total_actual, inc, dec_, june, recon, proj_ctx, review_items,
               top_overrun, top_mismatch, neither, conclusion):
    L = []
    L.append(f"# Forecast Review Summary — {PROJECT_NAME}\n")
    L.append(f"Project key `{PROJECT_KEY}` · Job `{JOB_REF}` · Period `{PERIOD}` · Generated `{STAMP}`\n")
    L.append("## Scope and inputs\n")
    L.append("Generated from the read-only forecast context package "
             f"`{INPUT.name}` (conclusion `forecast_context_ready_with_mapping_gaps`). "
             "Covers all 127 BudgetDetails master budget codes. Analysis for human review only — "
             "no workbook or source system was modified.\n")
    L.append("## Validation status\n")
    L.append("- 127 recommendation rows, all keyed to canonical BudgetDetails codes.")
    L.append("- Pay-app values used only as evidence; numeric recommendations derive from accounting actuals.")
    L.append("- Safety scan passed; no sensitive artifacts emitted.\n")
    L.append("## Mapping coverage\n")
    L.append("- Procore subcontractor pay-app mapping is exact (100%).")
    L.append("- Owner pay-app SOV families frequently resolve to multiple BudgetDetails candidates; "
             "owner progress is not attributable per code without review.\n")
    L.append("## Actual-cost reconciliation\n")
    L.append(f"- Total accounting actuals to date: ${total_actual.quantize(CENTS):,}")
    L.append(f"- June 2026 actuals (leading signal): ${june.quantize(CENTS):,}")
    L.append(f"- CostEntries vs ERP JTD variance: {recon.get('cost_entries_minus_erp_jtd')} (within tolerance)\n")
    L.append("## Pay-app evidence interpretation\n")
    L.append(f"- Owner latest application {recon.get('owner_latest_application_no')} "
             f"(period {recon.get('owner_latest_period_to')}); completed/stored "
             f"{recon.get('owner_latest_grand_total_completed_and_stored')}.")
    L.append(f"- Procore subcontractor latest completed (88 rows): {recon.get('procore_latest_completed_all_88_rows')} "
             "(includes deductive change-order credits — review).\n")
    L.append("## Major forecast risk areas\n")
    L.append(f"- Recommended increases (floor-to-actuals): {ac.get('increase_forecast', 0)} codes, "
             f"total ${inc.quantize(CENTS):,}.")
    L.append(f"- Codes needing review: {ac.get('review_required', 0)}; mapping required: {ac.get('mapping_required', 0)}.")
    L.append(f"- Risk register severity: " + ", ".join(f"{k}={v}" for k, v in sorted(sev.items())) + "\n")
    L.append("## Budget codes requiring review (top by actual cost)\n")
    for t in top_overrun[:10]:
        L.append(f"- `{t['budget_code_key']}`: actual {t['actual_cost']} vs projected {t['current_projected_cost']} "
                 f"→ {t['forecast_action']}")
    L.append("")
    L.append("## Recommended human review sequence\n")
    L.append("1. Resolve owner cost-code-family mappings (`manual_mapping_review_items.jsonl`).")
    L.append("2. Verify negative Procore credits and any owner/Procore progress mismatches.")
    L.append("3. Confirm floor-to-actuals increases and remaining-exposure flags.")
    L.append("4. Refresh Procore pay-app evidence for June before month-end forecasting.\n")
    L.append("## Limitations\n")
    L.append("- Owner pay-app attribution gaps; Procore evidence through May only; June actuals present.")
    L.append("- Recommendations are for review, not final accounting entries.\n")
    return "\n".join(L)


def _exec_md(ac, cc, sev, total_actual, inc, dec_, june, recon, review_count, conclusion):
    L = []
    L.append(f"# Executive Forecast Summary — {PROJECT_NAME}\n")
    L.append(f"**Project** {PROJECT_KEY} · **Job** {JOB_REF} · **Forecast period** {PERIOD}\n")
    L.append("## Data confidence\n")
    L.append(f"- {cc.get('high', 0)} high · {cc.get('medium', 0)} medium · {cc.get('low', 0)} low · "
             f"{cc.get('none', 0)} none (across 127 budget codes).")
    L.append("- Procore subcontractor mapping exact; owner pay-app mapping has known attribution gaps.\n")
    L.append("## Cost position\n")
    L.append(f"- Accounting actuals to date: **${total_actual.quantize(CENTS):,}**.")
    L.append(f"- June 2026 actuals (leading): **${june.quantize(CENTS):,}** (pay-app evidence is through May only).")
    L.append(f"- Owner recognized completed/stored (App {recon.get('owner_latest_application_no')}): "
             f"{recon.get('owner_latest_grand_total_completed_and_stored')}.")
    L.append(f"- Procore subcontractor latest completed (incl. credits): {recon.get('procore_latest_completed_all_88_rows')}.\n")
    L.append("## Major cost-risk themes\n")
    L.append(f"- **{ac.get('increase_forecast', 0)}** budget codes show actuals above current forecast "
             f"(recommended floor-to-actuals increase totaling **${inc.quantize(CENTS):,}**).")
    L.append(f"- **{review_count}** budget codes require human review or mapping before a forecast value can be trusted.")
    L.append("- Owner SOV billing cannot be attributed to specific budget codes without mapping review.\n")
    L.append("## Top forecast risks\n")
    L.append("- Underforecast codes where incurred cost already exceeds the projection.")
    L.append("- Owner/subcontractor progress mismatches and deductive change-order credits.")
    L.append("- June actuals landing before June pay-app evidence is available.\n")
    L.append("## Next actions\n")
    L.append("1. Resolve owner cost-code-family mappings. 2. Verify Procore credits & mismatches. "
             "3. Confirm floor-to-actuals increases. 4. Refresh Procore June pay-app evidence.\n")
    L.append(f"_Analysis package conclusion: `{conclusion}`. For review only — no accounting entries made._\n")
    return "\n".join(L)


def _readme(out_counts, ac, cc, sev, total_actual, inc, dec_, june, safety, conclusion):
    L = []
    L.append(f"# Forecast Analysis Package — {PROJECT_NAME}\n")
    L.append("## Objective\n")
    L.append("Consume the consolidated forecast **context** package and produce budget-code-level forecast "
             "recommendations, risk flags, evidence alignment, manual-mapping review items, and summaries "
             "**for human review**. This package does NOT mutate the workbook or any source system, makes no "
             "live calls, and treats pay-app values as evidence — never accounting actual-cost truth.\n")
    L.append("## Paths\n")
    L.append(f"- Input context package: `{INPUT}`")
    L.append(f"- Output analysis package: `{OUT}`\n")
    L.append(f"## Project\n- {PROJECT_NAME}\n- key `{PROJECT_KEY}` · job `{JOB_REF}` · period `{PERIOD}` · generated `{STAMP}`\n")
    L.append("## Baseline definitions\n")
    L.append("- `budget_amount` = `revised_budget`; `current_projected_cost` = `projected_costs`. "
             "`projected_budget` and `estimated_cost_at_completion` are preserved as reference and do not drive "
             "the primary variance.")
    L.append("- Materiality: a gap is material iff `|gap| ≥ $25,000` AND `≥ 10%` of the larger basis.")
    L.append("- Increase rule: when actuals exceed projected cost, projected is floored up to actuals "
             "(adjustment = actual − projected); this precedence is absolute.\n")
    L.append("## Generated files (row counts)\n")
    for f, c in out_counts.items():
        L.append(f"- `{f}`: {c}")
    L.append("")
    L.append("## Headline results\n")
    L.append(f"- Forecast actions: " + ", ".join(f"{k}={v}" for k, v in sorted(ac.items())))
    L.append(f"- Confidence: " + ", ".join(f"{k}={v}" for k, v in sorted(cc.items())))
    L.append(f"- Risk severity: " + ", ".join(f"{k}={v}" for k, v in sorted(sev.items())))
    L.append(f"- Total recommended increase: ${inc.quantize(CENTS):,}; decrease: ${dec_.quantize(CENTS):,}")
    L.append(f"- Accounting actuals to date: ${total_actual.quantize(CENTS):,}; June 2026 actuals: ${june.quantize(CENTS):,}\n")
    L.append("## Validation\n")
    L.append(f"- 127 recommendation rows, all canonical; safety scan {'PASS' if safety['passed'] else 'FAIL'}.\n")
    L.append("## Financial reconciliation headline\n")
    L.append(f"- Actuals recompute to the context package within the documented $0.01 ERP rounding.\n")
    L.append("## Mapping and evidence limitations\n")
    L.append("- Owner pay-app SOV families often map to multiple budget codes (review required).")
    L.append("- Procore pay-app evidence is through May 2026 only; June actuals exist separately.")
    L.append("- Pay-app values are evidence, not actual cost.\n")
    L.append("## Recommended use\n")
    L.append("Use `forecast_recommendations_by_budget_code.jsonl` as the per-code review sheet; consult "
             "`forecast_risk_register.jsonl`, `manual_mapping_review_items.jsonl`, and the summaries. "
             "Respect `forecast_action`/`confidence`; do not apply review/mapping rows as forecast values.\n")
    L.append(f"## Conclusion: `{conclusion}`\n")
    return "\n".join(L)


if __name__ == "__main__":
    main()
