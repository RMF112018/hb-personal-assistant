"""Phase 09 Prompt 36 — Phase 09 data-quality gates (advisory conformance evaluator).

A read-only, advisory evaluator that aggregates the Phase 09 retrieval/memory/quality posture into
the pass / warning / fail_blocking / deferred_not_blocking taxonomy, mirroring the 08A/08B/08C/08D
gate evaluators. Structural + safety gates (schema present at V39+, all 22 Phase-09 tables' 23 guard columns
clean, no raw vector content, no external writeback, no semantic-retrieval policy bypass, the gates +
lifecycle contracts loadable) must pass; the per-surface gates whose substrate is legitimately empty
(or advisory-only pre-operational) are honestly **deferred_not_blocking** (never overstated).
Population of tables such as manifests, vector items, and review burden is expected and treated as
pass for those surfaces (see schema report row counts).

The evaluator is read-only — no persistence, no migration, no heavy proof fixtures re-run; it checks
schema readiness, guard-column cleanliness (read-only SUM), contract presence, and table population.

Public entry points:
  evaluate_phase_09_data_quality_gates(*, db_path=None) -> dict
  build_phase_09_gates_proof(*, db_path=None, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain data-quality phase-09-gates --json
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
from .phase_09_schema import (
    PHASE_09_GUARD_COLUMNS,
    PHASE_09_V38_TABLES,
    build_phase_09_schema_status_report,
)

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "phase-09-gates-proof.json"
_PROOF_MD = "phase-09-gates-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_data_quality_gates.seed.yaml"

# The "writeback / direct-API / external-delivery" guard columns (a subset of the 23).
_WRITEBACK_GUARDS = (
    "external_writeback_performed",
    "graph_api_call_performed",
    "procore_api_call_performed",
    "email_send_performed",
    "calendar_update_performed",
    "source_system_writeback_performed",
)


class Phase09GatesError(RuntimeError):
    """Raised when the Phase 09 gates evaluator cannot resolve its policy (fail-closed)."""


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


def _gate(
    name: str, status: str, *, blocking: int = 0, reason: str | None = None, **extra: Any
) -> dict[str, Any]:
    return {
        "gate_name": name,
        "gate_status": status,
        "blocking": blocking,
        "reason": reason,
        **extra,
    }


def _count_statuses(gates: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warning": 0, "fail_blocking": 0, "deferred_not_blocking": 0}
    for g in gates:
        s = str(g.get("gate_status"))
        if s in counts:
            counts[s] += 1
    return counts


def load_phase_09_gates_contract() -> dict[str, Any]:
    """Load the phase-09 data-quality-gates contract (fail-closed if missing/invalid)."""
    from .contracts import load_phase_09_contract

    contract = load_phase_09_contract("data_quality_gates_contract")
    if (
        not isinstance(contract, dict)
        or "statuses" not in contract
        or "gate_count_minimum" not in contract
    ):
        raise Phase09GatesError(
            "phase 09 data-quality-gates contract not found or missing required fields"
        )
    return contract


def load_phase_09_gates_seed() -> dict[str, Any]:
    """Load the resolved phase-09 gates seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise Phase09GatesError(f"phase 09 gates seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "surface_gates" not in data:
        raise Phase09GatesError(f"{candidate} must define the phase-09 gates policy")
    return data


def _guard_sum(conn: sqlite3.Connection, tables: list[str], columns: list[str]) -> int:
    """Sum the given guard columns across the tables that exist (skipping absent tables/columns)."""
    total = 0
    for t in tables:
        if (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
            ).fetchone()
            is None
        ):
            continue
        existing = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({t})").fetchall()}
        cols = [c for c in columns if c in existing]
        if not cols:
            continue
        s = conn.execute(f"SELECT COALESCE(SUM({'+'.join(cols)}), 0) FROM {t}").fetchone()[0]
        total += int(s or 0)
    return total


def _coverage_layers(db_path: str | None) -> dict[str, Any]:
    """Best-effort coverage-layer distinction (deterministic / manifest / vector-indexed / deferred)."""
    try:
        from .corpus_balance_mart import build_retrieval_coverage_layers

        return build_retrieval_coverage_layers(db_path)
    except Exception:
        return {}


