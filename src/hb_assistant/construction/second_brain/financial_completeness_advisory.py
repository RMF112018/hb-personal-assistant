"""Phase 09 Prompt 06 — advisory financial data-completeness mart (read-only).

A deterministic, **read-only** advisory completeness assessment over the existing financial
fact tables. It profiles currency / period / WBS / cost-code completeness and orphan risk,
and emits **advisory recommendations + review labels** — a project-default-currency fallback
recommendation, a period-enrichment advisory, and a WBS/cost-code reconciliation advisory —
**before semantic retrieval over financial outputs**.

It is strictly advisory: it **never assigns a currency, sets a period, makes a financial /
claim / entitlement / payment determination, writes to the facts, or routes anything into the
review ledger**. Outputs are counts / enums / ISO-currency codes / labels only — never a raw
financial amount (money values are never read or echoed). Read-only; never writes.
"""

from __future__ import annotations

import re
import sqlite3
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

# Financial fact tables and the completeness columns each exposes (None = column absent).
_FACT_TABLES: tuple[dict[str, Any], ...] = (
    {
        "table": "procore_financial_amount_facts",
        "currency": "currency_iso_code",
        "period": ("period_start", "period_end"),
        "wbs": "wbs_code_id",
        "cost": "cost_code_id",
    },
    {
        "table": "procore_financial_line_items",
        "currency": "currency_iso_code",
        "period": None,
        "wbs": "wbs_code_id",
        "cost": "cost_code_id",
    },
    {
        "table": "procore_financial_budget_rows",
        "currency": None,
        "period": None,
        "wbs": "wbs_code_id",
        "cost": "cost_code_id",
    },
    {
        "table": "procore_financial_change_order_line_items",
        "currency": "currency_iso_code",
        "period": None,
        "wbs": "wbs_code_id",
        "cost": "cost_code_id",
    },
)

_NORMALIZED_TABLE = "second_brain_financial_amount_facts_normalized"

# 08C snapshot tables carrying the financial guard columns (re-attested clean, never written).
_GUARDED_SNAPSHOT_TABLES: tuple[str, ...] = (
    "second_brain_financial_currency_completeness_snapshots",
    "second_brain_financial_wbs_cost_code_snapshots",
    "second_brain_financial_source_coverage_snapshots",
)
_FINANCIAL_GUARD_COLUMNS: tuple[str, ...] = (
    "financial_determination_performed",
    "payment_decision_performed",
    "claim_or_entitlement_decision_performed",
    "external_writeback_performed",
    "raw_financial_source_payload_persisted",
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


def _null_count(conn: sqlite3.Connection, table: str, col: str) -> int:
    return int(
        conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL OR {col} = ''").fetchone()[
            0
        ]
    )


def _rate(n: int, total: int) -> float:
    return round(n / total, 4) if total else 0.0


def _currency_advisory(conn: sqlite3.Connection) -> dict[str, Any]:
    """Per-project advisory currency recommendation (dominant currency or default-required)."""
    table = "procore_financial_amount_facts"
    if not _table_exists(conn, table) or "currency_iso_code" not in _columns(conn, table):
        return {"applicable": False}
    total = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    null_n = _null_count(conn, table, "currency_iso_code")
    # Dominant non-null currency per project (advisory only; never assigned).
    per_project: dict[str, Any] = {}
    for pk, code, n in conn.execute(
        f"SELECT project_key, currency_iso_code, COUNT(*) FROM {table} "
        "WHERE currency_iso_code IS NOT NULL AND currency_iso_code <> '' "
        "GROUP BY project_key, currency_iso_code ORDER BY COUNT(*) DESC"
    ):
        per_project.setdefault(str(pk), {"dominant_currency": code, "explicit_count": int(n)})
    # Projects with any facts but no explicit currency → default-required (not derivable).
    projects = [str(r[0]) for r in conn.execute(f"SELECT DISTINCT project_key FROM {table}")]
    recommendations: dict[str, Any] = {}
    for pk in projects:
        if pk in per_project:
            recommendations[pk] = {
                "recommendation": "advisory_use_dominant_source_currency",
                "dominant_currency": per_project[pk]["dominant_currency"],
                "eligible_for_evidence_backed_default": True,
            }
        else:
            recommendations[pk] = {
                "recommendation": "project_default_currency_required",
                "dominant_currency": None,
                "eligible_for_evidence_backed_default": False,
                "reason": "no source currency present; cannot derive — requires policy/document default",
            }
    return {
        "applicable": True,
        "total_facts": total,
        "currency_null": null_n,
        "currency_null_rate": _rate(null_n, total),
        "per_project_recommendation": recommendations,
        "advisory_label": "currency_advisory_review_required",
    }


def _period_advisory(conn: sqlite3.Connection) -> dict[str, Any]:
    table = "procore_financial_amount_facts"
    if not _table_exists(conn, table):
        return {"applicable": False}
    cols = _columns(conn, table)
    if "period_start" not in cols:
        return {"applicable": False}
    total = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    null_n = int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table} "
            "WHERE period_start IS NULL OR period_start = '' "
            "OR period_end IS NULL OR period_end = ''"
        ).fetchone()[0]
    )
    return {
        "applicable": True,
        "total_facts": total,
        "period_null": null_n,
        "period_null_rate": _rate(null_n, total),
        "recommendation": "period_context_required",
        "reason": "period is source-context dependent (invoice/contract/budget date) — not derivable",
        "advisory_label": "period_advisory_review_required",
    }


