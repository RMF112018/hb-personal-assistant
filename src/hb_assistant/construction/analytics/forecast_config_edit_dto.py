"""Forecast config-edit validation, file emit/apply, diff, and redaction (Implementation Phase E).

Pure stdlib (no CFR, no FastAPI). The service layer (``forecast_config_edit_service``) does the DB
reads and the CFR ``import → snapshot → materialize → parity`` calls; this module owns:

  - which domains/fields an operator may edit (``forecast_controls`` is deprecated → rejected);
  - emitting a base config file tree from the chosen live snapshot's rows (content-faithful — parity
    compares parsed records, not bytes, so formatting is irrelevant);
  - applying validated edits to that tree (``project`` is a strict whitelist-merge that preserves but
    never exposes the dev-internal fields);
  - a changed-item diff (base vs edited);
  - ``summarize_edit`` — the **redaction-safe** report (no paths/stamps/manifest paths).
"""

from __future__ import annotations

import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks

# Domains an operator may edit. forecast_controls is deprecated (superseded by
# forecast_model_controls) and is rejected — it stays visible/read-only in the viewer.
EDITABLE_DOMAINS = (
    "project",
    "forecast_model_controls",
    "forecast_staffing",
    "owner_sov_crosswalk",
)
DEPRECATED_DOMAINS = ("forecast_controls",)

# project: only these business fields are editable; budget_view_id maps into nested budget_details.
# Everything else in the project JSON (default_data_root, llm, *_package stamps, crosswalk path) is a
# dev-internal that must be preserved on disk but NEVER surfaced.
PROJECT_EDITABLE_KEYS = (
    "project_name",
    "job_reference",
    "forecast_period",
    "materiality_absolute",
    "materiality_percent",
    "budget_amount_field",
    "current_projected_cost_field",
    "budget_view_id",
)
# Money/percent fields that must validate as Decimal strings (never floats).
_PROJECT_MONEY_KEYS = ("materiality_absolute",)
_PROJECT_PERCENT_KEYS = ("materiality_percent",)


class ForecastConfigEditError(RuntimeError):
    """Raised on invalid input / deprecated domain / fail-closed misconfig. Message is path-free."""


# -- item-key derivation (mirrors CFR config_registry._item_key) --------------


def item_key_for(domain: str, obj: dict[str, Any], order: int) -> str:
    if domain == "project":
        return str(obj.get("project_key") or "project")
    if domain == "forecast_model_controls":
        k = obj.get("control_id")
    elif domain == "forecast_staffing":
        sc, tg = obj.get("source_cost_code"), obj.get("target_budget_code_key")
        k = f"{sc}|{tg}" if sc is not None else None
    elif domain == "owner_sov_crosswalk":
        k = obj.get("crosswalk_id")
    else:
        k = None
    return str(k) if k else f"row_{order}"


# -- edit validation ----------------------------------------------------------


def _reject_floats_and_leaks(fields: dict[str, Any]) -> None:
    for key, val in fields.items():
        # Money must be Decimal-as-string; a float silently loses precision (repo rule).
        if isinstance(val, float):
            raise ForecastConfigEditError(f"invalid field {key!r}: numeric values must be strings")
        if find_redaction_leaks({key: val}):
            raise ForecastConfigEditError(f"invalid field {key!r}: value rejected")


def _validate_decimal(key: str, val: Any, *, percent: bool) -> None:
    try:
        d = Decimal(str(val))
    except (InvalidOperation, ValueError) as exc:
        raise ForecastConfigEditError(f"invalid {key!r}: not a decimal") from exc
    if d < 0:
        raise ForecastConfigEditError(f"invalid {key!r}: must be non-negative")
    if percent and d > 100:
        raise ForecastConfigEditError(f"invalid {key!r}: percent must be 0-100")


def validate_edits(edits: Any) -> list[dict[str, Any]]:
    """Return normalized edits or raise ForecastConfigEditError (400-class, path-free)."""
    if not isinstance(edits, list) or not edits:
        raise ForecastConfigEditError("invalid input: edits must be a non-empty list")
    out: list[dict[str, Any]] = []
    for raw in edits:
        if not isinstance(raw, dict):
            raise ForecastConfigEditError("invalid input: each edit must be an object")
        domain = raw.get("domain")
        op = raw.get("op", "modify")
        item_key = raw.get("item_key")
        fields = raw.get("fields")
        if domain in DEPRECATED_DOMAINS:
            raise ForecastConfigEditError(
                "forecast_controls is deprecated and read-only (use forecast_model_controls)"
            )
        if domain not in EDITABLE_DOMAINS:
            raise ForecastConfigEditError(f"invalid input: domain {domain!r} is not editable")
        if op not in ("modify", "add"):
            raise ForecastConfigEditError(f"invalid input: op {op!r} (modify|add only)")
        if not isinstance(item_key, str) or not item_key:
            raise ForecastConfigEditError("invalid input: item_key is required")
        if not isinstance(fields, dict) or not fields:
            raise ForecastConfigEditError("invalid input: fields must be a non-empty object")
        _reject_floats_and_leaks(fields)
        if domain == "project":
            if op != "modify":
                raise ForecastConfigEditError("invalid input: project supports modify only")
            bad = [k for k in fields if k not in PROJECT_EDITABLE_KEYS]
            if bad:
                raise ForecastConfigEditError(f"invalid input: project field(s) not editable: {bad}")
            for k in fields:
                if k in _PROJECT_MONEY_KEYS:
                    _validate_decimal(k, fields[k], percent=False)
                if k in _PROJECT_PERCENT_KEYS:
                    _validate_decimal(k, fields[k], percent=True)
        out.append({"domain": domain, "op": op, "item_key": item_key, "fields": dict(fields)})
    return out


