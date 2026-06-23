"""Phase 10 — controlled DB-cutover-readiness evidence (gate only).

Answers ONE question with deterministic, auditable evidence: *is the controlled DB-backed
context→analysis workflow (Phases 6–9) safe for intentional guarded operator use with this explicit
non-live DB and this explicit work root?* It is a **readiness gate**, not a default flip — it changes
no production default, runs no intelligence/comprehensive/model-backed/CSV workflow, and migrates no
new domain.

It owns the preflight safety checks, the temp/non-live v59 DB inspection, the ready/not-ready
decision, and the evidence report. It does NOT duplicate orchestration: it calls the Phase 9 parity
workflow (`run_controlled_context_analysis_parity`) to actually run the file-backed vs DB-backed
chain and compare.

Refusal vs decision:
  - unsafe / missing / ambiguous INPUTS fail closed before anything runs (`DbCutoverReadinessError`);
  - once preflight passes, the workflow runs and the DECISION is data — parity pass →
    ``ready_for_guarded_operator_use``; parity fail → ``not_ready`` (a successful gate outcome, not a
    refusal).

CFR-only / stdlib: the only `hb_assistant` touchpoint is a lazy, fail-closed live-DB check; schema /
table inspection uses stdlib ``sqlite3`` on a strictly read-only connection. Phase 9 behavior is
unchanged.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from ..common.project_eligibility import eligible_projects, is_project_eligible
from .controlled_db_context_analysis import (
    ControlledWorkflowError,
    run_controlled_context_analysis_parity,
    run_controlled_context_analysis_workflow,
)

SUPPORTED_PROJECT_KEY = "tropical"
READINESS_REPORT_SCHEMA_VERSION = 1

# The schema version that introduced the v59 forecast source-domain tables the DB-backed adapter
# reads. Stable even if LATEST_SCHEMA_VERSION later rises; the functional table checks are the gate.
REQUIRED_SCHEMA_VERSION = 59
REQUIRED_SOURCE_DOMAIN_TABLES = (
    "forecast_budget_details",
    "forecast_cost_entries",
    "forecast_monthly_actuals_by_budget_code",
)

READINESS_SUBDIR = "readiness"
READINESS_REPORT_NAME = "db_cutover_readiness_report.json"
DECISION_READY = "ready_for_guarded_operator_use"
DECISION_NOT_READY = "not_ready"

# Controlled-safety guard only (mirrors the generators' default Synology root); NOT an authoritative
# environment resolver. Monkeypatched in tests; the Phase 9 workflow enforces its own (identical)
# guard, this one fails the readiness preflight early.
_LIVE_ROOT = Path(
    "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive-BFmacSync/Work/"
    "NAS - HB/Projects/2023/TWN - NAS/30_Financials/Forecasts/Data/2026-June"
)


class DbCutoverReadinessError(RuntimeError):
    """Raised when a readiness run is rejected by a preflight safety check (fail closed)."""


def _is_under(path: Path, root: Path) -> bool:
    """True when ``path`` equals or is nested under ``root`` (resolved, non-strict)."""
    rp = path.expanduser().resolve(strict=False)
    rr = root.expanduser().resolve(strict=False)
    return rp == rr or rp.is_relative_to(rr)


def _write_json_deterministic(path: Path, obj: dict) -> Path:
    """Write sorted-key, indented JSON with a trailing newline (no wall-clock); return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _refuse_if_live_db(db_path: Path) -> None:
    """Fail closed if ``db_path`` is the live/default DB (or unresolvable).

    Imports the source-domain MODULE lazily and calls ``source_domain_engine.is_live_db_path`` via the
    module reference (not a name bound at import time) so tests can monkeypatch the safety behavior.
    """
    try:
        from hb_assistant.construction.forecast import source_domain_engine
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise DbCutoverReadinessError(
            f"cannot verify db_path against the live DB; hb_assistant unavailable: {exc}"
        ) from exc
    if source_domain_engine.is_live_db_path(Path(db_path)):
        raise DbCutoverReadinessError(
            f"db_path resolves to the live/default DB (or is unresolvable): {db_path}"
        )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (name,)
    ).fetchone()
    return row is not None


