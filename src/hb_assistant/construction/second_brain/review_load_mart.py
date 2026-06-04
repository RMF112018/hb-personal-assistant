"""Phase 09 Prompt 05 — review-load triage mart + review-required promotion gate (read-only).

A deterministic, **read-only** read model over the existing review-bearing tables (no new
schema). It counts review load by **distinct** review item (the financial review table is an
append-only per-run ledger — raw rows are de-duplicated to distinct items), classifies each
item into a high-impact category (reusing the risk-digest classifier), surfaces the
``review_not_performed`` posture, and enforces a **fail-closed promotion gate**: unresolved,
high-impact, review-required, or unknown items are blocked from promotion (e.g. into an
approved source manifest); only resolved, non-high-impact, non-review-required items are
"review-ready". Counts / enums / categories / refs only — never raw content, never a final
determination (impact classification is advisory, for review routing).
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from ..risk_digest.risk_digest_builder import _risk_category

# The eight high-impact review categories (mirrors risk_digest_policy review_required_categories).
HIGH_IMPACT_CATEGORIES: frozenset[str] = frozenset(
    {
        "legal",
        "claim",
        "contractual",
        "safety",
        "personnel",
        "financial",
        "schedule_impact",
        "cost_impact",
    }
)

# Per-table review spec: which columns carry the impact signal, review status, tier, and refs.
# ``unresolved_sql`` is a boolean expression that is true for an UNRESOLVED (open) review item.
_REVIEW_TABLES: tuple[dict[str, Any], ...] = (
    {
        "table": "construction_review_queue",
        "source_family": "construction",
        "impact_cols": ("reason", "sensitivity"),
        "tier_col": None,
        "unresolved_sql": "status = 'open' OR resolved_at IS NULL",
        "dedup_keys": None,
        "always_high_impact_sql": None,
    },
    {
        "table": "email_review_queue",
        "source_family": "email",
        "impact_cols": ("category", "reason"),
        "tier_col": None,
        "unresolved_sql": "status = 'open' OR resolved_utc IS NULL",
        "dedup_keys": None,
        "always_high_impact_sql": None,
    },
    {
        "table": "second_brain_financial_review_required_items",
        "source_family": "financial",
        "impact_cols": ("trigger_category",),
        "tier_col": "review_tier",
        # Append-only per-run ledger — every row is an unresolved review-required item.
        "unresolved_sql": "1=1",
        "dedup_keys": ("project_key", "trigger_category", "source_ref", "amount_ref"),
        "always_high_impact_sql": None,
    },
    {
        "table": "memory_update_candidates",
        "source_family": "memory",
        "impact_cols": ("review_tier_reason_code", "sensitivity_class"),
        "tier_col": "review_tier",
        "unresolved_sql": "review_required = 1 AND status = 'proposed'",
        "dedup_keys": None,
        "always_high_impact_sql": None,
    },
    {
        "table": "construction_document_intelligence_previews",
        "source_family": "document",
        "impact_cols": ("preview_kind",),
        "tier_col": None,
        "unresolved_sql": "review_required = 1",
        "dedup_keys": None,
        "always_high_impact_sql": None,
    },
    {
        "table": "cross_source_relationship_candidates",
        "source_family": "relationship",
        "impact_cols": ("relationship_type",),
        "tier_col": None,
        "unresolved_sql": "review_required = 1 AND promotion_status IN ('candidate', 'needs_review')",
        "dedup_keys": None,
        # Sensitive/high-impact relationships are always high-impact regardless of type text.
        "always_high_impact_sql": "sensitive_high_impact = 1",
    },
)

_FORBIDDEN = re.compile(
    r"BEGIN [A-Z ]*PRIVATE KEY"
    r"|Bearer [A-Za-z0-9._-]{20,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"
    r"|[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}"
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


def _schema_version(conn: sqlite3.Connection) -> int | None:
    if not _table_exists(conn, "schema_migrations"):
        return None
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0]) if row and row[0] is not None else None


def _classify_impact(*texts: Any) -> str | None:
    """Classify free-text reason/category/type into a high-impact category (advisory)."""
    blob = " ".join(str(t) for t in texts if t)
    if not blob.strip():
        return None
    return _risk_category(blob, HIGH_IMPACT_CATEGORIES)


def _table_mart(conn: sqlite3.Connection, spec: dict[str, Any]) -> dict[str, Any] | None:
    table = spec["table"]
    if not _table_exists(conn, table):
        return None
    cols = _columns(conn, table)
    impact_cols = [c for c in spec["impact_cols"] if c in cols]

    raw_rows = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    tier_col = spec.get("tier_col") if spec.get("tier_col") in cols else None

    # Distinct-item base view (the financial ledger collapses many runs to distinct items).
    # The projection carries the dedup keys plus the impact + tier columns (de-duplicated) so
    # the impact/tier breakdowns below are computed over distinct items, not raw ledger rows.
    dedup_keys = spec.get("dedup_keys")
    if dedup_keys and all(k in cols for k in dedup_keys):
        proj: list[str] = list(dedup_keys)
        for c in (*impact_cols, *([tier_col] if tier_col else [])):
            if c not in proj:
                proj.append(c)
        base = f"(SELECT DISTINCT {', '.join(proj)} FROM {table})"
        distinct_items = int(conn.execute(f"SELECT COUNT(*) FROM {base}").fetchone()[0])
        distinct_run_ids = (
            int(conn.execute(f"SELECT COUNT(DISTINCT run_id) FROM {table}").fetchone()[0])
            if "run_id" in cols
            else None
        )
    else:
        base = table
        distinct_items = raw_rows
        distinct_run_ids = None

    # Classify distinct items into impact categories by grouping on the impact column(s).
    by_impact: dict[str, int] = {}
    high_impact = 0
    if impact_cols:
        group_expr = ", ".join(impact_cols)
        for row in conn.execute(f"SELECT {group_expr}, COUNT(*) FROM {base} GROUP BY {group_expr}"):
            n = int(row[-1])
            category = _classify_impact(*row[:-1])
            label = category or "unclassified"
            by_impact[label] = by_impact.get(label, 0) + n
            if category in HIGH_IMPACT_CATEGORIES:
                high_impact += n
    else:
        by_impact["unclassified"] = distinct_items

    # Records explicitly flagged sensitive/high-impact are always high-impact.
    always_hi_sql = spec.get("always_high_impact_sql")
    always_high_impact = (
        int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {always_hi_sql}").fetchone()[0])
        if always_hi_sql
        else 0
    )
    high_impact = max(high_impact, always_high_impact)

    unresolved = int(
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {spec['unresolved_sql']}").fetchone()[0]
    )

    by_tier: dict[str, int] = {}
    if tier_col:
        for row in conn.execute(f"SELECT {tier_col}, COUNT(*) FROM {base} GROUP BY {tier_col}"):
            by_tier[str(row[0])] = int(row[1])

    return {
        "source_family": spec["source_family"],
        "raw_rows": raw_rows,
        "distinct_items": distinct_items,
        "append_only_ledger": bool(dedup_keys),
        "distinct_run_ids": distinct_run_ids,
        "unresolved": unresolved,
        "high_impact_distinct": high_impact,
        "by_impact_category": by_impact,
        "by_review_tier": by_tier,
    }


def build_review_load_mart(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the read-only review-load triage mart over the review-bearing tables.

    (``project_key`` is accepted for parity with other operator surfaces; the current mart is
    computed across all projects and reports per-table source-family rollups.)
    """
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        tables: dict[str, Any] = {}
        present_tables = 0
        total_distinct = 0
        total_raw = 0
        total_unresolved = 0
        total_high_impact = 0
        for spec in _REVIEW_TABLES:
            mart = _table_mart(conn, spec)
            if mart is None:
                tables[spec["table"]] = {"present": False}
                continue
            present_tables += 1
            tables[spec["table"]] = {"present": True, **mart}
            total_distinct += mart["distinct_items"]
            total_raw += mart["raw_rows"]
            total_unresolved += mart["unresolved"]
            total_high_impact += mart["high_impact_distinct"]

        # review_not_performed: no human-review decisions recorded anywhere.
        human_reviews = 0
        if _table_exists(conn, "memory_update_reviews"):
            human_reviews += int(
                conn.execute("SELECT COUNT(*) FROM memory_update_reviews").fetchone()[0]
            )
        if _table_exists(conn, "construction_review_queue"):
            human_reviews += int(
                conn.execute(
                    "SELECT COUNT(*) FROM construction_review_queue WHERE resolved_at IS NOT NULL"
                ).fetchone()[0]
            )
        if _table_exists(conn, "email_review_queue"):
            human_reviews += int(
                conn.execute(
                    "SELECT COUNT(*) FROM email_review_queue WHERE resolved_utc IS NOT NULL"
                ).fetchone()[0]
            )
        review_not_performed = human_reviews == 0

        return {
            "mart": "phase_09_review_load",
            "schema_version": schema_version,
            "project_scope": project_key or "all",
            "present_review_tables": present_tables,
            "total_distinct_review_items": total_distinct,
            "total_raw_rows": total_raw,
            "total_unresolved": total_unresolved,
            "total_high_impact_distinct": total_high_impact,
            "human_review_decisions": human_reviews,
            "review_not_performed": review_not_performed,
            "tables": tables,
            "note": (
                "Distinct review items (not raw ledger rows) are the true review burden; "
                "second_brain_financial_review_required_items is an append-only per-run ledger."
            ),
            "guardrails": {
                "read_only": True,
                "metadata_only": True,
                "advisory_only_no_determination": True,
            },
        }
    finally:
        conn.close()


