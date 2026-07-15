"""Phase 09 Prompt 32 — agent performance and feedback (advisory tracker).

A read-only, advisory **per-agent** tracker over the Phase 08A agent registry that aggregates:
  - **repeated_corrections** — operator feedback of class ``correct``/``reject`` (``second_brain_operator_feedback``),
    attributed to the owning agent via the ``target_kind`` -> agent map.
  - **review_burden** — agent run review tiers (``second_brain_agent_run_receipts``; a stable Phase-08B
    receipt table), per agent (tier-3 share = high burden).
  - **weak_coverage** — empty / deferred source families (``corpus_balance_mart``), attributed to the
    retrieval coverage owner.
  - **policy_recommendation** — a deterministic, **advisory** recommendation code derived from thresholds
    (never applied; for operator awareness only).

It makes **no determination**; recommendations are advisory suggestions. Persists metadata-only
per-(agent, metric) rows (on ``emit_receipt``) to the reserved V38
``second_brain_agent_performance_feedback_runs`` table. No raw feedback reason / prompt / response is
persisted or emitted — only counts, bucketed bands, agent names, metric names, and recommendation codes.
Read-only by default; fail-closed on missing policy or stale schema.

Public entry points:
  assess_agent_performance(receipts, feedback, coverage, *, agents, seed) -> dict
  build_agent_performance_feedback(db_path=None, *, project_key=None, emit_receipt=False) -> dict
  persist_agent_performance_feedback(db_path, result, *, policy_version) -> str
  build_agent_performance_feedback_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain agent-performance build | proof --json
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

from .financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "agent-performance-feedback-proof.json"
_PROOF_MD = "agent-performance-feedback-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_agent_performance_feedback.seed.yaml"

_RUNS_TABLE = "second_brain_agent_performance_feedback_runs"
_RECEIPTS_TABLE = "second_brain_agent_run_receipts"
_FEEDBACK_TABLE = "second_brain_operator_feedback"


class AgentPerformanceFeedbackError(RuntimeError):
    """Raised when the agent-performance builder cannot resolve policy/schema (fail-closed)."""


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


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=38 with the feedback-runs table), else raise fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise AgentPerformanceFeedbackError(
            "schema not ready for agent performance feedback (no database)"
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
            raise AgentPerformanceFeedbackError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 38 or not _has(_RUNS_TABLE):
            raise AgentPerformanceFeedbackError(
                f"schema not ready for agent performance feedback (version {version}, expected >= 38)"
            )
    finally:
        conn.close()
    return version


def load_agent_performance_feedback_contract() -> dict[str, Any]:
    """Load the agent-performance-feedback contract (fail-closed if missing/invalid)."""
    from .contracts import load_phase_09_contract

    contract = load_phase_09_contract("agent_performance_feedback_contract")
    if not isinstance(contract, dict) or "signal_categories" not in contract:
        raise AgentPerformanceFeedbackError(
            "phase 09 agent-performance-feedback contract not found or missing required fields"
        )
    return contract


def load_agent_performance_feedback_seed() -> dict[str, Any]:
    """Load the resolved agent-performance-feedback seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise AgentPerformanceFeedbackError(
            f"agent-performance-feedback seed not found at {candidate}"
        )
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "target_kind_to_agent" not in data:
        raise AgentPerformanceFeedbackError(
            f"{candidate} must define the agent-performance-feedback policy"
        )
    return data


def _count_band(n: int) -> str:
    if n <= 0:
        return "0"
    if n <= 2:
        return "1-2"
    if n <= 5:
        return "3-5"
    if n <= 10:
        return "6-10"
    return "11+"


def _share_band(frac: float) -> str:
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


