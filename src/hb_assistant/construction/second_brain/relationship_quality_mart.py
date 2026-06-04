"""Phase 09 Prompt 10 — advisory cross-source relationship quality mart (read-only).

A deterministic, **read-only** quality profile over the V25 cross-source relationship tables
(`cross_source_relationship_candidates`, `cross_source_relationships`, `source_evidence_trails`),
built **before semantic retrieval** consumes the relationship graph. It reports **link ratios**
(promotion / review / determinism / human-promotion shares), the **confidence-class distribution**
and `confidence_score` spread, and **orphan / duplicate** quality signals — promoted edges that lost
their candidate provenance, candidates/relationships missing an evidence trail, stale/unresolved
tallies, and source→target pairs carrying more than one relationship type.

It is strictly advisory: it **never promotes, rejects, writes, or makes a final
financial/legal/contractual/claim/entitlement/payment/schedule/safety determination** — orphan,
duplicate, and confidence outputs are quality signals + source-coverage warnings only. Outputs are
counts / ratios / enums only — no raw content, prompts, responses, tokens, URLs, or PEMs. The mart
opens the database read-only and never writes; it is database-path agnostic so it can run over the
operator DB, a controlled proof DB, or a temporary test DB.
"""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..risk_digest.risk_digest_builder import _risk_category
from .review_load_mart import HIGH_IMPACT_CATEGORIES

_CANDIDATES = "cross_source_relationship_candidates"
_RELATIONSHIPS = "cross_source_relationships"
_EVIDENCE_TRAILS = "source_evidence_trails"
_RELATIONSHIP_TABLES: tuple[str, ...] = (_CANDIDATES, _RELATIONSHIPS, _EVIDENCE_TRAILS)

# The 7-value confidence_class enum shared by candidates + promoted relationships.
_CONFIDENCE_CLASSES: tuple[str, ...] = (
    "deterministic",
    "strong_heuristic",
    "weak_heuristic",
    "model_proposed",
    "human_promoted",
    "rejected",
    "stale_or_unresolved",
)

# JSON / text columns scanned for forbidden raw-content shapes (per table).
_SCAN_COLUMNS: dict[str, tuple[str, ...]] = {
    _CANDIDATES: ("signals_json", "source_reference_json"),
    _RELATIONSHIPS: ("signals_json", "source_reference_json"),
    _EVIDENCE_TRAILS: ("source_refs_json", "stale_unknown_flags_json"),
}

# Forbidden raw-content value shapes (never echo a match — only the table.column).
_FORBIDDEN = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY"
    r"|Bearer [A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"|[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}"
    r"|https?://[^\s\"']*[?&](sig|token)="
)


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


def _count(
    conn: sqlite3.Connection, table: str, where: str = "", params: tuple[Any, ...] = ()
) -> int:
    sql = f"SELECT COUNT(*) FROM {table}"
    if where:
        sql += f" WHERE {where}"
    return int(conn.execute(sql, params).fetchone()[0])


def _rate(n: int, total: int) -> float:
    return round(n / total, 4) if total else 0.0


def _confidence_distribution(
    conn: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...]
) -> dict[str, int]:
    dist: dict[str, int] = dict.fromkeys(_CONFIDENCE_CLASSES, 0)
    for cls, n in conn.execute(
        f"SELECT confidence_class, COUNT(*) FROM {table} WHERE {where} GROUP BY confidence_class",
        params,
    ):
        dist[str(cls)] = dist.get(str(cls), 0) + int(n)
    return dist


def _score_spread(
    conn: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...]
) -> dict[str, Any]:
    if "confidence_score" not in _columns(conn, table):
        return {"applicable": False}
    row = conn.execute(
        f"SELECT MIN(confidence_score), AVG(confidence_score), MAX(confidence_score) "
        f"FROM {table} WHERE {where}",
        params,
    ).fetchone()
    if row is None or row[0] is None:
        return {"applicable": True, "min": None, "avg": None, "max": None}
    return {
        "applicable": True,
        "min": round(float(row[0]), 4),
        "avg": round(float(row[1]), 4),
        "max": round(float(row[2]), 4),
    }


