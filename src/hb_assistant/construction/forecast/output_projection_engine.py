"""Project a CFR forecast ANALYSIS package's model-run outputs into the v63 tables.

``plan_run_output_projection`` builds planned rows purely from an explicit analysis-package
directory read as plain JSON (no DB access, no CFR import, no latest-glob — explicit path
only), so a dry-run never requires a migrated DB. ``project_run_output`` returns that plan
for a dry-run, or writes it inside a single transaction (idempotent UPSERTs) for ``apply``,
and can optionally read the rows back and prove canonical DB↔package row-equivalence.

Safety (mirrors the v59 source-domain projector): ``apply`` requires an explicit ``db_path``
AND refuses any path that resolves to the live/default DB (``PathPolicy().get_db_path()``);
if path resolution fails, it fails closed rather than risk a live write. The original package
row is stored verbatim in ``raw_json`` and is the authoritative shape for read-parity.

Coverage this phase: the header (``forecast_outputs``), per-code recommendations
(``forecast_output_budget_codes``) from ``forecast_recommendations_by_budget_code.jsonl``, and
the risk register (``forecast_output_risks``) from ``forecast_risk_register.jsonl``. The other
v63 tables ship empty until a follow-on slice.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from . import output_repository as repo
from .source_domain_engine import is_live_db_path  # reuse the fail-closed live-DB guard

GUARDRAILS = {
    "scope": "v63_run_output_projection_only",
    "tables": "forecast_outputs/forecast_output_budget_codes/forecast_output_risks",
    "external_systems": "none",
    "forecast_reads": "file_backed_unchanged",
    "cfr_import": False,
    "dry_run_touches_db": False,
    "apply_requires_explicit_db_path": True,
    "apply_refuses_live_db": True,
}

_PLAN_KEYS = ("outputs", "budget_codes", "risks")

RECOMMENDATIONS_FILE = "forecast_recommendations_by_budget_code.jsonl"
RISK_REGISTER_FILE = "forecast_risk_register.jsonl"
PROJECT_SUMMARY_FILE = "summaries/project_forecast_analysis.json"
MANIFEST_FILE = "manifest.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _output_id(project_key: str, source_package: str) -> str:
    return f"fout-{_hash(f'{project_key}|{source_package}')[:32]}"


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _empty_planned() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in _PLAN_KEYS}


def plan_run_output_projection(
    *,
    analysis_package: Path,
    project_key: str,
    run_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Build planned v63 run-output rows from an explicit analysis package. No DB access."""
    now_utc = now_utc or _now()
    analysis_package = Path(analysis_package)
    warnings: list[str] = []
    planned = _empty_planned()

    if not analysis_package.is_dir():
        return {
            "ok": False,
            "reason": "analysis_package_not_found",
            "project_key": project_key,
            "source_package": analysis_package.name,
            "source_package_path": str(analysis_package),
            "run_id": run_id,
            "planned": planned,
            "counts": {k: 0 for k in _PLAN_KEYS},
            "warnings": [f"analysis package directory not found: {analysis_package}"],
        }

    source_package = analysis_package.name
    output_id = _output_id(project_key, source_package)

    manifest = _read_json(analysis_package / MANIFEST_FILE) or {}
    summary = _read_json(analysis_package / PROJECT_SUMMARY_FILE)
    if summary is None:
        warnings.append(f"{PROJECT_SUMMARY_FILE} not found; header raw_json falls back to manifest")
    header_payload = {"manifest": manifest, "project_summary": summary}
    planned["outputs"].append(
        {
            "output_id": output_id,
            "run_id": run_id,
            "project_key": project_key,
            "source_package": source_package,
            "forecast_period": manifest.get("forecast_period") or manifest.get("stamp"),
            "basis_labels": None,
            "estimated_final_cost": None,
            "forecast_at_completion": None,
            "cost_to_complete": None,
            "variance_to_budget": None,
            "variance_to_prior_forecast": None,
            "source_path": str(analysis_package),
            "source_sha256": None,
            "raw_json": json.dumps(header_payload, sort_keys=True),
            "created_utc": now_utc,
            "updated_utc": now_utc,
        }
    )

    rec_rows = _read_jsonl(analysis_package / RECOMMENDATIONS_FILE)
    if not rec_rows:
        warnings.append(f"{RECOMMENDATIONS_FILE} not found or empty; no budget-code outputs")
    for n, row in enumerate(rec_rows, start=1):
        key = row.get("budget_code_key")
        planned["budget_codes"].append(
            {
                "id": f"fobc-{_hash(f'{output_id}|{key or n}')[:32]}",
                "output_id": output_id,
                "project_key": project_key,
                "budget_code_key": key,
                "cost_code": row.get("cost_code"),
                "category": row.get("category"),
                "forecast_action": row.get("forecast_action"),
                "recommended_projected_cost": row.get("recommended_projected_cost"),
                "recommended_cost_to_complete": row.get("recommended_cost_to_complete"),
                "confidence": row.get("confidence"),
                "source_row_number": n,
                "raw_json": json.dumps(row, sort_keys=True),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    risk_rows = _read_jsonl(analysis_package / RISK_REGISTER_FILE)
    if not risk_rows:
        warnings.append(f"{RISK_REGISTER_FILE} not found or empty; no risk outputs")
    for n, row in enumerate(risk_rows, start=1):
        rid = row.get("risk_id")
        planned["risks"].append(
            {
                "id": f"forsk-{_hash(f'{output_id}|{rid or n}')[:32]}",
                "output_id": output_id,
                "project_key": project_key,
                "risk_id": rid,
                "severity": row.get("severity"),
                "budget_code_key": row.get("budget_code_key"),
                "cost_code": row.get("cost_code"),
                "category": row.get("category"),
                "risk_type": row.get("risk_type"),
                "source_row_number": n,
                "raw_json": json.dumps(row, sort_keys=True),
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    counts = {key: len(rows) for key, rows in planned.items()}
    return {
        "ok": True,
        "project_key": project_key,
        "source_package": source_package,
        "source_package_path": str(analysis_package),
        "output_id": output_id,
        "run_id": run_id,
        "planned": planned,
        "counts": counts,
        "warnings": warnings,
    }


def project_run_output(
    *,
    analysis_package: Path,
    project_key: str,
    db_path: Path | None = None,
    apply: bool = False,
    parity: bool = False,
    run_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Plan (dry-run) or plan+write (apply) run-output rows; optionally prove DB parity."""
    plan = plan_run_output_projection(
        analysis_package=analysis_package,
        project_key=project_key,
        run_id=run_id,
        now_utc=now_utc,
    )
    plan["guardrails"] = GUARDRAILS

    if not apply:
        plan["mode"] = "dry_run"
        if parity:
            # Fail closed: a dry-run wrote nothing, so there is no DB to compare against.
            plan["ok"] = False
            plan["parity"] = {
                "requested": True,
                "proven": False,
                "reason": "parity_requires_applied_db",
            }
            plan["warnings"].append(
                "--parity needs --apply against an explicit temp DB; dry-run proves no DB parity"
            )
        return plan

    if db_path is None:
        plan["mode"] = "apply"
        plan["ok"] = False
        plan["reason"] = "apply_requires_explicit_db_path"
        plan["warnings"].append(
            "--apply refuses the default live DB; pass --db-path to a temp v63 DB"
        )
        return plan

    if is_live_db_path(db_path):
        plan["mode"] = "apply"
        plan["ok"] = False
        plan["reason"] = "apply_refuses_live_db"
        plan["warnings"].append(
            "--db-path resolves to the live/default DB (or could not be resolved); refusing to write"
        )
        return plan

    written: dict[str, int] = dict.fromkeys(_PLAN_KEYS, 0)
    if plan["ok"]:
        with open_connection(Path(db_path)) as conn, transaction(conn):
            written = repo.apply_plan(conn, plan["planned"])
    plan["mode"] = "apply"
    plan["written"] = written

    if parity:
        plan["parity"] = _prove_parity(
            db_path=Path(db_path),
            output_id=plan["output_id"],
            planned=plan["planned"],
        )
        if not plan["parity"]["proven"]:
            plan["ok"] = False
    return plan


def _norm(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(r, sort_keys=True) for r in rows)


def _prove_parity(
    *,
    db_path: Path,
    output_id: str,
    planned: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Read rows back and compare (order-independent) to the projected package rows."""
    readers = {
        "outputs": repo.read_output_header_from_db,
        "budget_codes": repo.read_output_budget_codes_from_db,
        "risks": repo.read_output_risks_from_db,
    }
    per_table: dict[str, Any] = {}
    proven = True
    with open_connection(db_path) as conn:
        for kind, reader in readers.items():
            db_rows = reader(conn, output_id=output_id)
            src_rows = [json.loads(p["raw_json"]) for p in planned.get(kind, [])]
            match = _norm(db_rows) == _norm(src_rows)
            per_table[kind] = {
                "db_rows": len(db_rows),
                "source_rows": len(src_rows),
                "match": match,
            }
            proven = proven and match
    return {"requested": True, "proven": proven, "by_table": per_table}