def _wbs_cost_advisory(conn: sqlite3.Connection) -> dict[str, Any]:
    """Orphan/missing WBS + cost-code presence detection (no parent tables exist)."""
    per_table: dict[str, Any] = {}
    wbs_orphans = 0
    cost_orphans = 0
    for spec in _FACT_TABLES:
        table = spec["table"]
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        total = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        wbs_null = _null_count(conn, table, spec["wbs"]) if spec["wbs"] in cols else None
        cost_null = _null_count(conn, table, spec["cost"]) if spec["cost"] in cols else None
        per_table[table] = {
            "total": total,
            "wbs_orphan_or_missing": wbs_null,
            "cost_code_orphan_or_missing": cost_null,
        }
        wbs_orphans += wbs_null or 0
        cost_orphans += cost_null or 0
    return {
        "applicable": bool(per_table),
        "wbs_orphan_or_missing_total": wbs_orphans,
        "cost_code_orphan_or_missing_total": cost_orphans,
        "per_table": per_table,
        "recommendation": "wbs_cost_code_context_required",
        "reason": "no WBS/cost-code parent tables exist — presence-only detection; reconcile from source",
        "advisory_label": "wbs_cost_code_advisory_review_required",
    }


def build_financial_completeness_advisory(
    db_path: str | None = None, *, project_key: str | None = None
) -> dict[str, Any]:
    """Build the read-only advisory financial-completeness mart.

    (``project_key`` accepted for parity with other operator surfaces; the current mart is
    computed across all projects with per-project currency recommendations.)
    """
    resolved = db_path or str(PathPolicy().get_db_path())
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        schema_version = _schema_version(conn)
        normalized_rows = (
            int(conn.execute(f"SELECT COUNT(*) FROM {_NORMALIZED_TABLE}").fetchone()[0])
            if _table_exists(conn, _NORMALIZED_TABLE)
            else 0
        )
        present_fact_tables = [s["table"] for s in _FACT_TABLES if _table_exists(conn, s["table"])]
        return {
            "mart": "phase_09_financial_completeness_advisory",
            "schema_version": schema_version,
            "project_scope": project_key or "all",
            "present_fact_tables": present_fact_tables,
            "normalized_layer_populated": normalized_rows > 0,
            "normalized_rows": normalized_rows,
            "currency": _currency_advisory(conn),
            "period": _period_advisory(conn),
            "wbs_cost_code": _wbs_cost_advisory(conn),
            "advisory_only": True,
            "note": (
                "Advisory recommendations + review labels only — no currency assigned, no period set, "
                "no determination, no writes, nothing routed to the review ledger."
            ),
            "guardrails": {
                "read_only": True,
                "advisory_only_no_determination": True,
                "no_external_writeback": True,
                "money_never_echoed": True,
            },
        }
    finally:
        conn.close()


def _guard_columns_clean(conn: sqlite3.Connection) -> dict[str, Any]:
    """Re-attest the 08C snapshot guard columns are clean (the mart writes nothing)."""
    results: dict[str, Any] = {}
    violation = False
    for table in _GUARDED_SNAPSHOT_TABLES:
        if not _table_exists(conn, table):
            results[table] = {"present": False}
            continue
        cols = _columns(conn, table)
        guards = [c for c in _FINANCIAL_GUARD_COLUMNS if c in cols]
        guard_sum = 0
        if guards:
            expr = "+".join(f"COALESCE(SUM({c}),0)" for c in guards)
            guard_sum = int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0])
        adv_ok = True
        if "advisory_only" in cols:
            non_adv = int(
                conn.execute(f"SELECT COUNT(*) FROM {table} WHERE advisory_only <> 1").fetchone()[0]
            )
            adv_ok = non_adv == 0
        results[table] = {"present": True, "guard_sum": guard_sum, "advisory_only_ok": adv_ok}
        if guard_sum != 0 or not adv_ok:
            violation = True
    results["violation"] = violation
    return results


def build_financial_completeness_advisory_proof(db_path: str | None = None) -> dict[str, Any]:
    """Wrap the advisory mart + an advisory-only / no-determination / no-writeback attestation."""
    resolved = db_path or str(PathPolicy().get_db_path())
    mart = build_financial_completeness_advisory(resolved)
    conn = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    try:
        guards = _guard_columns_clean(conn)
    finally:
        conn.close()

    import json

    raw_findings: list[str] = []
    if _FORBIDDEN.search(json.dumps(mart, default=str)):
        raw_findings.append("mart")

    proof_passed = (
        bool(mart["present_fact_tables"])
        and not guards["violation"]
        and not raw_findings
        and mart["advisory_only"] is True
        and mart["schema_version"] == LATEST_SCHEMA_VERSION
    )
    return {
        "proof": "phase_09_financial_completeness_advisory",
        "schema_version": mart["schema_version"],
        "schema_version_expected": LATEST_SCHEMA_VERSION,
        "proof_passed": proof_passed,
        "advisory_only": True,
        "no_determination_attested": not guards["violation"],
        "guard_columns": guards,
        "raw_content_findings": raw_findings,
        "mart": mart,
    }
