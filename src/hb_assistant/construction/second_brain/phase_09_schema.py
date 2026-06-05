"""Phase 09 Prompt 12 — V39 schema status + table-lifecycle probe (read-only).

A deterministic, **read-only** status report over the Phase 09 retrieval / memory / agent metadata
tables (V38 base + V39 additive review burden tables; 22 tables total, list name retained PHASE_09_V38_TABLES
for compatibility). It verifies that the local schema is at the expected head (>=V39), that every
Phase 09 table exists and carries the full twenty-three guard columns (`CHECK(... = 0)`), and that the
Phase 09 lifecycle contract loads and classifies all tables. Row counts are reported per table (some
tables such as approved source manifests, vector index items, and review burden clusters are legitimately
populated by valid operations; population does not indicate failure). It is the schema-foundation
companion to the V38/V39 substrate — no LlamaIndex / embeddings / vector / semantic-retrieval runtime
is involved here.

Strictly advisory and **fail-closed**: the lifecycle contract is required (a missing/invalid contract
raises `Phase09SchemaContractError`), and `overall_status` is ``ready`` when schema (>=V39), tables
present, and all guards present (row-emptiness is **not** required for ready status; all_rows_zero
and per-table row_count are reported as diagnostics only). The probe opens the database **read-only**
(`?mode=ro`) and never writes; outputs are names / counts / booleans only — no raw content, prompts,
responses, tokens, URLs, or PEMs.

Public entry points:
  load_phase_09_lifecycle_contract() -> dict
  build_phase_09_schema_status_report(db_path=None) -> dict
CLI surface: hb-assistant second-brain data-quality phase-09-schema-status --json
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
from datetime import datetime, timezone
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

# Single source of truth for the Phase 09 V38+ tables (tests import this; V39 additive, list name retained for compat; 22 tables as of V39).
PHASE_09_V38_TABLES: list[str] = [
    "second_brain_retrieval_llamaindex_config_snapshots",
    "second_brain_retrieval_approved_source_manifests",
    "second_brain_retrieval_vector_index_runs",
    "second_brain_retrieval_vector_index_items",
    "second_brain_retrieval_embedding_model_evals",
    "second_brain_retrieval_hybrid_query_runs",
    "second_brain_retrieval_hybrid_query_results",
    "second_brain_retrieval_eval_sets",
    "second_brain_retrieval_eval_cases",
    "second_brain_retrieval_eval_runs",
    "second_brain_retrieval_benchmark_runs",
    "second_brain_retrieval_source_linked_proof_runs",
    "second_brain_retrieval_unsupported_claim_checks",
    "second_brain_retrieval_context_budget_runs",
    "second_brain_memory_quality_review_runs",
    "second_brain_memory_consolidation_candidates",
    "second_brain_memory_consolidation_review_items",
    "second_brain_agent_performance_feedback_runs",
    "second_brain_phase_09_validation_runs",
    # v39 Phase 09 review burden reduction (additive; two-step policy, financial separate,
    # clustered high-impact visibility, hash-only examples). Tables carry the full 23 guards.
    "second_brain_review_burden_runs",
    "second_brain_review_burden_clusters",
    "second_brain_review_burden_policy_evals",
]

# The twenty-three guard columns every V38 table must carry (each CHECK(... = 0)).
PHASE_09_GUARD_COLUMNS: list[str] = [
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_financial_source_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_api_call_performed",
    "procore_api_call_performed",
    "email_send_performed",
    "calendar_update_performed",
    "source_system_writeback_performed",
    "arbitrary_sql_performed",
    "raw_store_access_performed",
    "financial_determination_performed",
    "payment_decision_performed",
    "claim_or_entitlement_decision_performed",
    "unsupported_claim_performed",
    "raw_vector_content_persisted",
    "semantic_retrieval_bypassed_policy",
]

_CONTRACT_PKG = "hb_assistant.resources.json"
_CONTRACT_FILENAME = "phase_09_table_lifecycle_contract.json"


class Phase09SchemaContractError(RuntimeError):
    """Raised when the Phase 09 lifecycle contract cannot be loaded (fail-closed)."""


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


def load_phase_09_lifecycle_contract() -> dict[str, Any]:
    """Load the Phase 09 table-lifecycle contract (fail-closed if missing/invalid)."""
    text: str | None = None
    try:
        text = (importlib_resources.files(_CONTRACT_PKG) / _CONTRACT_FILENAME).read_text(
            encoding="utf-8"
        )
    except Exception:
        candidate = (
            Path(__file__).resolve().parents[4]
            / "src"
            / "hb_assistant"
            / "resources"
            / "json"
            / _CONTRACT_FILENAME
        )
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
    if text is None:
        raise Phase09SchemaContractError(
            f"phase 09 lifecycle contract not found: {_CONTRACT_PKG}/{_CONTRACT_FILENAME}"
        )
    try:
        data = json.loads(text)
    except Exception as exc:  # invalid JSON
        raise Phase09SchemaContractError(
            f"phase 09 lifecycle contract is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict) or not isinstance(data.get("tables"), dict):
        raise Phase09SchemaContractError("phase 09 lifecycle contract must define a tables object")
    if "phase_09_lifecycle_states" not in data:
        raise Phase09SchemaContractError(
            "phase 09 lifecycle contract must define phase_09_lifecycle_states"
        )
    missing = [t for t in PHASE_09_V38_TABLES if t not in data["tables"]]
    if missing:
        raise Phase09SchemaContractError(
            f"phase 09 lifecycle contract is missing tables: {sorted(missing)}"
        )
    return data


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    """Open the store read-only. Returns None if the DB file does not exist yet."""
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_version(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except sqlite3.OperationalError:
        return 0


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def build_phase_09_schema_status_report(db_path: str | None = None) -> dict[str, Any]:
    """Build the read-only V39 schema + table-lifecycle status report (fail-closed).

    Structural ready requires schema_version >= 39, all listed tables present, and all 23 guard
    columns present on each. Row counts are reported (some tables are expected to be populated
    after valid writes e.g. manifests, vector items, review burden); all_rows_zero is computed
    and emitted for diagnostics but is **not** required for overall_status == "ready".
    """
    contract = load_phase_09_lifecycle_contract()
    contract_tables: dict[str, Any] = contract.get("tables", {})

    conn = _open_ro(db_path)
    schema_version = _schema_version(conn) if conn is not None else 0
    schema_ready = schema_version >= 39

    table_reports: list[dict[str, Any]] = []
    try:
        for name in PHASE_09_V38_TABLES:
            present = conn is not None and _table_exists(conn, name)
            cols = _columns(conn, name) if (conn is not None and present) else set()
            missing_guards = [g for g in PHASE_09_GUARD_COLUMNS if g not in cols]
            row_count: int | None = None
            if conn is not None and present:
                row_count = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            lifecycle_spec = contract_tables.get(name, {})
            table_reports.append(
                {
                    "table_name": name,
                    "present": present,
                    "guard_columns_present": present and not missing_guards,
                    "missing_guard_columns": missing_guards,
                    "row_count": row_count,
                    "phase_09_lifecycle": lifecycle_spec.get("phase_09_lifecycle"),
                    "owning_prompt": lifecycle_spec.get("owning_prompt"),
                }
            )
    finally:
        if conn is not None:
            conn.close()

    all_tables_present = all(t["present"] for t in table_reports)
    all_guards_present = all(t["guard_columns_present"] for t in table_reports)
    all_rows_zero = all(t["row_count"] == 0 for t in table_reports)
    overall_ready = schema_ready and all_tables_present and all_guards_present
    # Note: all_rows_zero is retained for reporting/diagnostics (e.g. pre-pop proofs) but is
    # intentionally excluded from overall_ready so that legitimate population of tables such as
    # second_brain_retrieval_approved_source_manifests, vector_index_items, review_burden_* etc.
    # does not cause a false "not_ready" after valid apply operations.

    return {
        "command": "second-brain data-quality phase-09-schema-status",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_ready": schema_ready,
        "contract_schema": contract.get("schema"),
        "policy_loaded": True,
        "phase_09_table_count": len(PHASE_09_V38_TABLES),
        "guard_column_count": len(PHASE_09_GUARD_COLUMNS),
        "all_tables_present": all_tables_present,
        "all_guards_present": all_guards_present,
        "all_rows_zero": all_rows_zero,
        "overall_status": "ready" if overall_ready else "not_ready",
        "tables": table_reports,
        "read_only": True,
    }