def _project_rowcount(conn: sqlite3.Connection, table: str, project_key: str) -> int:
    # ``table`` is only ever one of REQUIRED_SOURCE_DOMAIN_TABLES (module constants), never user input.
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE project_key = ?", (project_key,)
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _inspect_temp_db(db_path: Path, project_key: str) -> dict[str, Any]:
    """Read-only inspection of an explicit temp v59 DB; fail closed on any unmet prerequisite.

    Opens a strictly read-only connection (``mode=ro`` never creates a missing file; the path is
    URL-encoded so spaces are safe). Verifies: readable SQLite; ``schema_migrations`` present;
    ``MAX(version) >= REQUIRED_SCHEMA_VERSION``; each required v59 source-domain table present; each
    has at least one ``project_key='tropical'`` row. Returns the ``db_checks`` evidence block.
    """
    db_path = Path(db_path)
    uri = f"file:{urllib.parse.quote(str(db_path.resolve(strict=False)))}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise DbCutoverReadinessError(
            f"db_path is not a readable SQLite database: {db_path} ({exc})"
        ) from exc
    try:
        try:
            conn.execute("SELECT 1 FROM sqlite_master LIMIT 1")
        except sqlite3.Error as exc:
            raise DbCutoverReadinessError(
                f"db_path is not a readable SQLite database: {db_path} ({exc})"
            ) from exc

        if not _table_exists(conn, "schema_migrations"):
            raise DbCutoverReadinessError(
                f"db_path has no schema_migrations table (cannot determine schema version): {db_path}"
            )
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        schema_version = int(row[0]) if row and row[0] is not None else 0
        if schema_version < REQUIRED_SCHEMA_VERSION:
            raise DbCutoverReadinessError(
                f"db_path schema version {schema_version} is below the required "
                f"{REQUIRED_SCHEMA_VERSION} for DB-backed reads: {db_path}"
            )

        present = {t: _table_exists(conn, t) for t in REQUIRED_SOURCE_DOMAIN_TABLES}
        if not all(present.values()):
            missing = sorted(t for t, ok in present.items() if not ok)
            raise DbCutoverReadinessError(
                f"db_path is missing required v59 source-domain tables {missing}: {db_path}"
            )

        counts = {t: _project_rowcount(conn, t, project_key) for t in REQUIRED_SOURCE_DOMAIN_TABLES}
        if not all(c > 0 for c in counts.values()):
            empty = sorted(t for t, c in counts.items() if c == 0)
            raise DbCutoverReadinessError(
                f"db_path has empty required v59 source-domain tables for "
                f"project_key={project_key!r} {empty}: {db_path}"
            )
    finally:
        conn.close()

    return {
        "db_exists": True,
        "live_db_refused": True,
        "schema_version": schema_version,
        "required_tables_present": True,
        "required_tables_nonempty": True,
    }