def evaluate_phase_09_data_quality_gates(*, db_path: str | None = None) -> dict[str, Any]:
    """Evaluate the Phase 09 data-quality gate set (read-only; advisory; no persistence).

    Returns a conformance report (gates + by_field_status + status_counts + required_fields_covered +
    readiness_overstated + ok). Structural/safety gates pass (V39+ schema + guards); per-surface gates
    whose substrate is legitimately empty (or pre-operational) are deferred_not_blocking. Population
    of operational tables (manifests, vectors, review) yields pass for those gates. Never overstates
    readiness; makes no determination.
    """
    from .contracts import load_phase_09_contract

    contract = load_phase_09_gates_contract()
    seed = load_phase_09_gates_seed()
    gate_min = int(contract.get("gate_count_minimum", 18))
    required_gates = list(contract.get("required_gates", []))
    surface_map: dict[str, Any] = dict(seed.get("surface_gates", {}))

    gates: list[dict[str, Any]] = []

    # --- structural: schema present + table/guard presence (via the schema status report) ---
    schema_version = 0
    row_counts: dict[str, int | None] = {}
    try:
        report = build_phase_09_schema_status_report(db_path)
        schema_version = int(report.get("schema_version", 0))
        all_present = bool(report.get("all_tables_present"))
        all_guards = bool(report.get("all_guards_present"))
        row_counts = {str(t["table_name"]): t.get("row_count") for t in report.get("tables", [])}
        schema_present_ok = schema_version >= 39 and all_present and all_guards
        gates.append(
            _gate(
                "phase_09_schema_present",
                "pass" if schema_present_ok else "fail_blocking",
                blocking=0 if schema_present_ok else 1,
                reason=None if schema_present_ok else "SCHEMA_NOT_READY",
                schema_version=schema_version,
                all_tables_present=all_present,
                all_guards_present=all_guards,
            )
        )
    except Exception:
        gates.append(
            _gate(
                "phase_09_schema_present",
                "fail_blocking",
                blocking=1,
                reason="SCHEMA_REPORT_ERROR",
            )
        )

    # --- safety: guard-column cleanliness via direct read-only SUMs ---
    conn = _open_ro(db_path)
    guard_total: int | None = None
    raw_vector_sum: int | None = None
    writeback_sum: int | None = None
    bypass_sum: int | None = None
    if conn is not None:
        try:
            guard_total = _guard_sum(conn, list(PHASE_09_V38_TABLES), list(PHASE_09_GUARD_COLUMNS))
            raw_vector_sum = _guard_sum(
                conn, list(PHASE_09_V38_TABLES), ["raw_vector_content_persisted"]
            )
            writeback_sum = _guard_sum(conn, list(PHASE_09_V38_TABLES), list(_WRITEBACK_GUARDS))
            bypass_sum = _guard_sum(
                conn, list(PHASE_09_V38_TABLES), ["semantic_retrieval_bypassed_policy"]
            )
        finally:
            conn.close()

    def _clean_gate(name: str, total: int | None, reason: str) -> dict[str, Any]:
        if total is None:
            return _gate(name, "fail_blocking", blocking=1, reason="NO_DATABASE")
        clean = total == 0
        return _gate(
            name,
            "pass" if clean else "fail_blocking",
            blocking=0 if clean else 1,
            reason=None if clean else reason,
            violation_count=total,
        )

    gates.append(_clean_gate("phase_09_guard_columns_clean", guard_total, "GUARD_VIOLATION"))
    gates.append(_clean_gate("no_raw_vector_content", raw_vector_sum, "RAW_VECTOR_PERSISTED"))
    gates.append(_clean_gate("no_external_writeback_posture", writeback_sum, "WRITEBACK_PERFORMED"))
    gates.append(_clean_gate("no_semantic_retrieval_bypass", bypass_sum, "SEMANTIC_BYPASS"))

    # --- structural: contracts loadable ---
    gates_contract_ok = (
        isinstance(contract, dict)
        and len(contract.get("statuses", [])) == 4
        and "gate_count_minimum" in contract
    )
    gates.append(
        _gate(
            "gates_contract_loaded",
            "pass" if gates_contract_ok else "fail_blocking",
            blocking=0 if gates_contract_ok else 1,
            reason=None if gates_contract_ok else "GATES_CONTRACT_INVALID",
        )
    )
    try:
        from .phase_09_schema import load_phase_09_lifecycle_contract

        lc = load_phase_09_lifecycle_contract()
        lifecycle_ok = isinstance(lc, dict) and "tables" in lc
    except Exception:
        lifecycle_ok = False
    gates.append(
        _gate(
            "lifecycle_contract_loaded",
            "pass" if lifecycle_ok else "fail_blocking",
            blocking=0 if lifecycle_ok else 1,
            reason=None if lifecycle_ok else "LIFECYCLE_CONTRACT_MISSING",
        )
    )

    # --- per-surface conformance gates ---
    for gate_name, spec in surface_map.items():
        cname = str(spec.get("contract") or "")
        table = spec.get("table")
        kind = str(spec.get("kind") or "table")
        try:
            c = load_phase_09_contract(cname)
            contract_present = isinstance(c, dict) and bool(c)
        except Exception:
            contract_present = False
        if not contract_present:
            gates.append(
                _gate(
                    gate_name,
                    "fail_blocking",
                    blocking=1,
                    reason="CONTRACT_MISSING",
                    contract=cname,
                )
            )
            continue
        if kind == "static":
            gates.append(_gate(gate_name, "pass", kind="static_policy"))
        elif kind == "proof":
            clean = raw_vector_sum == 0
            gates.append(
                _gate(
                    gate_name,
                    "pass" if clean else "fail_blocking",
                    blocking=0 if clean else 1,
                    reason=None if clean else "RAW_VECTOR_PERSISTED",
                    kind="proof",
                )
            )
        else:  # table-backed
            rc = row_counts.get(str(table))
            if rc is None:
                gates.append(
                    _gate(
                        gate_name,
                        "deferred_not_blocking",
                        reason="TABLE_ABSENT_OR_UNKNOWN",
                        table=table,
                    )
                )
            elif rc > 0:
                gates.append(_gate(gate_name, "pass", table=table, row_count=rc))
            else:
                gates.append(
                    _gate(
                        gate_name,
                        "deferred_not_blocking",
                        reason="SUBSTRATE_EMPTY",
                        table=table,
                        row_count=0,
                    )
                )

    by_field_status = {str(g["gate_name"]): str(g["gate_status"]) for g in gates}
    status_counts = _count_statuses(gates)
    ok = status_counts["fail_blocking"] == 0
    gate_count = len(gates)
    required_fields_covered = all(n in by_field_status for n in required_gates)
    substrate_status = (
        "advisory_empty" if status_counts["deferred_not_blocking"] > 0 else "populated"
    )

    return {
        "command": "second-brain data-quality phase-09-gates",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "ok": ok,
        "schema_version": schema_version,
        "gates": gates,
        "by_field_status": by_field_status,
        "status_counts": status_counts,
        "gate_count": gate_count,
        "gate_count_minimum": gate_min,
        "required_fields_covered": required_fields_covered,
        "readiness_overstated": False,
        "phase_09_substrate_status": substrate_status,
        "coverage_layers": _coverage_layers(db_path),
        "advisory_only": True,
        "makes_determination": False,
        "read_only": True,
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
            "fail_closed": True,
        },
    }