# -- base-tree emit (content-faithful; parity compares parsed records) --------


def emit_base_tree(base_dir: Path, grouped: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
    """Write the base config tree. ``grouped`` maps (rel_path, source_format) -> ordered raw objs."""
    for (rel_path, fmt), objs in grouped.items():
        out = base_dir / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            payload = objs[0] if len(objs) == 1 else objs
            out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        elif fmt == "jsonl":
            out.write_text(
                "".join(json.dumps(o, sort_keys=True) + "\n" for o in objs), encoding="utf-8"
            )
        elif fmt == "csv":
            _write_csv(out, objs)
        else:
            raise ForecastConfigEditError(f"unsupported source_format: {fmt!r}")


def _write_csv(out: Path, objs: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for o in objs:
        for k in o:
            if k not in fieldnames:
                fieldnames.append(k)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=sorted(fieldnames))
        w.writeheader()
        for o in objs:
            w.writerow({k: ("" if o.get(k) is None else o.get(k)) for k in sorted(fieldnames)})


# -- apply edits --------------------------------------------------------------


def apply_edits(edited_dir: Path, edits: list[dict[str, Any]], domain_files: dict[str, str]) -> None:
    """Apply validated edits to the edited tree in place. domain_files maps domain -> primary rel_path."""
    for edit in edits:
        domain = edit["domain"]
        rel = domain_files.get(domain)
        if rel is None:
            raise ForecastConfigEditError(f"invalid input: no config file for domain {domain!r}")
        target = edited_dir / rel
        if domain == "project":
            _apply_project(target, edit["fields"])
        else:
            _apply_jsonl(target, domain, edit)
            _sync_crosswalk_csv(edited_dir, domain, target)


def _apply_project(path: Path, fields: dict[str, Any]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ForecastConfigEditError("project config is not an object")
    for k, v in fields.items():
        if k == "budget_view_id":
            bd = data.get("budget_details")
            if not isinstance(bd, dict):
                bd = {}
                data["budget_details"] = bd
            bd["budget_view_id"] = v
        else:
            data[k] = v
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _apply_jsonl(path: Path, domain: str, edit: dict[str, Any]) -> None:
    objs = _read_jsonl(path)
    target_key = edit["item_key"]
    found = False
    for i, obj in enumerate(objs):
        if item_key_for(domain, obj, i) == target_key:
            obj.update(edit["fields"])
            found = True
            break
    if not found:
        if edit["op"] == "add":
            objs.append(dict(edit["fields"]))
        else:
            raise ForecastConfigEditError(f"unknown item_key {target_key!r} in {domain}")
    path.write_text("".join(json.dumps(o, sort_keys=True) + "\n" for o in objs), encoding="utf-8")


def _sync_crosswalk_csv(edited_dir: Path, domain: str, jsonl_path: Path) -> None:
    """Keep an owner_sov_crosswalk CSV sibling consistent with its (authoritative) JSONL."""
    if domain != "owner_sov_crosswalk":
        return
    csv_sibling = jsonl_path.with_suffix(".csv")
    if csv_sibling.exists():
        _write_csv(csv_sibling, _read_jsonl(jsonl_path))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    objs: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            objs.append(json.loads(line))
    return objs


# -- changed-item diff --------------------------------------------------------


def changed_items(
    base_dir: Path, edited_dir: Path, edits: list[dict[str, Any]], domain_files: dict[str, str]
) -> list[dict[str, Any]]:
    """Business-safe per-item change summary (values only for editable/whitelisted fields)."""
    out: list[dict[str, Any]] = []
    for edit in edits:
        domain, key = edit["domain"], edit["item_key"]
        rel = domain_files[domain]
        before = _load_item(base_dir / rel, domain, key)
        after = _load_item(edited_dir / rel, domain, key)
        changed = sorted(edit["fields"].keys())
        op = "added" if before is None else "modified"
        safe = PROJECT_EDITABLE_KEYS if domain == "project" else None
        values = {
            f: after.get(f) if f != "budget_view_id" else _nested_view_id(after)
            for f in changed
            if (safe is None or f in safe)
        }
        out.append(
            {"domain": domain, "item_key": key, "op": op, "changed_fields": changed, "values": values}
        )
    return out


def _nested_view_id(obj: dict[str, Any]) -> Any:
    bd = obj.get("budget_details")
    return bd.get("budget_view_id") if isinstance(bd, dict) else None


def _load_item(path: Path, domain: str, key: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if domain == "project":
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    for i, obj in enumerate(_read_jsonl(path)):
        if item_key_for(domain, obj, i) == key:
            return obj
    return None


# -- redaction-safe report ----------------------------------------------------


def summarize_parity(parity: dict[str, Any]) -> dict[str, Any]:
    """Map parity output to a path-free shape (domain keys + coded reasons, never paths)."""
    domains = parity.get("domains") if isinstance(parity.get("domains"), dict) else {}
    safe_domains = {
        str(d): {
            "match": bool(v.get("match")),
            "file_count": int(v.get("file_count") or 0),
            "db_count": int(v.get("db_count") or 0),
        }
        for d, v in domains.items()
    }
    # Differences carry materialized abs paths — reduce to the set of domain keys that differ.
    differing = sorted(d for d, v in safe_domains.items() if not v["match"])
    return {
        "status": "pass" if parity.get("status") == "pass" else "fail",
        "domains": dict(sorted(safe_domains.items())),
        "differing_domains": differing,
    }
