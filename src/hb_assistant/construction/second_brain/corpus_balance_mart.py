"""Phase 09 Prompt 11 — retrieval corpus-balance + source-family coverage mart (read-only).

A deterministic, **read-only** balance profile over the **retrieval corpus** — the families the
Retrieval Broker may read (`ALLOWLISTED_SOURCE_FAMILIES`), each backed by a local read-model table.
It reports per-family **coverage** (covered / empty / deferred-no-reader), corpus **balance** metrics
(per-family share, dominant family + share, covered / empty family counts), and source-coverage
**warnings** in the broker's vocabulary, then evaluates a **fail-closed corpus-balance gate** against
a committed threshold policy — built **before** semantic retrieval consumes the corpus (gap G-10:
the corpus is procore/financial-heavy while brief/research/mcp/memory/automation families are empty).

It is strictly advisory: balance / coverage outputs are **signals + warnings**, never a determination,
and the gate verdict (`imbalanced` at preflight) is reported, not enforced. Outputs are counts /
shares / enums only — no raw content, prompts, responses, tokens, URLs, or PEMs. The mart opens the
database read-only and never writes; it draws only from allowlisted families (never an
`EXCLUDED_FAMILIES` raw family). Database-path agnostic.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .retrieval.policy import ALLOWLISTED_SOURCE_FAMILIES, EXCLUDED_FAMILIES
from .retrieval.readers import READER_REGISTRY

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_corpus_balance_policy.seed.yaml"
SEED_ENV_VAR = "HB_SECOND_BRAIN_CORPUS_BALANCE_POLICY"

# Allowlisted family -> (read-model table, extra WHERE clause). Families absent here are counted via a
# dedicated branch below (obsidian via the manifest-scoped helper; generated outputs + correspondence
# via composite/projection counters).
_FAMILY_TABLE: dict[str, tuple[str, str]] = {
    "phase_07d_source_evidence_trails": ("source_evidence_trails", ""),
    "project_issue_history_items": ("project_issue_history_items", ""),
    "project_risk_digest_items": ("project_risk_digest_items", ""),
    "aging_exposure_report_items": ("aging_exposure_report_items", ""),
    "accepted_long_term_memory": ("long_term_memory_items", "review_status = 'accepted'"),
    "cross_source_relationships": ("cross_source_relationships", ""),
    "meeting_prep_brief_sections": ("meeting_prep_brief_sections", ""),
}
_OBSIDIAN_FAMILY = "approved_obsidian_generated_outputs"
_GENERATED_FAMILY = "generated_outputs"
_CORRESPONDENCE_FAMILY = "review_controlled_correspondence_context"
_VECTOR_ITEMS_TABLE = "second_brain_retrieval_vector_index_items"
_VECTOR_RUNS_TABLE = "second_brain_retrieval_vector_index_runs"

# Safe text / JSON columns scanned for forbidden raw-content shapes (PRAGMA-guarded per table).
_SCAN_COLUMNS: dict[str, tuple[str, ...]] = {
    "source_evidence_trails": ("source_refs_json", "stale_unknown_flags_json"),
    "cross_source_relationships": ("signals_json", "source_reference_json"),
    "obsidian_index_entries": ("note_path_redacted", "heading_redacted", "source_refs_json"),
    "project_issue_history_items": ("summary_redacted",),
    "project_risk_digest_items": ("summary_redacted",),
    "aging_exposure_report_items": ("threshold_band",),
    "long_term_memory_items": ("statement_redacted",),
    "meeting_prep_brief_sections": ("section_redacted",),
    "second_brain_research_packets": ("summary_redacted",),
    "email_thread_summaries": ("summary_redacted",),
}
# Corpus tables whose guard CHECK(=0) columns are re-attested clean.
_GUARDED_TABLES: tuple[str, ...] = (
    "source_evidence_trails",
    "cross_source_relationships",
    "obsidian_index_manifests",
)

_FORBIDDEN = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY"
    r"|Bearer [A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"|[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}"
    r"|https?://[^\s\"']*[?&](sig|token)="
)


class CorpusBalancePolicyError(RuntimeError):
    """Raised when the corpus-balance policy seed cannot be loaded (fail-closed)."""


def load_corpus_balance_policy() -> dict[str, Any]:
    """Load the corpus-balance threshold policy seed (fail-closed if missing/invalid)."""
    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    env_value = os.environ.get(SEED_ENV_VAR)
    if env_value:
        candidate = Path(env_value).expanduser()
    if not candidate.exists():
        raise CorpusBalancePolicyError(f"corpus-balance policy seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "min_covered_families" not in data:
        raise CorpusBalancePolicyError(f"{candidate} must define corpus-balance thresholds")
    return data


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _guard_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    return [
        c
        for c in cols
        if c.endswith("_persisted") or c.endswith("_performed") or c.endswith("_allowed")
    ]


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _family_count(
    conn: sqlite3.Connection, table: str, where_extra: str, project_key: str | None
) -> int:
    cols = _columns(conn, table)
    clauses: list[str] = []
    params: list[Any] = []
    if where_extra:
        clauses.append(where_extra)
    if project_key is not None and "project_key" in cols:
        clauses.append("project_key = ?")
        params.append(project_key)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}{where}", tuple(params)).fetchone()[0])


def _obsidian_count(conn: sqlite3.Connection, project_key: str | None) -> int:
    """Count entries of the latest approved (else most recent) obsidian index manifest."""
    if not _table_exists(conn, "obsidian_index_entries") or not _table_exists(
        conn, "obsidian_index_manifests"
    ):
        return 0
    row = conn.execute(
        "SELECT manifest_id FROM obsidian_index_manifests "
        "ORDER BY (mode = 'apply') DESC, generated_utc DESC, manifest_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return 0
    clause = ""
    params: list[Any] = [row[0]]
    if project_key is not None:
        clause = " AND project_key = ?"
        params.append(project_key)
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM obsidian_index_entries WHERE manifest_id = ?{clause}",
            tuple(params),
        ).fetchone()[0]
    )


def _generated_count(conn: sqlite3.Connection, project_key: str | None) -> int:
    """Count generated-output corpus rows: accepted research packets + applied source-linked briefs."""
    total = 0
    if _table_exists(conn, "second_brain_research_packets"):
        total += _family_count(
            conn, "second_brain_research_packets", "review_status = 'accepted'", project_key
        )
    # daily_brief_runs has no project_key column; only counted when unscoped.
    if project_key is None and _table_exists(conn, "daily_brief_runs"):
        total += int(
            conn.execute(
                "SELECT COUNT(*) FROM daily_brief_runs WHERE mode = 'apply' AND status != 'blocked' "
                "AND output_path_hash IS NOT NULL AND source_ref_count > 0"
            ).fetchone()[0]
        )
    return total


def _correspondence_count(conn: sqlite3.Connection, project_key: str | None) -> int:
    """Count the review-controlled correspondence substrate (email-thread anchors) cheaply.

    Uses the anchor ``email_thread_summaries`` table on the existing read-only connection rather than
    running the (heavy) Phase 07D projection builder — an advisory balance signal only."""
    if not _table_exists(conn, "email_thread_summaries"):
        return 0
    return _family_count(conn, "email_thread_summaries", "", project_key)


def _applied_vector_families(conn: sqlite3.Connection) -> list[str]:
    """Distinct source families present in applied vector-index item receipts (metadata-only)."""
    if not _table_exists(conn, _VECTOR_ITEMS_TABLE) or not _table_exists(conn, _VECTOR_RUNS_TABLE):
        return []
    rows = conn.execute(
        f"SELECT DISTINCT i.source_family FROM {_VECTOR_ITEMS_TABLE} i "
        f"JOIN {_VECTOR_RUNS_TABLE} r ON i.run_id = r.run_id WHERE r.status = 'applied' "
        "ORDER BY i.source_family"
    ).fetchall()
    return [str(r[0]) for r in rows]


def _approved_manifest_categories() -> list[str]:
    """The manifest categories the approved-source manifest admits (cheap seed read; no live build)."""
    try:
        from .retrieval.source_manifest import load_approved_source_manifest_seed

        return sorted(str(c) for c in load_approved_source_manifest_seed().get("enabled_categories", []))
    except Exception:
        return []


def build_corpus_balance_mart(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the read-only retrieval corpus-balance + source-family coverage mart."""
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        families: dict[str, Any] = {}
        warnings: list[str] = []
        total = 0
        covered: list[str] = []
        empty: list[str] = []
        deferred: list[str] = []

        for family in ALLOWLISTED_SOURCE_FAMILIES:
            has_reader = family in READER_REGISTRY
            if not has_reader:
                families[family] = {
                    "has_reader": False,
                    "row_count": 0,
                    "coverage_status": "deferred_no_reader",
                }
                deferred.append(family)
                warnings.append(f"no_read_model:{family}")
                continue
            if family == _OBSIDIAN_FAMILY:
                count = _obsidian_count(conn, project_key)
                table = "obsidian_index_entries"
            elif family == _GENERATED_FAMILY:
                count = _generated_count(conn, project_key)
                table = "second_brain_research_packets+daily_brief_runs"
            elif family == _CORRESPONDENCE_FAMILY:
                count = _correspondence_count(conn, project_key)
                table = "email_thread_summaries"
            else:
                table, where_extra = _FAMILY_TABLE[family]
                count = (
                    _family_count(conn, table, where_extra, project_key)
                    if _table_exists(conn, table)
                    else 0
                )
            total += count
            status = "covered" if count > 0 else "empty"
            families[family] = {
                "has_reader": True,
                "table": table,
                "row_count": count,
                "coverage_status": status,
            }
            if count > 0:
                covered.append(family)
            else:
                empty.append(family)
                warnings.append(f"empty_family:{family}")

        # Per-family shares + dominant family.
        dominant_family: str | None = None
        dominant_share = 0.0
        for family in covered:
            share = round(families[family]["row_count"] / total, 4) if total else 0.0
            families[family]["share"] = share
            if share > dominant_share:
                dominant_share = share
                dominant_family = family

        coverage_layers = {
            "deterministic_reader_families": [
                f for f in ALLOWLISTED_SOURCE_FAMILIES if f in READER_REGISTRY
            ],
            "deterministic_covered_families": covered,
            "approved_manifest_categories": _approved_manifest_categories(),
            "vector_indexed_families": _applied_vector_families(conn),
            "deferred_families_no_reader": deferred,
            "deferred_memory_substrate": True,
        }

        return {
            "mart": "phase_09_corpus_balance",
            "schema_version": schema_version,
            "project_scope": project_key or "all",
            "total_corpus_rows": total,
            "families": families,
            "covered_families": covered,
            "empty_families": empty,
            "deferred_families": deferred,
            "covered_family_count": len(covered),
            "dominant_family": dominant_family,
            "dominant_share": dominant_share,
            "coverage_layers": coverage_layers,
            "warnings": warnings,
            "excluded_raw_families_count": len(EXCLUDED_FAMILIES),
            "advisory_only": True,
            "note": (
                "Coverage + balance signals only over the retrieval corpus (allowlisted families). "
                "No raw families counted; no promotion, no writes, no determination."
            ),
            "guardrails": _GUARDRAILS,
        }
    finally:
        conn.close()


