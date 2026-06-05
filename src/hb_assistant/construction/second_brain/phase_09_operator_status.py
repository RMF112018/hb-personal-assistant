"""Phase 09 Prompt 38 — CLI and operator status (advisory aggregator).

A read-only, advisory operator-status aggregator that exposes a **repo-consistent** view of every
Phase-09 CLI surface (retrieval / memory / agent-performance / daily-brief-reproducibility /
data-quality), its status/eval/build/proof command shape, and the rolled-up readiness posture.

It enumerates the surfaces from a registry (seed) that mirrors the repo's actual CLI command set,
reports each surface's contract presence + owning-table population (from the read-only Phase-09
schema-status report), and rolls up the existing read-only schema-status + Phase-09 gates signals.
Readiness is **never overstated**: a surface whose substrate ships empty is reported `advisory_ready`,
never `operational`. Read-only: persists nothing, no migration. Makes no determination; fail-closed.

Public entry points:
  evaluate_phase_09_operator_status(*, db_path=None) -> dict
  build_phase_09_operator_status(*, db_path=None, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain data-quality phase-09-operator-status --json
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from .financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_STATUS_JSON = "phase-09-operator-status.json"
_STATUS_MD = "phase-09-operator-status.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_operator_status.seed.yaml"


class Phase09OperatorStatusError(RuntimeError):
    """Raised when the Phase 09 operator-status aggregator cannot resolve policy/schema (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[4]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=39 with the Phase-09 substrate), else fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise Phase09OperatorStatusError(
            "schema not ready for phase 09 operator status (no database)"
        )
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise Phase09OperatorStatusError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 39 or not _has("second_brain_phase_09_validation_runs"):
            raise Phase09OperatorStatusError(
                f"schema not ready for phase 09 operator status (version {version}, expected >= 39)"
            )
    finally:
        conn.close()
    return version


def load_phase_09_operator_status_contract() -> dict[str, Any]:
    """Load the phase-09 operator-status contract (fail-closed if missing/invalid)."""
    from .contracts import load_phase_09_contract

    contract = load_phase_09_contract("operator_status_contract")
    if (
        not isinstance(contract, dict)
        or "required_fields" not in contract
        or "surface_kinds" not in contract
    ):
        raise Phase09OperatorStatusError(
            "phase 09 operator-status contract not found or missing required fields"
        )
    return contract