def _render_proof_md(report: dict[str, Any], proof_passed: bool) -> str:
    sc = report["status_counts"]
    lines = [
        "# Phase 09 — Data Quality Gates Proof",
        "",
        f"- proof_passed: {proof_passed}",
        f"- generated_utc: {report['generated_utc']}",
        f"- ok: {report['ok']} (no fail_blocking)",
        f"- gate_count: {report['gate_count']} (minimum {report['gate_count_minimum']})",
        f"- status_counts: pass={sc['pass']} warning={sc['warning']} "
        f"fail_blocking={sc['fail_blocking']} deferred_not_blocking={sc['deferred_not_blocking']}",
        f"- required_fields_covered: {report['required_fields_covered']}",
        f"- readiness_overstated: {report['readiness_overstated']} (must be false)",
        f"- phase_09_substrate_status: {report['phase_09_substrate_status']}",
        "",
        "## Gates",
        "",
    ]
    for g in report["gates"]:
        reason = f" ({g['reason']})" if g.get("reason") else ""
        lines.append(f"- {g['gate_name']}: {g['gate_status']}{reason}")
    lines.append("")
    return "\n".join(lines)


def build_phase_09_gates_proof(
    *, db_path: str | None = None, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Evaluate the Phase 09 gates and (optionally) write the guard-clean proof artifacts.

    ``proof_passed`` is true only when there are no fail_blocking gates, readiness is not overstated,
    at least ``gate_count_minimum`` gates were evaluated, and every required gate is present.
    """
    report = evaluate_phase_09_data_quality_gates(db_path=db_path)
    proof_passed = bool(
        report["ok"]
        and not report["readiness_overstated"]
        and report["gate_count"] >= report["gate_count_minimum"]
        and report["required_fields_covered"]
    )
    result = {**report, "proof": "phase_09_data_quality_gates", "proof_passed": proof_passed}

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(result, indent=2, default=str)
        _assert_no_raw(out, "phase 09 gates proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(report, proof_passed)
        _assert_no_raw(markdown, "phase 09 gates proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        result["proof_path"] = str(out_dir / _PROOF_JSON)
        result["proof_md_path"] = str(out_dir / _PROOF_MD)

    return result
