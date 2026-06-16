"""Deterministic CostEntries actuals to BudgetDetails ERP cost-to-date cross-check.

This is an additive reconciliation package. CostEntries/Sage remain accounting truth;
BudgetDetails ERP job-to-date cost is evidence only and never overwrites actuals or
caps a forecast.
"""
from __future__ import annotations

from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ..common.hashing import sha256_file
from ..common.io import read_json, read_jsonl, write_csv, write_json, write_jsonl
from ..common.money import D, dec, money_str

ZERO = Decimal("0")
CENTS = Decimal("0.01")
PCT_Q = Decimal("0.000001")
DEFAULT_CONFIG = OrderedDict([
    ("enabled", True),
    ("erp_cost_to_date_field", "amounts.erp_job_to_date_costs"),
    ("absolute_variance_materiality", "0.01"),
    ("percent_variance_materiality", None),
    ("warn_on_material_variance", True),
    ("fail_on_material_variance", False),
    ("fail_on_missing_erp_cost_to_date", False),
    ("fail_on_unmapped_budget_code_key", True),
    ("emit_monthly_reconciliation", True),
])

DATA_FILES = (
    "actuals_erp_crosscheck_by_budget_code.jsonl",
    "actuals_erp_crosscheck_summary.json",
    "actuals_monthly_reconciliation_by_budget_code.jsonl",
    "actuals_monthly_reconciliation_by_month.csv",
    "actuals_erp_crosscheck_variances.csv",
)
AUDIT_FILES = (
    "audit/actuals_source_lineage_audit.json",
    "audit/actuals_mapping_audit.json",
    "audit/actuals_month_assignment_audit.json",
    "audit/actuals_erp_cost_to_date_field_audit.json",
    "audit/actuals_erp_variance_audit.json",
    "audit/actuals_monthly_sum_to_date_audit.json",
    "audit/actuals_crosscheck_validation_report.json",
)
PACKAGE_FILES = DATA_FILES + AUDIT_FILES + ("validation_report.json", "manifest.json", "README.md")
STATUS_MATCHED = "matched"
STATUS_ROUNDING = "rounding_only"
STATUS_MATERIAL = "material_variance"
STATUS_MISSING_ERP = "missing_erp_cost_to_date"
STATUS_MISSING_ACTUAL = "missing_calculated_actual"
STATUS_MAPPING = "mapping_missing"
STATUS_CUTOFF = "not_comparable_cutoff_mismatch"
STATUS_GRANULARITY = "not_comparable_granularity_mismatch"
STATUS_SEMANTICS = "not_comparable_field_semantics"
ALLOWED_STATUSES = (
    STATUS_MATCHED, STATUS_ROUNDING, STATUS_MATERIAL, STATUS_MISSING_ERP,
    STATUS_MISSING_ACTUAL, STATUS_MAPPING, STATUS_CUTOFF, STATUS_GRANULARITY,
    STATUS_SEMANTICS,
)


def merged_config(cfg: dict) -> OrderedDict:
    out = OrderedDict(DEFAULT_CONFIG)
    out.update(cfg.get("actuals_erp_crosscheck") or {})
    return out


def _field_value(row: dict, dotted: str):
    cur: Any = row
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _pct_str(v):
    if v is None:
        return None
    return str(v.quantize(PCT_Q))


def _month_from_date(date_s):
    if isinstance(date_s, str) and len(date_s) >= 7 and date_s[4] == "-":
        return date_s[:7]
    return None


def _variance_status(variance: Decimal, abs_threshold: Decimal, pct_threshold, pct):
    abs_v = abs(variance)
    if abs_v == ZERO:
        return STATUS_MATCHED
    if abs_v <= abs_threshold:
        return STATUS_ROUNDING
    if pct_threshold is not None and pct is not None and abs(pct) < pct_threshold:
        return STATUS_ROUNDING
    return STATUS_MATERIAL


def _safe_hashes(paths):
    out = OrderedDict()
    errors = []
    for p in sorted({Path(p) for p in paths}, key=lambda x: str(x)):
        try:
            out[str(p)] = sha256_file(p) if p.exists() else None
        except Exception as e:
            out[str(p)] = None
            errors.append(OrderedDict([("path", str(p)), ("error", str(e))]))
    return out, errors