_GUARDRAILS = {
    "read_only": True,
    "metadata_only": True,
    "advisory_only_no_determination": True,
    "no_external_writeback": True,
}


def build_retrieval_coverage_layers(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Read-only coverage layers distinguishing deterministic-reader vs approved-manifest vs
    vector-indexed vs deferred coverage. Thin wrapper over the corpus-balance mart (single source)."""
    return dict(build_corpus_balance_mart(db_path, project_key=project_key)["coverage_layers"])


def evaluate_corpus_balance_gate(mart: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed corpus-balance gate: balanced requires enough covered families + no dominance."""
    min_covered = int(policy.get("min_covered_families", 5))
    max_share = float(policy.get("max_dominant_family_share", 0.6))
    covered = int(mart["covered_family_count"])
    dominant_share = float(mart["dominant_share"])
    total = int(mart["total_corpus_rows"])

    reasons: list[str] = []
    if total == 0:
        reasons.append("empty_corpus")
    if covered < min_covered:
        reasons.append(f"too_few_covered_families:{covered}<{min_covered}")
    if dominant_share > max_share:
        reasons.append(
            f"dominant_family_share_exceeds:{dominant_share}>{max_share}"
            f" ({mart.get('dominant_family')})"
        )
    balanced = not reasons
    return {
        "fail_closed": True,
        "corpus_balance_ok": balanced,
        "verdict": "balanced" if balanced else "imbalanced",
        "covered_family_count": covered,
        "min_covered_families": min_covered,
        "dominant_family": mart.get("dominant_family"),
        "dominant_share": dominant_share,
        "max_dominant_family_share": max_share,
        "blocking_reasons": reasons,
        "advisory_only": True,
    }


def build_corpus_balance_proof(db_path: str | None = None) -> dict[str, Any]:
    """Wrap policy-load (fail-closed) + mart + gate + guard-clean / no-raw attestation."""
    resolved = db_path or str(PathPolicy().get_db_path())

    policy_loaded = True
    policy_error: str | None = None
    policy: dict[str, Any] = {}
    try:
        policy = load_corpus_balance_policy()
    except CorpusBalancePolicyError as exc:
        policy_loaded = False
        policy_error = type(exc).__name__

    mart = build_corpus_balance_mart(resolved, project_key=None)
    gate = (
        evaluate_corpus_balance_gate(mart, policy)
        if policy_loaded
        else {
            "fail_closed": True,
            "corpus_balance_ok": False,
            "verdict": "policy_missing",
            "blocking_reasons": ["corpus_balance_policy_not_loaded"],
            "advisory_only": True,
        }
    )

    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        # Guard-column attestation over the corpus tables that carry guard CHECK(=0) columns.
        guard_results: dict[str, Any] = {}
        guard_violation = False
        for table in _GUARDED_TABLES:
            if not _table_exists(conn, table):
                guard_results[table] = {"present": False}
                continue
            guards = _guard_columns(conn, table)
            guard_sum = 0
            if guards:
                expr = "+".join(f"COALESCE(SUM({c}),0)" for c in guards)
                guard_sum = int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0])
            guard_results[table] = {
                "present": True,
                "guard_columns": len(guards),
                "guard_sum": guard_sum,
            }
            if guard_sum != 0:
                guard_violation = True

        # Forbidden raw-content scan over present corpus text/JSON columns (report table.column only).
        raw_findings: list[str] = []
        for table, cols in _SCAN_COLUMNS.items():
            if not _table_exists(conn, table):
                continue
            present = _columns(conn, table)
            for col in cols:
                if col not in present:
                    continue
                for (val,) in conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"):
                    if isinstance(val, str) and _FORBIDDEN.search(val):
                        raw_findings.append(f"{table}.{col}")
                        break
    finally:
        conn.close()

    if _FORBIDDEN.search(json.dumps(mart, default=str)):
        raw_findings.append("mart")

    schema_ok = mart["schema_version"] == LATEST_SCHEMA_VERSION
    proof_passed = bool(policy_loaded and schema_ok and not guard_violation and not raw_findings)
    return {
        "proof": "phase_09_corpus_balance",
        "schema_version": mart["schema_version"],
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_ok": schema_ok,
        "proof_passed": proof_passed,
        "policy_loaded": policy_loaded,
        "policy_error": policy_error,
        "policy_version": policy.get("version") if policy_loaded else None,
        "advisory_only": True,
        "no_determination_attested": not guard_violation,
        "guard_violation": guard_violation,
        "guard_columns": guard_results,
        "raw_content_findings": raw_findings,
        "corpus_balance_ok": gate.get("corpus_balance_ok"),
        "gate": gate,
        "mart": mart,
    }
