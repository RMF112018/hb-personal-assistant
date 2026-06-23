"""Generate the comprehensive integrated forecast package for Tropical World Nursery.

Discovers + consumes the accepted evidence packages (context, intelligence, monthly, probability,
history-informed, cost-frequency; crosswalk-v2 + schedule-integrated for completeness), normalizes them
into a per-code evidence registry, scores advisory evidence within bounded, de-duplicated weights, and
emits integrated final-cost / monthly / probability recommendations with full lineage, an evidence
conflict register, and a human-acceptance review queue. Never re-runs the heavy generators; never mutates
any package. Deterministic (frozen stamp); probability is a deterministic transform of the accepted
distribution (no fresh Monte Carlo). CostEntries are truth; actual cost to date is the only floor; no cap.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-comprehensive --project tropical \
        [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR] [--with-llm]
"""
from __future__ import annotations

import tempfile
from collections import Counter, OrderedDict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from ..common import lineage
from ..common.hashing import sha256_file
from ..common.io import read_json, read_jsonl, write_csv, write_json, write_jsonl
from ..common.money import D, money_str
from ..common.safety import safety_scan
from ..forecast_actuals import actuals_export
from ..forecast_cost_basis import apply as cost_basis_apply
from ..forecast_cost_basis import validation as cost_basis_validation
from ..forecast_staffing_basis import apply as staffing_basis_apply
from ..forecast_staffing_basis import validation as staffing_basis_validation
from ..forecast_controls import integration as fctl_integration
from ..forecast_model_controls import integration as fmc_integration
from ..forecast_intelligence import db_inventory
from ..schedule_analysis.schedule_mapping import build_canonical_index
from . import (
    conflicts,
    evidence_registry,
    final_package,
    intelligence_consumer,
    monthly_consumer,
    package_discovery,
    probability_consumer,
)
from . import evidence_scoring as scoring
from . import human_acceptance as ha
from . import validation as fc_validation

SUBPROJECT_ROOT = Path(__file__).resolve().parents[3]
ZERO = Decimal("0")
CENTS = Decimal("0.01")

DATA_FILES = (
    "integrated_forecast_by_budget_code.jsonl",
    "integrated_evidence_registry_by_budget_code.jsonl",
    "integrated_evidence_weights_by_budget_code.jsonl",
    "integrated_final_cost_recommendations.jsonl",
    "integrated_monthly_forecast_by_budget_code.jsonl",
    "integrated_monthly_project_forecast.jsonl",
    "integrated_probability_by_budget_code.jsonl",
    "integrated_probability_project_summary.json",
    "integrated_risk_register.jsonl",
    "integrated_human_review_queue.jsonl",
    "integrated_change_explanation.jsonl",
    "evidence_conflict_register.jsonl",
    "model_package_inventory.json",
    "project_comprehensive_forecast_summary.json",
    "top_overrun_risks.json",
    "top_confidence_improvements.json",
    "top_evidence_conflicts.json",
    "top_human_review_items.json",
    "data_quality_warnings.jsonl",
) + actuals_export.ACTUALS_DATA_FILES + actuals_export.ACTUALS_PLUS_FORECAST_DATA_FILES
AUDIT_DATA_FILES = (
    actuals_export.ACTUALS_AUDIT_FILE,
    actuals_export.ACTUALS_PLUS_FORECAST_AUDIT_FILE,
    "audit/evidence_registry_audit.json",
    "audit/evidence_weighting_audit.json",
    "audit/history_consumption_audit.json",
    "audit/frequency_consumption_audit.json",
    "audit/monthly_reconciliation_audit.json",
    "audit/probability_adjustment_audit.json",
    "audit/no_upper_cap_audit.json",
    "audit/actuals_floor_audit.json",
    "audit/model_evidence_completeness_matrix.json",
    "audit/forecast_cost_basis_decision_audit.json",
    "audit/forecast_staffing_basis_decision_audit.json",
    "audit/forecast_run_lineage_audit.json",
)

# stages whose consumed-context stamp must match the comprehensive context for a consistent fresh run
_LINEAGE_PTYPES = ("context", "intelligence", "staffing_plan", "monthly", "cost_frequency", "probability")


def _run_lineage_audit(project_key, discovery, own_lineage) -> "OrderedDict":
    """Compare the consumed context stamp across every present upstream package vs the comprehensive
    context. A genuine inconsistency (a package recorded a DIFFERENT context stamp) always fails. Missing
    lineage metadata fails closed only under a pinned fresh run (strict); on legacy/ad-hoc runs it is
    reported but does not by itself fail the gate (the inconsistency check is still authoritative).
    Absent/not-required packages are not_applicable."""
    own_stamp = (own_lineage or {}).get("consumed_context_stamp")
    strict = (own_lineage or {}).get("lineage_source") == "pinned"
    rows, inconsistent, missing_meta = [], False, False
    for pt in _LINEAGE_PTYPES:
        d = discovery.get(pt) or {}
        if not d.get("present"):
            rows.append(OrderedDict([("package_type", pt), ("present", False),
                                     ("consumed_context_stamp", None), ("status", "not_applicable")]))
            continue
        path = Path(d["path"])
        if pt == "context":
            consumed, has_meta = lineage._stamp_of(path), True
        else:
            ii_path = path / "input_inventory.json"
            ii = read_json(ii_path) if ii_path.exists() else None
            cl = (ii or {}).get("context_lineage") or {}
            consumed = cl.get("consumed_context_stamp")
            has_meta = bool(ii is not None and (ii or {}).get("context_lineage") is not None)
        if not has_meta:
            status, missing_meta = "missing_context_lineage_metadata", True
        elif consumed == own_stamp:
            status = "consistent"
        else:
            status, inconsistent = "inconsistent", True
        rows.append(OrderedDict([("package_type", pt), ("present", True),
                                 ("consumed_context_stamp", consumed), ("status", status)]))
    consistent = (not inconsistent) and (not (strict and missing_meta))
    return OrderedDict([
        ("project_key", project_key),
        ("comprehensive_context_stamp", own_stamp),
        ("strict_lineage_enforced", bool(strict)),
        ("full_run_lineage_consistent", bool(consistent)),
        ("missing_context_lineage_metadata", bool(missing_meta)),
        ("packages", rows),
    ])


