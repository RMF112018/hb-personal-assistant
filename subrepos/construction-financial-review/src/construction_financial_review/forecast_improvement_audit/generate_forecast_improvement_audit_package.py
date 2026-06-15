"""Generate the additive forecast improvement-audit package for Tropical World Nursery.

Validates the seven forecasting-priority improvements against repo + data truth and implements each ONLY
where the available JSON packages / SQLite tables support it. Additive, deterministic (frozen stamp),
local-first, read-only against all source data; never mutates an accepted/source/historical package or
the SQLite DB. Every diagnostic is advisory (requires human acceptance). Governance: CostEntries actuals
are the only floor; reference values never cap NON-fee forecasts; FEE codes are capped by the projected
budget value subject to the actuals floor.

Run:
    PYTHONPATH=src python3 -m construction_financial_review.cli forecast-improvement-audit \
        --project tropical [--frozen-stamp YYYYMMDD_HHMMSS] [--out-root DIR]
"""
from __future__ import annotations

import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from ..common.hashing import sha256_file
from ..common.io import read_jsonl, write_json, write_jsonl
from ..common.safety import safety_scan
from . import (
    boe,
    calibration,
    change_order,
    decisions,
    gcgr_fee,
    inputs_io,
    lag,
    schedule_readiness,
)
from . import validation as fia_validation

DATA_FILES = (
    "improvement_support_decisions.json",
    "data_inventory.json",
    "sqlite_inventory.json",
    "basis_of_estimate_coverage.json",
    "calibration_enhancements.jsonl",
    "actual_cost_lag_diagnostics.jsonl",
    "schedule_cost_loading_readiness_audit.json",
    "gcgr_behavior_diagnostics.jsonl",
    "fee_cap_diagnostics.jsonl",
    "change_order_exposure_evidence.jsonl",
    "change_order_exposure_summary.json",
    "improvement_data_gaps.jsonl",
)
AUDIT_DATA_FILES = (
    "audit/improvement_coverage_audit.json",
    "audit/cap_governance_scan_report.json",
)


def _build_collections(inputs: dict, cfg: dict) -> dict:
    project_key = inputs["project_key"]
    data_root = Path(inputs["data_root"])

    calib_rows, calib_gaps = calibration.build(inputs, cfg)
    lag_rows, lag_gaps = lag.build(inputs, cfg)
    sched_audit, sched_gaps = schedule_readiness.build(inputs, cfg)
    gcgr_rows = gcgr_fee.build_gcgr_behavior(inputs, cfg)
    fee_rows, fee_gaps = gcgr_fee.build_fee_cap(inputs, cfg)
    fee_followup_gaps = gcgr_fee.fee_followups(inputs, cfg, fee_rows)
    co_rows, co_summary, co_gaps = change_order.build(inputs, cfg)

    all_gaps = (calib_gaps + lag_gaps + sched_gaps + fee_gaps + fee_followup_gaps + co_gaps)
    all_gaps.sort(key=lambda g: (g.get("improvement") or "", g.get("gap_type") or "",
                                 str(g.get("budget_code_key") or "")))

    counts = {
        "priority_3": {"calibration_rows": len(calib_rows)},
        "priority_4": {"lag_rows": len(lag_rows)},
        "priority_5": {"schedule_activities": len(inputs["schedule_activities"])},
        "priority_6": {"gcgr_rows": len(gcgr_rows), "fee_rows": len(fee_rows)},
        "priority_7": {"change_order_rows": len(co_rows)},
    }
    decision_rows = decisions.build_decisions(inputs, counts)

    coverage_audit = OrderedDict([
        ("project_key", project_key),
        ("priority_1_history_informed", OrderedDict([
            ("decision", "implemented_and_validated"),
            ("hardening_items_confirmed_in_repo", OrderedDict([
                ("item_1_monthly_source_shares", "history_monthly_distribution.build_distribution + "
                 "source_shares_available / distribution_source_basis (verified in tests)"),
                ("item_2_divergence_gate", "validation.history_vs_actual_divergence_reported fail-closed "
                 "(no unconditional pass; requires reality-check fields + validation_class)"),
                ("item_3_tiered_actual_evidence", "actual_evidence_support_score present; "
                 "invoice_support_score absent"),
                ("item_4_config_zero_inactivity", "actual_inactivity_months_for_zero_support enforced; "
                 "validated_zero_inactive / inconclusive_zero / contradicted_unexpected_actuals"),
            ])),
            ("note", "FHI is audit-confirmed only; this package does not patch or re-run it"),
        ])),
        ("improvement_decisions", [OrderedDict([("improvement_id", d["improvement_id"]),
                                                ("decision", d["decision"])]) for d in decision_rows]),
    ])

    cap_gov_scan = OrderedDict([
        ("project_key", project_key),
        ("rule", "reference values never cap NON-fee forecasts; FEE codes are capped by projected budget "
                 "value subject to the actuals floor; CostEntries actuals are the only floor"),
        ("non_fee_rows_scanned", len(gcgr_rows) + len(lag_rows) + len(co_rows)),
        ("non_fee_reference_cap_found", not fia_validation._non_fee_has_no_cap(gcgr_rows + lag_rows + co_rows)),
        ("fee_rows_scanned", len(fee_rows)),
        ("fee_cap_enforced", fia_validation.fee_cap_enforced(fee_rows)),
        ("fee_cap_basis_correct", fia_validation.fee_basis_correct(fee_rows)),
        ("fee_actuals_floor_preserved", fia_validation.fee_floor_preserved(fee_rows)),
        ("fee_cap_source_field", (cfg.get("forecast_improvement_audit") or {}).get(
            "fee_cap_source_field", "projected_budget")),
        ("fee_codes", sorted({r["budget_code_key"] for r in fee_rows})),
    ])

    out = {
        "improvement_support_decisions.json": decision_rows,
        "data_inventory.json": decisions.data_inventory(inputs),
        "sqlite_inventory.json": decisions.sqlite_inventory(inputs),
        "basis_of_estimate_coverage.json": boe.coverage(inputs, data_root),
        "calibration_enhancements.jsonl": calib_rows,
        "actual_cost_lag_diagnostics.jsonl": lag_rows,
        "schedule_cost_loading_readiness_audit.json": sched_audit,
        "gcgr_behavior_diagnostics.jsonl": gcgr_rows,
        "fee_cap_diagnostics.jsonl": fee_rows,
        "change_order_exposure_evidence.jsonl": co_rows,
        "change_order_exposure_summary.json": co_summary,
        "improvement_data_gaps.jsonl": all_gaps,
        "audit/improvement_coverage_audit.json": coverage_audit,
        "audit/cap_governance_scan_report.json": cap_gov_scan,
    }
    return out