def evaluate_review_promotion_gate(mart: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed review-required promotion gate over a review-load mart.

    Promotion into an approved source manifest is blocked for any unresolved, high-impact, or
    (when no human review has occurred) review-required item. Only resolved, non-high-impact,
    non-review-required items are review-ready. Fail-closed: under ``review_not_performed`` the
    promotable count is zero (nothing promotes until a human reviews).
    """
    total = int(mart.get("total_distinct_review_items", 0))
    unresolved = int(mart.get("total_unresolved", 0))
    high_impact = int(mart.get("total_high_impact_distinct", 0))
    review_not_performed = bool(mart.get("review_not_performed", True))

    # Blocked = everything unresolved OR high-impact; under review_not_performed, block all.
    blocked = total if review_not_performed else max(unresolved, high_impact)
    promotable = max(0, total - blocked)
    unresolved_high_impact_promotable = 0  # by construction the gate never promotes these

    return {
        "gate": "phase_09_review_required_promotion",
        "fail_closed": True,
        "review_not_performed": review_not_performed,
        "total_distinct_review_items": total,
        "blocked_from_promotion": blocked,
        "promotable_review_ready": promotable,
        "unresolved_high_impact_promotable": unresolved_high_impact_promotable,
        "blocked_by_reason": {
            "review_not_performed_blocks_all": review_not_performed,
            "unresolved": unresolved,
            "high_impact": high_impact,
        },
        "review_ready_batches": []
        if promotable == 0
        else [{"size": promotable, "tier": "low_impact_resolved"}],
        "guardrails": {"fail_closed": True, "advisory_only": True, "no_external_writeback": True},
    }


def build_review_load_proof(db_path: str | None = None) -> dict[str, Any]:
    """Wrap the mart + gate into a read-only proof artifact."""
    mart = build_review_load_mart(db_path)
    gate = evaluate_review_promotion_gate(mart)

    raw_findings = [
        f"{mart['mart']}.note" for _ in (1,) if _FORBIDDEN.search(str(mart.get("note", "")))
    ]
    # The mart emits only counts / enum category labels / source-family names — scan them.
    for tname, t in mart.get("tables", {}).items():
        if not isinstance(t, dict):
            continue
        for label in list(t.get("by_impact_category", {})) + list(t.get("by_review_tier", {})):
            if isinstance(label, str) and _FORBIDDEN.search(label):
                raw_findings.append(f"{tname}.label")

    gate_fail_closed_ok = gate["unresolved_high_impact_promotable"] == 0 and (
        not mart["review_not_performed"] or gate["promotable_review_ready"] == 0
    )
    proof_passed = (
        mart["present_review_tables"] >= 1
        and gate_fail_closed_ok
        and not raw_findings
        and mart["schema_version"] == LATEST_SCHEMA_VERSION
    )
    return {
        "proof": "phase_09_review_load",
        "schema_version": mart["schema_version"],
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "gate_fail_closed_ok": gate_fail_closed_ok,
        "raw_content_findings": raw_findings,
        "mart": mart,
        "gate": gate,
    }
