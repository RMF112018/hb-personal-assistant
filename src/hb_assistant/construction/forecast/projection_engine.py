"""Project a CFR forecast run + packages into the five v58 foundation tables.

``plan_run`` builds the planned rows purely from files (no DB access), so a dry-run
never requires the DB to be migrated. ``project_run`` returns that plan for a dry-run,
or writes it inside a single transaction for ``apply`` (idempotent UPSERTs).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import open_connection, transaction

from . import package_reader, repository, run_reader

GUARDRAILS = {
    "scope": "v58_foundation_lineage_only",
    "domain_rows_projected": False,
    "external_systems": "read_only",
    "forecast_reads": "file_backed_unchanged",
    "dry_run_touches_db": False,
}


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ingestion_id(project_key: str, source_package: str, source_sha256: str) -> str:
    return f"fsi-{_hash(f'{project_key}|{source_package}|{source_sha256}')[:32]}"


def _package_id(project_key: str, package_name: str) -> str:
    return f"fpm-{_hash(f'{project_key}|{package_name}')[:32]}"


def plan_run(
    *,
    subproject_root: Path | None = None,
    project_key: str | None = None,
    run_state_path: Path | None = None,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Build planned v58 rows for a run, purely from files. No DB access.

    Returns a receipt: ``ok``, ``project_key``, ``run_id``, ``planned`` (rows per
    table), ``counts``, ``packages`` (per-package detail), and ``warnings``.
    """
    now_utc = now_utc or _now()
    warnings: list[str] = []

    state = run_reader.resolve_run_state(
        subproject_root=subproject_root, project_key=project_key, run_state_path=run_state_path
    )
    if state is None:
        return {
            "ok": False,
            "project_key": project_key,
            "run_id": None,
            "reason": "no_active_run_state",
            "planned": _empty_planned(),
            "counts": dict.fromkeys(_PLAN_KEYS, 0),
            "packages": [],
            "warnings": [
                "no run_state_path provided and no active current_<project> pointer found"
            ],
        }

    resolved_project = state.get("project_key") or project_key
    run_id = state.get("run_id")
    if not resolved_project or not run_id:
        warnings.append("run-state missing project_key or run_id")

    planned: dict[str, list[dict[str, Any]]] = _empty_planned()
    packages_detail: list[dict[str, Any]] = []

    context_package_name: str | None = None
    project_name: str | None = None
    job_number: str | None = None
    event_seq = 0

    # Deterministic package order: by stamp then ptype, so event_seq is stable across re-runs.
    ordered = sorted(
        state["packages"].items(),
        key=lambda kv: (str(kv[1].get("stamp") or ""), str(kv[0])),
    )

    for ptype, rec in ordered:
        pkg = package_reader.read_package(Path(rec["path"]), package_type=ptype)
        warnings.extend(f"[{ptype}] {w}" for w in pkg.get("warnings", []))
        packages_detail.append(
            {
                "package_type": pkg["package_type"],
                "package_name": pkg["package_name"],
                "present": pkg.get("present", False),
                "source_count": len(pkg.get("sources", [])),
                "validation_event_count": len(pkg.get("validation_events", [])),
            }
        )
        if not pkg.get("present"):
            continue

        if ptype == "context":
            context_package_name = pkg["package_name"]
        # Project identity comes from the manifest project block; take the first that has it
        # (prefer the context package, which always carries it).
        if project_name is None and pkg.get("project_name"):
            project_name = pkg.get("project_name")
        if job_number is None and pkg.get("job_number"):
            job_number = pkg.get("job_number")

        # forecast_package_manifests (1 per package)
        planned["package_manifests"].append(
            {
                "package_id": _package_id(resolved_project or "", pkg["package_name"]),
                "project_key": resolved_project,
                "run_id": run_id,
                "package_type": pkg["package_type"],
                "package_name": pkg["package_name"],
                "package_stamp": pkg.get("package_stamp"),
                "upstream_packages": json.dumps(pkg.get("upstream_packages") or [], default=str),
                "source_data_hashes": json.dumps(pkg.get("source_data_hashes") or {}, default=str),
                "row_counts": json.dumps(pkg.get("row_counts") or {}, default=str),
                "validation_passed": _as_int_bool(pkg.get("validation_passed")),
                "validation_conclusion": pkg.get("validation_conclusion"),
                "file_path": pkg["package_dir"],
                "created_utc": now_utc,
            }
        )

        # forecast_source_ingestions (N per package)
        for src in pkg.get("sources", []):
            sha = src["source_sha256"]
            planned["source_ingestions"].append(
                {
                    "ingestion_id": _ingestion_id(resolved_project or "", pkg["package_name"], sha),
                    "project_key": resolved_project,
                    "run_id": run_id,
                    "source_kind": src["source_kind"],
                    "source_package": pkg["package_name"],
                    "source_path": src["source_path"],
                    "source_sha256": sha,
                    "row_count": src.get("row_count"),
                    "created_utc": now_utc,
                }
            )

        # forecast_validation_events (M per package; monotonic stable event_seq across the run)
        for ev in pkg.get("validation_events", []):
            event_seq += 1
            planned["validation_events"].append(
                {
                    "run_id": run_id,
                    "event_seq": event_seq,
                    "project_key": resolved_project,
                    "gate_name": f"{pkg['package_type']}:{ev['gate_name']}",
                    "status": ev["status"],
                    "detail": ev.get("detail"),
                    "created_utc": now_utc,
                }
            )

    # forecast_projects (1) — identity from the first package that carried a project block.
    if resolved_project:
        planned["projects"].append(
            {
                "project_key": resolved_project,
                "project_name": project_name,
                "job_number": job_number,
                "enabled": 1,
                "created_utc": now_utc,
                "updated_utc": now_utc,
            }
        )

    # forecast_runs (1)
    if run_id and resolved_project:
        planned["runs"].append(
            {
                "run_id": run_id,
                "project_key": resolved_project,
                "context_package": context_package_name,
                "status": "projected",
                "notes": f"phase2 lineage projection; packages={len(planned['package_manifests'])}",
                "created_utc": state.get("run_started_at_utc") or now_utc,
            }
        )

    counts = {key: len(rows) for key, rows in planned.items()}
    return {
        "ok": True,
        "project_key": resolved_project,
        "run_id": run_id,
        "state_path": state.get("state_path"),
        "planned": planned,
        "counts": counts,
        "packages": packages_detail,
        "warnings": warnings,
    }