# --------------------------------------------------------------------------- pure deterministic build

def _build_collections(inputs: dict, project_key: str) -> dict:
    cfg_fc = (inputs.get("_cfg") or {}).get("forecast_comprehensive") or {}
    canonical = inputs["canonical_keys"]
    per_code = inputs["per_code"]
    items = inputs["evidence_items"]
    discovery = inputs["discovery"]
    seed = cfg_fc.get("deterministic_seed")

    weights_rows, forecast_rows, final_recs = [], [], []
    monthly_rows, probability_rows, conflict_rows = [], [], []
    floor_audits, monthly_audits, review_rows, change_rows, risk_rows, warnings = [], [], [], [], [], []
    cost_basis_rows = []
    staffing_basis_rows = []
    staffing_basis_applied_keys = set()
    monthly_total_by_key = {}
    project_months = OrderedDict()
    totals = {"accepted_final": ZERO, "integrated_final": ZERO, "integrated_ctc": ZERO, "actual": ZERO}
    prob_dir_counts = Counter()

    for key in sorted(canonical):
        entry = per_code[key]
        sc = scoring.score_code(entry, cfg_fc)
        weights_rows.append(scoring.weights_row(project_key, key, entry, sc))

        (f_row, rec_row, floor_audit, integ_final, integ_ctc, cb_decision,
         sb_decision) = intelligence_consumer.build(project_key, key, entry, sc)
        entry["cost_basis"] = cb_decision   # downstream consumers (probability) read the selected basis
        entry["staffing_basis"] = sb_decision
        if sb_decision.get("staffing_basis_applied"):
            staffing_basis_applied_keys.add(key)
        forecast_rows.append(f_row)
        final_recs.append(rec_row)
        floor_audits.append(floor_audit)
        totals["accepted_final"] += D(f_row["accepted_recommended_final_cost"])
        totals["integrated_final"] += integ_final
        totals["integrated_ctc"] += integ_ctc
        totals["actual"] += D(f_row["actual_cost_to_date"])

        m_row, m_months, m_audit = monthly_consumer.build(project_key, key, entry, sc, integ_ctc)
        if m_row:
            # disclose the staffing basis on the monthly row (timing logic unchanged; when the basis is
            # applied the monthly sum already reconciles to the staffing-plan CTC via integ_ctc)
            m_row["staffing_basis_status"] = sb_decision.get("staffing_basis_status")
            monthly_rows.append(m_row)
            monthly_audits.append(m_audit)
            for mo, c in m_months.items():
                project_months[mo] = project_months.get(mo, ZERO) + c
            monthly_total_by_key[key] = sum(m_months.values(), ZERO)
        cost_basis_rows.append(cost_basis_apply.build_cost_basis_audit_row(
            cb_decision, monthly_total_after_basis=monthly_total_by_key.get(key)))
        staffing_basis_rows.append(staffing_basis_apply.build_staffing_basis_audit_row(
            sb_decision, monthly_total_after_staffing_basis=monthly_total_by_key.get(key)))

        p_row, p_contrib = probability_consumer.build(project_key, key, entry, sc, cfg_fc)
        if p_row:
            probability_rows.append(p_row)
            prob_dir_counts[p_row["integrated_uncertainty_direction"]] += 1

        code_conflicts = conflicts.build(project_key, key, entry, sc, integ_final)
        conflict_rows.extend(code_conflicts)

        delta = integ_final - D(f_row["accepted_recommended_final_cost"])
        if delta.copy_abs() > CENTS:
            change_rows.append(OrderedDict([
                ("project_key", project_key), ("budget_code_key", key),
                ("cost_code", f_row["cost_code"]),
                ("accepted_recommended_final_cost", f_row["accepted_recommended_final_cost"]),
                ("integrated_recommended_final_cost", f_row["integrated_recommended_final_cost"]),
                ("change_amount", money_str(delta)),
                ("history_final_cost_weight", f_row["history_final_cost_weight"]),
                ("reason_codes", sc["reason_codes"]),
            ]))
        high_conf = [c for c in code_conflicts if c["severity"] == "high"]
        if delta.copy_abs() > CENTS or high_conf or sc["contradicted"]:
            priority = "high" if (high_conf or sc["contradicted"]) else "medium"
            review_rows.append(ha.review_item(
                project_key, key, f_row["cost_code"], priority,
                "integrated final-cost change or high-severity conflict or actuals contradict history",
                [c["conflict_class"] for c in code_conflicts]))
            risk_rows.append(ha.stamp(OrderedDict([
                ("project_key", project_key), ("budget_code_key", key), ("cost_code", f_row["cost_code"]),
                ("integrated_recommended_final_cost", f_row["integrated_recommended_final_cost"]),
                ("integrated_minus_accepted_final_cost", money_str(delta)),
                ("conflict_count", len(code_conflicts)),
                ("max_conflict_severity", "high" if high_conf else (
                    "medium" if any(c["severity"] == "medium" for c in code_conflicts) else "low")),
                ("review_priority", priority),
            ])))

    # operator staffing-plan conflicts for unmapped / non-canonical cost codes (per-code ones are
    # already emitted via conflicts.build); surface them in the integrated register too.
    canon_set = set(canonical)
    for c in inputs.get("staffing_plan_conflicts") or []:
        k = c.get("budget_code_key")
        if k is None or k not in canon_set:
            conflict_rows.append(c)

    # ---- project monthly rollup + reconciliation ----
    proj_months = sorted(project_months.keys())
    project_monthly = [OrderedDict([
        ("project_key", project_key), ("forecast_month", m),
        ("integrated_month_cost", money_str(project_months[m]))]) for m in proj_months]
    project_month_total = sum(project_months.values(), ZERO)
    per_code_recon = all(a["reconciled"] for a in monthly_audits)
    project_recon = abs(project_month_total - totals["integrated_ctc"]) <= CENTS * (len(monthly_audits) or 1)

    # ---- audits ----
    floor_all = all(a["floor_respected"] for a in floor_audits)
    cap_rows_ok = all(r["upper_cap_applied"] is False for r in forecast_rows) and \
        all(r["upper_cap_applied"] is False for r in probability_rows)
    hist_status_counts = Counter(r["history_consumption_status"] for r in forecast_rows)
    freq_status_counts = Counter(r["frequency_consumption_status"] for r in forecast_rows)

    audits = {
        "audit/evidence_registry_audit.json": OrderedDict([
            ("project_key", project_key), ("evidence_item_count", len(items)),
            ("by_evidence_family", dict(Counter(i["evidence_family"] for i in items))),
            ("by_source_package_type", dict(Counter(i["source_package_type"] for i in items))),
            ("lineage_complete", all(i.get("source_package_type") and i.get("source_row_id") for i in items))]),
        "audit/evidence_weighting_audit.json": OrderedDict([
            ("project_key", project_key),
            ("independence_groups", ["actuals_truth", "cost_entry_trend", "budget_reference",
                                     "pay_application", "schedule", "base_model", "history",
                                     "frequency", "operator_control", "staffing_plan", "narrative"]),
            ("no_double_count_rule", "evidence in the same independence_group counts once; the same "
             "CostEntries trend surfacing in context/intelligence/monthly/history is not weighted 4x"),
            ("bounds", OrderedDict([
                ("max_history_final_cost_weight", cfg_fc.get("max_history_final_cost_weight")),
                ("max_history_monthly_shape_weight", cfg_fc.get("max_history_monthly_shape_weight")),
                ("max_history_probability_weight", cfg_fc.get("max_history_probability_weight")),
                ("max_frequency_monthly_shape_weight", cfg_fc.get("max_frequency_monthly_shape_weight"))])),
            ("frequency_final_cost_weight", "0.0000 (cadence shapes timing only)")]),
        "audit/history_consumption_audit.json": OrderedDict([
            ("project_key", project_key), ("status_counts", dict(hist_status_counts)),
            ("every_code_consumed_or_downgraded",
             all(s in ("consumed", "downgraded", "missing") for s in hist_status_counts))]),
        "audit/frequency_consumption_audit.json": OrderedDict([
            ("project_key", project_key), ("disposition", inputs["frequency_disposition"]),
            ("disposition_reason", inputs["frequency_reason"]),
            ("status_counts", dict(freq_status_counts)),
            ("cadence_affects_final_cost", False),
            ("note", "cost-frequency shapes monthly timing + timing-risk only; zero final-cost weight")]),
        "audit/monthly_reconciliation_audit.json": OrderedDict([
            ("project_key", project_key),
            ("per_code_all_reconciled", bool(per_code_recon)),
            ("per_code_count", len(monthly_audits)),
            ("project_total_reconciled", bool(project_recon)),
            ("integrated_cost_to_complete_total", money_str(totals["integrated_ctc"])),
            ("project_monthly_total", money_str(project_month_total)),
            ("note", "per code: Σ integrated monthly == integrated CTC; project: Σ months == Σ CTC")]),
        "audit/probability_adjustment_audit.json": OrderedDict([
            ("project_key", project_key),
            ("probability_method", probability_consumer.PROBABILITY_METHOD),
            ("deterministic_no_monte_carlo", True),
            ("deterministic_seed", seed),
            ("direction_counts", dict(prob_dir_counts)),
            ("note", "deterministic reshaping of the accepted probability band around P50; NOT a fresh "
             "Monte Carlo; floored at actuals; never capped")]),
        "audit/no_upper_cap_audit.json": OrderedDict([
            ("project_key", project_key), ("no_upper_cap_anywhere", bool(cap_rows_ok)),
            ("final_cost_rows_checked", len(forecast_rows)),
            ("probability_rows_checked", len(probability_rows)),
            ("rule", "no history / pay-app / owner SOV / ERP budget / commitment / prior forecast / "
             "probability value is used as a hard cap; integrated final floored at actuals only")]),
        "audit/actuals_floor_audit.json": OrderedDict([
            ("project_key", project_key), ("all_floors_respected", bool(floor_all)),
            ("codes_checked", len(floor_audits)),
            ("floored_at_actuals_count", sum(1 for r in forecast_rows if r["floored_at_actuals"]))]),
        "audit/model_evidence_completeness_matrix.json": final_package.completeness_matrix(
            project_key, discovery, inputs["frequency_disposition"],
            bool(cfg_fc.get("history_enabled", True))),
    }

    cost_basis_checks = cost_basis_validation.validate_cost_basis_decisions(
        cost_basis_rows, monthly_total_by_key=monthly_total_by_key)
    audits["audit/forecast_cost_basis_decision_audit.json"] = OrderedDict([
        ("project_key", project_key),
        ("package_stamp", seed if seed is not None else None),
        ("summary_counts_by_cost_basis_status",
         dict(Counter(r["cost_basis_status"] for r in cost_basis_rows))),
        ("validation_checks", cost_basis_checks),
        ("rows", sorted(cost_basis_rows, key=lambda r: r.get("budget_code_key") or "")),
    ])

    staffing_cfg = (inputs.get("_cfg") or {}).get("forecast_staffing_plan") or {}
    staffing_present = bool((discovery.get("staffing_plan") or {}).get("present"))
    staffing_mapping_rows = inputs.get("staffing_mapping_rows") or []
    staffing_basis_checks = staffing_basis_validation.validate_staffing_basis_decisions(
        staffing_basis_rows, monthly_total_by_key=monthly_total_by_key)
    staffing_basis_checks["staffing_package_present_if_config_enabled"] = bool(
        (not staffing_cfg.get("enabled")) or staffing_present)
    staffing_basis_checks["staffing_mapping_all_accepted_rows_resolved"] = bool(
        all(r.get("mapping_status") in ("mapped_operator_approved_lab",
                                        "resolved_unique_lab_pending_acceptance")
            for r in staffing_mapping_rows if r.get("override_acceptance_status") == "accepted"))
    # a staffing-basis code is never simultaneously governed by an accepted value-asserting model control
    staffing_basis_checks["model_controls_override_staffing"] = bool(
        all(r.get("operator_model_control_status") != "applied_model_value"
            for r in forecast_rows if r.get("staffing_basis_status") == "operator_staffing_plan_basis"))
    audits["audit/forecast_staffing_basis_decision_audit.json"] = OrderedDict([
        ("project_key", project_key),
        ("package_stamp", seed if seed is not None else None),
        ("staffing_active", staffing_present),
        ("summary_counts_by_staffing_basis_status",
         dict(Counter(r["staffing_basis_status"] for r in staffing_basis_rows))),
        ("applied_count", len(staffing_basis_applied_keys)),
        ("validation_checks", staffing_basis_checks),
        # audit only staffing-relevant codes (those carrying a staffing cost-code mapping)
        ("rows", sorted([r for r in staffing_basis_rows if r.get("staffing_mapping_status")],
                        key=lambda r: r.get("budget_code_key") or "")),
    ])

    audits["audit/forecast_run_lineage_audit.json"] = _run_lineage_audit(
        project_key, discovery, inputs.get("context_lineage") or {})

    if inputs["frequency_disposition"] != "consumed":
        warnings.append(OrderedDict([
            ("project_key", project_key), ("warning_type", "cost_frequency_package_missing"),
            ("severity", "medium"), ("message", inputs["frequency_reason"])]))
    for c in conflict_rows:
        if c["severity"] == "high":
            warnings.append(OrderedDict([
                ("project_key", project_key), ("budget_code_key", c["budget_code_key"]),
                ("warning_type", "evidence_conflict"), ("severity", "high"),
                ("message", f"{c['conflict_class']}: {c['detail']}")]))

    # deterministic sorts
    skey = lambda r: (r.get("budget_code_key") or "", r.get("cost_code") or "")  # noqa: E731
    for lst in (weights_rows, forecast_rows, final_recs, monthly_rows, probability_rows, change_rows,
                review_rows, risk_rows):
        lst.sort(key=skey)
    conflict_rows.sort(key=lambda c: (c.get("budget_code_key") or "", c.get("conflict_class") or ""))
    warnings.sort(key=lambda w: (w.get("warning_type") or "", w.get("budget_code_key") or ""))

    top_over, top_conf, top_confl, top_rev = final_package.tops(
        forecast_rows, probability_rows, conflict_rows, review_rows)
    prob_summary = OrderedDict([
        ("project_key", project_key),
        ("probability_method", probability_consumer.PROBABILITY_METHOD),
        ("deterministic_seed", seed),
        ("integrated_p50_total", money_str(sum((D(r["integrated_p50"]) for r in probability_rows), ZERO))),
        ("integrated_p90_total", money_str(sum((D(r["integrated_p90"]) for r in probability_rows), ZERO))),
        ("integrated_p95_total", money_str(sum((D(r["integrated_p95"]) for r in probability_rows), ZERO))),
        ("direction_counts", dict(prob_dir_counts)),
        ("note", "deterministic transform of the accepted probability package, not a fresh Monte Carlo"),
        ("requires_human_acceptance", True),
    ])
    summary = final_package.summary(project_key, discovery, forecast_rows, monthly_rows, probability_rows,
                                    review_rows, conflict_rows, inputs["frequency_disposition"], totals)

    out = {
        "integrated_forecast_by_budget_code.jsonl": forecast_rows,
        "integrated_evidence_registry_by_budget_code.jsonl": items,
        "integrated_evidence_weights_by_budget_code.jsonl": weights_rows,
        "integrated_final_cost_recommendations.jsonl": final_recs,
        "integrated_monthly_forecast_by_budget_code.jsonl": monthly_rows,
        "integrated_monthly_project_forecast.jsonl": project_monthly,
        "integrated_probability_by_budget_code.jsonl": probability_rows,
        "integrated_probability_project_summary.json": prob_summary,
        "integrated_risk_register.jsonl": risk_rows,
        "integrated_human_review_queue.jsonl": review_rows,
        "integrated_change_explanation.jsonl": change_rows,
        "evidence_conflict_register.jsonl": conflict_rows,
        "model_package_inventory.json": final_package.model_package_inventory(project_key, discovery),
        "project_comprehensive_forecast_summary.json": summary,
        "top_overrun_risks.json": top_over,
        "top_confidence_improvements.json": top_conf,
        "top_evidence_conflicts.json": top_confl,
        "top_human_review_items.json": top_rev,
        "data_quality_warnings.jsonl": warnings,
    }
    out.update(audits)
    out.update(actuals_export.build_collections(
        project_key, inputs["budget_codes"], inputs["actuals_monthly_by_key"],
        inputs["actuals_to_date_by_key"], rec_by_key=inputs["actuals_rec_by_key"],
        forecast_start_month=None))
    # combined actuals(historical) + integrated forecast month-by-month matrix, collapsed to cost code.
    # Controlled keys reconcile the combined CSV row to the AUTHORITATIVE integrated final (current-month
    # actuals counted once). For value-changing controls the integrated final equals the controlled final;
    # for shape-only controls it is the history-blended final the integrated monthly already sums to.
    model_by_key = ((inputs.get("model_controls_bundle") or {}).get("resolved") or {}).get("by_key") or {}
    integ_final_by_key = {r["budget_code_key"]: r["integrated_recommended_final_cost"]
                          for r in out["integrated_final_cost_recommendations.jsonl"]}
    controlled = {k: {"final": integ_final_by_key.get(k, money_str(d["controlled_final_cost"])),
                      "actual": d["actual_cost_to_date"]}
                  for k, d in model_by_key.items()}
    out.update(actuals_export.build_actuals_plus_forecast(
        project_key, inputs["budget_codes"], out["actuals_monthly_by_cost_code.jsonl"],
        out["actuals_monthly_by_budget_code.jsonl"], out["integrated_monthly_forecast_by_budget_code.jsonl"],
        controlled=controlled))
    return out