def _resolve_context_package(cfg, data_root=None):
    root = Path(data_root or cfg["default_data_root"])
    name = cfg.get("forecast_context_package")
    if not name:
        raise SystemExit("ERROR: project config missing forecast_context_package")
    context_pkg = Path(name)
    if not context_pkg.is_absolute():
        context_pkg = root / name
    try:
        context_pkg.resolve().relative_to(root.resolve())
        under_root = True
    except Exception:
        under_root = False
    return context_pkg, root, under_root


def _read_context_manifest(context_pkg):
    p = Path(context_pkg) / "manifest.json"
    try:
        return read_json(p) if p.exists() else {}
    except PermissionError as e:
        raise SystemExit(f"ERROR: cannot read context package manifest at {p}: {e}") from e


def _read_context_validation(context_pkg):
    p = Path(context_pkg) / "validation_report.json"
    try:
        return read_json(p) if p.exists() else {}
    except PermissionError as e:
        raise SystemExit(f"ERROR: cannot read context package validation report at {p}: {e}") from e


def _read_required_jsonl(path: Path, label: str):
    try:
        return list(read_jsonl(path))
    except PermissionError as e:
        raise SystemExit(f"ERROR: cannot read required context {label} file at {path}: {e}") from e


def load_context_inputs(cfg, project_key, data_root=None) -> OrderedDict:
    context_pkg, root, under_root = _resolve_context_package(cfg, data_root)
    required = OrderedDict([
        ("budget_codes", context_pkg / "canonical" / "budget_codes.jsonl"),
        ("cost_entries", context_pkg / "canonical" / "cost_entries.jsonl"),
        ("monthly_actuals", context_pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl"),
    ])
    manifest = _read_context_manifest(context_pkg)
    validation = _read_context_validation(context_pkg)
    source_paths = [context_pkg / "manifest.json", context_pkg / "validation_report.json", *required.values()]
    before_hashes, hash_errors = _safe_hashes(source_paths)
    missing = [label for label, p in required.items() if not p.exists()]
    if missing:
        raise SystemExit(f"ERROR: context package missing required file(s): {missing} at {context_pkg}")
    return OrderedDict([
        ("project_key", project_key),
        ("data_root", root),
        ("context_pkg", context_pkg),
        ("context_under_data_root", under_root),
        ("manifest", manifest),
        ("validation", validation),
        ("required_files", required),
        ("source_paths", source_paths),
        ("source_hashes_before", before_hashes),
        ("hash_errors_before", hash_errors),
        ("budget_codes", _read_required_jsonl(required["budget_codes"], "budget_codes")),
        ("cost_entries", _read_required_jsonl(required["cost_entries"], "cost_entries")),
        ("monthly_actuals", _read_required_jsonl(required["monthly_actuals"], "monthly_actuals")),
    ])


def _project_from_manifest(manifest):
    project = manifest.get("project") or {}
    if "project_key" in project:
        return project
    return OrderedDict([
        ("project_key", project.get("project_key")),
        ("project_name", project.get("name")),
        ("job_reference", project.get("job")),
        ("forecast_period", project.get("package_period")),
    ])


def build_crosscheck_collections(inputs: dict, cfg: dict, project_key: str, *,
                                 strict: bool = False, frozen_stamp: str | None = None) -> OrderedDict:
    xcfg = merged_config(cfg)
    field = xcfg["erp_cost_to_date_field"]
    abs_threshold = D(xcfg.get("absolute_variance_materiality") or "0.01")
    pct_threshold = dec(xcfg.get("percent_variance_materiality"))
    budget_rows = inputs["budget_codes"]
    cost_rows = inputs["cost_entries"]
    monthly_rows = inputs["monthly_actuals"]

    canonical_rows = OrderedDict()
    duplicate_canonical_erp_rows = []
    malformed_budget_rows = []
    erp_by_key = {}
    erp_source_by_key = {}
    field_present_count = 0
    nonzero_erp_count = 0
    for idx, row in enumerate(budget_rows, start=1):
        key = row.get("budget_code_key")
        if not key:
            malformed_budget_rows.append(OrderedDict([("row_number", idx), ("reason", "missing_budget_code_key")]))
            continue
        if key in canonical_rows:
            duplicate_canonical_erp_rows.append(key)
            continue
        canonical_rows[key] = row
        raw = _field_value(row, field)
        if raw is not None:
            field_present_count += 1
        d = dec(raw)
        if d is not None and d != ZERO:
            nonzero_erp_count += 1
        erp_by_key[key] = d
        erp_source_by_key[key] = "canonical/budget_codes.jsonl"
    canonical_keys = set(canonical_rows)

    field_semantics_ok = (
        field == "amounts.erp_job_to_date_costs"
        and field_present_count > 0
        and not malformed_budget_rows
    )
    field_audit = OrderedDict([
        ("project_key", project_key),
        ("selected_field", field),
        ("explicit_config_field", True),
        ("field_present_count", field_present_count),
        ("canonical_budget_code_count", len(canonical_rows)),
        ("nonzero_value_count", nonzero_erp_count),
        ("semantic_status", "comparable" if field_semantics_ok else "not_comparable"),
        ("semantic_basis", [
            "field is explicitly configured, not inferred",
            "field path is BudgetDetails.amounts.erp_job_to_date_costs",
            "context generator separately labels this total as budget_details_erp_job_to_date_total",
            "field name denotes ERP job-to-date costs; budget, committed, projected, retainage, and current-period fields are not used",
        ]),
        ("not_used_fields", [
            "amounts.revised_budget", "amounts.original_budget", "amounts.committed_costs",
            "amounts.projected_costs", "retainage", "current_period_cost",
        ]),
        ("zero_or_negative_values_valid", True),
        ("malformed_budget_rows", malformed_budget_rows),
        ("duplicate_canonical_erp_rows", sorted(set(duplicate_canonical_erp_rows))),
    ])

    actual_by_key = OrderedDict((k, ZERO) for k in sorted(canonical_keys))
    actual_count_by_key = Counter()
    unmapped_cost_entries = []
    malformed_cost_entries = []
    dates_by_bucket = Counter()
    latest_actual_date = None
    earliest_actual_date = None
    monthly_from_cost_entries = defaultdict(Decimal)
    for idx, row in enumerate(cost_rows, start=1):
        key = row.get("mapped_budget_code_key") or row.get("budget_code_key")
        status = row.get("mapping_status")
        amount_raw = row.get("amount_decimal_string") if row.get("amount_decimal_string") is not None else row.get("amount")
        amount = dec(amount_raw)
        if status != "mapped" or key not in canonical_keys:
            unmapped_cost_entries.append(OrderedDict([
                ("row_number", idx),
                ("budget_code_key", row.get("budget_code_key")),
                ("mapped_budget_code_key", row.get("mapped_budget_code_key")),
                ("mapping_status", status),
            ]))
            continue
        if amount is None:
            malformed_cost_entries.append(OrderedDict([
                ("row_number", idx), ("budget_code_key", key), ("amount", amount_raw),
                ("reason", "malformed_amount"),
            ]))
            continue
        actual_by_key[key] += amount
        actual_count_by_key[key] += 1
        acct_date = row.get("accounting_date")
        month = row.get("accounting_month") or _month_from_date(acct_date)
        if month:
            monthly_from_cost_entries[(key, month)] += amount
        bucket = row.get("actual_period_bucket") or "unknown"
        dates_by_bucket[bucket] += 1
        if acct_date:
            latest_actual_date = acct_date if latest_actual_date is None else max(latest_actual_date, acct_date)
            earliest_actual_date = acct_date if earliest_actual_date is None else min(earliest_actual_date, acct_date)

    monthly_by_key = defaultdict(Decimal)
    monthly_project = defaultdict(Decimal)
    monthly_non_costentries = []
    monthly_unknown_keys = []
    malformed_monthly_rows = []
    for idx, row in enumerate(monthly_rows, start=1):
        key = row.get("mapped_budget_code_key") or row.get("budget_code_key")
        amount = dec(row.get("amount_decimal_string") if row.get("amount_decimal_string") is not None
                     else row.get("amount"))
        month = row.get("month")
        if row.get("source") != "CostEntries":
            monthly_non_costentries.append(OrderedDict([("row_number", idx), ("budget_code_key", key),
                                                        ("source", row.get("source"))]))
            continue
        if key not in canonical_keys:
            monthly_unknown_keys.append(OrderedDict([("row_number", idx), ("budget_code_key", key)]))
            continue
        if amount is None or not month:
            malformed_monthly_rows.append(OrderedDict([("row_number", idx), ("budget_code_key", key),
                                                       ("month", month), ("amount", row.get("amount"))]))
            continue
        monthly_by_key[key] += amount
        monthly_project[month] += amount

    actuals_reliable = not malformed_cost_entries and not monthly_non_costentries
    structural_mapping_failure = bool(
        duplicate_canonical_erp_rows or malformed_budget_rows or
        (unmapped_cost_entries and xcfg.get("fail_on_unmapped_budget_code_key", True)) or
        monthly_unknown_keys or malformed_monthly_rows
    )
    if not inputs.get("context_under_data_root"):
        structural_mapping_failure = True

    recon_rows = []
    recon_status_counts = Counter()
    for key in sorted(canonical_keys):
        actual = actual_by_key[key]
        msum = monthly_by_key.get(key, ZERO)
        diff = actual - msum
        if diff == ZERO:
            status = "exact_match"
        elif abs(diff) <= abs_threshold:
            status = "rounding_only_variance"
        else:
            status = "material_mismatch"
        recon_status_counts[status] += 1
        row = canonical_rows[key]
        recon_rows.append(OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("cost_code", row.get("cost_code")),
            ("category", row.get("category")),
            ("calculated_actual_cost_to_date", money_str(actual)),
            ("monthly_actuals_sum_to_date", money_str(msum)),
            ("actuals_monthly_reconciliation_variance", money_str(diff)),
            ("absolute_variance", money_str(abs(diff))),
            ("monthly_reconciliation_status", status),
            ("rounding_layer", "2dp money strings; exact Decimal sums compared before status assignment"),
            ("actual_entry_count", int(actual_count_by_key.get(key, 0))),
        ]))

    compare_rows = []
    variance_rows = []
    status_counts = Counter()
    project_actual = ZERO
    project_erp = ZERO
    project_month_sum = ZERO
    for key in sorted(canonical_keys):
        meta = canonical_rows[key]
        actual = actual_by_key[key]
        erp = erp_by_key.get(key)
        month_sum = monthly_by_key.get(key, ZERO)
        project_actual += actual
        project_month_sum += month_sum
        if erp is not None:
            project_erp += erp
        variance = actual - (erp or ZERO)
        pct = None if erp in (None, ZERO) else variance / erp
        notes = None
        if not actuals_reliable:
            status = STATUS_MISSING_ACTUAL
            notes = "calculated actuals input is malformed or contaminated"
        elif key not in canonical_keys:
            status = STATUS_MAPPING
        elif not field_semantics_ok:
            status = STATUS_SEMANTICS
            notes = "configured ERP field semantics could not be proven comparable"
        elif erp is None:
            status = STATUS_MISSING_ERP
            notes = "BudgetDetails ERP cost-to-date value missing or nonnumeric"
        else:
            status = _variance_status(variance, abs_threshold, pct_threshold, pct)
        status_counts[status] += 1
        mrec = next(r for r in recon_rows if r["budget_code_key"] == key)
        row = OrderedDict([
            ("project_key", project_key),
            ("budget_code_key", key),
            ("cost_code", meta.get("cost_code")),
            ("category", meta.get("category")),
            ("calculated_actual_cost_to_date", money_str(actual)),
            ("erp_cost_to_date", money_str(erp) if erp is not None else None),
            ("variance", money_str(variance) if erp is not None else None),
            ("absolute_variance", money_str(abs(variance)) if erp is not None else None),
            ("variance_pct", _pct_str(pct)),
            ("variance_status", status),
            ("actuals_cutoff_date", latest_actual_date),
            ("erp_cost_to_date_source_file", erp_source_by_key.get(key)),
            ("erp_cost_to_date_field", field),
            ("calculated_actuals_source", "CostEntries"),
            ("mapping_status", "canonical_key_matched"),
            ("month_sum_reconciles_to_calculated_actual",
             mrec["monthly_reconciliation_status"] in ("exact_match", "rounding_only_variance")),
            ("notes", notes),
        ])
        compare_rows.append(row)
        variance_rows.append(row)

    project_variance = project_actual - project_erp
    project_month_variance = project_actual - project_month_sum
    material_count = status_counts[STATUS_MATERIAL]
    validation_checks = OrderedDict([
        ("context_package_under_data_root", bool(inputs.get("context_under_data_root"))),
        ("context_manifest_present", bool(inputs.get("manifest"))),
        ("context_validation_status_present", bool(inputs.get("validation"))),
        ("canonical_budget_codes_present", bool(canonical_rows)),
        ("no_duplicate_canonical_erp_rows", not duplicate_canonical_erp_rows),
        ("erp_field_present", field_present_count > 0),
        ("erp_field_semantics_comparable", field_semantics_ok),
        ("calculated_actuals_input_reliable", actuals_reliable),
        ("no_unmapped_costentries_when_fail_closed",
         not (unmapped_cost_entries and xcfg.get("fail_on_unmapped_budget_code_key", True))),
        ("monthly_actuals_input_reliable", not monthly_non_costentries and not monthly_unknown_keys
         and not malformed_monthly_rows),
        ("monthly_sums_reconcile", recon_status_counts["material_mismatch"] == 0),
        ("source_hashes_unchanged", True),
        ("strict_mode_material_variance_ok", not (strict and material_count > 0)),
    ])
    advisory_failures = [k for k, v in validation_checks.items() if not v]
    fatal = structural_mapping_failure or (strict and material_count > 0) or (
        bool(xcfg.get("fail_on_material_variance")) and material_count > 0) or (
        bool(xcfg.get("fail_on_missing_erp_cost_to_date")) and status_counts[STATUS_MISSING_ERP] > 0)
    validation_passed = all(validation_checks.values()) if strict else not fatal

    by_month_rows = []
    for month in sorted(monthly_project):
        by_month_rows.append(OrderedDict([
            ("project_key", project_key),
            ("month", month),
            ("monthly_actual_total", money_str(monthly_project[month])),
            ("actual_source", "CostEntries"),
            ("rounding_layer", "2dp money strings"),
        ]))

    summary = OrderedDict([
        ("project_key", project_key),
        ("package_stamp", frozen_stamp),
        ("mode", "strict" if strict else "advisory"),
        ("total_budget_code_keys", len(canonical_rows)),
        ("matched_count", status_counts[STATUS_MATCHED]),
        ("rounding_only_count", status_counts[STATUS_ROUNDING]),
        ("material_variance_count", material_count),
        ("missing_erp_cost_to_date_count", status_counts[STATUS_MISSING_ERP]),
        ("missing_calculated_actual_count", status_counts[STATUS_MISSING_ACTUAL]),
        ("not_comparable_field_semantics_count", status_counts[STATUS_SEMANTICS]),
        ("project_calculated_actual_cost_to_date", money_str(project_actual)),
        ("project_erp_cost_to_date", money_str(project_erp)),
        ("project_level_variance", money_str(project_variance)),
        ("sum_monthly_actuals_through_cutoff", money_str(project_month_sum)),
        ("project_level_monthly_to_date_variance", money_str(project_month_variance)),
        ("actuals_cutoff_date", latest_actual_date),
        ("validation_passed", validation_passed),
        ("warnings", advisory_failures),
    ])

    lineage = OrderedDict([
        ("project_key", project_key),
        ("context_package_path", str(inputs["context_pkg"])),
        ("data_root", str(inputs["data_root"])),
        ("context_package_under_data_root", bool(inputs.get("context_under_data_root"))),
        ("context_manifest_project", _project_from_manifest(inputs.get("manifest") or {})),
        ("context_manifest_generated_stamp", (inputs.get("manifest") or {}).get("generated_stamp")),
        ("context_validation_status", (inputs.get("manifest") or {}).get("validation_status")),
        ("source_hashes_before", inputs.get("source_hashes_before")),
        ("actuals_cutoff_date", latest_actual_date),
        ("earliest_actual_accounting_date", earliest_actual_date),
        ("costentries_date_bucket_counts", dict(sorted(dates_by_bucket.items()))),
        ("calculated_actuals_source", "canonical/cost_entries.jsonl"),
        ("erp_source", "canonical/budget_codes.jsonl"),
    ])
    mapping_audit = OrderedDict([
        ("project_key", project_key),
        ("canonical_budget_code_count", len(canonical_rows)),
        ("costentries_unmapped_count", len(unmapped_cost_entries)),
        ("costentries_unmapped_rows", unmapped_cost_entries[:250]),
        ("monthly_unknown_key_count", len(monthly_unknown_keys)),
        ("monthly_unknown_key_rows", monthly_unknown_keys[:250]),
        ("duplicate_canonical_erp_rows", sorted(set(duplicate_canonical_erp_rows))),
        ("mapping_basis", "canonical budget_code_key; no family-level cost-code comparison"),
    ])
    month_assignment_audit = OrderedDict([
        ("project_key", project_key),
        ("date_field_used_for_transaction_month", "accounting_date/accounting_month from canonical CostEntries"),
        ("month_key_format", "YYYY-MM"),
        ("timezone_normalization", "none; source date strings are used as local accounting dates"),
        ("current_month_to_date_included", bool(dates_by_bucket.get("june_2026_to_date", 0))),
        ("cutoff_date_behavior", "all mapped CostEntries present in the context package are included"),
        ("negative_corrections_credits_included", True),
        ("retainage_handling", "not separately adjusted; CostEntries amounts are summed as accounting truth"),
        ("category_splits_preserved", True),
        ("costentries_monthly_totals_by_source_transaction", [
            OrderedDict([("budget_code_key", k), ("month", m), ("amount", money_str(v))])
            for (k, m), v in sorted(monthly_from_cost_entries.items())
        ][:500]),
    ])
    variance_audit = OrderedDict([
        ("project_key", project_key),
        ("variance_formula", "calculated_actual_cost_to_date - erp_cost_to_date"),
        ("absolute_variance_materiality", money_str(abs_threshold)),
        ("percent_variance_materiality", str(pct_threshold) if pct_threshold is not None else None),
        ("status_counts", dict((s, status_counts[s]) for s in ALLOWED_STATUSES)),
        ("default_advisory_behavior", not strict),
    ])
    monthly_audit = OrderedDict([
        ("project_key", project_key),
        ("rounding_layer", "Decimal arithmetic; money normalized to 2dp strings for output"),
        ("status_counts", dict(sorted(recon_status_counts.items()))),
        ("project_calculated_actual_cost_to_date", money_str(project_actual)),
        ("sum_monthly_actuals_through_cutoff", money_str(project_month_sum)),
        ("project_level_monthly_to_date_variance", money_str(project_month_variance)),
    ])
    validation = OrderedDict([
        ("project_key", project_key),
        ("package_stamp", frozen_stamp),
        ("mode", "strict" if strict else "advisory"),
        ("checks", validation_checks),
        ("fatal", fatal),
        ("passed", validation_passed),
        ("advisory_failures", advisory_failures),
    ])

    csv_fields = [
        "project_key", "budget_code_key", "cost_code", "category",
        "calculated_actual_cost_to_date", "erp_cost_to_date", "variance",
        "absolute_variance", "variance_pct", "variance_status",
        "actuals_cutoff_date", "mapping_status", "notes",
    ]
    return OrderedDict([
        ("actuals_erp_crosscheck_by_budget_code.jsonl", compare_rows),
        ("actuals_erp_crosscheck_summary.json", summary),
        ("actuals_monthly_reconciliation_by_budget_code.jsonl", recon_rows),
        ("actuals_monthly_reconciliation_by_month.csv",
         {"fieldnames": ["project_key", "month", "monthly_actual_total", "actual_source", "rounding_layer"],
          "rows": by_month_rows}),
        ("actuals_erp_crosscheck_variances.csv", {"fieldnames": csv_fields, "rows": variance_rows}),
        ("audit/actuals_source_lineage_audit.json", lineage),
        ("audit/actuals_mapping_audit.json", mapping_audit),
        ("audit/actuals_month_assignment_audit.json", month_assignment_audit),
        ("audit/actuals_erp_cost_to_date_field_audit.json", field_audit),
        ("audit/actuals_erp_variance_audit.json", variance_audit),
        ("audit/actuals_monthly_sum_to_date_audit.json", monthly_audit),
        ("audit/actuals_crosscheck_validation_report.json", validation),
        ("validation_report.json", validation),
        ("_summary", summary),
        ("_validation", validation),
    ])