def _write_collections(out: Path, collections: dict):
    for fname in DATA_FILES + AUDIT_DATA_FILES:
        payload = collections[fname]
        (out / fname).parent.mkdir(parents=True, exist_ok=True)
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        else:
            write_json(out / fname, payload)


def _determinism_check(inputs, cfg) -> OrderedDict:
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        p1, p2 = Path(d1), Path(d2)
        _write_collections(p1, _build_collections(inputs, cfg))
        _write_collections(p2, _build_collections(inputs, cfg))
        per_file, ok = [], True
        for fname in DATA_FILES + AUDIT_DATA_FILES:
            h1, h2 = sha256_file(p1 / fname), sha256_file(p2 / fname)
            same = h1 == h2
            ok = ok and same
            per_file.append(OrderedDict([("file", fname), ("sha256", h1), ("identical", same)]))
    return OrderedDict([("performed", True), ("quantitative_core_byte_identical", ok),
                        ("diff_result", "pass" if ok else "fail"), ("per_file", per_file)])


def _source_hashes(files) -> OrderedDict:
    out = OrderedDict()
    for p in files:
        out[str(p)] = sha256_file(p) if Path(p).exists() else None
    return out


def generate(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None,
             with_llm=False, llm_model=None) -> dict:
    data_root = Path(data_root or cfg["default_data_root"])
    inputs = inputs_io.load_inputs(cfg, data_root, project_key)
    pre_hashes = _source_hashes(inputs["source_files"])

    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_ts = frozen_stamp if frozen_stamp else datetime.now().isoformat(timespec="seconds")
    out_base = Path(out_root) if out_root else data_root
    out = out_base / f"forecast_improvement_audit_package_tropical_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "audit").mkdir(exist_ok=True)

    collections = _build_collections(inputs, cfg)
    _write_collections(out, collections)
    determinism = _determinism_check(inputs, cfg)

    command = (f"python3 -m construction_financial_review.cli forecast-improvement-audit "
               f"--project {project_key}")
    meta = OrderedDict([
        ("generator", "construction_financial_review.forecast_improvement_audit."
                      "generate_forecast_improvement_audit_package"),
        ("command", command), ("package_stamp", stamp), ("generated_timestamp_local", generated_ts),
        ("project_key", project_key)])

    after = _source_hashes(inputs["source_files"])
    src_audit = OrderedDict([("before", pre_hashes), ("after", after),
                             ("unchanged", pre_hashes == after)])

    # documentation + Basis of Estimate
    boe_md = boe.basis_of_estimate_md(inputs, meta, collections["improvement_support_decisions.json"],
                                      bool(inputs["db"].get("db_present")))
    (out / "BASIS_OF_ESTIMATE.md").write_text(boe_md, encoding="utf-8")
    _write_readme(out, project_key, meta, collections, determinism)
    _write_schema(out)
    write_json(out / "input_inventory.json", OrderedDict([("generation", meta),
                                                          ("discovery", inputs["discovery"])]))

    # environment audits (deterministic but env-pathful; excluded from the byte-diff set)
    write_json(out / "audit" / "source_files_used.json", OrderedDict([
        ("source_file_count", len(inputs["source_files"])),
        ("source_files", [str(p) for p in inputs["source_files"]])]))
    write_json(out / "audit" / "db_inventory.json", inputs["db_schema_inventory"])
    write_json(out / "audit" / "source_hashes_before_after.json", src_audit)

    data_files = sorted(p for p in out.rglob("*") if p.is_file()
                        and p.name not in ("manifest.json", "validation_report.json"))
    safety = safety_scan(data_files)
    write_json(out / "audit" / "safety_scan_report.json", safety)

    validation = fia_validation.build_validation(out, inputs, collections, determinism, safety, meta,
                                                 src_audit)
    write_json(out / "validation_report.json", validation)
    conclusion = ("forecast_improvement_audit_ready" if validation["passed"]
                  else "forecast_improvement_audit_not_ready")
    write_json(out / "manifest.json", _manifest(out, project_key, meta, conclusion, validation))

    return {"output_package": str(out), "validation_passed": validation["passed"],
            "safety_passed": safety["passed"],
            "determinism_passed": determinism["diff_result"] == "pass",
            "source_hashes_unchanged": src_audit["unchanged"],
            "db_present": bool(inputs["db"].get("db_present")),
            "improvement_decisions": [OrderedDict([("improvement_id", d["improvement_id"]),
                                                   ("decision", d["decision"])])
                                      for d in collections["improvement_support_decisions.json"]],
            "fee_rows": validation["fee_row_count"], "gcgr_rows": validation["gcgr_row_count"],
            "lag_rows": validation["lag_row_count"],
            "change_order_rows": validation["change_order_row_count"],
            "data_gaps": validation["data_gap_count"]}


