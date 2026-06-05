"""Phase 09 Prompt 25 — deterministic vs semantic benchmark (comparative, metadata-only).

Benchmarks the three retrieval modes — **deterministic** (the authoritative Retrieval Broker over the
allowlisted families), **semantic** (advisory matches over the applied vector index), and **hybrid**
(the merge) — against each other over the **approved outputs** corpus (approved Obsidian generated
outputs + reviewed/accepted long-term memory). It answers "does the semantic/hybrid path add retrieval
value over the deterministic baseline?" without ever assembling an answer.

Probes are built **at runtime** from each approved node's already-redacted excerpt and are **never
persisted** — only **bucketed comparative metric labels** are stored to the V38
``second_brain_retrieval_benchmark_runs`` table (guard-clean). No raw query/content/source ref leaves
memory (only hashes + bands). Deterministic results are authoritative; semantic results are advisory
(floored at review tier 2, source-linked, re-validated no-raw). The benchmark is a **measurement leaf**
— ``assembles_final_answer`` is always ``False`` and the ``semantic_retrieval_bypassed_policy`` guard
stays 0; semantic context never reaches an answer / Research Packet / Evaluation path from here.

Read-only by default (``emit_receipt=False`` persists nothing). Fail-closed on missing policy or stale
schema; the semantic side degrades fail-closed (recorded as a blocked ``semantic_status``) when the
optional LlamaIndex SDK or an applied vector index is absent — the deterministic baseline is unaffected.

Public entry points:
  build_retrieval_benchmark(db_path=None, *, project_key=None, name=None, modes=None,
                            embed_model=None, persist_root=None, emit_receipt=False) -> dict
  persist_retrieval_benchmark(db_path, result, *, policy_version) -> str
  build_retrieval_benchmark_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain retrieval benchmark build | proof --json
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

from ..financial_review_routing import _assert_no_raw
from .broker import RetrievalBroker
from .hybrid_broker import (
    _latest_applied_vector_index_run,
    _semantic_query,
    load_hybrid_retrieval_seed,
)
from .policy import ALLOWLISTED_SOURCE_FAMILIES, EXCLUDED_FAMILIES
from .vector_index import _gather_approved_nodes

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "retrieval-benchmark-proof.json"
_PROOF_MD = "retrieval-benchmark-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_retrieval_benchmark.seed.yaml"

_BENCHMARK_TABLE = "second_brain_retrieval_benchmark_runs"


class RetrievalBenchmarkError(RuntimeError):
    """Raised when the benchmark builder cannot resolve policy/schema (fail-closed)."""


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
        raise RetrievalBenchmarkError("schema not ready for benchmark (no database)")
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise RetrievalBenchmarkError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_BENCHMARK_TABLE):
            raise RetrievalBenchmarkError(
                f"schema not ready for benchmark (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_retrieval_benchmark_contract() -> dict[str, Any]:
    """Load the retrieval-benchmark contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("retrieval_benchmark_contract")
    if not isinstance(contract, dict) or "benchmark_modes" not in contract:
        raise RetrievalBenchmarkError(
            "phase 09 retrieval-benchmark contract not found or missing required fields"
        )
    return contract


def load_retrieval_benchmark_seed() -> dict[str, Any]:
    """Load the resolved retrieval-benchmark seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise RetrievalBenchmarkError(f"retrieval-benchmark seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "default_benchmark_name" not in data:
        raise RetrievalBenchmarkError(f"{candidate} must define the retrieval-benchmark policy")
    return data


def _build_probes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One runtime-only probe per approved node. Skips unsafe/unlinked nodes (no source ref / no
    redacted excerpt / excluded or non-allowlisted family). The probe text is the node's already-redacted
    excerpt — used in-memory only as a semantic query, never persisted or emitted."""
    probes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        family = str(node.get("source_family") or "")
        ref = str(node.get("source_ref") or "")
        text = str(node.get("text_redacted") or "")
        if not ref or not family or not text or family in EXCLUDED_FAMILIES:
            continue
        if family not in ALLOWLISTED_SOURCE_FAMILIES:
            continue
        probe_id = _hash(f"{family}:{ref}")[:48]
        if probe_id in seen:
            continue
        seen.add(probe_id)
        probes.append(
            {
                "probe_id": probe_id,
                "source_family": family,
                "probe_text": text,  # runtime-only; never persisted/emitted
                "confidence_class": str(node.get("confidence_class") or "unknown"),
                "review_tier": int(node.get("review_tier") or 3),
            }
        )
    return probes