def _write_readme(out: Path, project_key: str, summary: dict):
    md = [
        f"# actuals_erp_crosscheck_package_{project_key}",
        "",
        "Additive reconciliation evidence comparing CostEntries-derived actual cost-to-date to "
        "BudgetDetails ERP job-to-date cost by canonical budget_code_key.",
        "",
        "CostEntries/Sage remain transaction-level accounting truth. BudgetDetails ERP values are "
        "reconciliation evidence only and never overwrite actuals or cap forecast values.",
        "",
        f"- Mode: {summary.get('mode')}",
        f"- Budget-code keys: {summary.get('total_budget_code_keys')}",
        f"- Material variances: {summary.get('material_variance_count')}",
        f"- Project-level variance: {summary.get('project_level_variance')}",
        "",
    ]
    (out / "README.md").write_text("\n".join(md), encoding="utf-8")


def _write_collections(out: Path, collections: dict):
    for fname in DATA_FILES + AUDIT_FILES + ("validation_report.json",):
        payload = collections[fname]
        (out / fname).parent.mkdir(parents=True, exist_ok=True)
        if fname.endswith(".jsonl"):
            write_jsonl(out / fname, payload)
        elif fname.endswith(".csv"):
            write_csv(out / fname, payload["fieldnames"], payload["rows"])
        else:
            write_json(out / fname, payload)
    _write_readme(out, collections["_summary"]["project_key"], collections["_summary"])


