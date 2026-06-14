"""Authoritative owner SOV scope crosswalk validator.

Validates the structural integrity and required mapping facts of the authoritative crosswalk. When a
forecast context package is available, also confirms full canonical BudgetDetails (127) and Procore
latest WBS (42) coverage. Prints a JSON report to stdout; exits non-zero on failure.

Usage:
    python -m construction_financial_review.mapping.validate_owner_sov_scope_crosswalk <crosswalk.jsonl> \
        [--context-package /path/to/forecast_context_package]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, OrderedDict
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..common.io import read_jsonl
from ..common.money import dec
from . import crosswalk as xw

REQUIRED_FIELDS = (
    "crosswalk_id", "owner_sov_code", "scope_relationship", "comparison_level",
    "coverage_type", "covered_budget_code_keys",
)

# Required mapping facts (owner_sov_code -> must explicitly cover these budget keys).
REQUIRED_MAPS = {
    "20-18-105": ["1000.20-18-170.MAT"],
    "99-01-790": ["1000.90-01-300.MAT"],
    "15-01-426": ["1000.15-01-426.MAT"],
    "15-01-530": ["1000.15-01-530.LAB", "1000.15-01-530.LBN",
                  "1000.15-01-530.MAT", "1000.15-01-530.SUB"],
}
# 15-01-XXX must NOT cover these excluded keys.
EXCLUDED_FROM_15_01_XXX = ["1000.15-01-426.MAT", "1000.15-01-530.LAB",
                           "1000.15-01-530.LBN", "1000.15-01-530.MAT", "1000.15-01-530.SUB"]


def _as_bool(v) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    return None


def validate(crosswalk_path: str | Path,
             canonical_keys: Optional[set] = None,
             procore_wbs: Optional[set] = None) -> "OrderedDict":
    checks = OrderedDict()
    errors = []
    rows = xw.load_crosswalk(crosswalk_path)
    checks["crosswalk_row_count"] = len(rows)

    # parse already succeeded if we got here
    checks["jsonl_parses"] = True

    # required fields + blanks
    missing_fields = []
    blank_sov = blank_rel = blank_level = 0
    for r in rows:
        for f in REQUIRED_FIELDS:
            if f not in r:
                missing_fields.append((r.get("crosswalk_id"), f))
        if not (r.get("owner_sov_code") or "").strip():
            blank_sov += 1
        if not (r.get("scope_relationship") or "").strip():
            blank_rel += 1
        if not (r.get("comparison_level") or "").strip():
            blank_level += 1
    checks["all_required_fields_present"] = (len(missing_fields) == 0)
    checks["no_blank_owner_sov_code"] = (blank_sov == 0)
    checks["no_blank_scope_relationship"] = (blank_rel == 0)
    checks["no_blank_comparison_level"] = (blank_level == 0)

    # duplicate crosswalk_id
    id_counts = Counter(r.get("crosswalk_id") for r in rows)
    dup_ids = sorted(i for i, c in id_counts.items() if c > 1)
    checks["no_duplicate_crosswalk_id"] = (len(dup_ids) == 0)

    # allocation_required boolean-compatible + 100.00 totals when true
    bad_alloc_bool = []
    bad_alloc_total = []
    for r in rows:
        b = _as_bool(r.get("allocation_required"))
        if b is None:
            bad_alloc_bool.append(r.get("crosswalk_id"))
            continue
        if b is True:
            pct_map = r.get("allocation_percent_by_budget_code") or {}
            total = sum((dec(v) or Decimal("0")) for v in pct_map.values())
            if total != Decimal("100.00") and total != Decimal("100"):
                bad_alloc_total.append((r.get("crosswalk_id"), str(total)))
    checks["allocation_required_boolean_compatible"] = (len(bad_alloc_bool) == 0)
    checks["allocation_percentages_total_100_when_required"] = (len(bad_alloc_total) == 0)

    # 10-XX-XXX description-sensitive: exactly two rows
    ten = [r for r in rows if r.get("owner_sov_code") == "10-XX-XXX"]
    checks["owner_10xx_two_description_sensitive_rows"] = (len(ten) == 2)

    # required maps
    for sov, keys in REQUIRED_MAPS.items():
        checks[f"map_{sov.replace('-', '_')}"] = all(xw.covers(rows, sov, k) for k in keys)
    # 15-01-XXX exclusions
    checks["map_15_01_xxx_excludes_426_530"] = not any(
        xw.covers(rows, "15-01-XXX", k) for k in EXCLUDED_FROM_15_01_XXX)

    # coverage (only when canonical/procore universes provided)
    if canonical_keys is not None:
        assign, dups = xw.build_budget_assignment(rows, canonical_keys)
        covered = set(assign)
        uncovered = sorted(canonical_keys - covered)
        checks["canonical_budget_coverage_127"] = (len(covered) == len(canonical_keys) == 127 and not uncovered)
        checks["zero_duplicate_covered_budget_codes"] = (len(dups) == 0)
        checks["uncovered_canonical_budget_codes"] = uncovered
    if procore_wbs is not None:
        passign = xw.build_procore_assignment(rows, procore_wbs)
        pcov = set(passign)
        puncov = sorted(procore_wbs - pcov)
        checks["procore_latest_wbs_coverage_42"] = (len(pcov) == len(procore_wbs) == 42 and not puncov)
        checks["uncovered_procore_latest_wbs_codes"] = puncov

    # unresolved owner SOV rows = rows covering nothing
    unresolved = [r.get("crosswalk_id") for r in rows
                  if not (r.get("covered_budget_code_keys") or r.get("covered_procore_wbs_flat_codes"))]
    checks["zero_unresolved_owner_sov_rows"] = (len(unresolved) == 0)

    if missing_fields:
        errors.append({"missing_fields": missing_fields})
    if dup_ids:
        errors.append({"duplicate_crosswalk_ids": dup_ids})
    if bad_alloc_total:
        errors.append({"allocation_total_not_100": bad_alloc_total})

    boolean_checks = [v for v in checks.values() if isinstance(v, bool)]
    passed = all(boolean_checks)
    return OrderedDict([
        ("crosswalk_path", str(crosswalk_path)),
        ("checks", checks),
        ("errors", errors),
        ("passed", passed),
    ])


def _load_universes(context_package: Optional[str]):
    canonical = procore = None
    if context_package:
        cp = Path(context_package)
        bc = cp / "canonical" / "budget_codes.jsonl"
        pl = cp / "canonical" / "procore_latest_subcontractor_invoice_by_budget_code.jsonl"
        if bc.exists():
            canonical = {r["budget_code_key"] for r in read_jsonl(bc)}
        if pl.exists():
            procore = {r["wbs_flat_code"] for r in read_jsonl(pl)}
    return canonical, procore


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Validate the authoritative owner SOV scope crosswalk.")
    ap.add_argument("crosswalk", help="Path to the crosswalk JSONL file.")
    ap.add_argument("--context-package", default=None,
                    help="Optional forecast context package path for full 127/42 coverage checks.")
    args = ap.parse_args(argv)
    canonical, procore = _load_universes(args.context_package)
    report = validate(args.crosswalk, canonical, procore)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
