"""Load + parse the operator forecast-control file (fail-closed parsing).

The control file is a project-level JSONL config (in-repo). This module resolves its path from the
project config, parses it line-by-line, and reports parse errors, duplicate control_ids, and missing
human-acceptance fields. It does NOT raise on content issues — the caller (package generator or the
integration gate) decides whether to fail closed — so the standalone package can still emit an audit
that documents the problem.
"""
from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path

from ..common.config_root import resolve_config_base
from . import control_schema as cs

DEFAULT_CONTROL_FILE = "config/forecast_controls/tropical/code_forecast_controls.jsonl"


def controls_config(cfg: dict) -> dict:
    return cfg.get("forecast_controls") or {}


def control_file_path(cfg: dict, subproject_root: Path) -> Path:
    rel = controls_config(cfg).get("control_file") or DEFAULT_CONTROL_FILE
    p = Path(rel)
    # Phase 16: CFR_CONFIG_ROOT (opt-in) overrides the base; unset -> subproject_root (unchanged).
    return p if p.is_absolute() else (resolve_config_base(subproject_root) / rel)


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


def load(cfg: dict, subproject_root: Path, stamp_iso: str | None = None) -> "OrderedDict":
    """Return a structured load result. Deterministic: controls are sorted by control_id."""
    enabled = bool(controls_config(cfg).get("enabled"))
    path = control_file_path(cfg, subproject_root)
    present = path.exists()

    raw_controls, parse_errors = ([], [])
    if present:
        raw_controls, parse_errors = _parse_lines(path)

    # duplicate control_id detection
    seen, duplicate_ids = set(), []
    for c in raw_controls:
        cid = c.get("control_id")
        if cid in seen:
            duplicate_ids.append(cid)
        else:
            seen.add(cid)

    # required-field validation (identity + human-acceptance)
    missing_field_controls = []
    for c in raw_controls:
        missing = [f for f in cs.REQUIRED_IDENTITY_FIELDS if f not in c or c.get(f) in (None, "")]
        missing += [f for f in cs.REQUIRED_ACCEPTANCE_FIELDS if f not in c]
        bad_type = c.get("control_type") not in cs.CONTROL_TYPES
        bad_status = c.get("acceptance_status") not in cs.ACCEPTANCE_STATUSES
        if missing or bad_type or bad_status:
            missing_field_controls.append(OrderedDict([
                ("control_id", c.get("control_id")),
                ("missing_fields", missing),
                ("invalid_control_type", bad_type),
                ("invalid_acceptance_status", bad_status),
            ]))

    normalized = [cs.normalize_control(c, stamp_iso) for c in raw_controls]
    normalized.sort(key=lambda r: (r.get("control_id") or ""))

    parse_ok = not parse_errors
    structurally_valid = parse_ok and not duplicate_ids and not missing_field_controls

    return OrderedDict([
        ("enabled", enabled),
        ("control_file", str(path)),
        ("present", present),
        ("control_count", len(normalized)),
        ("controls", normalized),
        ("parse_ok", parse_ok),
        ("parse_errors", parse_errors),
        ("duplicate_control_ids", sorted(set(duplicate_ids))),
        ("controls_missing_required_fields", missing_field_controls),
        ("structurally_valid", structurally_valid),
    ])