def _manifest(out: Path, project_key: str, cfg: dict, xcfg: dict, inputs: dict, summary: dict,
              validation: dict, stamp: str, strict: bool, after_hashes: dict) -> OrderedDict:
    files = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "manifest.json":
            rows = sum(1 for _ in read_jsonl(p)) if p.suffix == ".jsonl" else None
            files.append(OrderedDict([
                ("path", str(p.relative_to(out))),
                ("size_bytes", p.stat().st_size),
                ("row_count", rows),
                ("sha256", sha256_file(p)),
            ]))
    return OrderedDict([
        ("package_name", out.name),
        ("manifest_title", "Actuals ERP Cross-Check Package - Tropical World Nursery"),
        ("manifest_version", "1.0.0"),
        ("project", OrderedDict([
            ("project_key", project_key),
            ("project_name", cfg.get("project_name")),
            ("job_reference", cfg.get("job_reference")),
            ("forecast_period", cfg.get("forecast_period")),
        ])),
        ("generation", OrderedDict([
            ("package_stamp", stamp),
            ("generated_timestamp_local", stamp if stamp else datetime.now().isoformat(timespec="seconds")),
            ("mode", "strict" if strict else "advisory"),
            ("frozen_stamp", stamp),
        ])),
        ("source_context_package", str(inputs["context_pkg"])),
        ("source_hashes_before", inputs.get("source_hashes_before")),
        ("source_hashes_after", after_hashes),
        ("source_hashes_unchanged", inputs.get("source_hashes_before") == after_hashes),
        ("config_used", xcfg),
        ("output_files", files),
        ("validation_status", OrderedDict([
            ("passed", validation["passed"]),
            ("checks", validation["checks"]),
        ])),
        ("summary", summary),
    ])