# --------------------------------------------------------------------------- write + orchestrate

def _write_collections(out: Path, collections: dict):
    for fname in DATA_FILES + AUDIT_DATA_FILES:
        payload = collections[fname]
        (out / fname).parent.mkdir(parents=True, exist_ok=True)
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        elif fname.endswith(".csv"):
            write_csv(out / fname, payload["fieldnames"], payload["rows"])
        else:
            write_json(out / fname, payload)


def _determinism_check(inputs, project_key) -> OrderedDict:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        p1, p2 = Path(d1), Path(d2)
        c1 = _build_collections(inputs, project_key)
        c2 = _build_collections(inputs, project_key)
        _write_collections(p1, c1)
        _write_collections(p2, c2)
        per_file, ok = [], True
        for fname in DATA_FILES + AUDIT_DATA_FILES:
            h1, h2 = sha256_file(p1 / fname), sha256_file(p2 / fname)
            same = h1 == h2
            ok = ok and same
            per_file.append(OrderedDict([("file", fname), ("sha256", h1), ("identical", same)]))
    return OrderedDict([
        ("performed", True), ("quantitative_core_byte_identical", ok),
        ("llm_excluded_from_byte_diff", True), ("diff_result", "pass" if ok else "fail"),
        ("per_file", per_file)])


