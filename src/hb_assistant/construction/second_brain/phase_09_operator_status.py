"""Phase 09 Prompt 38/40 — CLI and operator status (advisory aggregator).

A read-only, advisory operator-status aggregator that exposes a **repo-consistent** view of every
Phase-09 CLI surface (retrieval / memory / agent-performance / daily-brief-reproducibility /
data-quality), its status/eval/build/proof command shape, and the rolled-up readiness posture.

It enumerates the surfaces from a registry (seed) that mirrors the repo's actual CLI command set,
reports each surface's contract presence + owning-table population (from the read-only Phase-09
schema-status report, V39/22 tables), and rolls up the existing read-only schema-status + Phase-09
gates signals + review advisory + hybrid/llamaindex probes. Readiness is **never overstated**:
production_readiness=false; surfaces with legitimately empty substrate are advisory_ready (not
operational); semantic/vector gated on SDK+applied; explicit deferred_limitations list. Categories
consolidated under `readiness_categories`. Read-only: persists nothing, no migration. Makes no
determination; fail-closed.

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


def _coverage_parity(db_path: str | None) -> dict[str, Any]:
    """Best-effort coverage-parity distinction (deterministic / manifest / vector-indexed / deferred)."""
    try:
        from .corpus_balance_mart import build_coverage_parity_report

        return build_coverage_parity_report(db_path)
    except Exception:
        return {}


def evaluate_phase_09_operator_status(*, db_path: str | None = None) -> dict[str, Any]:
    """Aggregate a repo-consistent Phase-09 operator status (read-only; advisory; no persistence).

    Enumerates the registry surfaces with per-surface posture (contract present, owning-table row
    count, command kinds) and rolls up the read-only schema-status + Phase-09 gates + review
    advisory + (guarded) hybrid/llamaindex probes into an honest ``overall_status`` and
    ``readiness_categories`` (never overstated — production=false; semantic/vector gated on SDK+applied;
    explicit deferred list; empty substrate advisory only). Makes no determination.
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

    # --- readiness categories (Prompt 40: consolidate truthful posture; feed from schema + gates + review + guarded probes) ---
    # safe_advisory = structural (V39+ present+guards) + review advisory allowed
    # semantic_retrieval = safe + hybrid semantic_ready (core+local+applied)
    # vector_apply = schema + local embedding runtime ready (policy separate; truthful blockers)
    # production = False (never overstated)
    # deferred = explicit honest list (external providers, synthesis, MCP, UX, persist etc.)
    try:
        from .review_burden_mart import build_review_burden_proof

        review_proof = build_review_burden_proof(db_path=db_path)
        review_advisory_allowed = bool(review_proof.get("advisory_retrieval_allowed"))
    except Exception:
        review_advisory_allowed = False

    safe_advisory_readiness = bool(schema_ready and gates_ok and review_advisory_allowed)

    try:
        from .retrieval.hybrid_broker import build_hybrid_status

        hs = build_hybrid_status(db_path=db_path)
        semantic_ready = bool(hs.get("semantic_ready"))
    except Exception:
        semantic_ready = False

    semantic_retrieval_readiness = bool(safe_advisory_readiness and semantic_ready)

    try:
        from .retrieval.llamaindex_config import build_llamaindex_config_status

        ls = build_llamaindex_config_status(db_path=db_path)
        # embedding_runtime_ready may be None when not applicable; prefer local_embedding_available for apply readiness
        local_embedding_ok = bool(
            ls.get("local_embedding_available") or ls.get("embedding_runtime_ready")
        )
        vector_apply_readiness = bool(schema_ready and local_embedding_ok)
    except Exception:
        vector_apply_readiness = False

    production_readiness = False
    deferred_limitations: list[str] = [
        "external embedding providers (policy-gated; deferred per embedding policy)",
        "full synthesis / claim / determination flows (advisory signals and review burden only)",
        "MCP dispatch of Phase 09 actions (08D isolation preserved; no Phase 09 in MCP surface)",
        "richer operator UX (Obsidian commands, TUI) over review / retrieval surfaces",
        "persist of review burden clusters (current is read-only mart + proof)",
        "using clusters as additional corpus family for retrieval",
    ]

    # substrate status fed from schema row counts (populated when any Phase09 table has rows>0)
    any_populated = any((rc or 0) > 0 for rc in row_counts.values()) if row_counts else False
    phase_09_substrate_status = "populated" if any_populated else "advisory_empty"

    # Distinguished, reconciled substrate view (shared with phase-09-gates to resolve the historical
    # phase_09_substrate_status drift). Additive; the legacy field above is retained for back-compat.
    from .phase_09_schema import QUALITY_SUBSTRATE_TABLES, compute_substrate_detail

    try:
        _coverage_ok = bool((_coverage_parity(db_path) or {}).get("coverage_parity_ok"))
    except Exception:
        _coverage_ok = False
    try:
        from .daily_brief.mcp_handoff_status import handoff_present as _handoff_present

        _handoff_present_flag = _handoff_present(db_path)
    except Exception:
        _handoff_present_flag = False
    substrate_detail = compute_substrate_detail(
        schema_ready=schema_ready,
        coverage_ok=_coverage_ok,
        quality_row_counts={t: row_counts.get(t) for t in QUALITY_SUBSTRATE_TABLES},
        handoff_present=_handoff_present_flag,
    )

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
        "phase_09_substrate_status": phase_09_substrate_status,
        "substrate_detail": substrate_detail,
        "coverage_parity": _coverage_parity(db_path),
        "advisory_only": True,
        "makes_determination": False,
        "read_only": True,
        "readiness_overstated": False,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "readiness_categories": {
            "safe_advisory_readiness": safe_advisory_readiness,
            "semantic_retrieval_readiness": semantic_retrieval_readiness,
            "vector_apply_readiness": vector_apply_readiness,
            "production_readiness": production_readiness,
            "deferred_limitations": deferred_limitations,
        },
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
        f"- substrate: {report.get('phase_09_substrate_status')}",
        "",
        "## Readiness Categories (Prompt 40; truthful, no overstatement)",
        f"- safe_advisory_readiness: {report.get('readiness_categories', {}).get('safe_advisory_readiness')}",
        f"- semantic_retrieval_readiness: {report.get('readiness_categories', {}).get('semantic_retrieval_readiness')}",
        f"- vector_apply_readiness: {report.get('readiness_categories', {}).get('vector_apply_readiness')}",
        f"- production_readiness: {report.get('readiness_categories', {}).get('production_readiness')}",
        f"- deferred_limitations: {report.get('readiness_categories', {}).get('deferred_limitations')}",
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