def generate(project_key: str, cfg: dict, data_root=None, frozen_stamp=None, out_root=None,
             strict: bool = False) -> dict:
    if not merged_config(cfg).get("enabled", True):
        raise SystemExit("ERROR: actuals_erp_crosscheck is disabled in project config")
    stamp = frozen_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    inputs = load_context_inputs(cfg, project_key, data_root=data_root)
    collections = build_crosscheck_collections(inputs, cfg, project_key, strict=strict, frozen_stamp=stamp)
    out_base = Path(out_root) if out_root else Path(data_root or cfg["default_data_root"])
    out = out_base / f"actuals_erp_crosscheck_package_{project_key}_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    _write_collections(out, collections)
    after_hashes, hash_errors_after = _safe_hashes(inputs["source_paths"])
    validation = collections["_validation"]
    validation["checks"]["source_hashes_unchanged"] = inputs.get("source_hashes_before") == after_hashes
    validation["hash_errors_after"] = hash_errors_after
    validation["passed"] = bool(validation["passed"] and validation["checks"]["source_hashes_unchanged"])
    write_json(out / "validation_report.json", validation)
    write_json(out / "audit" / "actuals_crosscheck_validation_report.json", validation)
    write_json(out / "manifest.json", _manifest(
        out, project_key, cfg, merged_config(cfg), inputs, collections["_summary"], validation, stamp,
        strict, after_hashes))
    return OrderedDict([
        ("output_package", str(out)),
        ("validation_passed", validation["passed"]),
        ("mode", "strict" if strict else "advisory"),
        ("summary", collections["_summary"]),
    ])


def run(project_key: str, cfg: dict, data_root=None, frozen_stamp=None, out_root=None,
        strict: bool = False) -> int:
    import json
    res = generate(project_key, cfg, data_root=data_root, frozen_stamp=frozen_stamp,
                   out_root=out_root, strict=strict)
    print(json.dumps(OrderedDict([("status", "ok" if res["validation_passed"] else "validation_failed"),
                                  *res.items()]), indent=2))
    return 0 if res["validation_passed"] else 1