def _manifest(out, project_key, meta, conclusion, validation):
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([("path", str(p.relative_to(out))), ("size_bytes", p.stat().st_size),
                                      ("row_count", rows), ("sha256", sha256_file(p))]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Forecast Improvement Audit Package — Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([("project_key", project_key),
                                 ("project_name", "Tropical World Nursery Senior Living Facility"),
                                 ("job_reference", "23-435-01"), ("forecast_period", "2026-June")])),
        ("generation", meta), ("output_files", files),
        ("validation_status", OrderedDict([("passed", validation["passed"]),
                                           ("checks", validation["checks"])])),
        ("conclusion", conclusion)])


def _write_readme(out, project_key, meta, collections, determinism):
    dec = collections["improvement_support_decisions.json"]
    gaps = collections["improvement_data_gaps.jsonl"]
    md = [
        f"# forecast_improvement_audit_package_tropical ({meta['package_stamp']})",
        "",
        "Additive, advisory, read-only audit of the seven forecasting-priority improvements for "
        f"Tropical World Nursery ({project_key} / 23-435-01 / 2026-June). Each improvement is implemented "
        "ONLY where the available JSON packages / SQLite tables support it; unsupported pieces are "
        "reported as data gaps, never silently skipped. Nothing here mutates an accepted/source/historical "
        "package or the SQLite DB (opened strictly read-only), and nothing is applied into accepted "
        "outputs — every row is advisory (`requires_human_acceptance: true`).",
        "",
        "## Improvement decisions",
    ]
    for d in dec:
        md.append(f"- **{d['improvement_id']} {d['title']}** → `{d['decision']}`")
    md += [
        "",
        "## Governance (corrected)",
        "- CostEntries/Sage actual cost to date is the only hard FLOOR, everywhere.",
        "- Reference values (budget / current projected cost / revised budget / ERP / owner SOV / pay app "
        "/ invoice / schedule / change order / historical forecast) never cap NON-fee forecasts.",
        "- FEE codes (currently `20-18-110 CONTRACTORS FEE`) ARE capped by the projected budget value, "
        "subject to the actuals floor; a missing cap value yields a data gap, never an invented cap.",
        "- Validation distinguishes `no_reference_caps_for_non_fee_codes`, "
        "`fee_projected_budget_cap_enforced`, and `actuals_floor_preserved`.",
        "",
        "## Key outputs",
        "- `improvement_support_decisions.json` — the 7-row decision table with evidence + limitations.",
        "- `BASIS_OF_ESTIMATE.md` + `basis_of_estimate_coverage.json` — BOE for this package + coverage "
        "audit of the rest (follow-up only; no accepted package mutated).",
        "- `calibration_enhancements.jsonl` — backtest calibration with sample-size/denominator guards.",
        "- `actual_cost_lag_diagnostics.jsonl` — CostEntries-vs-leading-indicator lag risk (no inferred cost).",
        "- `schedule_cost_loading_readiness_audit.json` — schedule use-posture.",
        "- `gcgr_behavior_diagnostics.jsonl` + `fee_cap_diagnostics.jsonl` — GC/GR behavior + fee cap.",
        "- `change_order_exposure_evidence.jsonl` (+ summary) — CO exposure classes + double-count risk.",
        "- `improvement_data_gaps.jsonl` — every valid-but-unsupported piece + required follow-ups.",
        "- `audit/*` — coverage, cap-governance scan, source hashes, db inventory, safety, source files.",
        "",
        f"Deterministic quantitative core: {determinism['diff_result']} "
        f"({len(gaps)} data-gap rows). Same frozen stamp + same inputs => byte-identical core.",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_schema(out):
    md = [
        "# Forecast Improvement Audit Package — Schema",
        "",
        "Money is Decimal-string (2dp). All diagnostic rows are ADVISORY (`requires_human_acceptance: "
        "true`); rows proposing a change carry `do_not_auto_apply: true`. The package consumes accepted "
        "package OUTPUT rows + read-only SQLite and never mutates them.",
        "",
        "## Files",
        "- `improvement_support_decisions.json` — per-priority decision (one of implemented_and_validated "
        "/ newly_implemented / partially_supported_diagnostic_only / unsupported_data_gap / ...), evidence, "
        "data fields, limitations, validation/tests, advisory flag.",
        "- `data_inventory.json` / `sqlite_inventory.json` — discovered packages + read-only DB schema/counts.",
        "- `basis_of_estimate_coverage.json` — per-package BOE section coverage; `BASIS_OF_ESTIMATE.md` is "
        "this package's own BOE (14 required sections incl. governance).",
        "- `calibration_enhancements.jsonl` — method/cohort MAPE + bias with `insufficient_sample` + "
        "`mape_denominator_valid` guards (WAPE/MAE not invented).",
        "- `actual_cost_lag_diagnostics.jsonl` — `lag_classification`, `lag_flags`, indicator values; "
        "`actual_cost_inferred_from_indicators` is always false.",
        "- `schedule_cost_loading_readiness_audit.json` — mapped/unmapped, completeness fractions, "
        "`recommended_posture` (can_drive / inform_phasing_only / context_only / not_usable).",
        "- `gcgr_behavior_diagnostics.jsonl` — GC/GR behavior class; advisory, never changes final cost.",
        "- `fee_cap_diagnostics.jsonl` — `fee_projected_budget_cap_value`, `evidence_supported_fee_before_cap`, "
        "`fee_forecast_after_cap`, `fee_projected_budget_cap_applied`, `actuals_exceed_fee_cap_exception`, "
        "`fee_cap_basis` (projected_budget_value | none).",
        "- `change_order_exposure_evidence.jsonl` (+ summary) — exposure class (approved_executed / "
        "pending_unsigned / potential_unapproved / void_rejected / unknown_status), project/family-level "
        "mapping (confidence none), double-count risk.",
        "- `improvement_data_gaps.jsonl` — valid-but-unsupported pieces + required follow-ups.",
        "",
        "## Rules",
        "- CostEntries/Sage incurred cost is the only actual-cost source + the only hard floor.",
        "- NON-fee forecasts are never reference-capped; FEE forecasts are capped by projected budget "
        "value subject to the actuals floor; missing cap value => data gap, never an invented cap.",
        "- SQLite opened strictly read-only; no source/accepted/historical package or DB is mutated.",
        "- Deterministic: same frozen stamp + same inputs => byte-identical quantitative core.",
        "",
    ]
    (out / "SCHEMA.md").write_text("\n".join(md), encoding="utf-8")


def run(project_key, cfg, data_root=None, frozen_stamp=None, out_root=None, with_llm=False,
        llm_model=None) -> int:
    import json
    res = generate(project_key, cfg, data_root=data_root, frozen_stamp=frozen_stamp, out_root=out_root,
                   with_llm=with_llm, llm_model=llm_model)
    print(json.dumps(OrderedDict([("status", "ok" if res["validation_passed"] else "validation_failed"),
                                  *res.items()]), indent=2))
    return 0 if res["validation_passed"] else 1
