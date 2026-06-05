"""Phase 09 Prompt 26 — project-specific retrieval benchmarks + coverage reports (advisory).

Scopes the Prompt 25 deterministic/semantic/hybrid retrieval benchmark **per project** and pairs each
with the read-only **corpus-balance coverage mart** (per-allowlisted-family covered/empty/deferred). For
each project enumerated from the approved retrieval corpus it answers "is the retrieval corpus complete,
and does semantic/hybrid add value over the deterministic baseline?".

Pure orchestration over two shipped builders — it adds no new retrieval logic:
  - per-project benchmark: ``benchmark.build_retrieval_benchmark(..., project_key=P)`` (Prompt 25),
    which persists P's project-distinct, metadata-only ``benchmark_runs`` rows iff ``emit_receipt``;
  - per-project coverage: ``corpus_balance_mart.build_corpus_balance_mart(..., project_key=P)``, a
    read-only advisory mart (never persisted).

Projects are enumerated from the deterministic ``RetrievalBroker`` corpus (``RetrievalItem.project_key``).
Coverage is read-only (never persisted), matching the mart convention. ``project_key`` is a non-sensitive
config identifier (kebab-case), emitted in plaintext as the existing marts/snapshots do.

It is an **orchestration leaf**: ``assembles_final_answer`` is always ``False`` and the
``semantic_retrieval_bypassed_policy`` guard stays 0; semantic context never reaches an answer / Research
Packet / Evaluation path from here. Read-only by default (``emit_receipt=False`` persists nothing).
Fail-closed on missing policy or stale schema. No raw query/probe/content/source ref is created or stored
(only hashes, bands, counts, project keys, and family names).

Public entry points:
  build_project_retrieval_benchmarks(db_path=None, *, projects=None, name=None, embed_model=None,
                                     persist_root=None, emit_receipt=False) -> dict
  build_project_retrieval_benchmarks_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval project-benchmark build | proof --json
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..corpus_balance_mart import build_corpus_balance_mart
from ..financial_review_routing import _assert_no_raw
from .benchmark import build_retrieval_benchmark
from .broker import RetrievalBroker

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "project-retrieval-benchmark-proof.json"
_PROOF_MD = "project-retrieval-benchmark-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_project_retrieval_benchmark.seed.yaml"

_BENCHMARK_TABLE = "second_brain_retrieval_benchmark_runs"


class ProjectRetrievalBenchmarkError(RuntimeError):
    """Raised when the project-benchmark builder cannot resolve policy/schema (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with the benchmark table), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise ProjectRetrievalBenchmarkError("schema not ready for project benchmark (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise ProjectRetrievalBenchmarkError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_BENCHMARK_TABLE):
            raise ProjectRetrievalBenchmarkError(
                f"schema not ready for project benchmark (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_project_retrieval_benchmark_contract() -> dict[str, Any]:
    """Load the project-retrieval-benchmark contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("project_retrieval_benchmark_contract")
    if not isinstance(contract, dict) or "benchmark_modes" not in contract:
        raise ProjectRetrievalBenchmarkError(
            "phase 09 project-retrieval-benchmark contract not found or missing required fields"
        )
    return contract


def load_project_retrieval_benchmark_seed() -> dict[str, Any]:
    """Load the resolved project-retrieval-benchmark seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise ProjectRetrievalBenchmarkError(
            f"project-retrieval-benchmark seed not found at {candidate}"
        )
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "default_benchmark_name" not in data:
        raise ProjectRetrievalBenchmarkError(
            f"{candidate} must define the project-retrieval-benchmark policy"
        )
    return data


def _enumerate_projects(db_path: str | None) -> list[str]:
    """Distinct project keys present in the deterministic approved retrieval corpus (read-only)."""
    env = RetrievalBroker(db_path).retrieve(project_key=None, emit_receipt=False)
    return sorted({it.project_key for it in env.items if it.project_key})


def _coverage_report(db_path: str | None, project_key: str) -> dict[str, Any]:
    """Per-project source-family coverage (reuses the read-only corpus-balance mart)."""
    mart = build_corpus_balance_mart(db_path, project_key=project_key)
    empty_reader_backed = list(mart.get("empty_families", []))
    return {
        "covered_family_count": int(mart.get("covered_family_count", 0)),
        "covered_families": list(mart.get("covered_families", [])),
        "empty_families": empty_reader_backed,
        "deferred_families": list(mart.get("deferred_families", [])),
        "dominant_family": mart.get("dominant_family"),
        "total_corpus_rows": int(mart.get("total_corpus_rows", 0)),
        "coverage_complete": not empty_reader_backed,
        "warnings": list(mart.get("warnings", [])),
    }


def build_project_retrieval_benchmarks(
    db_path: str | None = None,
    *,
    projects: tuple[str, ...] | None = None,
    name: str | None = None,
    embed_model: Any | None = None,
    persist_root: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Benchmark + coverage per project over the approved corpus (read-only, fail-closed, advisory).

    Returns a JSON-safe, metadata-only summary (per-project benchmark + coverage report, never raw
    query/content/source ref); persists nothing unless ``emit_receipt`` (then each project's benchmark
    rows are persisted via the Prompt 25 builder). Coverage is read-only (never persisted).
    """
    contract = load_project_retrieval_benchmark_contract()
    seed = load_project_retrieval_benchmark_seed()
    schema_version = _schema_ready(db_path)
    base_name = name or str(
        seed.get("default_benchmark_name", "approved_project_retrieval_benchmark")
    )
    max_projects = int(seed.get("max_projects", 25)) or 25

    available = _enumerate_projects(db_path)
    warnings: list[str] = []
    if projects is not None:
        requested = tuple(projects)
        selected = [p for p in available if p in requested]
        for p in requested:
            if p not in available:
                warnings.append(f"requested_project_absent:{_hash(p)[:16]}")
    else:
        selected = list(available)
    if len(selected) > max_projects:
        warnings.append(f"project_cap_applied:{max_projects}_of_{len(selected)}")
        selected = selected[:max_projects]

    if not selected:
        warnings.append("no_projects")
        return _summary(
            status="empty",
            schema_version=schema_version,
            base_name=base_name,
            projects_count=0,
            per_project=[],
            warnings=warnings,
            seed=seed,
            contract=contract,
            emit_receipt=emit_receipt,
        )

    per_project: list[dict[str, Any]] = []
    for project_key in selected:
        bench = build_retrieval_benchmark(
            db_path,
            project_key=project_key,
            name=f"{base_name}:{project_key}",
            embed_model=embed_model,
            persist_root=persist_root,
            emit_receipt=emit_receipt,
        )
        coverage = _coverage_report(db_path, project_key)
        bench_sem = (bench.get("mode_metrics") or {}).get("semantic", {})
        bench_det = (bench.get("mode_metrics") or {}).get("deterministic", {})
        per_project.append(
            {
                "project_key": project_key,
                "benchmark": {
                    "status": bench["status"],
                    "bench_run_id": bench["bench_run_id"],
                    "probe_count": bench["probe_count"],
                    "metric_row_count": bench["metric_row_count"],
                    "semantic_status": bench_sem.get("status", "n/a"),
                    "hit_rate_pct": bench_sem.get("hit_rate_pct", 0),
                    "deterministic_count": bench_det.get("result_count", 0),
                },
                "coverage": coverage,
            }
        )

    projects_with_semantic = sum(
        1 for p in per_project if p["benchmark"]["semantic_status"] == "available"
    )
    projects_coverage_complete = sum(1 for p in per_project if p["coverage"]["coverage_complete"])
    rollup = {
        "projects_with_semantic_available": projects_with_semantic,
        "projects_coverage_complete": projects_coverage_complete,
        "projects_with_empty_families": sum(
            1 for p in per_project if p["coverage"]["empty_families"]
        ),
    }

    return _summary(
        status="built",
        schema_version=schema_version,
        base_name=base_name,
        projects_count=len(per_project),
        per_project=per_project,
        warnings=warnings,
        seed=seed,
        contract=contract,
        emit_receipt=emit_receipt,
        rollup=rollup,
    )


def _summary(
    *,
    status: str,
    schema_version: int,
    base_name: str,
    projects_count: int,
    per_project: list[dict[str, Any]],
    warnings: list[str],
    seed: dict[str, Any],
    contract: dict[str, Any],
    emit_receipt: bool,
    rollup: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the metadata-only project-benchmark summary (no raw query/content/source ref)."""
    return {
        "command": "second-brain retrieval project-benchmark build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "name_hash": _hash(base_name)[:48],
        "schema_version": schema_version,
        "deterministic_authoritative": True,
        "semantic_advisory_only": True,
        "assembles_final_answer": False,
        "projects_count": projects_count,
        "per_project": per_project,
        "rollup": rollup,
        "warnings": warnings,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }


# --- Proof ---------------------------------------------------------------------------------------


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    return [
        c
        for c in cols
        if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
    ]


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Project-Specific Retrieval Benchmarks + Coverage Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- projects_count: {proof['projects_count']}",
        f"- per_project_benchmarks_persisted: {proof['per_project_benchmarks_persisted']}",
        f"- per_project_coverage_present: {proof['per_project_coverage_present']}",
        f"- rows_persisted_guard_clean: {proof['rows_persisted_guard_clean']}",
        f"- semantic_retrieval_bypassed_policy: {proof['semantic_retrieval_bypassed_policy']} (must be 0)",
        f"- assembles_final_answer: {proof['assembles_final_answer']} (must be false)",
        f"- read_only_default_no_persist: {proof['read_only_default_no_persist']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        f"- coverage_excludes_raw_families: {proof['coverage_excludes_raw_families']}",
        "",
    ]
    return "\n".join(lines)


def build_project_retrieval_benchmarks_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: per-project benchmarks (persisted metadata-only + guard-clean) are paired with
    read-only per-project coverage reports; ≥1 project is enumerated; the read-only default persists
    nothing; coverage never counts raw/excluded families; assembles no answer and no raw is emitted."""
    import tempfile

    from .hybrid_broker import _mock_embed_model
    from .policy import EXCLUDED_FAMILIES
    from .vector_index import _mock_vector_writer, _proof_db, build_vector_index_apply

    _BM_TABLE = _BENCHMARK_TABLE

    with tempfile.TemporaryDirectory() as tmp:
        embed = _mock_embed_model()
        db = _proof_db(tmp)
        persist_root = str(Path(tmp) / "vector_store")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)

        result = build_project_retrieval_benchmarks(
            db,
            name="proof_project_benchmark",
            embed_model=embed,
            persist_root=persist_root,
            emit_receipt=True,
        )

        conn = sqlite3.connect(db)
        try:
            guard_cols = _guard_columns(conn, _BM_TABLE)
            per_project_rows: list[int] = []
            per_project_guard: list[int] = []
            for entry in result["per_project"]:
                run_prefix = f"{entry['benchmark']['bench_run_id']}:%"
                per_project_rows.append(
                    conn.execute(
                        f"SELECT COUNT(*) FROM {_BM_TABLE} WHERE run_id LIKE ?", (run_prefix,)
                    ).fetchone()[0]
                )
                per_project_guard.append(
                    conn.execute(
                        f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_BM_TABLE} "
                        "WHERE run_id LIKE ?",
                        (run_prefix,),
                    ).fetchone()[0]
                )
            bypass_sum = conn.execute(
                f"SELECT COALESCE(SUM(semantic_retrieval_bypassed_policy), 0) FROM {_BM_TABLE}"
            ).fetchone()[0]
        finally:
            conn.close()

        # Read-only default: a second build persists nothing new.
        before = _bench_row_count(db)
        build_project_retrieval_benchmarks(
            db, name="proof_project_benchmark_ro", embed_model=embed, persist_root=persist_root
        )
        read_only_no_persist = _bench_row_count(db) == before

    projects_count = result["projects_count"]
    benchmarks_persisted = projects_count >= 1 and all(n >= 1 for n in per_project_rows)
    coverage_present = all(
        isinstance(e.get("coverage"), dict) and "covered_family_count" in e["coverage"]
        for e in result["per_project"]
    )
    rows_clean = all(int(g or 0) == 0 for g in per_project_guard)
    serialized_summary = json.dumps(result, default=str)
    no_raw_emitted = (
        "probe_text" not in serialized_summary and "text_redacted" not in serialized_summary
    )
    # Coverage never lists an excluded raw family as covered/empty/deferred.
    coverage_excludes_raw = all(
        not (
            EXCLUDED_FAMILIES
            & set(
                e["coverage"]["covered_families"]
                + e["coverage"]["empty_families"]
                + e["coverage"]["deferred_families"]
            )
        )
        for e in result["per_project"]
    )

    proof_passed = (
        result["status"] == "built"
        and projects_count >= 1
        and benchmarks_persisted
        and coverage_present
        and rows_clean
        and int(bypass_sum or 0) == 0
        and result["assembles_final_answer"] is False
        and read_only_no_persist
        and no_raw_emitted
        and coverage_excludes_raw
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_project_retrieval_benchmark",
        "command": "second-brain retrieval project-benchmark proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "projects_count": projects_count,
        "per_project_benchmarks_persisted": benchmarks_persisted,
        "per_project_coverage_present": coverage_present,
        "rows_persisted_guard_clean": rows_clean,
        "semantic_retrieval_bypassed_policy": int(bypass_sum or 0),
        "assembles_final_answer": result["assembles_final_answer"],
        "read_only_default_no_persist": read_only_no_persist,
        "no_raw_emitted": no_raw_emitted,
        "coverage_excludes_raw_families": coverage_excludes_raw,
        "metadata_only": True,
        "guardrails": {
            "deterministic_source_of_truth": True,
            "semantic_advisory_only": True,
            "no_final_answer_assembly": True,
            "no_semantic_retrieval_bypass": True,
            "approved_outputs_only": True,
            "coverage_read_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "project retrieval benchmark proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "project retrieval benchmark proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _bench_row_count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_BENCHMARK_TABLE}").fetchone()[0])
    finally:
        conn.close()