def assess_agent_performance(
    receipts: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    coverage: dict[str, Any],
    *,
    agents: list[str],
    seed: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate per-agent performance signals + advisory recommendations (metadata-only).

    ``receipts`` rows: {agent_id, review_tier, status}. ``feedback`` rows: {target_kind, feedback_class}.
    ``coverage``: a corpus-balance mart dict (empty_families / deferred_families). Returns per-agent signal
    records (counts + bucketed bands + advisory recommendation codes) — no raw reason text. No determination.
    """
    high_corr = int(seed.get("high_corrections_count", 3))
    high_tier3 = float(seed.get("high_tier3_share", 0.50))
    kind_to_agent: dict[str, str] = dict(seed.get("target_kind_to_agent", {}))
    correction_classes = set(seed.get("correction_feedback_classes", ["correct", "reject"]))
    coverage_owner = str(seed.get("coverage_owner_agent", "retrieval_source_broker_agent"))

    # review burden per agent (from receipts)
    run_count: dict[str, int] = {}
    tier3_count: dict[str, int] = {}
    for r in receipts:
        a = str(r.get("agent_id") or "")
        run_count[a] = run_count.get(a, 0) + 1
        if int(r.get("review_tier") or 0) >= 3:
            tier3_count[a] = tier3_count.get(a, 0) + 1

    # repeated corrections per agent (from feedback, attributed via target_kind)
    corrections: dict[str, int] = {}
    for f in feedback:
        if str(f.get("feedback_class") or "") not in correction_classes:
            continue
        agent = kind_to_agent.get(str(f.get("target_kind") or ""))
        if agent is None:
            continue  # unattributable target_kind -> counts to no agent (never crashes)
        corrections[agent] = corrections.get(agent, 0) + 1

    # weak coverage (attributed to the coverage owner agent)
    empty_families = list(coverage.get("empty_families", []))
    deferred_families = list(coverage.get("deferred_families", []))
    weak_coverage_count = len(empty_families) + len(deferred_families)

    per_agent: list[dict[str, Any]] = []
    for agent in agents:
        runs = run_count.get(agent, 0)
        t3 = tier3_count.get(agent, 0)
        tier3_share = (t3 / runs) if runs else 0.0
        corr = corrections.get(agent, 0)
        weak = weak_coverage_count if agent == coverage_owner else 0

        if corr >= high_corr:
            recommendation = "recommend_review_tier_increase"
        elif tier3_share >= high_tier3 and runs > 0:
            recommendation = "recommend_confidence_tuning"
        elif weak > 0:
            recommendation = "recommend_source_expansion"
        else:
            recommendation = "no_action"

        per_agent.append(
            {
                "agent_name": agent,
                "repeated_corrections": corr,
                "corrections_band": _count_band(corr),
                "review_burden_run_count": runs,
                "review_burden_tier3_count": t3,
                "review_burden_tier3_share_band": _share_band(tier3_share),
                "weak_coverage_count": weak,
                "weak_coverage_band": _count_band(weak),
                "policy_recommendation": recommendation,
            }
        )

    signal_count = sum(
        a["repeated_corrections"] + a["review_burden_run_count"] + a["weak_coverage_count"]
        for a in per_agent
    )
    has_signal = any(
        a["repeated_corrections"] or a["review_burden_run_count"] or a["weak_coverage_count"]
        for a in per_agent
    )
    return {
        "agent_count": len(agents),
        "signal_count": signal_count,
        "status": "built" if has_signal else "empty",
        "per_agent": per_agent,
    }


def _read_receipts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_RECEIPTS_TABLE,)
        ).fetchone()
        is None
    ):
        return []
    return [
        {"agent_id": r[0], "review_tier": r[1], "status": r[2]}
        for r in conn.execute(
            f"SELECT agent_id, review_tier, status FROM {_RECEIPTS_TABLE}"
        ).fetchall()
    ]


def _read_feedback(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_FEEDBACK_TABLE,)
        ).fetchone()
        is None
    ):
        return []
    return [
        {"target_kind": r[0], "feedback_class": r[1]}
        for r in conn.execute(
            f"SELECT target_kind, feedback_class FROM {_FEEDBACK_TABLE}"
        ).fetchall()
    ]


def build_agent_performance_feedback(
    db_path: str | None = None,
    *,
    project_key: str | None = None,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Aggregate per-agent performance + feedback signals (read-only, advisory).

    Returns a JSON-safe, metadata-only summary (per-agent counts + bands + advisory recommendation codes —
    never raw reason text); persists nothing unless ``emit_receipt``. Makes no determination.
    """
    from .agents.loader import load_agent_registry
    from .corpus_balance_mart import build_corpus_balance_mart

    contract = load_agent_performance_feedback_contract()
    seed = load_agent_performance_feedback_seed()
    schema_version = _schema_ready(db_path)

    agents = [a.agent_id for a in load_agent_registry().agents]
    coverage = build_corpus_balance_mart(db_path, project_key=project_key)

    conn = _open_ro(db_path)
    if conn is None:
        raise AgentPerformanceFeedbackError(
            "schema not ready for agent performance feedback (no database)"
        )
    try:
        receipts = _read_receipts(conn)
        feedback = _read_feedback(conn)
    finally:
        conn.close()

    a = assess_agent_performance(receipts, feedback, coverage, agents=agents, seed=seed)
    run_id = f"apf_{_hash(f'{project_key or ""}|{a["agent_count"]}|{a["signal_count"]}|{a["status"]}')[:32]}"

    result = {
        "command": "second-brain agent-performance build",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": a["status"],
        "run_id": run_id,
        "schema_version": schema_version,
        "project_key": project_key,
        "agent_count": a["agent_count"],
        "signal_count": a["signal_count"],
        "per_agent": a["per_agent"],
        "advisory_only": True,
        "makes_determination": False,
        "recommendations_advisory_only": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "receipt_emitted": emit_receipt,
        "read_only": not emit_receipt,
    }

    if emit_receipt:
        persist_agent_performance_feedback(db_path, result, policy_version=str(seed.get("version")))

    return result


def persist_agent_performance_feedback(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist guard-clean metadata-only per-(agent, metric) rows. Returns run_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    schema_version = int(result["schema_version"])
    project_key = result.get("project_key")
    status = str(result["status"])
    metrics = [
        ("repeated_corrections", "repeated_corrections", "corrections_band"),
        ("review_burden", "review_burden_run_count", "review_burden_tier3_share_band"),
        ("weak_coverage", "weak_coverage_count", "weak_coverage_band"),
        ("policy_recommendation", None, "policy_recommendation"),
    ]
    conn = sqlite3.connect(resolved)
    try:
        for agent in result["per_agent"]:
            agent_name = str(agent["agent_name"])
            for metric_name, count_key, label_key in metrics:
                count_val = int(agent.get(count_key, 0)) if count_key else 0
                # Row PK shares the logical run_id prefix so a run groups its per-(agent, metric) rows.
                row_run_id = f"{run_id}:{_hash(agent_name)[:12]}:{metric_name}"
                conn.execute(
                    f"INSERT OR REPLACE INTO {_RUNS_TABLE} "
                    "(run_id, policy_version, schema_version, agent_name, project_key, signal_count, "
                    "metric_name, metric_value_label, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        row_run_id,
                        policy_version,
                        schema_version,
                        agent_name,
                        project_key,
                        count_val,
                        metric_name,
                        str(agent.get(label_key, "")),
                        status,
                    ),
                )
        conn.commit()
    finally:
        conn.close()
    return run_id


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
        "# Phase 09 — Agent Performance and Feedback Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- status: {proof['status']}",
        f"- agent_count: {proof['agent_count']}",
        f"- corrections_attributed: {proof['corrections_attributed']}",
        f"- review_burden_computed: {proof['review_burden_computed']}",
        f"- weak_coverage_computed: {proof['weak_coverage_computed']}",
        f"- recommendation_emitted: {proof['recommendation_emitted']}",
        f"- makes_determination: {proof['makes_determination']} (must be false)",
        f"- rows_persisted_guard_clean: {proof['rows_persisted_guard_clean']}",
        f"- read_only_default_no_persist: {proof['read_only_default_no_persist']}",
        f"- no_raw_emitted: {proof['no_raw_emitted']}",
        "",
    ]
    return "\n".join(lines)


