"""Project TWN cost-forecast JSONL source rows into the three v59 source-domain tables.

``plan_source_domain_projection`` builds planned rows purely from files (no DB access),
so a dry-run never requires the DB to be migrated. ``project_source_domain`` returns that
plan for a dry-run, or writes it inside a single transaction for ``apply`` (idempotent
UPSERTs), and can optionally read the rows back and prove DB↔JSONL parity.

Safety (stronger than Phase 2): ``apply`` requires an explicit ``db_path`` AND refuses any
path that resolves to the live/default DB (``PathPolicy().get_db_path()``); if path
resolution fails, it fails closed rather than risk a live write. The original JSONL row is
stored verbatim in ``raw_json`` and is the authoritative shape for read-parity.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import open_connection, transaction

from . import source_domain_repository as repo
from . import source_reader

GUARDRAILS = {
    "scope": "v59_source_domain_read_parity_only",
    "tables": "forecast_budget_details/cost_entries/monthly_actuals_by_budget_code",
    "external_systems": "read_only",
    "forecast_reads": "file_backed_unchanged",
    "dry_run_touches_db": False,
    "apply_requires_explicit_db_path": True,
    "apply_refuses_live_db": True,
}

_PLAN_KEYS = ("budget_details", "cost_entries", "monthly_actuals")


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cost_entry_id(project_key: str, source_package: str, source_row_number: int) -> str:
    return f"fce-{_hash(f'{project_key}|{source_package}|{source_row_number}')[:32]}"


def _empty_planned() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in _PLAN_KEYS}


def is_live_db_path(db_path: Path) -> bool:
    """True if ``db_path`` resolves to the live/default DB — or if resolution fails.

    Fails closed: an unresolvable path is treated as live so ``apply`` refuses it.
    """
    try:
        live = PathPolicy().get_db_path().resolve()
        return Path(db_path).resolve() == live
    except Exception:
        return True


def plan_source_domain_projection(
    *,
    source_package: Path,
    project_key: str,
    run_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Build planned v59 source-domain rows for a package, purely from files. No DB access."""
    now_utc = now_utc or _now()
    warnings: list[str] = []
    pkg_name = source_reader.package_name_of(source_package)
    planned = _empty_planned()
    source_hashes: dict[str, str | None] = {}
    source_row_counts: dict[str, int] = {}

    for kind in _PLAN_KEYS:
        filename = source_reader.SOURCE_FILES[kind]
        path = source_reader.resolve_source_path(source_package, filename)
        if path is None:
            warnings.append(f"[{kind}] source file not found: {filename}")
            source_hashes[kind] = None
            source_row_counts[kind] = 0
            continue
        sha, used_fallback = source_reader.resolve_source_sha256(path, pkg_name)
        if used_fallback:
            warnings.append(f"[{kind}] file sha unavailable; derived from package|path fallback")
        source_hashes[kind] = sha
        rows = source_reader.read_rows(path)
        source_row_counts[kind] = len(rows)
        builder = _BUILDERS[kind]
        for entry in rows:
            built = builder(
                row=entry["row"],
                source_row_number=entry["source_row_number"],
                project_key=project_key,
                pkg_name=pkg_name,
                source_path=str(path),
                sha=sha,
                run_id=run_id,
                now_utc=now_utc,
                warnings=warnings,
            )
            if built is not None:
                planned[kind].append(built)

    counts = {key: len(rows) for key, rows in planned.items()}
    return {
        "ok": True,
        "project_key": project_key,
        "source_package": pkg_name,
        "source_package_path": str(source_package),
        "run_id": run_id,
        "planned": planned,
        "counts": counts,
        "source_hashes": source_hashes,
        "source_row_counts": source_row_counts,
        "warnings": warnings,
    }


def project_source_domain(
    *,
    source_package: Path,
    project_key: str,
    db_path: Path | None = None,
    apply: bool = False,
    parity: bool = False,
    run_id: str | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Plan (dry-run) or plan+write (apply) source-domain rows; optionally prove DB parity."""
    plan = plan_source_domain_projection(
        source_package=source_package,
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
            "--apply refuses the default live DB; pass --db-path to a temp v59 DB"
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
            project_key=project_key,
            source_package=plan["source_package"],
            planned=plan["planned"],
        )
        if not plan["parity"]["proven"]:
            plan["ok"] = False
    return plan


def _prove_parity(
    *,
    db_path: Path,
    project_key: str,
    source_package: str,
    planned: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Read rows back from the DB and compare (order-independent) to the projected source rows."""
    readers = {
        "budget_details": repo.read_budget_details_from_db,
        "cost_entries": repo.read_cost_entries_from_db,
        "monthly_actuals": repo.read_monthly_actuals_from_db,
    }
    per_table: dict[str, Any] = {}
    proven = True
    with open_connection(db_path) as conn:
        for kind, reader in readers.items():
            db_rows = reader(conn, project_key=project_key, source_package=source_package)
            src_rows = [json.loads(p["raw_json"]) for p in planned.get(kind, [])]
            match = _norm(db_rows) == _norm(src_rows)
            per_table[kind] = {
                "db_rows": len(db_rows),
                "source_rows": len(src_rows),
                "match": match,
            }
            proven = proven and match
    return {"requested": True, "proven": proven, "by_table": per_table}


def _norm(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(json.dumps(r, sort_keys=True, default=str) for r in rows)


# --- per-table planned-row builders -----------------------------------------------------


def _build_budget_detail(
    *, row, source_row_number, project_key, pkg_name, source_path, sha, run_id, now_utc, warnings
):
    key = row.get("budget_code_key")
    if not key:
        warnings.append(
            f"[budget_details] row {source_row_number} missing budget_code_key; skipped"
        )
        return None
    return {
        "project_key": project_key,
        "budget_code_key": key,
        "source_package": pkg_name,
        "cost_code": row.get("cost_code"),
        "category": row.get("category"),
        "source_path": source_path,
        "source_sha256": sha,
        "source_row_number": source_row_number,
        "run_id": run_id,
        "raw_json": json.dumps(row, default=str),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def _build_cost_entry(
    *, row, source_row_number, project_key, pkg_name, source_path, sha, run_id, now_utc, warnings
):
    return {
        "cost_entry_id": _cost_entry_id(project_key, pkg_name, source_row_number),
        "project_key": project_key,
        "source_package": pkg_name,
        "source_row_number": source_row_number,
        "budget_code_key": row.get("budget_code_key"),
        "accounting_month": row.get("accounting_month"),
        "source_path": source_path,
        "source_sha256": sha,
        "run_id": run_id,
        "raw_json": json.dumps(row, default=str),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


def _build_monthly_actual(
    *, row, source_row_number, project_key, pkg_name, source_path, sha, run_id, now_utc, warnings
):
    key = row.get("budget_code_key")
    month = row.get("month")
    rtype = row.get("type")
    if not key or not month or not rtype:
        warnings.append(
            f"[monthly_actuals] row {source_row_number} missing budget_code_key/month/type; skipped"
        )
        return None
    return {
        "project_key": project_key,
        "budget_code_key": key,
        "month": month,
        "type": rtype,
        "source_package": pkg_name,
        "amount": row.get("amount"),
        "entry_count": row.get("entry_count"),
        "source_path": source_path,
        "source_sha256": sha,
        "source_row_number": source_row_number,
        "run_id": run_id,
        "raw_json": json.dumps(row, default=str),
        "created_utc": now_utc,
        "updated_utc": now_utc,
    }


_BUILDERS = {
    "budget_details": _build_budget_detail,
    "cost_entries": _build_cost_entry,
    "monthly_actuals": _build_monthly_actual,
}