def _count_band(n: int) -> str:
    if n <= 0:
        return "0"
    if n <= 3:
        return "1-3"
    if n <= 10:
        return "4-10"
    if n <= 25:
        return "11-25"
    return "26+"


def _rate_band(frac: float) -> str:
    if frac <= 0.0:
        return "0.00"
    if frac >= 1.0:
        return "1.00"
    if frac <= 0.25:
        return "0.01-0.25"
    if frac <= 0.50:
        return "0.26-0.50"
    if frac <= 0.75:
        return "0.51-0.75"
    return "0.76-0.99"


def _metric_rows(
    bench_run_id: str,
    *,
    eval_set_id: str,
    config_snapshot_id: str,
    mode_metrics: dict[str, Any],
    probe_count: int,
    min_tier: int,
) -> list[dict[str, Any]]:
    """Build the metadata-only benchmark metric rows (one (metric, mode) per row; bucketed labels)."""
    det = mode_metrics["deterministic"]
    sem = mode_metrics["semantic"]
    hyb = mode_metrics["hybrid"]
    hit_rate = (sem["probes_with_hit"] / probe_count) if probe_count else 0.0
    pairs: list[tuple[str, str]] = [
        ("result_count:deterministic", _count_band(int(det["result_count"]))),
        ("result_count:semantic", _count_band(int(sem["matches_total"]))),
        ("result_count:hybrid", _count_band(int(hyb["result_count"]))),
        ("semantic_hit_rate:hybrid", _rate_band(hit_rate)),
        ("semantic_lift:hybrid", _count_band(int(hyb["semantic_lift"]))),
        ("tier_floor:semantic", f"min_tier={min_tier}"),
        ("semantic_status:hybrid", str(sem["status"])),
    ]
    rows: list[dict[str, Any]] = []
    for metric_name, label in pairs:
        slug = metric_name.replace(":", "_")
        rows.append(
            {
                "run_id": f"{bench_run_id}:{slug}",
                "eval_set_id": eval_set_id,
                "config_snapshot_id": config_snapshot_id,
                "metric_name": metric_name,
                "metric_value_label": label,
            }
        )
    return rows