def _high_impact_relationship_types(
    conn: sqlite3.Connection, table: str, where: str, params: tuple[Any, ...]
) -> dict[str, int]:
    """Advisory tally of high-impact relationship_type values (routing signal, never a determination)."""
    out: dict[str, int] = {}
    for rtype, n in conn.execute(
        f"SELECT relationship_type, COUNT(*) FROM {table} WHERE {where} GROUP BY relationship_type",
        params,
    ):
        category = _risk_category(str(rtype), HIGH_IMPACT_CATEGORIES)
        if category:
            out[category] = out.get(category, 0) + int(n)
    return out


def _candidate_profile(
    conn: sqlite3.Connection, scope: str, params: tuple[Any, ...]
) -> dict[str, Any]:
    total = _count(conn, _CANDIDATES, scope, params)
    promoted = _count(conn, _CANDIDATES, f"{scope} AND promotion_status = 'promoted'", params)
    review_required = _count(conn, _CANDIDATES, f"{scope} AND review_required = 1", params)
    sensitive = _count(conn, _CANDIDATES, f"{scope} AND sensitive_high_impact = 1", params)
    deterministic = _count(conn, _CANDIDATES, f"{scope} AND deterministic = 1", params)
    model_proposed = _count(conn, _CANDIDATES, f"{scope} AND model_proposed = 1", params)
    return {
        "total": total,
        "by_confidence_class": _confidence_distribution(conn, _CANDIDATES, scope, params),
        "confidence_score": _score_spread(conn, _CANDIDATES, scope, params),
        "promotion_status_promoted": promoted,
        "review_required": review_required,
        "sensitive_high_impact": sensitive,
        "deterministic": deterministic,
        "model_proposed": model_proposed,
        "high_impact_relationship_types": _high_impact_relationship_types(
            conn, _CANDIDATES, scope, params
        ),
        "link_ratios": {
            "promoted_share": _rate(promoted, total),
            "review_required_share": _rate(review_required, total),
            "deterministic_share": _rate(deterministic, total),
            "model_proposed_share": _rate(model_proposed, total),
            "sensitive_high_impact_share": _rate(sensitive, total),
        },
    }


def _relationship_profile(
    conn: sqlite3.Connection, scope: str, params: tuple[Any, ...]
) -> dict[str, Any]:
    total = _count(conn, _RELATIONSHIPS, scope, params)
    human = _count(conn, _RELATIONSHIPS, f"{scope} AND promoted_by = 'human'", params)
    review_required = _count(conn, _RELATIONSHIPS, f"{scope} AND review_required = 1", params)
    return {
        "total": total,
        "by_confidence_class": _confidence_distribution(conn, _RELATIONSHIPS, scope, params),
        "promoted_by_human": human,
        "promoted_by_deterministic": total - human,
        "review_required": review_required,
        "link_ratios": {
            "human_promoted_share": _rate(human, total),
            "review_required_share": _rate(review_required, total),
        },
    }