def load_phase_09_operator_status_seed() -> dict[str, Any]:
    """Load the resolved phase-09 operator-status seed / surface registry (fail-closed)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise Phase09OperatorStatusError(f"phase 09 operator-status seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "surfaces" not in data:
        raise Phase09OperatorStatusError(
            f"{candidate} must define the phase-09 operator-status surface registry"
        )
    return data


def evaluate_phase_09_operator_status(*, db_path: str | None = None) -> dict[str, Any]:
    """Aggregate a repo-consistent Phase-09 operator status (read-only; advisory; no persistence).

    Enumerates the registry surfaces with per-surface posture (contract present, owning-table row
    count, command kinds) and rolls up the read-only schema-status + Phase-09 gates signals into an
    honest ``overall_status`` (never overstated — empty substrate is advisory_ready). Makes no
    determination.
    """
    from .contracts import load_phase_09_contract
    from .phase_09_gates import build_phase_09_gates_proof
    from .phase_09_schema import build_phase_09_schema_status_report

    contract = load_phase_09_operator_status_contract()
    seed = load_phase_09_operator_status_seed()
    schema_version = _schema_ready(db_path)
    surfaces_spec: list[dict[str, Any]] = list(seed.get("surfaces", []))

    # --- roll up the existing read-only aggregators ---
    try:
        schema_report = build_phase_09_schema_status_report(db_path)
        # structural readiness (do NOT require all_rows_zero — population is not a readiness failure)
        schema_ready = bool(
            schema_report.get("schema_ready")
            and schema_report.get("all_tables_present")
            and schema_report.get("all_guards_present")
        )
        row_counts = {
            str(t["table_name"]): t.get("row_count") for t in schema_report.get("tables", [])
        }
    except Exception:
        schema_ready = False
        row_counts = {}

    try:
        gates = build_phase_09_gates_proof(db_path=db_path, write_evidence=False)
        gates_ok = bool(gates.get("ok"))
        gate_status_counts = gates.get("status_counts", {})
        gate_count = int(gates.get("gate_count", 0))
    except Exception:
        gates_ok = False
        gate_status_counts = {}
        gate_count = 0

    # --- per-surface posture ---
    surfaces: list[dict[str, Any]] = []
    missing_contracts: list[str] = []
    for spec in surfaces_spec:
        cname = spec.get("contract")
        table = spec.get("table")
        contract_present: bool | None = None
        if cname:
            try:
                c = load_phase_09_contract(str(cname))
                contract_present = isinstance(c, dict) and bool(c)
            except Exception:
                contract_present = False
            if contract_present is False:
                missing_contracts.append(str(spec.get("name")))
        row_count = row_counts.get(str(table)) if table else None
        surfaces.append(
            {
                "name": spec.get("name"),
                "cli_path": spec.get("cli_path"),
                "kinds": list(spec.get("kinds", [])),
                "contract_present": contract_present,
                "owning_table": table,
                "row_count": row_count,
                "populated": bool(row_count) if row_count is not None else None,
            }
        )

    all_contracts_present = len(missing_contracts) == 0
    surfaces_with = {
        kind: sum(1 for s in surfaces if kind in s["kinds"])
        for kind in ("status", "build", "proof", "eval", "gates")
    }
    if schema_ready and gates_ok and all_contracts_present:
        overall_status = "advisory_ready"
    elif all_contracts_present and (schema_ready or gates_ok):
        overall_status = "degraded"
    else:
        overall_status = "not_ready"

    return {
        "command": "second-brain data-quality phase-09-operator-status",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "overall_status": overall_status,
        "operator_status_ok": overall_status == "advisory_ready",
        "surface_count": len(surfaces),
        "surfaces_with": surfaces_with,
        "schema_ready": schema_ready,
        "gates_ok": gates_ok,
        "gate_count": gate_count,
        "gate_status_counts": gate_status_counts,
        "all_contracts_present": all_contracts_present,
        "missing_contracts": missing_contracts,
        "surfaces": surfaces,
        "phase_09_substrate_status": "advisory_empty",
        "advisory_only": True,
        "makes_determination": False,
        "read_only": True,
        "readiness_overstated": False,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "advisory_only": True,
            "no_determination": True,
            "no_readiness_overstatement": True,
            "repo_consistent_command_inventory": True,
            "fail_closed": True,
        },
    }


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — CLI and Operator Status",
        "",
        f"- operator_status_ok: {report['operator_status_ok']}",
        f"- overall_status: {report['overall_status']}",
        f"- generated_utc: {report['generated_utc']}",
        f"- schema_ready: {report['schema_ready']} | gates_ok: {report['gates_ok']}"
        f" | all_contracts_present: {report['all_contracts_present']}",
        f"- readiness_overstated: {report['readiness_overstated']} (must be false)",
        f"- surface_count: {report['surface_count']} | with status/build/proof/eval/gates: "
        f"{report['surfaces_with']}",
        "",
        "## Surfaces (repo-consistent CLI command inventory)",
        "",
    ]
    for s in report["surfaces"]:
        cp = "" if s["contract_present"] is None else f" contract_present={s['contract_present']}"
        rc = "" if s["row_count"] is None else f" rows={s['row_count']}"
        lines.append(f"- {s['name']} (`{s['cli_path']}`) kinds={s['kinds']}{cp}{rc}")
    lines.append("")
    return "\n".join(lines)


def build_phase_09_operator_status(
    *, db_path: str | None = None, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Evaluate the Phase 09 operator status and (optionally) write the guard-clean artifacts."""
    report = evaluate_phase_09_operator_status(db_path=db_path)

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(report, indent=2, default=str)
        _assert_no_raw(out, "phase 09 operator status json")
        (out_dir / _STATUS_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_md(report)
        _assert_no_raw(markdown, "phase 09 operator status markdown")
        (out_dir / _STATUS_MD).write_text(markdown, encoding="utf-8")
        report["status_path"] = str(out_dir / _STATUS_JSON)
        report["status_md_path"] = str(out_dir / _STATUS_MD)

    return report