def _source_hashes(files) -> OrderedDict:
    out = OrderedDict()
    for p in files:
        out[str(p)] = sha256_file(p) if Path(p).exists() else None
    return out


def _maybe_generate_cost_frequency(cfg, data_root, project_key, frozen_stamp, discovery):
    """Refinement #2: if no cost-frequency package and the CLI can produce one, generate it first."""
    fc = cfg.get("forecast_comprehensive") or {}
    if discovery["cost_frequency"]["present"] or not fc.get("frequency_enabled", True):
        return discovery, ("consumed" if discovery["cost_frequency"]["present"] else "intentionally_excluded"), \
            "cost-frequency package already present" if discovery["cost_frequency"]["present"] \
            else "frequency_enabled is false"
    try:
        from ..forecast_cost_frequency import generate_forecast_cost_frequency_package as fcfgen
        fcfgen.generate(project_key, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=None)
        discovery = package_discovery.discover(cfg, data_root)
        return discovery, "consumed", "cost-frequency package generated into the data root, then consumed"
    except FileExistsError:
        discovery = package_discovery.discover(cfg, data_root)
        return discovery, "consumed", "cost-frequency package already existed for this stamp"
    except Exception as e:
        if fc.get("allow_degraded_without_frequency_package", True):
            return discovery, "degraded_missing", f"cost-frequency generation failed: {e}; degraded allowed"
        raise