def project_run(
    *,
    subproject_root: Path | None = None,
    project_key: str | None = None,
    run_state_path: Path | None = None,
    db_path: Path | None = None,
    apply: bool = False,
    now_utc: str | None = None,
) -> dict[str, Any]:
    """Plan (dry-run) or plan+write (apply) a run's lineage into the v58 tables.

    Dry-run (``apply=False``, default) never opens the DB. Apply requires an explicit
    ``db_path`` — Phase 2 refuses to write the default/live DB.
    """
    plan = plan_run(
        subproject_root=subproject_root,
        project_key=project_key,
        run_state_path=run_state_path,
        now_utc=now_utc,
    )
    plan["guardrails"] = GUARDRAILS

    if not apply:
        plan["mode"] = "dry_run"
        return plan

    if db_path is None:
        plan["mode"] = "apply"
        plan["ok"] = False
        plan["reason"] = "apply_requires_explicit_db_path"
        plan["warnings"].append(
            "Phase 2 --apply refuses the default live DB; pass --db-path to a temp v58 DB"
        )
        return plan

    written: dict[str, int] = dict.fromkeys(_PLAN_KEYS, 0)
    if plan["ok"]:
        with open_connection(Path(db_path)) as conn, transaction(conn):
            written = repository.apply_plan(conn, plan["planned"])
    plan["mode"] = "apply"
    plan["written"] = written
    return plan


_PLAN_KEYS = ("projects", "runs", "package_manifests", "source_ingestions", "validation_events")


def _empty_planned() -> dict[str, list[dict[str, Any]]]:
    return {key: [] for key in _PLAN_KEYS}


def _as_int_bool(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if value else 0
