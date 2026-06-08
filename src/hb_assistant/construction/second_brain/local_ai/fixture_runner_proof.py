"""Phase 10 Prompt 06 — Action candidate fixture-runner proof (advisory, read-only).

Runs the action-candidate fixture suite (:func:`run_fixture_suite`) and proves the load-bearing
guarantees of Prompt 06's batch validation/regression harness:

- every suite fixture's actual outcome matches its declared ``expected_outcome`` (the full matrix);
- the six required schema-validation-failure behaviours are each demonstrated by a fixture:
  invalid JSON rejected, missing required field rejected, stale/forbidden field rejected, a
  high-risk candidate routed to review (and a high-risk *pre-accepted* candidate rejected), no
  candidate accepted without source references, and no raw prompt/response/body persistence;
- a dry-run pass with a real (throwaway) store writes **zero** ``local_model_run_receipts`` rows and
  the 13 no-raw / no-writeback guard columns sum to 0.

The store demonstration runs against a throwaway temp SQLite DB so the ambient app DB is never
touched. The only optional side effect is writing the evidence JSON/MD when ``write_evidence=True``.

Public entry point:
    build_action_candidate_fixture_runner_proof(*, evidence_dir=None, write_evidence=False) -> dict
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .fixture_runner import DEFAULT_SUITE_DIR, run_fixture_suite
from .schema import PHASE_10_GUARD_COLUMNS

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "06-action-candidate-fixture-runner-proof.json"
_PROOF_MD = "06-action-candidate-fixture-runner-proof.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PathPolicy().resolve_repo_root(),
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _by_scenario(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("scenario")): row for row in suite.get("fixtures", [])}


def build_action_candidate_fixture_runner_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Run the fixture suite and prove the Prompt 06 harness guarantees."""
    repo_root = PathPolicy().resolve_repo_root()
    suite_dir = repo_root / DEFAULT_SUITE_DIR

    # 1. Full matrix over the suite (advisory, dry-run, no store).
    suite = run_fixture_suite(fixtures_dir=suite_dir)
    rows = _by_scenario(suite)

    def _is_invalid(scenario: str) -> bool:
        row = rows.get(scenario)
        return row is not None and row.get("status") == "schema_invalid"

    gates: dict[str, bool] = {}
    gates["all_outcomes_matched"] = bool(suite["all_matched"])
    gates["invalid_json_rejected"] = _is_invalid("malformed_json")
    gates["missing_required_field_rejected"] = _is_invalid("missing_required_field")
    gates["stale_forbidden_field_rejected"] = _is_invalid("stale_forbidden_field")
    gates["no_accept_without_source_refs"] = _is_invalid("empty_source_refs")
    # High-risk handling: a valid high-risk candidate routes to review; a pre-accepted one is rejected.
    high_risk = rows.get("high_risk_review")
    gates["high_risk_routed_to_review"] = bool(
        high_risk
        and high_risk.get("status") == "ok"
        and high_risk.get("high_risk_review") is True
        and high_risk.get("high_risk_routing_ok") is True
        and _is_invalid("high_risk_preaccepted")
    )

    # 2. No-raw / no-writeback: a dry-run pass with a real store writes zero receipts; guards sum to 0.
    dry_run_rows = -1
    guard_sum = -1
    raw_absent = False
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p10p06-proof.db")
        store = ConstructionStore(db_path=db)
        run_fixture_suite(fixtures_dir=suite_dir, store=store, dry_run=True)
        receipts = store.list_local_model_run_receipts()
        dry_run_rows = len(receipts)
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        guard_sum = int(
            conn.execute(f"SELECT {expr} FROM local_model_run_receipts").fetchone()[0]
        )
        conn.close()
        # The forbidden-field fixture's placeholder must never reach any persisted row.
        raw_absent = "PLACEHOLDER_REJECTED_NEVER_PERSISTED" not in json.dumps(receipts)

    gates["dry_run_zero_receipts"] = dry_run_rows == 0
    gates["receipt_guards_clean"] = guard_sum == 0
    gates["no_raw_persistence"] = raw_absent

    proof_passed = all(gates.values())
    result: dict[str, Any] = {
        "proof": "phase_10_action_candidate_fixture_runner_proof",
        "command": "second-brain action-intel run-fixtures",
        "phase": "10",
        "prompt": "06",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gates": gates,
        "suite_summary": {
            "fixtures_dir": suite["fixtures_dir"],
            "count": suite["count"],
            "matched_count": suite["matched_count"],
            "by_outcome": suite["by_outcome"],
            "all_matched": suite["all_matched"],
            "high_risk_routing_ok": suite["high_risk_routing_ok"],
        },
        "fixtures": suite["fixtures"],
        "guard_columns": PHASE_10_GUARD_COLUMNS,
        "guard_sum": guard_sum,
        "dry_run_receipt_rows": dry_run_rows,
        "guardrails": {
            "local_only": True,
            "advisory_only": True,
            "dry_run_default": True,
            "schema_validation_required": True,
            "no_raw_persistence": True,
            "no_external_writeback": True,
            "high_stakes_review_only": True,
            "fixtures_isolated_from_ai_jobs_glob": True,
        },
    }
    if write_evidence:
        result["evidence_written"] = _write_evidence(result, evidence_dir)
    return result


def _write_evidence(result: dict[str, Any], evidence_dir: str | None) -> dict[str, str]:
    base = Path(evidence_dir) if evidence_dir else PathPolicy().resolve_repo_root() / EVIDENCE_DIR
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / _PROOF_JSON
    md_path = base / _PROOF_MD
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 10 Prompt 06 — Action Candidate Fixture Runner Proof",
        "",
        f"**Status:** {result['overall_status']} · **proof_passed:** {result['proof_passed']}"
        f" · **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- schema_version: V{result['schema_version']}",
        f"- guard_sum: {result['guard_sum']} (must be 0)",
        f"- dry_run_receipt_rows: {result['dry_run_receipt_rows']} (must be 0)",
        "",
        "## Gates",
        "",
        "| Gate | Pass |",
        "| --- | --- |",
    ]
    for k, v in result["gates"].items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "## Fixture matrix",
        "",
        "| Scenario | Expected | Status | Matched | Low conf | High risk | Routing ok |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for f in result["fixtures"]:
        lines.append(
            f"| {f.get('scenario')} | {f.get('expected_outcome')} | {f.get('status')} |"
            f" {f.get('matched')} | {f.get('low_confidence')} | {f.get('high_risk_review')} |"
            f" {f.get('high_risk_routing_ok')} |"
        )
    lines += [
        "",
        "## Guardrails",
        "",
        "Local-only batch harness; advisory and dry-run (no DB write, no writeback); structured output"
        " validated against ActionCandidate before any (here: zero) write; only SHA-256[:12] hashes are"
        " surfaced (no raw prompt/response/body/URL/token/path); high-stakes items stay review-only; the"
        " 13 no-raw/no-writeback guard columns sum to 0; suite fixtures live in a subdirectory so the"
        " ai_jobs glob never sees the intentionally-invalid fixtures.",
    ]
    return "\n".join(lines) + "\n"