def load_inputs(cfg, data_root, project_key, frozen_stamp, control_file=None):
    discovery = package_discovery.discover(cfg, data_root)
    missing = package_discovery.missing_required(discovery)
    if missing:
        raise SystemExit(f"ERROR: required package(s) missing: {missing}")
    discovery, freq_disp, freq_reason = _maybe_generate_cost_frequency(
        cfg, data_root, project_key, frozen_stamp, discovery)

    context_pkg = Path(discovery["context"]["path"])
    budget_codes = list(read_jsonl(context_pkg / "canonical" / "budget_codes.jsonl"))
    index = build_canonical_index(budget_codes)
    canonical_keys = set(index["keys"])

    sources = evidence_registry.load_sources(discovery)

    # monthly actuals export (CostEntries/Sage only; re-emitted so the comprehensive package is
    # self-contained)
    actuals_load = actuals_export.load_costentries_monthly(context_pkg)
    actuals_to_date_by_key = {k: (r.get("actuals") or {}).get("actual_cost_all_source_to_date")
                              for k, r in sources["context_by"].items()}
    actuals_rec_by_key = {k: {"recommended_cost_to_complete": r.get("recommended_cost_to_complete")}
                          for k, r in sources["rec_by"].items()}

    # operator forecast controls (read-only; fail closed before generation if unsafe)
    actuals_by_key = {k: D((r.get("actuals") or {}).get("actual_cost_all_source_to_date"))
                      for k, r in sources["context_by"].items()}
    controls_bundle = fctl_integration.prepare(cfg, SUBPROJECT_ROOT, canonical_keys, actuals_by_key,
                                               project_key)
    fctl_integration.assert_integration_safe(cfg, controls_bundle)
    controls_active = fctl_integration.integration_active(cfg, controls_bundle)
    resolved = controls_bundle["resolved"]
    apps_by_key = {}
    for a in resolved["applications"]:
        if a.get("budget_code_key"):
            apps_by_key.setdefault(a["budget_code_key"], []).append(a)
    controls_ctx = {
        "by_key": resolved["by_key"] if controls_active else {},
        "apps_by_key": apps_by_key if controls_active else {},
        "control_file": controls_bundle["load_result"]["control_file"],
        "active": controls_active,
    }
    items, per_code = evidence_registry.build_registry(canonical_keys, sources, project_key, controls_ctx)

    # operator forecast-MODEL controls (read-only; fail closed before generation if unsafe). Resolved
    # against the comprehensive month set; decisions injected into per_code so the final / monthly /
    # probability consumers override the controlled code to the operator's window / shape / value.
    amounts_by_key = {k: (r.get("budget_amounts") or {}) for k, r in sources["context_by"].items()}
    rec_by = {k: (per_code.get(k, {}).get("rec") or {}) for k in canonical_keys}
    model_final = {k: D(rec_by[k].get("recommended_final_cost")) if rec_by[k].get("recommended_final_cost")
                   is not None else None for k in canonical_keys}
    model_ctc = {k: D(rec_by[k].get("recommended_cost_to_complete"))
                 if rec_by[k].get("recommended_cost_to_complete") is not None else None for k in canonical_keys}
    ref_ctx = fmc_integration.build_ref_ctx(canonical_keys, amounts_by_key, rec_by,
                                            context_package_path=str(context_pkg))
    schedule_by_key, latest_proj = {}, None
    for k in canonical_keys:
        sev = per_code.get(k, {}).get("sched") or {}
        fin = sev.get("latest_schedule_finish")
        if fin:
            schedule_by_key[k] = {"latest_schedule_finish": fin, "latest_remaining_finish": fin}
            if latest_proj is None or fin > latest_proj:
                latest_proj = fin
    project_schedule = {"schedule_present": bool(latest_proj), "latest_project_schedule_date": latest_proj}
    comp_months = sorted({w["month"] for k in canonical_keys
                          for w in ((per_code.get(k, {}).get("monthly_dist") or {})
                                    .get("monthly_distribution_weights") or [])})
    model_bundle = fmc_integration.prepare(cfg, SUBPROJECT_ROOT, canonical_keys, actuals_by_key, ref_ctx,
                                           schedule_by_key, project_schedule, comp_months, model_final,
                                           model_ctc, project_key, override_path=control_file)
    fmc_integration.assert_integration_safe(cfg, model_bundle)
    model_active = fmc_integration.integration_active(cfg, model_bundle)
    model_by_key = model_bundle["resolved"]["by_key"] if model_active else {}
    for k in canonical_keys:
        amts = amounts_by_key.get(k) or {}
        per_code[k]["committed_costs"] = amts.get("committed_costs")
        per_code[k]["original_budget_amount"] = amts.get("original_budget_amount")
        # full BudgetDetails amounts for the deterministic cost-basis decision (forecast_cost_basis)
        for _f in ("commitment_invoiced", "erp_direct_costs", "erp_job_to_date_costs",
                   "pending_cost_changes", "projected_costs", "estimated_cost_at_completion",
                   "forecast_to_complete", "revised_budget", "projected_budget"):
            per_code[k][_f] = amts.get(_f)
        per_code[k]["category"] = k.split(".")[-1] if "." in k else None
    for k, decision in model_by_key.items():
        if k in per_code:
            per_code[k]["model_control"] = decision

    source_files = []
    for pth in sources["_paths"].values():
        if pth:
            source_files.extend(sorted(pth.rglob("*.jsonl")))
    pre_hashes = _source_hashes(source_files[:400])   # bound the hash set for speed; deterministic order

    return OrderedDict([
        ("project_key", project_key), ("discovery", discovery),
        ("budget_codes", budget_codes), ("index", index), ("canonical_keys", canonical_keys),
        ("evidence_items", items), ("per_code", per_code),
        ("frequency_disposition", freq_disp), ("frequency_reason", freq_reason),
        ("source_files", source_files[:400]), ("source_hashes_before", pre_hashes),
        ("controls_active", controls_active), ("controls_bundle", controls_bundle),
        ("controls_ctx", controls_ctx),
        ("model_controls_active", model_active), ("model_controls_bundle", model_bundle),
        ("staffing_plan_active", bool(discovery.get("staffing_plan", {}).get("present"))),
        ("staffing_plan_conflicts", sources.get("staffing_plan_conflicts") or []),
        ("staffing_mapping_rows", list((sources.get("staffing_mapping_by_cc") or {}).values())),
        ("actuals_monthly_by_key", actuals_load["by_key"]),
        ("actuals_to_date_by_key", actuals_to_date_by_key),
        ("actuals_rec_by_key", actuals_rec_by_key),
        ("actuals_contamination_ok", actuals_load["contamination_ok"]),
    ])


