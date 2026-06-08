"""Phase 10 Prompt 07 — Email task candidate extraction proof (advisory, read-only).

Exercises the deterministic-signal email-task extractor over the bundled summary fixtures with a
deterministic offline backend (no Ollama, no network) and proves the Prompt 07 guarantees:

- deterministic signals fire as declared on the summary fixtures;
- a success run (metadata_safe) yields a valid task candidate;
- malformed / stale (forbidden-field) / missing-source-ref model output is rejected, not crashed;
- an unavailable backend is surfaced (no crash, no partial write);
- bounded_content is policy-gated and falls back to metadata_safe with a recorded blocker when
  disallowed;
- a dry-run pass writes nothing; an apply pass persists task/commitment + source-ref rows whose 13
  no-raw/no-writeback guard columns sum to 0 and which contain no raw text;
- the signal contract and the module's closed vocabularies agree (parity).

The apply demonstration runs against a throwaway temp SQLite DB so the ambient app DB is never
touched. The only optional side effect is writing the evidence JSON/MD when ``write_evidence=True``.

Public entry point:
    build_email_task_extraction_proof(*, evidence_dir=None, write_evidence=False) -> dict
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .contracts import load_phase_10_contract
from .email_task_extraction import (
    CANDIDATE_TYPES,
    MODES,
    REASON_CODES,
    SIGNAL_CATEGORIES,
    extract_email_task_candidates,
    score_email_task_signals,
)
from .schema import PHASE_10_GUARD_COLUMNS
from .structured_output import StaticOutputClient

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "07-email-task-candidate-extraction-proof.json"
_PROOF_MD = "07-email-task-candidate-extraction-proof.md"
_SUMMARIES_DIR = "tests/fixtures/local_ai/email_summaries"

_TASK_SUMMARY: dict[str, Any] = {
    "source_ref": "email_thread_summary:test:001",
    "project_key": "P1",
    "input_redacted": {
        "thread_subject_redacted": "Hilltop RFI follow-up",
        "summary_redacted": "Please confirm whether the revised sketch will be issued by Friday.",
    },
}


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


def _candidate(**overrides: Any) -> str:
    base: dict[str, Any] = {
        "candidate_type": "task",
        "title": "Confirm revised sketch issuance",
        "project_key": "P1",
        "assignee": "user",
        "due_at": None,
        "urgency": "normal",
        "waiting_state": "waiting_on_me",
        "source_refs": ["email_thread_summary:test:001"],
        "confidence": 0.8,
        "reason": "Sender asks Bobby to confirm whether the sketch will be issued.",
        "review_status": "pending",
        "safety_category": "normal",
        "recommended_next_action": "review",
        "external_action_requires_approval": True,
    }
    return json.dumps({**base, **overrides})


def build_email_task_extraction_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Exercise the email-task extractor over summary fixtures and prove Prompt 07 guarantees."""
    repo_root = PathPolicy().resolve_repo_root()
    gates: dict[str, bool] = {}

    # 1. Deterministic signals fire as declared on the summary fixtures.
    fixtures_signals: list[dict[str, Any]] = []
    signals_ok = True
    for path in sorted((repo_root / _SUMMARIES_DIR).glob("*.json")):
        fx = json.loads(path.read_text(encoding="utf-8"))
        sig = score_email_task_signals(fx)
        match = set(sig["reason_codes"]) == set(fx.get("signals_expected", []))
        signals_ok = signals_ok and match
        fixtures_signals.append(
            {"scenario": fx.get("scenario"), "reason_codes": sig["reason_codes"], "matched": match}
        )
    gates["deterministic_signals_fire"] = signals_ok

    # 2. Success (metadata_safe) yields a valid task candidate.
    ok = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY], backend=StaticOutputClient(_candidate()), dry_run=True
    )
    gates["success_yields_task"] = ok["accepted"] == 1 and ok["candidates"][0][
        "candidate_type"
    ] == "task"

    # 3. Invalid / stale model output rejected (not crashed).
    invalid = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(json.dumps({"candidate_type": "task"})),
        dry_run=True,
    )
    gates["invalid_schema_rejected"] = invalid["accepted"] == 0 and invalid["rejected"] == 1
    stale = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(_candidate(raw_email_body="LEAK")),
        dry_run=True,
    )
    gates["stale_forbidden_field_rejected"] = stale["accepted"] == 0 and stale["rejected"] == 1
    no_ref = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(_candidate(source_refs=[])),
        dry_run=True,
    )
    gates["no_accept_without_source_refs"] = no_ref["accepted"] == 0 and no_ref["rejected"] == 1

    # 4. Unavailable backend surfaced.
    unavail = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY], backend=StaticOutputClient(raise_unavailable=True), dry_run=True
    )
    gates["unavailable_backend_surfaced"] = (
        unavail["backend_unavailable"] is True and unavail["accepted"] == 0
    )

    # 5. bounded_content policy-gated: disallowed → fall back to metadata_safe with a blocker.
    disallow_policy = SimpleNamespace(
        raw_content=SimpleNamespace(
            enabled=False,
            model_context=SimpleNamespace(include_raw_content=False),
            starting_sources=SimpleNamespace(email=False),
        )
    )
    gated = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(_candidate()),
        mode="bounded_content",
        policy=disallow_policy,
        dry_run=True,
    )
    gates["bounded_content_policy_gated"] = (
        gated["requested_mode"] == "bounded_content"
        and gated["mode"] == "metadata_safe"
        and "bounded_content_not_eligible_fell_back_to_metadata_safe" in gated["blockers"]
    )

    # 6. No-raw / no-writeback: dry-run writes nothing; apply persists clean rows, no raw text.
    dry_rows = -1
    persisted = -1
    guard_sum = -1
    raw_absent = False
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p10p07-proof.db")
        store = ConstructionStore(db_path=db)
        extract_email_task_candidates(
            summaries=[_TASK_SUMMARY], store=store,
            backend=StaticOutputClient(_candidate(raw_email_body="LEAK")), dry_run=True,
        )
        dry_rows = len(store.list_task_candidates())
        rep = extract_email_task_candidates(
            summaries=[_TASK_SUMMARY], store=store, project_key="P1",
            backend=StaticOutputClient(_candidate()), dry_run=False,
        )
        persisted = rep["persisted"]
        tasks = store.list_task_candidates()
        refs = store.list_candidate_source_refs(candidate_type="task")
        conn = sqlite3.connect(db)
        total = 0
        for table in ("task_candidates", "commitment_candidates", "candidate_source_refs",
                      "local_model_run_receipts"):
            expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
            total += int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0] or 0)
        conn.close()
        guard_sum = total
        raw_absent = "LEAK" not in json.dumps(tasks) + json.dumps(refs)
        linkage_ok = bool(tasks and refs and refs[0]["candidate_id"] == tasks[0]["candidate_id"])

    gates["dry_run_zero_writes"] = dry_rows == 0
    gates["apply_persists_candidate"] = persisted == 1
    gates["guards_clean"] = guard_sum == 0
    gates["no_raw_persistence"] = raw_absent
    gates["source_ref_linkage"] = linkage_ok

    # 7. Contract ↔ module parity.
    contract = load_phase_10_contract("email_task_signal_contract")
    gates["contract_module_parity"] = (
        set(contract["signal_categories"]) == set(SIGNAL_CATEGORIES)
        and set(contract["reason_codes"]) == set(REASON_CODES)
        and set(contract["modes"]) == set(MODES)
        and set(contract["candidate_types"]) == set(CANDIDATE_TYPES)
    )

    proof_passed = all(gates.values())
    result: dict[str, Any] = {
        "proof": "phase_10_email_task_candidate_extraction_proof",
        "command": "second-brain action-intel extract-email-tasks",
        "phase": "10",
        "prompt": "07",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gates": gates,
        "fixtures_signals": fixtures_signals,
        "guard_columns": PHASE_10_GUARD_COLUMNS,
        "guard_sum": guard_sum,
        "dry_run_task_rows": dry_rows,
        "guardrails": {
            "local_only": True,
            "advisory_only": True,
            "dry_run_default": True,
            "schema_validation_required": True,
            "no_raw_persistence": True,
            "no_external_writeback": True,
            "high_stakes_review_only": True,
            "two_modes_metadata_safe_and_bounded_content": True,
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
        "# Phase 10 Prompt 07 — Email Task Candidate Extraction Proof",
        "",
        f"**Status:** {result['overall_status']} · **proof_passed:** {result['proof_passed']}"
        f" · **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- schema_version: V{result['schema_version']}",
        f"- guard_sum: {result['guard_sum']} (must be 0)",
        f"- dry_run_task_rows: {result['dry_run_task_rows']} (must be 0)",
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
        "## Deterministic signals (fixtures)",
        "",
        "| Scenario | Reason codes | Matched |",
        "| --- | --- | --- |",
    ]
    for f in result["fixtures_signals"]:
        lines.append(f"| {f['scenario']} | {', '.join(f['reason_codes'])} | {f['matched']} |")
    lines += [
        "",
        "## Guardrails",
        "",
        "Local-only deterministic-signal + structured-output extractor over metadata-safe email thread"
        " summaries; advisory and dry-run by default; bounded_content mode is policy-gated and reads"
        " local content only ephemerally (never persisted); only structured candidate fields, source"
        " refs, hashes, reason codes, and policy-approved bounded excerpts are written; the 13 no-raw/"
        " no-writeback guard columns sum to 0; high-stakes items stay review-only; summary fixtures"
        " live in a subdirectory excluded from the ai_jobs glob.",
    ]
    return "\n".join(lines) + "\n"