def _seed_proof_db(db: str) -> None:
    """Seed agent_run_receipts (incl. tier-3 runs -> review burden) + operator_feedback (corrections on a
    retrieval target) directly (metadata-only synthetic ids/tiers)."""
    conn = sqlite3.connect(db)
    try:
        for i, tier in enumerate([3, 3, 1]):
            conn.execute(
                f"INSERT INTO {_RECEIPTS_TABLE} "
                "(agent_run_id, agent_id, run_kind, status, review_tier, created_utc) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    f"run-{i}",
                    "retrieval_source_broker_agent",
                    "retrieval",
                    "succeeded",
                    tier,
                    "2026-01-0%d" % (i + 1),
                ),
            )
        for i, cls in enumerate(["correct", "reject", "correct", "accept"]):
            conn.execute(
                f"INSERT INTO {_FEEDBACK_TABLE} "
                "(feedback_id, target_kind, target_id, feedback_class, created_utc) "
                "VALUES (?, ?, ?, ?, ?)",
                (f"fb-{i}", "retrieval", f"t-{i}", cls, "2026-01-0%d" % (i + 1)),
            )
        conn.commit()
    finally:
        conn.close()


def build_agent_performance_feedback_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: per-agent corrections / review burden / weak coverage are computed and an advisory
    policy recommendation is emitted (no determination); the feedback-run rows are guard-clean + metadata-
    only; no raw feedback reason is emitted."""
    import tempfile

    from hb_assistant.store.migrator import ensure_schema_ready

    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "apf.sqlite")
        ensure_schema_ready(db)
        _seed_proof_db(db)

        before = _run_rows(db)
        result = build_agent_performance_feedback(db)
        read_only_no_persist = _run_rows(db) == before

        result2 = build_agent_performance_feedback(db, emit_receipt=True)
        run_id = result2["run_id"]
        conn = sqlite3.connect(db)
        try:
            row_count = conn.execute(
                f"SELECT COUNT(*) FROM {_RUNS_TABLE} WHERE run_id LIKE ?", (f"{run_id}:%",)
            ).fetchone()[0]
            guard_cols = _guard_columns(conn, _RUNS_TABLE)
            guard_sum = conn.execute(
                f"SELECT COALESCE(SUM({'+'.join(guard_cols)}), 0) FROM {_RUNS_TABLE} WHERE run_id LIKE ?",
                (f"{run_id}:%",),
            ).fetchone()[0]
        finally:
            conn.close()

    broker: dict[str, Any] = next(
        (a for a in result["per_agent"] if a["agent_name"] == "retrieval_source_broker_agent"), {}
    )
    corrections_attributed = bool(broker) and broker["repeated_corrections"] >= 2
    review_burden_computed = bool(broker) and broker["review_burden_run_count"] >= 3
    weak_coverage_computed = bool(broker) and "weak_coverage_band" in broker
    recommendation_emitted = bool(broker) and broker["policy_recommendation"] != "no_action"
    rows_guard_clean = row_count >= 1 and int(guard_sum or 0) == 0
    serialized = json.dumps(result, default=str)
    no_raw_emitted = "reason_redacted" not in serialized and "reason" not in serialized.replace(
        "policy_recommendation", ""
    ).replace("recommendation", "")

    proof_passed = (
        corrections_attributed
        and review_burden_computed
        and weak_coverage_computed
        and recommendation_emitted
        and result["makes_determination"] is False
        and rows_guard_clean
        and read_only_no_persist
        and no_raw_emitted
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_agent_performance_feedback",
        "command": "second-brain agent-performance proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "status": result["status"],
        "agent_count": result["agent_count"],
        "corrections_attributed": corrections_attributed,
        "review_burden_computed": review_burden_computed,
        "weak_coverage_computed": weak_coverage_computed,
        "recommendation_emitted": recommendation_emitted,
        "makes_determination": result["makes_determination"],
        "rows_persisted_guard_clean": rows_guard_clean,
        "read_only_default_no_persist": read_only_no_persist,
        "no_raw_emitted": no_raw_emitted,
        "metadata_only": True,
        "guardrails": {
            "advisory_only": True,
            "no_determination": True,
            "recommendations_advisory_only": True,
            "no_raw": True,
            "no_external_writeback": True,
            "local_first": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "agent performance feedback proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "agent performance feedback proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


def _run_rows(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {_RUNS_TABLE}").fetchone()[0])
    finally:
        conn.close()