def generate(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None,
             with_llm=False, llm_model=None, control_file=None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    cfg, _ctx_pkg, ctx_lineage = lineage.pin_context_into_cfg(cfg, data_root, project_key)
    inputs = load_inputs(cfg, data_root, project_key, frozen_stamp, control_file=control_file)
    inputs["_cfg"] = cfg
    inputs["context_lineage"] = ctx_lineage

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_comprehensive_package_{project_key}_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)
    (out / "llm").mkdir(exist_ok=True)

    collections = _build_collections(inputs, project_key)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, project_key)

    narratives, receipts, ollama_status = _run_llm(with_llm, cfg, llm_model,
                                                   collections["integrated_human_review_queue.jsonl"])
    write_jsonl(out / "llm" / "comprehensive_narratives.jsonl", narratives)
    write_jsonl(out / "llm" / "comprehensive_narrative_receipts.jsonl", receipts)

    command = (f"python3 -m construction_financial_review.cli forecast-comprehensive "
               f"--project {project_key}" + (" --with-llm" if with_llm else ""))
    meta = OrderedDict([
        ("generator", "construction_financial_review.forecast_comprehensive."
                      "generate_comprehensive_forecast_package"),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("project_key", project_key)])

    after = _source_hashes(inputs["source_files"])
    src_audit = OrderedDict([("before", inputs["source_hashes_before"]), ("after", after),
                             ("unchanged", inputs["source_hashes_before"] == after)])
    audit = OrderedDict([
        ("actuals_floor_audit", collections["audit/actuals_floor_audit.json"]),
        ("no_upper_cap_audit", collections["audit/no_upper_cap_audit.json"]),
        ("monthly_reconciliation_audit", collections["audit/monthly_reconciliation_audit.json"]),
        ("probability_adjustment_audit", collections["audit/probability_adjustment_audit.json"]),
        ("history_consumption_audit", collections["audit/history_consumption_audit.json"]),
        ("frequency_consumption_audit", collections["audit/frequency_consumption_audit.json"]),
        ("cost_basis_decision_audit", collections["audit/forecast_cost_basis_decision_audit.json"]),
        ("staffing_basis_decision_audit", collections["audit/forecast_staffing_basis_decision_audit.json"]),
        ("run_lineage_audit", collections["audit/forecast_run_lineage_audit.json"]),
        ("source_hashes_before_after", src_audit)])
    write_json(out / "audit" / "source_hashes_before_after.json", src_audit)
    write_json(out / "audit" / "source_packages_used.json",
               final_package.model_package_inventory(project_key, inputs["discovery"]))
    db_inv = db_inventory.inventory(cfg, project_key)
    write_json(out / "audit" / "db_inventory.json", db_inv)
    write_json(out / "input_inventory.json", OrderedDict([("generation", meta),
                                                          ("context_lineage", inputs["context_lineage"]),
                                                          ("discovery", inputs["discovery"])]))
    _write_readme(out, project_key, meta, collections)
    _write_schema(out)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)
    validation = fc_validation.build_validation(out, inputs, collections, audit, determinism, safety,
                                                meta, inputs["discovery"],
                                                bool(with_llm and ollama_status == "available"), receipts)
    write_json(out / "validation_report.json", validation)
    conclusion = ("forecast_comprehensive_ready" if validation["passed"]
                  else "forecast_comprehensive_not_ready")
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    summary = collections["project_comprehensive_forecast_summary.json"]
    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"], "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": src_audit["unchanged"],
            "frequency_disposition": inputs["frequency_disposition"],
            "packages_consumed": summary["packages_consumed"], "packages_missing": summary["packages_missing"],
            "canonical_codes_covered": summary["canonical_codes_covered"],
            "integrated_final_cost_recommendations": summary["integrated_final_cost_recommendations"],
            "integrated_monthly_rows": summary["integrated_monthly_rows"],
            "integrated_probability_rows": summary["integrated_probability_rows"],
            "human_review_items": summary["human_review_items"],
            "evidence_conflicts": summary["evidence_conflicts"], "llm_status": ollama_status}


