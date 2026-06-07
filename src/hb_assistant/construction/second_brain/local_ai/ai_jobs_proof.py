"""Phase 10 Prompt 05 — AI job queue + run receipts proof (advisory, read-only output).

Exercises the full job lifecycle on a throwaway temp SQLite DB (no Ollama, no network, the ambient
app DB is never touched) and proves the Prompt 05 guarantees:

- idempotent enqueue (a duplicate is a no-op);
- run `--apply` transitions a job to ``succeeded``, writes an ``ai_job_runs`` row + hash-only
  ``local_model_run_receipts`` rows, and both V41 receipt tables' 13 guard columns sum to 0;
- dry-run writes nothing;
- no-overlap: a held lock blocks a concurrent run;
- retry/backoff: a forced failure increments ``retry_count`` and reaches ``failed`` at
  ``max_retries``, with the backoff window suppressing re-claim;
- environment isolation: dev and production queues are independent.

Public entry point:
    build_ai_jobs_proof(*, evidence_dir=None, write_evidence=False) -> dict
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

from .ai_jobs import enqueue_ai_job_request, run_ai_jobs
from .schema import PHASE_10_GUARD_COLUMNS
from .structured_output import StaticOutputClient

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-10-local-action-intelligence"
_PROOF_JSON = "05-ai-job-queue-and-receipts-proof.json"
_PROOF_MD = "05-ai-job-queue-and-receipts-proof.md"


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


def _guard_sum(db: str, table: str) -> int:
    conn = sqlite3.connect(db)
    expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
    val = conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]
    conn.close()
    return int(val or 0)


def build_ai_jobs_proof(
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = False,
) -> dict[str, Any]:
    """Drive enqueue → run → receipts → retry → no-overlap on a temp DB; prove the guarantees."""
    gates: dict[str, bool] = {}
    counts: dict[str, Any] = {}
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "ai-jobs-proof.db")
        locks = str(Path(td) / "locks")
        store = ConstructionStore(db_path=db)

        # 1. Idempotent enqueue.
        first = enqueue_ai_job_request(
            store=store, job_type="extract_email_tasks", environment="dev", dry_run=False
        )
        dup = enqueue_ai_job_request(
            store=store, job_type="extract_email_tasks", environment="dev", dry_run=False
        )
        gates["enqueue_idempotent"] = (
            first["status"] == "enqueued"
            and dup["status"] == "exists"
            and len(store.list_ai_jobs(environment="dev")) == 1
        )
        gates["invalid_job_type_blocked"] = (
            enqueue_ai_job_request(
                store=store, job_type="not_a_job", environment="dev", dry_run=False
            )["status"]
            == "blocked"
        )

        # 2. Dry-run writes nothing.
        dry = run_ai_jobs(store=store, environment="dev", dry_run=True, locks_dir=locks)
        gates["dry_run_zero_writes"] = (
            dry["status"] == "ok"
            and store.list_ai_jobs(environment="dev")[0]["status"] == "queued"
            and store.list_local_model_run_receipts() == []
        )

        # 3. No-overlap blocks a concurrent run.
        from hb_assistant.construction.second_brain.run_registry import (
            acquire_run_lock,
            release_run_lock,
        )

        held = acquire_run_lock(run_kind="ai_jobs_run", lock_name="ai_jobs_dev", locks_dir=locks)
        blocked = run_ai_jobs(store=store, environment="dev", dry_run=False, locks_dir=locks)
        if held.token:
            release_run_lock(token=held.token, lock_name="ai_jobs_dev", locks_dir=locks)
        gates["no_overlap_blocks"] = (
            blocked["status"] == "blocked" and "run_overlap_blocked" in blocked["blockers"]
        )

        # 4. Apply succeeds + writes hash-only receipts; guard columns sum to 0.
        applied = run_ai_jobs(store=store, environment="dev", dry_run=False, locks_dir=locks)
        receipts = store.list_local_model_run_receipts()
        run_guard = _guard_sum(db, "ai_job_runs")
        receipt_guard = _guard_sum(db, "local_model_run_receipts")
        gates["apply_succeeds"] = (
            applied["status"] == "ok"
            and applied["succeeded"] == 1
            and store.list_ai_jobs(environment="dev")[0]["status"] == "succeeded"
        )
        gates["receipts_written_hash_only"] = bool(receipts) and all(
            len(r["input_context_hash"]) == 12 for r in receipts
        )
        gates["guard_columns_clean"] = run_guard == 0 and receipt_guard == 0
        counts["receipts"] = len(receipts)
        counts["run_count"] = store.ai_job_status_summary(environment="dev")["runs"]["run_count"]

        # 5. Retry/backoff on a fresh failing job.
        enqueue_ai_job_request(
            store=store,
            job_type="extract_email_tasks",
            environment="dev",
            idempotency_key="retry-demo",
            dry_run=False,
        )
        bad = StaticOutputClient(raise_unavailable=True)
        a1 = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks,
            now="2026-06-07T10:00:00+00:00",
        )
        within = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks,
            now="2026-06-07T10:00:10+00:00",
        )
        a2 = run_ai_jobs(
            store=store, environment="dev", dry_run=False, backend=bad, locks_dir=locks,
            now="2026-06-07T10:01:00+00:00",
        )
        retry_job = next(
            j for j in store.list_ai_jobs(environment="dev") if j["idempotency_key"] == "retry-demo"
        )
        gates["retry_then_failed"] = (
            any(r.get("outcome") == "retry_scheduled" for r in a1["results"])
            and within["claimed"] == 0
            and any(r.get("outcome") == "failed" for r in a2["results"])
            and retry_job["status"] == "failed"
            and retry_job["retry_count"] == 2
        )

        # 6. Environment isolation.
        enqueue_ai_job_request(
            store=store, job_type="extract_email_tasks", environment="production", dry_run=False
        )
        gates["environment_isolated"] = (
            len(store.list_ai_jobs(environment="production")) == 1
            and store.list_ai_jobs(environment="production")[0]["status"] == "queued"
        )

    proof_passed = all(gates.values())
    result: dict[str, Any] = {
        "proof": "phase_10_ai_job_queue_and_receipts_proof",
        "command": "second-brain ai-jobs enqueue/status/run (Prompt 05)",
        "phase": "10",
        "prompt": "05",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gates": gates,
        "counts": counts,
        "guard_columns": PHASE_10_GUARD_COLUMNS,
        "guardrails": {
            "local_only": True,
            "no_external_writeback": True,
            "no_raw_persistence": True,
            "receipts_hash_only": True,
            "no_overlap_single_flight": True,
            "retry_with_backoff": True,
            "dry_run_default": True,
            "environment_isolated": True,
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
        "# Phase 10 Prompt 05 — AI Job Queue and Run Receipts Proof",
        "",
        f"**Status:** {result['overall_status']} · **proof_passed:** {result['proof_passed']}"
        f" · **generated_utc:** {result['generated_utc']}",
        "",
        f"- repo_sha: `{result['repo_sha']}`",
        f"- schema_version: V{result['schema_version']}",
        f"- receipts written: {result['counts'].get('receipts')} · run_count: "
        f"{result['counts'].get('run_count')}",
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
        "## Guardrails",
        "",
        "Local-only; idempotent enqueue; no-overlap single-flight via an atomic file lock; retry with"
        " backoff (failed → queued until max_retries → failed); dry-run default (zero writes);"
        " ai_job_runs + local_model_run_receipts carry only hashes/metadata with all 13 no-raw/"
        " no-writeback guard columns summing to 0; dev/production queues isolated by the `environment`"
        " column. Exercised on a throwaway temp DB — the app DB is never mutated.",
    ]
    return "\n".join(lines) + "\n"
