"""Load + parse the forecast-model-control file (fail-closed parsing).

The committed control file is a project-level JSONL config (in-repo, dormant by default). A
validation/operator override path may be supplied (``--forecast-model-control-file``) and, when given,
is used instead of the committed file by EVERY consumer — never a silent fallback. This module resolves
the path, parses it line-by-line, and reports parse errors, duplicate control_ids, and missing
required/conditional/acceptance fields. It does NOT raise on content issues — the caller decides whether
to fail closed — so the standalone package can still emit an audit documenting the problem.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from . import control_schema as cs

DEFAULT_CONTROL_FILE = "config/forecast_model_controls/tropical/code_forecast_model_controls.jsonl"


def model_controls_config(cfg: dict) -> dict:
    return cfg.get("forecast_model_controls") or {}


def control_file_path(cfg: dict, subproject_root: Path, override_path: str | Path | None = None) -> Path:
    """Resolve the control file path. An explicit override always wins (no fallback to committed)."""
    rel = override_path or model_controls_config(cfg).get("control_file") or DEFAULT_CONTROL_FILE
    p = Path(rel)
    return p if p.is_absolute() else (Path(subproject_root) / rel)


def _parse_lines(path: Path):
    controls, errors = [], []
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
            controls.append(obj)
    return controls, errors


def _conditional_missing(c: dict) -> list:
    """Required fields that depend on value_constraint_policy / model_type."""
    missing = []
    vc = cs.effective_value_constraint(c)
    mt = cs.effective_model_type(c)
    if vc in cs.REFERENCE_REQUIRED_POLICIES and not c.get("reference_source"):
        missing.append("reference_source")
    if vc in cs.EXPLICIT_AMOUNT_POLICIES and c.get("explicit_value_amount") in (None, ""):
        missing.append("explicit_value_amount")
    if mt == cs.MT_MANUAL_TOTAL:
        has_final = c.get("manual_final_cost") not in (None, "")
        has_rem = c.get("manual_remaining_cost") not in (None, "")
        if has_final == has_rem:  # need exactly one
            missing.append("manual_final_cost_xor_manual_remaining_cost")
    if mt == cs.MT_MANUAL_MONTHLY:
        mmv = c.get("manual_monthly_values")
        if not isinstance(mmv, dict) or not mmv:
            missing.append("manual_monthly_values")
    return missing


def load(cfg: dict, subproject_root: Path, stamp_iso: str | None = None,
         override_path: str | Path | None = None) -> "OrderedDict":
    """Return a structured load result. Deterministic: controls are sorted by control_id."""
    enabled = bool(model_controls_config(cfg).get("enabled"))
    path = control_file_path(cfg, subproject_root, override_path)
    present = path.exists()

    raw_controls, parse_errors = ([], [])
    if present:
        raw_controls, parse_errors = _parse_lines(path)

    seen, duplicate_ids = set(), []
    for c in raw_controls:
        cid = c.get("control_id")
        if cid in seen:
            duplicate_ids.append(cid)
        else:
            seen.add(cid)

    missing_field_controls = []
    for c in raw_controls:
        missing = [f for f in cs.REQUIRED_IDENTITY_FIELDS if f not in c or c.get(f) in (None, "")]
        missing += [f for f in cs.REQUIRED_ACCEPTANCE_FIELDS if f not in c]
        if not c.get("budget_code_key") and not c.get("cost_code"):
            missing.append("budget_code_key_or_cost_code")
        missing += _conditional_missing(c)
        bad_type = c.get("control_type") not in cs.CONTROL_TYPES
        bad_status = c.get("acceptance_status") not in cs.ACCEPTANCE_STATUSES
        bad_start = cs.effective_start_policy(c) not in cs.FORECAST_START_POLICIES
        bad_end = cs.effective_end_policy(c) not in cs.FORECAST_END_POLICIES
        bad_vc = cs.effective_value_constraint(c) not in cs.VALUE_CONSTRAINT_POLICIES
        bad_model = cs.effective_model_type(c) not in cs.MODEL_TYPES
        acc = c.get("acceptance_status") == "accepted"
        missing_acceptance_provenance = acc and (not c.get("accepted_by") or not c.get("accepted_at"))
        if (missing or bad_type or bad_status or bad_start or bad_end or bad_vc or bad_model
                or missing_acceptance_provenance):
            missing_field_controls.append(OrderedDict([
                ("control_id", c.get("control_id")),
                ("missing_fields", missing),
                ("invalid_control_type", bad_type),
                ("invalid_acceptance_status", bad_status),
                ("invalid_start_policy", bad_start),
                ("invalid_end_policy", bad_end),
                ("invalid_value_constraint_policy", bad_vc),
                ("invalid_model_type", bad_model),
                ("missing_acceptance_provenance", missing_acceptance_provenance),
            ]))

    normalized = [cs.normalize_control(c, stamp_iso) for c in raw_controls]
    normalized.sort(key=lambda r: (r.get("control_id") or ""))

    parse_ok = not parse_errors
    structurally_valid = parse_ok and not duplicate_ids and not missing_field_controls

    return OrderedDict([
        ("enabled", enabled),
        ("control_file", str(path)),
        ("control_file_is_override", override_path is not None),
        ("present", present),
        ("control_count", len(normalized)),
        ("controls", normalized),
        ("parse_ok", parse_ok),
        ("parse_errors", parse_errors),
        ("duplicate_control_ids", sorted(set(duplicate_ids))),
        ("controls_missing_required_fields", missing_field_controls),
        ("structurally_valid", structurally_valid),
    ])