def _manifest(out, project_key, meta, conclusion, validation):
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    from ..common.project_config import load_project_config

    _pcfg = load_project_config(project_key)
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", f"Comprehensive Integrated Forecast Package — {_pcfg['project_display_name']}"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", _pcfg["project_name"]),
                                 ("job_reference", _pcfg["job_reference"]),
                                 ("forecast_period", _pcfg["forecast_period"])])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion)])


def _run_llm(with_llm, cfg, llm_model, review_rows):
    if not with_llm:
        return [], [], "disabled"
    try:
        from ..forecast_accuracy.llm import narrate
        from ..forecast_accuracy.llm.client import OllamaClient
    except Exception:
        return [], [], "unavailable"
    llm_cfg = cfg.get("llm") or {}
    model = llm_model or llm_cfg.get("model", "qwen2.5:14b")
    client = OllamaClient(model=model, endpoint=llm_cfg.get("endpoint", "http://localhost:11434"),
                          temperature=float(llm_cfg.get("temperature", 0)),
                          seed=int(llm_cfg.get("seed", 7)), timeout=float(llm_cfg.get("timeout_seconds", 60)))
    up, _present = client.available() if hasattr(client, "available") else (False, False)
    if not up:
        return [], [], "unavailable"
    backend = narrate.make_backend(client) if hasattr(narrate, "make_backend") else None
    narratives, receipts = [], []
    for r in review_rows[:15]:
        facts = OrderedDict([("budget_code_key", r.get("budget_code_key")), ("cost_code", r.get("cost_code")),
                             ("review_priority", r.get("review_priority")), ("review_reason", r.get("review_reason"))])
        try:
            nrow, rrow = narrate.narrate_one(facts, backend, model)
            narratives.append(nrow)
            receipts.append(rrow)
        except Exception:
            continue
    return narratives, receipts, "available"