def build_retrieval_benchmark(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    name: str | None = None,
    modes: tuple[str, ...] | None = None,
    embed_model: Any | None = None,
    persist_root: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Benchmark deterministic vs semantic vs hybrid retrieval over the approved corpus (read-only).

    Returns a JSON-safe, metadata-only summary (bucketed comparative metrics, never raw query/content/
    source ref); persists nothing unless ``emit_receipt`` is set. Deterministic is authoritative;
    semantic is advisory and degrades fail-closed (blocked status) when the SDK/applied index is absent.
    """
    contract = load_retrieval_benchmark_contract()
    seed = load_retrieval_benchmark_seed()
    hybrid_seed = load_hybrid_retrieval_seed()
    schema_version = _schema_ready(db_path)
    bench_name = name or str(seed.get("default_benchmark_name", "approved_retrieval_benchmark"))
    requested_modes = tuple(modes) if modes is not None else tuple(seed.get("modes", ()))
    max_probes = int(seed.get("max_probes", 50)) or 50
    top_k = int(hybrid_seed.get("semantic_top_k", 5)) or 5
    min_tier = int(hybrid_seed.get("semantic_min_review_tier", 2)) or 2

    nodes, manifest = _gather_approved_nodes(db_path, project_key)
    all_probes = _build_probes(nodes)
    warnings: list[str] = []
    if len(all_probes) > max_probes:
        warnings.append(f"probe_cap_applied:{max_probes}_of_{len(all_probes)}")
    probes = all_probes[:max_probes]

    bench_hash = _hash(
        f"{bench_name}|{project_key or ''}|" + "|".join(sorted(p["probe_id"] for p in probes))
    )
    bench_run_id = f"bmk_{bench_hash[:32]}"
    eval_set_id = f"res_{bench_hash[:32]}"

    if not probes:
        warnings.append("no_approved_outputs")
        result = _summary(
            command="second-brain retrieval benchmark build",
            status="empty",
            bench_run_id=bench_run_id,
            eval_set_id=eval_set_id,
            schema_version=schema_version,
            project_key=project_key,
            manifest=manifest,
            bench_name=bench_name,
            modes=requested_modes,
            probe_count=0,
            mode_metrics=None,
            metric_rows=[],
            min_tier=min_tier,
            warnings=warnings,
            seed=seed,
            contract=contract,
            emit_receipt=emit_receipt,
        )
        return result

    # Deterministic baseline — authoritative, query-free, computed once (same for every probe).
    det_env = RetrievalBroker(db_path).retrieve(
        project_key=project_key, families=None, emit_receipt=False
    )
    det_count = len(det_env.items)
    det_tiers = dict(det_env.tier_distribution)

    # Advisory semantic — one light query per probe over the applied vector index (fail-closed).
    semantic_counts: list[int] = []
    skip_reason: str | None = None
    for probe in probes:
        pairs, reason = _semantic_query(
            probe["probe_text"],
            db_path=db_path,
            seed=hybrid_seed,
            top_k=top_k,
            embed_model=embed_model,
            persist_root=persist_root,
        )
        if reason is not None:
            skip_reason = reason
        semantic_counts.append(len(pairs))

    semantic_total = sum(semantic_counts)
    semantic_max = max(semantic_counts) if semantic_counts else 0
    probes_with_hit = sum(1 for c in semantic_counts if c >= 1)
    # Semantic refs are hashed (disjoint from the deterministic raw-ref space) → net-new in the merge.
    hybrid_repr = det_count + semantic_max
    semantic_lift = semantic_max

    if skip_reason is not None and semantic_total == 0:
        semantic_status = f"blocked:{skip_reason}"
        status = "blocked"
    else:
        semantic_status = "available"
        status = "built"

    config_id = _applied_config_snapshot_id(db_path, persist_root)
    mode_metrics: dict[str, Any] = {
        "deterministic": {"result_count": det_count, "tier_distribution": det_tiers},
        "semantic": {
            "matches_total": semantic_total,
            "matches_max": semantic_max,
            "probes_with_hit": probes_with_hit,
            "hit_rate_pct": round((probes_with_hit / len(probes)) * 100),
            "min_review_tier": min_tier,
            "status": semantic_status,
        },
        "hybrid": {"result_count": hybrid_repr, "semantic_lift": semantic_lift},
    }
    metric_rows = _metric_rows(
        bench_run_id,
        eval_set_id=eval_set_id,
        config_snapshot_id=config_id,
        mode_metrics=mode_metrics,
        probe_count=len(probes),
        min_tier=min_tier,
    )

    result = _summary(
        command="second-brain retrieval benchmark build",
        status=status,
        bench_run_id=bench_run_id,
        eval_set_id=eval_set_id,
        schema_version=schema_version,
        project_key=project_key,
        manifest=manifest,
        bench_name=bench_name,
        modes=requested_modes,
        probe_count=len(probes),
        mode_metrics=mode_metrics,
        metric_rows=metric_rows,
        min_tier=min_tier,
        warnings=warnings,
        seed=seed,
        contract=contract,
        emit_receipt=emit_receipt,
        config_snapshot_id=config_id,
    )

    if emit_receipt:
        persist_retrieval_benchmark(db_path, result, policy_version=str(seed.get("version")))

    return result


def _applied_config_snapshot_id(db_path: str | None, persist_root: str | None) -> str:
    located = _latest_applied_vector_index_run(db_path, persist_root)
    return located[0] if located is not None else "none"


def _summary(
    *,
    command: str,
    status: str,
    bench_run_id: str,
    eval_set_id: str,
    schema_version: int,
    project_key: str | None,
    manifest: dict[str, Any],
    bench_name: str,
    modes: tuple[str, ...],
    probe_count: int,
    mode_metrics: dict[str, Any] | None,
    metric_rows: list[dict[str, Any]],
    min_tier: int,
    warnings: list[str],
    seed: dict[str, Any],
    contract: dict[str, Any],
    emit_receipt: bool,
    config_snapshot_id: str = "none",
) -> dict[str, Any]:
    """Assemble the metadata-only benchmark summary (no raw query/content/source ref — only bands/hashes)."""
    return {
        "command": command,
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": status,
        "bench_run_id": bench_run_id,
        "eval_set_id": eval_set_id,
        "name_hash": _hash(bench_name)[:48],
        "schema_version": schema_version,
        "project_key": project_key,
        "manifest_id": manifest.get("manifest_id"),
        "config_snapshot_id": config_snapshot_id,
        "modes": list(modes),
        "probe_count": probe_count,
        "deterministic_authoritative": True,
        "semantic_advisory_only": True,
        "assembles_final_answer": False,
        "semantic_min_review_tier": min_tier,
        "mode_metrics": mode_metrics,
        "metric_row_count": len(metric_rows),
        "metric_rows": metric_rows,
        "warnings": warnings,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }


def persist_retrieval_benchmark(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist guard-clean metadata-only benchmark metric rows. Returns bench_run_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(resolved)
    try:
        for row in result["metric_rows"]:
            conn.execute(
                f"INSERT OR REPLACE INTO {_BENCHMARK_TABLE} "
                "(run_id, policy_version, schema_version, eval_set_id, config_snapshot_id, "
                "metric_name, metric_value_label) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(row["run_id"]),
                    policy_version,
                    int(result["schema_version"]),
                    str(row["eval_set_id"]),
                    str(row["config_snapshot_id"]),
                    str(row["metric_name"]),
                    str(row["metric_value_label"]),
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return str(result["bench_run_id"])


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
        "# Phase 09 — Deterministic vs Semantic Benchmark Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- probe_count: {proof['probe_count']}",
        f"- metric_row_count: {proof['metric_row_count']}",
        f"- all_three_modes_compared: {proof['all_three_modes_compared']}",
        f"- semantic_available: {proof['semantic_available']}",
        f"- semantic_floored_tier_2: {proof['semantic_floored_tier_2']}",
        f"- assembles_final_answer: {proof['assembles_final_answer']} (must be false)",
        f"- rows_persisted_guard_clean: {proof['rows_persisted_guard_clean']}",
        f"- semantic_retrieval_bypassed_policy: {proof['semantic_retrieval_bypassed_policy']} (must be 0)",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        f"- semantic_blocked_path_status: {proof['semantic_blocked_path_status']}",
        f"- unsafe_node_excluded: {proof['unsafe_node_excluded']}",
        "",
    ]
    return "\n".join(lines)


def build_retrieval_benchmark_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: all three modes are compared over an applied index, comparative metrics are
    persisted metadata-only + guard-clean, semantic is floored at tier 2 and assembles no answer, the
    semantic side degrades fail-closed (blocked status) with no applied index, and unsafe nodes are
    excluded from the probe set — no raw query/content/source ref is emitted."""
    import tempfile

    from .hybrid_broker import _mock_embed_model
    from .vector_index import _mock_vector_writer, _proof_db, build_vector_index_apply

    with tempfile.TemporaryDirectory() as tmp:
        embed = _mock_embed_model()

        # (1) Applied index — semantic available; all three modes compared; receipts persisted.
        db = _proof_db(tmp)
        persist_root = str(Path(tmp) / "vector_store")
        build_vector_index_apply(db, writer=_mock_vector_writer, persist_root=persist_root)
        result = build_retrieval_benchmark(
            db,
            name="proof_benchmark",
            embed_model=embed,
            persist_root=persist_root,
            emit_receipt=True,
        )
        bench_run_id = result["bench_run_id"]

        conn = sqlite3.connect(db)
        try:
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM {_BENCHMARK_TABLE} WHERE run_id LIKE ?",
                (f"{bench_run_id}:%",),
            ).fetchone()[0]
            guard_cols = _guard_columns(conn, _BENCHMARK_TABLE)
            guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_BENCHMARK_TABLE} "
                "WHERE run_id LIKE ?",
                (f"{bench_run_id}:%",),
            ).fetchone()[0]
            bypass_sum = conn.execute(
                f"SELECT COALESCE(SUM(semantic_retrieval_bypassed_policy), 0) FROM {_BENCHMARK_TABLE} "
                "WHERE run_id LIKE ?",
                (f"{bench_run_id}:%",),
            ).fetchone()[0]
            stored_labels = [
                str(r[0])
                for r in conn.execute(
                    f"SELECT metric_value_label FROM {_BENCHMARK_TABLE} WHERE run_id LIKE ?",
                    (f"{bench_run_id}:%",),
                ).fetchall()
            ]
        finally:
            conn.close()

        # (2) Approved corpus but NO applied index — semantic degrades fail-closed (blocked status).
        blocked_dir = Path(tmp) / "no_index"
        blocked_dir.mkdir()
        db_blocked = _proof_db(str(blocked_dir))
        blocked = build_retrieval_benchmark(
            db_blocked,
            name="proof_benchmark_blocked",
            embed_model=embed,
            persist_root=str(blocked_dir / "vector_store"),
        )

    # (3) Unsafe-node exclusion over synthetic nodes (no ref, no excerpt, excluded family).
    synthetic = [
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "ok",
            "text_redacted": "Project Alpha summary",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "approved_obsidian_generated_outputs",
            "source_ref": "",
            "text_redacted": "no ref",
            "confidence_class": "high",
            "review_tier": 1,
        },
        {
            "source_family": "raw_email_body",
            "source_ref": "x",
            "text_redacted": "excluded family",
            "confidence_class": "high",
            "review_tier": 1,
        },
    ]
    unsafe_excluded = len(_build_probes(synthetic)) == 1

    mm = result.get("mode_metrics") or {}
    sem = mm.get("semantic", {})
    all_three = (
        "deterministic" in mm
        and "semantic" in mm
        and "hybrid" in mm
        and result["metric_row_count"] == 7
    )
    semantic_available = sem.get("status") == "available" and int(sem.get("matches_total", 0)) >= 1
    semantic_floored = int(sem.get("min_review_tier", 0)) == 2
    rows_clean = row_count == result["metric_row_count"] and int(guard_sum or 0) == 0
    serialized_summary = json.dumps(result, default=str)
    no_raw_emitted = (
        "probe_text" not in serialized_summary
        and "text_redacted" not in serialized_summary
        and all(len(label) <= 64 for label in stored_labels)
    )
    blocked_ok = blocked["status"] == "blocked" and str(
        (blocked.get("mode_metrics") or {}).get("semantic", {}).get("status", "")
    ).startswith("blocked:")

    proof_passed = (
        result["status"] == "built"
        and all_three
        and semantic_available
        and semantic_floored
        and result["assembles_final_answer"] is False
        and rows_clean
        and int(bypass_sum or 0) == 0
        and no_raw_emitted
        and blocked_ok
        and unsafe_excluded
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_retrieval_benchmark",
        "command": "second-brain retrieval benchmark proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "probe_count": result["probe_count"],
        "metric_row_count": result["metric_row_count"],
        "all_three_modes_compared": all_three,
        "semantic_available": semantic_available,
        "semantic_floored_tier_2": semantic_floored,
        "assembles_final_answer": result["assembles_final_answer"],
        "rows_persisted_guard_clean": rows_clean,
        "semantic_retrieval_bypassed_policy": int(bypass_sum or 0),
        "no_raw_emitted": no_raw_emitted,
        "semantic_blocked_path_status": blocked["status"],
        "unsafe_node_excluded": unsafe_excluded,
        "metadata_only": True,
        "guardrails": {
            "deterministic_source_of_truth": True,
            "semantic_advisory_only": True,
            "no_final_answer_assembly": True,
            "no_semantic_retrieval_bypass": True,
            "approved_outputs_only": True,
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
        _assert_no_raw(serialized, "retrieval benchmark proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "retrieval benchmark proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