def _orphan_and_duplicate_signals(
    conn: sqlite3.Connection, scope: str, params: tuple[Any, ...]
) -> dict[str, Any]:
    """Within-schema referential-gap + multi-edge quality signals (advisory; checkable)."""
    cand_cols = _columns(conn, _CANDIDATES)
    rel_cols = _columns(conn, _RELATIONSHIPS)

    # Promoted relationships that lost their candidate provenance.
    rel_missing_candidate = _count(
        conn,
        _RELATIONSHIPS,
        f"{scope} AND (candidate_id IS NULL OR candidate_id NOT IN "
        f"(SELECT candidate_id FROM {_CANDIDATES}))",
        params,
    )
    # Candidates missing an evidence trail (NULL or dangling) — a true provenance orphan.
    cand_missing_trail = (
        _count(
            conn,
            _CANDIDATES,
            f"{scope} AND (evidence_trail_id IS NULL OR evidence_trail_id NOT IN "
            f"(SELECT evidence_trail_id FROM {_EVIDENCE_TRAILS}))",
            params,
        )
        if "evidence_trail_id" in cand_cols
        else 0
    )
    # Relationships whose OWN evidence_trail_id is absent/dangling — informational (denormalization),
    # NOT an orphan if the relationship can still reach a trail via its candidate (counted next).
    rel_direct_trail_absent = (
        _count(
            conn,
            _RELATIONSHIPS,
            f"{scope} AND (evidence_trail_id IS NULL OR evidence_trail_id NOT IN "
            f"(SELECT evidence_trail_id FROM {_EVIDENCE_TRAILS}))",
            params,
        )
        if "evidence_trail_id" in rel_cols
        else 0
    )
    # True evidence-orphan: a relationship that can reach an evidence trail by NEITHER its own
    # evidence_trail_id NOR via candidate_id -> candidate.evidence_trail_id.
    rel_evidence_unreachable = (
        int(
            conn.execute(
                f"SELECT COUNT(*) FROM {_RELATIONSHIPS} WHERE {scope} "
                f"AND (evidence_trail_id IS NULL OR evidence_trail_id NOT IN "
                f"(SELECT evidence_trail_id FROM {_EVIDENCE_TRAILS})) "
                f"AND (candidate_id IS NULL OR candidate_id NOT IN "
                f"(SELECT candidate_id FROM {_CANDIDATES} WHERE evidence_trail_id IS NOT NULL "
                f"AND evidence_trail_id IN (SELECT evidence_trail_id FROM {_EVIDENCE_TRAILS})))",
                params,
            ).fetchone()[0]
        )
        if "evidence_trail_id" in rel_cols
        else 0
    )
    # Stale / unresolved tallies.
    cand_stale = _count(
        conn,
        _CANDIDATES,
        f"{scope} AND (confidence_class = 'stale_or_unresolved' OR promotion_status = 'stale')",
        params,
    )
    rel_stale = _count(
        conn,
        _RELATIONSHIPS,
        f"{scope} AND (confidence_class = 'stale_or_unresolved' OR promotion_status = 'stale')",
        params,
    )

    # Multi-edge pairs: same source→target pair carrying more than one relationship_type
    # (exact-duplicate edges are blocked by the UNIQUE constraint; this surfaces near-duplicates).
    multi_edge_pairs = 0
    for table in (_CANDIDATES, _RELATIONSHIPS):
        row = conn.execute(
            "SELECT COUNT(*) FROM (SELECT 1 FROM "
            f"{table} WHERE {scope} "
            "GROUP BY source_family, source_record_ref, target_family, target_record_ref "
            "HAVING COUNT(DISTINCT relationship_type) > 1)",
            params,
        ).fetchone()
        multi_edge_pairs += int(row[0])

    orphan_total = rel_missing_candidate + cand_missing_trail + rel_evidence_unreachable
    return {
        "orphan_total": orphan_total,
        "promoted_missing_candidate": rel_missing_candidate,
        "candidate_missing_evidence_trail": cand_missing_trail,
        "relationship_evidence_unreachable": rel_evidence_unreachable,
        "relationship_direct_evidence_trail_absent": rel_direct_trail_absent,
        "stale_or_unresolved_candidates": cand_stale,
        "stale_or_unresolved_relationships": rel_stale,
        "multi_edge_pairs": multi_edge_pairs,
        "note": (
            "Orphan = promoted edge without a candidate parent, a candidate without an evidence "
            "trail, or a relationship that reaches a trail by neither its own evidence_trail_id nor "
            "its candidate. relationship_direct_evidence_trail_absent is informational only "
            "(denormalization — still traceable via candidate). Multi-edge = one source→target "
            "pair under >1 relationship_type (exact duplicates are blocked by the UNIQUE edge "
            "constraint). Advisory signals only."
        ),
    }