def run_db_cutover_readiness(
    *,
    data_root: Path,
    work_root: Path,
    context_stamp: str,
    db_path: Path,
    project_key: str = SUPPORTED_PROJECT_KEY,
    run_parity: bool = True,
) -> dict[str, Any]:
    """Produce deterministic DB-cutover-readiness evidence for the controlled chain.

    Preflight fails closed (``DbCutoverReadinessError``) BEFORE running anything on: non-tropical
    project; missing/non-dir data root; missing work root or a work root under the live forecast root;
    empty context stamp; missing/non-existent db_path; live/default db_path; an unreadable DB or one
    missing ``schema_migrations``, below schema v59, or missing/empty required v59 source-domain
    tables; or a ``<work_root>/readiness`` that already holds output.

    Then runs the Phase 9 parity workflow under ``<work_root>/readiness`` and renders the decision:
    parity ``pass`` → ``ready_for_guarded_operator_use``; parity ``fail`` → ``not_ready``. Returns the
    readiness report dict (plus ``report_path``).
    """
    # --- Preflight (fail closed before any run). --------------------------------------------------
    if not is_project_eligible(project_key):
        raise DbCutoverReadinessError(
            f"project_key {project_key!r} is not eligible; allowed: {sorted(eligible_projects())}"
        )
    if not data_root:
        raise DbCutoverReadinessError("data_root is required for a readiness run")
    data_root = Path(data_root)
    if not data_root.exists() or not data_root.is_dir():
        raise DbCutoverReadinessError(f"data_root not found or not a directory: {data_root}")
    if not work_root:
        raise DbCutoverReadinessError("work_root is required (explicit; no implicit output root)")
    work_root = Path(work_root)
    if _is_under(work_root, _LIVE_ROOT):
        raise DbCutoverReadinessError(
            f"work_root is at/under the live forecast root (refused): {work_root}"
        )
    if not context_stamp:
        raise DbCutoverReadinessError("context_stamp is required (explicit; no latest-glob)")
    if not db_path:
        raise DbCutoverReadinessError("db_path is required (explicit temp/non-live v59 DB)")
    db_path = Path(db_path)
    if not db_path.exists():
        raise DbCutoverReadinessError(f"db_path not found: {db_path}")

    _refuse_if_live_db(db_path)
    db_checks = _inspect_temp_db(db_path, project_key)

    readiness_root = work_root / READINESS_SUBDIR
    if readiness_root.exists() and any(readiness_root.iterdir()):
        raise DbCutoverReadinessError(
            f"readiness work root already contains output (refusing to reuse): {readiness_root}"
        )

    # --- Run the Phase 9 workflow (orchestration reused, never duplicated). -----------------------
    if run_parity:
        try:
            parity = run_controlled_context_analysis_parity(
                data_root=data_root,
                work_root=readiness_root,
                context_stamp=context_stamp,
                db_path=db_path,
                project_key=project_key,
            )
        except ControlledWorkflowError as exc:
            raise DbCutoverReadinessError(
                f"controlled workflow refused during readiness run: {exc}"
            ) from exc
        file_report = json.loads(Path(parity["file_report"]).read_text(encoding="utf-8"))
        db_report = json.loads(Path(parity["db_report"]).read_text(encoding="utf-8"))
        workflow_block = {
            "parity_report": parity["parity_report_path"],
            "file_report": parity["file_report"],
            "db_report": parity["db_report"],
            "file_chain_manifest": file_report["chain_manifest"],
            "db_chain_manifest": db_report["chain_manifest"],
        }
        parity_block = {
            "context_match": parity["context_comparison"]["match"],
            "analysis_match": parity["analysis_comparison"]["match"],
            "chain_match": parity["chain_comparison"]["match"],
        }
        ready = parity["status"] == "pass"
    else:
        try:
            db_only = run_controlled_context_analysis_workflow(
                data_root=data_root,
                work_root=readiness_root,
                context_stamp=context_stamp,
                mode="db",
                db_path=db_path,
                project_key=project_key,
            )
        except ControlledWorkflowError as exc:
            raise DbCutoverReadinessError(
                f"controlled workflow refused during readiness run: {exc}"
            ) from exc
        workflow_block = {
            "parity_report": None,
            "file_report": None,
            "db_report": db_only["report_path"],
            "file_chain_manifest": None,
            "db_chain_manifest": db_only["chain_manifest"],
        }
        # Parity evidence (file vs DB) is required to certify readiness; without it we never go ready.
        parity_block = {"ran": False}
        ready = False

    decision = DECISION_READY if ready else DECISION_NOT_READY
    status = "ready" if ready else "not_ready"

    report = {
        "schema_version": READINESS_REPORT_SCHEMA_VERSION,
        "project_key": project_key,
        "status": status,
        "decision": decision,
        "data_root": str(data_root),
        "work_root": str(work_root),
        "context_stamp": context_stamp,
        "db_path": str(db_path),
        "db_checks": db_checks,
        "workflow": workflow_block,
        "parity": parity_block,
        # Grounded in this controlled run's preflight + explicit-path checks (NOT a global FS audit):
        # the work root is verified outside the live root, and the DB-backed path refuses the live DB.
        "safety": {
            "production_defaults_changed": False,
            "live_root_written": False,
            "live_db_written": False,
        },
    }
    report_path = readiness_root / READINESS_REPORT_NAME
    _write_json_deterministic(report_path, report)
    return {**report, "report_path": str(report_path)}