def _write_readme(out, project_key, meta, collections):
    from ..common.project_config import load_project_config

    _pcfg = load_project_config(project_key)
    s = collections["project_comprehensive_forecast_summary.json"]
    md = [
        f"# forecast_comprehensive_package_{project_key} ({meta['package_stamp']})",
        "",
        f"Comprehensive integrated forecast for {_pcfg['project_display_name']} "
        f"({project_key} / {_pcfg['job_reference']} / {_pcfg['forecast_period']}). "
        "Discovers and CONSUMES the accepted evidence packages "
        "(context, intelligence, monthly, probability, history-informed, cost-frequency; crosswalk-v2 + "
        "schedule-integrated for completeness) into a per-budget-code evidence registry, scores advisory "
        "evidence at bounded de-duplicated weights, and emits integrated final-cost / monthly / "
        "probability recommendations with full lineage, an evidence-conflict register, and a "
        "human-acceptance review queue. It does NOT replace or mutate the standalone packages.",
        "",
        f"- Packages consumed: {s['packages_consumed']}; missing: {s['packages_missing']}; cost-frequency: "
        f"{s['frequency_disposition']}.",
        f"- Canonical codes covered: {s['canonical_codes_covered']}; integrated final-cost recs: "
        f"{s['integrated_final_cost_recommendations']}; monthly rows: {s['integrated_monthly_rows']}; "
        f"probability rows: {s['integrated_probability_rows']}.",
        f"- Human-review items: {s['human_review_items']}; evidence conflicts: {s['evidence_conflicts']} "
        f"{s['evidence_conflicts_by_class']}.",
        "",
        "**How evidence flows.** Accepted forecast-intelligence `recommended_final_cost` is the BASE. "
        "History-informed final cost is one advisory family, consumed at a bounded weight that COLLAPSES "
        "when CostEntries contradict it. Cost-frequency shapes monthly TIMING only (zero final-cost "
        "weight). Monthly phasing reshapes by frequency (weekday) + history curve-shape tilt and "
        "reconciles exactly to the integrated cost-to-complete (per code and project total). Probability "
        "is a **deterministic transform** of the accepted distribution band around P50 "
        "(`probability_method = accepted_distribution_deterministic_adjustment`) — NOT a fresh Monte "
        "Carlo.",
        "",
        "**Posture.** CostEntries/Sage incurred cost is accounting truth; actual cost to date is the only "
        "hard floor; no evidence (history / pay-app / owner SOV / ERP budget / commitment / prior "
        "forecast / probability) is ever a cap. Every recommendation is advisory and requires human "
        "acceptance (`acceptance_status: pending`). The local LLM is advisory only (no numeric output) "
        "and excluded from the determinism gate.",
        "",
        "**Accepted vs pending.** This package PROPOSES an integrated forecast; nothing here is formally "
        "accepted. An operator reviews `integrated_human_review_queue.jsonl` + `evidence_conflict_register"
        ".jsonl`, then accepts/rejects per code. See `audit/model_evidence_completeness_matrix.json` for "
        "which model outputs were discovered / consumed / partially consumed / downgraded / missing.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Comprehensive Integrated Forecast Package — Schema",
        "",
        "Money is Decimal-string (2dp); weights/scores are 4dp Decimal strings. Integrated outputs are "
        "ADVISORY (human-acceptance pending); they consume accepted package OUTPUT rows and never mutate "
        "them.",
        "",
        "## Key files",
        "- `integrated_forecast_by_budget_code.jsonl` — master per-code row: actual floor, accepted vs "
        "integrated final cost + CTC, history final-cost weight (frequency final-cost weight = 0), "
        "evidence-family disposition, the six `*_consumption_status` fields, human-acceptance fields.",
        "- `integrated_evidence_registry_by_budget_code.jsonl` — every normalized evidence item with "
        "lineage (`source_package_type/path/file/row_id`), `evidence_family`, `independence_group`, "
        "support flags, contradiction score.",
        "- `integrated_evidence_weights_by_budget_code.jsonl` — bounded, de-duplicated weights + "
        "accept/downgrade/reject reason codes per code.",
        "- `integrated_final_cost_recommendations.jsonl` — accepted base + bounded history adjustment, "
        "floored at actuals, never capped.",
        "- `integrated_monthly_forecast_by_budget_code.jsonl` / `integrated_monthly_project_forecast.jsonl` "
        "— integrated phasing with six source shares (cost_entry/invoice/schedule/history_shape/frequency/"
        "fallback); reconciles to integrated CTC per code and project total.",
        "- `integrated_probability_by_budget_code.jsonl` / `integrated_probability_project_summary.json` — "
        "deterministic adjustment of the accepted band (`probability_method = "
        "accepted_distribution_deterministic_adjustment`); floored at actuals; never capped.",
        "- `integrated_risk_register.jsonl`, `integrated_human_review_queue.jsonl`, "
        "`integrated_change_explanation.jsonl`, `evidence_conflict_register.jsonl` (7 conflict classes), "
        "`model_package_inventory.json`, `project_comprehensive_forecast_summary.json`, `top_*`.",
        "- `audit/*` — evidence_registry, evidence_weighting (no-double-count), history_consumption, "
        "frequency_consumption, monthly_reconciliation (per-code + project), probability_adjustment "
        "(deterministic, non-MC), no_upper_cap, actuals_floor, model_evidence_completeness_matrix, "
        "source_hashes_before_after, safety_scan. `llm/*` advisory only, excluded from determinism.",
        "",
        "## Rules",
        "- CostEntries/Sage incurred cost is the only actual-cost source; actual cost to date is the only "
        "hard floor; NO evidence is ever a hard cap.",
        "- Accepted intelligence is the base final cost; advisory evidence is bounded + contradiction-"
        "collapsed with explicit reason codes; independence groups prevent double-counting.",
        "- Cost-frequency shapes monthly timing + timing-risk only — never final cost by itself.",
        "- Probability is a DETERMINISTIC transform of the accepted package, not a fresh Monte Carlo.",
        "- Every posture-changing row carries human-acceptance fields (default pending).",
        "- Deterministic: same frozen stamp + same input packages => byte-identical quantitative core.",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None, with_llm=False,
        llm_model=None, control_file=None) -> int:
    import json
    res = generate(project_key, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model, control_file=control_file)
    print(json.dumps(OrderedDict([("status", "ok" if res["validation_passed"] else "validation_failed"),
                                  *res.items()]), indent=2))
    return 0 if res["validation_passed"] else 1