def build_relationship_quality_mart(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the read-only advisory relationship-quality mart (link ratios / confidence / orphans)."""
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        present = [t for t in _RELATIONSHIP_TABLES if _table_exists(conn, t)]
        have_core = (
            _CANDIDATES in present and _RELATIONSHIPS in present and _EVIDENCE_TRAILS in present
        )

        if not have_core:
            return {
                "mart": "phase_09_relationship_quality",
                "schema_version": schema_version,
                "project_scope": project_key or "all",
                "present_relationship_tables": present,
                "populated": False,
                "candidates": {"total": 0},
                "relationships": {"total": 0},
                "evidence_trails": {"total": 0},
                "orphan_duplicate": {},
                "warnings": [],
                "advisory_only": True,
                "guardrails": _GUARDRAILS,
            }

        scope = "project_key = ?" if project_key else "1=1"
        params: tuple[Any, ...] = (project_key,) if project_key else ()

        candidates = _candidate_profile(conn, scope, params)
        relationships = _relationship_profile(conn, scope, params)
        evidence_trails = {"total": _count(conn, _EVIDENCE_TRAILS, scope, params)}
        orphan_dup = _orphan_and_duplicate_signals(conn, scope, params)

        warnings: list[str] = []
        if orphan_dup["orphan_total"]:
            warnings.append(
                f"orphan_total={orphan_dup['orphan_total']} (advisory source-coverage warning)"
            )
        if orphan_dup["multi_edge_pairs"]:
            warnings.append(
                f"multi_edge_pairs={orphan_dup['multi_edge_pairs']} (advisory near-duplicate warning)"
            )
        stale = (
            orphan_dup["stale_or_unresolved_candidates"]
            + orphan_dup["stale_or_unresolved_relationships"]
        )
        if stale:
            warnings.append(f"stale_or_unresolved={stale} (advisory freshness warning)")

        return {
            "mart": "phase_09_relationship_quality",
            "schema_version": schema_version,
            "project_scope": project_key or "all",
            "present_relationship_tables": present,
            "populated": candidates["total"] > 0 or relationships["total"] > 0,
            "candidates": candidates,
            "relationships": relationships,
            "evidence_trails": evidence_trails,
            "promotion_rate_candidates_to_relationships": _rate(
                relationships["total"], candidates["total"]
            ),
            "orphan_duplicate": orphan_dup,
            "warnings": warnings,
            "advisory_only": True,
            "note": (
                "Quality signals only — link ratios, confidence distribution, and orphan/duplicate "
                "counts. No promotion, no rejection, no writes, no determination."
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
    "no_automatic_promotion": True,
}


def build_relationship_quality_proof(db_path: str | None = None) -> dict[str, Any]:
    """Wrap the relationship-quality mart + guard-clean / no-raw / no-determination attestation."""
    resolved = db_path or str(PathPolicy().get_db_path())
    mart = build_relationship_quality_mart(resolved)
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        # Guard-column attestation: the 8 CHECK(=0) guard columns on each table must sum to 0.
        guard_results: dict[str, Any] = {}
        guard_violation = False
        for table in _RELATIONSHIP_TABLES:
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

        # Forbidden raw-content scan over the JSON/text columns (report table.column only).
        raw_findings: list[str] = []
        for table in _RELATIONSHIP_TABLES:
            if not _table_exists(conn, table):
                continue
            cols = _columns(conn, table)
            for col in _SCAN_COLUMNS.get(table, ()):
                if col not in cols:
                    continue
                for (val,) in conn.execute(f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL"):
                    if isinstance(val, str) and _FORBIDDEN.search(val):
                        raw_findings.append(f"{table}.{col}")
                        break
    finally:
        conn.close()

    # Defensive: never echo a raw value even if the mart somehow carried one.
    if _FORBIDDEN.search(json.dumps(mart, default=str)):
        raw_findings.append("mart")

    tables_present = all(_t in mart["present_relationship_tables"] for _t in _RELATIONSHIP_TABLES)
    schema_ok = mart["schema_version"] == LATEST_SCHEMA_VERSION
    proof_passed = bool(
        tables_present
        and schema_ok
        and not guard_violation
        and not raw_findings
        and mart["advisory_only"] is True
    )
    return {
        "proof": "phase_09_relationship_quality",
        "schema_version": mart["schema_version"],
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "schema_ok": schema_ok,
        "proof_passed": proof_passed,
        "advisory_only": True,
        "no_determination_attested": not guard_violation,
        "guard_violation": guard_violation,
        "guard_columns": guard_results,
        "raw_content_findings": raw_findings,
        "mart": mart,
    }
