"""Priority 2 — Basis of Estimate for the audit package + BOE coverage audit of existing packages.

Generates a deterministic ``BASIS_OF_ESTIMATE.md`` for THIS package (all required reviewer-facing
sections, including the corrected no-cap / fee-cap governance) and a ``basis_of_estimate_coverage.json``
that scores each existing forecast package's current documentation against the BOE section checklist.
Per the agreed scope, it does NOT modify or re-run any other generator; gaps for those packages are
recorded as follow-up work.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

BOE_SECTIONS = (
    "project_identity",
    "forecast_period",
    "input_packages_and_source_hashes",
    "accounting_actuals_basis",
    "budget_and_current_projected_cost_basis",
    "owner_pay_app_basis",
    "subcontractor_invoice_basis",
    "schedule_basis",
    "historical_forecast_basis",
    "db_tables_used",
    "what_the_model_does_not_do",
    "guardrails",
    "confidence_limitations_and_data_gaps",
    "human_review_requirements",
)

# doc-artifact -> BOE sections it materially covers
_DOC_SECTION_MAP = {
    "README.md": ("project_identity", "forecast_period", "what_the_model_does_not_do"),
    "SCHEMA.md": ("input_packages_and_source_hashes", "guardrails"),
    "manifest.json": ("project_identity", "input_packages_and_source_hashes"),
    "validation_report.json": ("guardrails", "human_review_requirements"),
    "input_inventory.json": ("input_packages_and_source_hashes",),
}


def coverage(inputs: dict, data_root: Path) -> OrderedDict:
    """Score each discovered package's existing docs against the BOE section checklist."""
    discovery = inputs["discovery"]
    packages = []
    for ptype, d in discovery.items():
        if not d.get("present"):
            packages.append(OrderedDict([("package_type", ptype), ("present", False)]))
            continue
        pkg = Path(d["path"])
        present_docs = [name for name in _DOC_SECTION_MAP if (pkg / name).exists()]
        covered = set()
        for name in present_docs:
            covered.update(_DOC_SECTION_MAP[name])
        boe_present = (pkg / "BASIS_OF_ESTIMATE.md").exists() or (pkg / "basis_of_estimate.json").exists()
        missing = [s for s in BOE_SECTIONS if s not in covered]
        packages.append(OrderedDict([
            ("package_type", ptype),
            ("present", True),
            ("package_name", d.get("package_name")),
            ("formal_boe_present", boe_present),
            ("doc_artifacts_present", present_docs),
            ("boe_sections_covered_by_docs", sorted(covered)),
            ("boe_sections_missing", missing),
            ("coverage_fraction", round(len(covered) / len(BOE_SECTIONS), 4)),
            ("follow_up", None if boe_present else
             "no formal Basis of Estimate; add BASIS_OF_ESTIMATE.md to this generator (follow-up work, "
             "out of scope this run — accepted packages are not mutated)"),
        ]))
    return OrderedDict([
        ("project_key", inputs["project_key"]),
        ("boe_section_checklist", list(BOE_SECTIONS)),
        ("audit_package_has_formal_boe", True),
        ("note", "BOE implemented for the new audit package only this run; existing packages get a "
                 "coverage score + follow-up (no accepted package mutated)."),
        ("packages", packages),
    ])


def basis_of_estimate_md(inputs: dict, meta: dict, decisions: list, db_present: bool) -> str:
    cfg_project = inputs["project_key"]
    discovery = inputs["discovery"]
    consumed = [ptype for ptype, d in discovery.items() if d.get("present")]
    md = [
        f"# Basis of Estimate — Forecast Improvement Audit ({meta['package_stamp']})",
        "",
        "## project_identity",
        "- Project: Tropical World Nursery Senior Living Facility",
        f"- Project key: {cfg_project}  ·  Job reference: 23-435-01",
        "",
        "## forecast_period",
        "- Forecast period: 2026-June (deterministic frozen-stamp run).",
        "",
        "## input_packages_and_source_hashes",
        f"- Packages discovered + consumed (read-only): {', '.join(consumed)}.",
        "- Every source file is SHA-256 hashed before and after the run; "
        "`audit/source_hashes_before_after.json` proves no source mutation.",
        "",
        "## accounting_actuals_basis",
        "- CostEntries/Sage incurred cost is the only actual-cost source and the only hard FLOOR.",
        "- Actuals are read from the context package (`costentries_total_amount`, "
        "`monthly_actuals_by_budget_code`); never derived from invoices, pay apps, schedule, or history.",
        "",
        "## budget_and_current_projected_cost_basis",
        "- Budget / revised budget / projected budget / current projected cost are REFERENCE values for "
        "variance + the fee cap only; they never cap a non-fee forecast.",
        "",
        "## owner_pay_app_basis",
        "- Owner pay-app totals inform lag diagnostics only (leading indicator); never an actual cost.",
        "",
        "## subcontractor_invoice_basis",
        "- Subcontractor invoice evidence (latest invoice by budget code; DB invoice tables) informs lag "
        "+ change-order exposure only; never an actual cost.",
        "",
        "## schedule_basis",
        "- Schedule activities inform the cost-loading readiness posture only; schedule never overrides "
        "actuals and never creates actual cost.",
        "",
        "## historical_forecast_basis",
        "- Prior cash-flow + GC/GR forecasts are prior-assumption EVIDENCE only (GC/GR behavior context); "
        "never treated as actual cost and never used as a cap.",
        "",
        "## db_tables_used",
        f"- Local SQLite opened strictly read-only (`mode=ro`). DB present this run: {db_present}. "
        "Tables: procore_financial_change_orders / contracts / subcontractor_invoices / invoice_items / "
        "amount_facts / budget_rows (schema + counts inventoried; CO rows read for exposure).",
        "",
        "## what_the_model_does_not_do",
        "- Does not re-run heavy generators or Monte Carlo; does not mutate any accepted/source/historical "
        "package, Excel, or the DB; does not apply any forecast change into accepted outputs; does not "
        "make live external calls.",
        "",
        "## guardrails",
        "- No external calls. No mutation of source/accepted/historical packages or the SQLite DB.",
        "- Historical forecast is never used as actual cost.",
        "- NON-fee forecasts are never hard-capped by budget / current projected cost / revised budget / "
        "ERP / owner SOV / pay app / invoice / schedule / change order / historical forecast.",
        "- FEE forecasts ARE capped by the projected budget value, subject to the actuals floor; a missing "
        "cap value yields a data gap, never an invented cap.",
        "- CostEntries/Sage actual cost to date is the only hard floor wherever a final-cost number appears.",
        "",
        "## confidence_limitations_and_data_gaps",
        "- See `improvement_data_gaps.jsonl`. Notably: calibration limited to MAPE + bias (small cohort); "
        "schedule→budget-code mapping is sparse; change orders carry no per-budget-code link.",
        "",
        "## human_review_requirements",
        "- Every diagnostic/recommendation is advisory (`requires_human_acceptance: true`) and proposed "
        "changes carry `do_not_auto_apply: true`. Nothing here is accepted.",
        "",
        "## improvement_support_decisions",
    ]
    for d in decisions:
        md.append(f"- **{d['improvement_id']} {d['title']}** → `{d['decision']}`")
    md.append("")
    return "\n".join(md)
