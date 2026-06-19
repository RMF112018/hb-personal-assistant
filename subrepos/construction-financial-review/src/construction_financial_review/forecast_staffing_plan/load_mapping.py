"""Load + parse the operator staffing budget-code mapping-override file (fail-closed parsing).

The override file is a project-level JSONL config (in-repo). It records how a source staffing cost code
maps to a canonical ``.LAB`` budget-code key, with acceptance metadata. This module resolves the path
from project config, parses it line-by-line, and reports parse errors, duplicate (cost_code, target)
rows, missing required fields, and per-cost-code allocation shares that exceed 1.0000. It never raises
on content issues — the caller decides whether to fail closed.
"""
from __future__ import annotations

import json
from collections import OrderedDict, defaultdict
from decimal import Decimal
from pathlib import Path

from ..common.config_root import resolve_config_base
from ..common.money import D
from . import staffing_schema as ss

DEFAULT_MAPPING_FILE = "config/forecast_staffing/tropical/staffing_budget_code_mapping.jsonl"


def staffing_config(cfg: dict) -> dict:
    return cfg.get("forecast_staffing_plan") or {}


def mapping_file_path(cfg: dict, subproject_root: Path) -> Path:
    rel = staffing_config(cfg).get("mapping_file") or DEFAULT_MAPPING_FILE
    p = Path(rel)
    # Phase 16: CFR_CONFIG_ROOT (opt-in) overrides the base; unset -> subproject_root (unchanged).
    return p if p.is_absolute() else (resolve_config_base(subproject_root) / rel)


def _parse_lines(path: Path):
    rows, errors = [], []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:  # noqa: BLE001 - record, do not crash
                errors.append(OrderedDict([("line", lineno), ("error", f"json_parse: {e}")]))
                continue
            if not isinstance(obj, dict):
                errors.append(OrderedDict([("line", lineno), ("error", "not_a_json_object")]))
                continue
            rows.append(obj)
    return rows, errors


def load(cfg: dict, subproject_root: Path, stamp_iso: str | None = None) -> "OrderedDict":
    """Return a structured load result. Deterministic: rows sorted by (source_cost_code, target key)."""
    enabled = bool(staffing_config(cfg).get("enabled"))
    path = mapping_file_path(cfg, subproject_root)
    present = path.exists()

    raw_rows, parse_errors = ([], [])
    if present:
        raw_rows, parse_errors = _parse_lines(path)

    seen, duplicates = set(), []
    for r in raw_rows:
        sig = (r.get("project_key"), r.get("source_cost_code"), r.get("target_budget_code_key"))
        if sig in seen:
            duplicates.append(sig[1])
        else:
            seen.add(sig)

    missing_field_rows = []
    for r in raw_rows:
        missing = [f for f in ss.REQUIRED_MAPPING_FIELDS if f not in r or r.get(f) in (None, "")]
        bad_status = r.get("acceptance_status") not in ss.ACCEPTANCE_STATUSES
        if missing or bad_status:
            missing_field_rows.append(OrderedDict([
                ("source_cost_code", r.get("source_cost_code")),
                ("target_budget_code_key", r.get("target_budget_code_key")),
                ("missing_fields", missing), ("invalid_acceptance_status", bad_status)]))

    # per-cost-code accepted allocation share must not exceed 1.0000
    share_by_cc = defaultdict(lambda: Decimal("0"))
    for r in raw_rows:
        if r.get("acceptance_status") == "accepted":
            share_by_cc[r.get("source_cost_code")] += D(r.get("allocation_share") if r.get("allocation_share")
                                                         is not None else "1.0")
    over_allocated = sorted(cc for cc, s in share_by_cc.items() if s > Decimal("1.0001"))

    normalized = [ss.normalize_mapping(r, stamp_iso) for r in raw_rows]
    normalized.sort(key=lambda r: (r.get("source_cost_code") or "", r.get("target_budget_code_key") or ""))

    parse_ok = not parse_errors
    structurally_valid = parse_ok and not duplicates and not missing_field_rows and not over_allocated

    return OrderedDict([
        ("enabled", enabled),
        ("mapping_file", str(path)),
        ("present", present),
        ("row_count", len(normalized)),
        ("rows", normalized),
        ("parse_ok", parse_ok),
        ("parse_errors", parse_errors),
        ("duplicate_cost_codes", sorted(set(duplicates))),
        ("rows_missing_required_fields", missing_field_rows),
        ("over_allocated_cost_codes", over_allocated),
        ("structurally_valid", structurally_valid),
    ])
