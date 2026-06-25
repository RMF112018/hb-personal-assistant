"""Phase C — DB-native source-domain snapshot.

Proves the typed snapshot builds deterministically from a controlled SQLite fixture (DB only, no
source packages), is explicit about missing vs zero data, distinguishes sparse from blocked, keeps
source_package internal (never in public output), supports multiple projects, stays read-only, and
imports nothing from CFR.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_db_native_source_snapshot import (
    build_db_native_source_snapshot,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.forecast.source_domain_repository import (
    upsert_budget_detail,
    upsert_cost_entry,
    upsert_monthly_actual,
)
from hb_assistant.store.migrator import SQLiteMigrator
from tests.schedule_project_test_helpers import seed_procore_ep_project

# A deliberately package-like batch name: the redaction test proves it never reaches public output.
_PKG = "twn_cost_forecast_json_package"


def _db() -> str:
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _seed_v59(
    db: str,
    project_key: str,
    *,
    source_package: str = _PKG,
    budget: list[dict] | None = None,
    cost: list[dict] | None = None,
    monthly: list[dict] | None = None,
) -> None:
    conn = sqlite3.connect(db)
    try:
        for i, row in enumerate(budget or [], start=1):
            upsert_budget_detail(
                conn,
                {
                    "project_key": project_key,
                    "budget_code_key": row["budget_code_key"],
                    "source_package": source_package,
                    "cost_code": row.get("cost_code"),
                    "category": row.get("category"),
                    "source_row_number": i,
                    "raw_json": json.dumps(row),
                    "created_utc": "2026-06-20T00:00:00Z",
                },
            )
        for i, row in enumerate(cost or [], start=1):
            upsert_cost_entry(
                conn,
                {
                    "cost_entry_id": f"{project_key}|{source_package}|{i}",
                    "project_key": project_key,
                    "source_package": source_package,
                    "source_row_number": i,
                    "budget_code_key": row.get("budget_code_key"),
                    "accounting_month": row.get("accounting_month"),
                    "raw_json": json.dumps(row),
                    "created_utc": "2026-06-20T00:00:00Z",
                },
            )
        for i, row in enumerate(monthly or [], start=1):
            upsert_monthly_actual(
                conn,
                {
                    "project_key": project_key,
                    "budget_code_key": row["budget_code_key"],
                    "month": row["month"],
                    "type": row["type"],
                    "source_package": source_package,
                    "amount": row.get("amount"),
                    "entry_count": row.get("entry_count"),
                    "source_row_number": i,
                    "raw_json": json.dumps(row),
                    "created_utc": "2026-06-20T00:00:00Z",
                },
            )
        conn.commit()
    finally:
        conn.close()


_BUDGET = [
    {"budget_code_key": "01-100", "cost_code": "01-100", "category": "labor", "amount": "1000.00"},
    {"budget_code_key": "02-200", "cost_code": "02-200", "category": "material", "amount": "0.00"},
]
_COST = [{"budget_code_key": "01-100", "accounting_month": "2026-05", "amount": "250.00"}]
_MONTHLY = [
    {"budget_code_key": "01-100", "month": "2026-05", "type": "actual", "amount": "250.00", "entry_count": 1}
]


def _seed_full_project(db: str, project_key: str, display_name: str) -> None:
    seed_procore_ep_project(db, project_key=project_key, display_name=display_name)
    _seed_v59(db, project_key, budget=_BUDGET, cost=_COST, monthly=_MONTHLY)


# -- 1. builds from a controlled fixture --------------------------------------


def test_builds_from_controlled_fixture() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    snap = build_db_native_source_snapshot("tropical", db_path=db)
    pub = snap.public()
    assert pub["project_key"] == "tropical"
    assert pub["display_name"] == "Tropical Resort"
    assert pub["financial_basis"]["budget_details"]["row_count"] == 2
    assert pub["financial_basis"]["cost_entries"]["row_count"] == 1
    assert pub["financial_basis"]["monthly_actuals"]["row_count"] == 1
    assert pub["financial_basis"]["active_source_batch_present"] is True
    assert set(pub["provenance"]["source_families_present"]) >= {"budget_details", "cost_entries", "monthly_actuals"}
    # A zero-amount budget row is a real input fact (present, not missing).
    amounts = [r.get("amount") for r in pub["financial_basis"]["budget_details"]["rows"]]
    assert "0.00" in amounts
    assert pub["blockers"] == []


# -- 2. missing optional families produce warnings, not crashes ---------------


def test_missing_optional_enrichment_families_warn_not_crash() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    pub = build_db_native_source_snapshot("tropical", db_path=db).public()
    fams = pub["enrichment_families"]
    assert set(fams) == {"commitments", "commitment_changes", "change_events"}
    assert all(f["present"] is False and f["row_count"] == 0 for f in fams.values())
    for name in ("commitments", "commitment_changes", "change_events"):
        assert f"enrichment_family_unavailable:{name}" in pub["warnings"]


# -- 3. missing required financial basis -> explicit blocker ------------------


def test_missing_financial_basis_blocks() -> None:
    db = _db()
    seed_procore_ep_project(db, project_key="barren", display_name="Barren Site")  # identity only
    pub = build_db_native_source_snapshot("barren", db_path=db).public()
    assert pub["readiness"]["readiness_status"] == "blocked"
    assert "no_financial_basis" in pub["blockers"]
    assert pub["financial_basis"]["budget_details"]["present"] is False
    assert pub["financial_basis"]["active_source_batch_present"] is False


def test_unknown_project_blocks_on_identity() -> None:
    db = _db()  # migrated, but no project seeded
    pub = build_db_native_source_snapshot("ghost", db_path=db).public()
    assert pub["blockers"] == ["no_project_identity"]
    assert pub["readiness"]["readiness_status"] == "blocked"


# -- 4. sparse first-run is distinct from blocked -----------------------------


def test_sparse_first_run_distinct_from_blocked() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")  # basis present, no schedule/prior
    pub = build_db_native_source_snapshot("tropical", db_path=db).public()
    # Has a financial basis -> NOT blocked, but thin -> sparse + maturity-driven.
    assert pub["blockers"] == []
    assert pub["readiness"]["readiness_status"] in ("degraded", "ready")
    assert pub["readiness"]["sparse"] is True
    assert pub["readiness"]["forecast_maturity"] in ("baseline_only", "cost_informed")


# -- 5. no paths / package names / raw_json / source_package leak -------------


def test_public_snapshot_is_redaction_safe() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    pub = build_db_native_source_snapshot("tropical", db_path=db).public()
    assert find_redaction_leaks(pub) == []
    blob = json.dumps(pub)
    # The internal (package-like) batch name must never reach public output.
    assert _PKG not in blob
    assert "source_package" not in blob
    assert "cost_forecast_json_package" not in blob
    assert "source_path" not in blob
    assert "raw_json" not in blob
    assert "/Users/" not in blob


def test_source_package_kept_internal_but_available() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    snap = build_db_native_source_snapshot("tropical", db_path=db)
    # Internal attribute resolves the active batch (for later phases)...
    assert snap.active_source_package == _PKG
    # ...but public() exposes only package-safe provenance.
    assert "active_source_package" not in snap.public()["financial_basis"]
    assert snap.public()["financial_basis"]["active_source_batch_present"] is True


# -- 6. multiple project keys supported (not hard-coded tropical) -------------


def test_multiple_project_keys_supported() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    seed_procore_ep_project(db, project_key="harbor", display_name="Harbor Tower")
    _seed_v59(
        db,
        "harbor",
        source_package="harbor_batch_alpha",
        budget=[{"budget_code_key": "03-300", "cost_code": "03-300", "category": "equipment", "amount": "500.00"}],
    )
    trop = build_db_native_source_snapshot("tropical", db_path=db).public()
    harb = build_db_native_source_snapshot("harbor", db_path=db).public()
    assert trop["display_name"] == "Tropical Resort"
    assert harb["display_name"] == "Harbor Tower"
    assert trop["financial_basis"]["budget_details"]["row_count"] == 2
    assert harb["financial_basis"]["budget_details"]["row_count"] == 1
    assert harb["financial_basis"]["cost_entries"]["row_count"] == 0


# -- determinism + read-only --------------------------------------------------


def test_build_is_deterministic_and_read_only() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    before = hashlib.sha256(Path(db).read_bytes()).hexdigest()
    first = build_db_native_source_snapshot("tropical", db_path=db).public()
    second = build_db_native_source_snapshot("tropical", db_path=db).public()
    after = hashlib.sha256(Path(db).read_bytes()).hexdigest()
    assert first == second  # same DB state -> identical snapshot
    assert before == after  # builder did not mutate the DB (read-only)


# -- CFR-independence boundary guard ------------------------------------------


def test_module_has_no_cfr_or_package_dependency() -> None:
    src = Path(
        "src/hb_assistant/construction/analytics/forecast_db_native_source_snapshot.py"
    ).read_text()
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
    forbidden = (
        "construction_financial_review",
        "package_resolution",
        "generate_forecast_context_package",
        "db_source_adapter",
        "run_controlled_context_analysis_workflow",
    )
    leaked = [tok for tok in forbidden if any(tok in name for name in names)]
    assert leaked == [], f"snapshot module references package/CFR symbols: {leaked}"


# =====================================================================================
# Phase E2 — DB-native BudgetDetails cost-basis inputs (procore_ep_budget_detail_rows +
# procore_ep_budget_detail_row_cells). Rows carry stable money columns; the two dynamic
# fields (pending_cost_changes / commitment_invoiced) come only from cells via
# budget_column_roles, with DB-deterministic single-view selection.
# =====================================================================================

_BD_AMOUNT_COLS = (
    "committed_costs",
    "erp_direct_costs",
    "projected_costs",
    "actual_cost",
    "estimated_cost_at_completion",
    "pending_budget_changes",
    "job_to_date_costs",
    "erp_job_to_date_costs",
    "forecast_to_complete",
    "payload_seen_last_utc",
)


def _seed_budgetdetails(db: str, project_key: str, rows: list[dict]) -> None:
    """Seed procore_ep_budget_detail_rows (+ row_cells). Each row: code, view, source_quality,
    money cols, and optional ``cells`` {label: value_decimal_text}."""
    conn = sqlite3.connect(db)
    try:
        for r in rows:
            cells = r.get("cells") or {}
            code = r["code"]
            rec = r.get("record_key") or f"{r['view']}-{code}"
            cols = ["record_key", "endpoint_key", "project_key", "record_id", "budget_view_id",
                    "wbs_flat_code", "canonical_budget_code_key", "source_quality", "is_current"]
            vals: list = [rec, "budget-details", project_key, rec, r["view"], code, code,
                          r.get("source_quality", "live_full_payload"), 1]
            for col in _BD_AMOUNT_COLS:
                if col in r:
                    cols.append(col)
                    vals.append(r[col])
            conn.execute(
                f"INSERT INTO procore_ep_budget_detail_rows ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' for _ in cols)})",
                vals,
            )
            for i, (label, value) in enumerate(cells.items()):
                # a list value means duplicated-conflicting cells for the same label
                for j, v in enumerate(value if isinstance(value, list) else [value]):
                    conn.execute(
                        "INSERT INTO procore_ep_budget_detail_row_cells "
                        "(cell_key, record_key, endpoint_key, column_label, value_decimal_text, "
                        "source_quality, is_current) VALUES (?, ?, ?, ?, ?, ?, 1)",
                        (f"{rec}|{i}|{j}", rec, "budget-details", label, v, "live_full_payload"),
                    )
        conn.commit()
    finally:
        conn.close()


_K = "1000.15-01-426.MAT"


def _cbi_rows(db: str, project_key: str) -> list[dict]:
    pub = build_db_native_source_snapshot(project_key, db_path=db).public()
    return pub["budgetdetails_cost_basis_inputs"]["rows"]


def test_cost_basis_inputs_sourced_from_rows_and_cells() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "5885", "committed_costs": "600.00", "erp_direct_costs": "300.00",
         "projected_costs": "1000.00", "actual_cost": "200.00", "estimated_cost_at_completion": "850.00",
         "pending_budget_changes": "42.00",
         "cells": {"Pending Cost Changes": "100.00", "Commitment Invoiced": "550.00"}},
    ])
    rows = _cbi_rows(db, "tropical")
    assert len(rows) == 1
    r = rows[0]
    assert r["budget_code_key"] == _K
    assert r["erp_direct_costs"] == "300.00"
    assert r["pending_cost_changes"] == "100.00"  # from a row-cell, not a row column
    assert r["commitment_invoiced"] == "550.00"
    assert r["formula_reconciles"] is True  # 600 + 300 + 100 == 1000
    assert r["formula_variance"] == "0.00"
    assert r["missing_formula_fields"] == []
    # pending_budget_changes is carried as budget-side context, never the formula's pending_cost_changes
    assert r["pending_budget_changes"] == "42.00"


def test_pending_budget_changes_not_used_for_formula() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    # No "Pending Cost Changes" cell; only a budget-side pending_budget_changes column.
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "5885", "committed_costs": "600.00", "erp_direct_costs": "300.00",
         "projected_costs": "900.00", "pending_budget_changes": "0.00"},
    ])
    r = _cbi_rows(db, "tropical")[0]
    assert r["pending_cost_changes"] is None
    assert "pending_cost_changes" in r["missing_formula_fields"]
    assert r["formula_reconciles"] is False  # cannot reconcile without the cost-side field


def test_dynamic_cell_conflict_emits_warning_and_no_value() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "5885", "committed_costs": "600.00", "erp_direct_costs": "300.00",
         "projected_costs": "1000.00", "cells": {"Pending Cost Changes": ["100.00", "150.00"]}},
    ])
    r = _cbi_rows(db, "tropical")[0]
    assert r["pending_cost_changes"] is None  # conflicting cells -> ambiguous -> missing
    assert "budgetdetails_dynamic_cell_conflict" in r["selection_warnings"]
    assert r["formula_reconciles"] is False


def test_multi_view_selection_prefers_source_quality() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_budgetdetails(db, "tropical", [
        # higher source_quality but non-reconciling (no pending cell)
        {"code": _K, "view": "100", "source_quality": "live_full_payload",
         "committed_costs": "600.00", "erp_direct_costs": "300.00", "projected_costs": "1000.00"},
        # lower source_quality but reconciling
        {"code": _K, "view": "200", "source_quality": "fixture_full_payload",
         "committed_costs": "600.00", "erp_direct_costs": "300.00", "projected_costs": "900.00",
         "cells": {"Pending Cost Changes": "0.00"}},
    ])
    r = _cbi_rows(db, "tropical")[0]
    assert r["candidate_view_count"] == 2
    assert r["selected_source_quality"] == "live_full_payload"  # source_quality dominates
    assert r["selected_budget_view_id"] == "100"
    assert r["formula_reconciles"] is False
    assert "budgetdetails_multiple_budget_views_detected" in r["selection_warnings"]
    assert "budgetdetails_selected_view_unverified" in r["selection_warnings"]


def test_multi_view_tie_on_quality_prefers_reconciling_then_deterministic() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "200", "source_quality": "live_full_payload",
         "committed_costs": "600.00", "erp_direct_costs": "300.00", "projected_costs": "1000.00"},
        {"code": _K, "view": "300", "source_quality": "live_full_payload",
         "committed_costs": "600.00", "erp_direct_costs": "300.00", "projected_costs": "1000.00",
         "cells": {"Pending Cost Changes": "100.00"}},
    ])
    r = _cbi_rows(db, "tropical")[0]
    assert r["formula_reconciles"] is True  # reconciling view wins the equal-quality tie
    assert r["selected_budget_view_id"] == "300"


def test_multi_view_full_tie_uses_deterministic_view_id() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "300", "source_quality": "live_full_payload",
         "committed_costs": "600.00", "projected_costs": "1000.00"},
        {"code": _K, "view": "100", "source_quality": "live_full_payload",
         "committed_costs": "600.00", "projected_costs": "1000.00"},
    ])
    r = _cbi_rows(db, "tropical")[0]
    assert r["selected_budget_view_id"] == "100"  # smallest budget_view_id wins the full tie


def test_cost_basis_inputs_redaction_safe_and_no_record_key() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "5885", "committed_costs": "600.00", "erp_direct_costs": "300.00",
         "projected_costs": "1000.00", "cells": {"Pending Cost Changes": "100.00"}},
    ])
    pub = build_db_native_source_snapshot("tropical", db_path=db).public()
    assert find_redaction_leaks(pub) == []
    blob = json.dumps(pub)
    assert "record_key" not in blob
    assert "payload_hash" not in blob
    assert "raw_json" not in blob


def test_cost_basis_inputs_projects_isolated() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")
    _seed_full_project(db, "harbor", "Harbor Tower")
    _seed_budgetdetails(db, "tropical", [
        {"code": _K, "view": "1", "committed_costs": "600.00", "projected_costs": "600.00"}])
    _seed_budgetdetails(db, "harbor", [
        {"code": "2000.20-02-100.LAB", "view": "1", "committed_costs": "10.00", "projected_costs": "10.00"}])
    trop = {r["budget_code_key"] for r in _cbi_rows(db, "tropical")}
    harbor = {r["budget_code_key"] for r in _cbi_rows(db, "harbor")}
    assert trop == {_K}
    assert harbor == {"2000.20-02-100.LAB"}


def test_cost_basis_inputs_absent_when_no_budgetdetails_rows() -> None:
    db = _db()
    _seed_full_project(db, "tropical", "Tropical Resort")  # v59 spine only, no budgetdetails rows
    pub = build_db_native_source_snapshot("tropical", db_path=db).public()
    cbi = pub["budgetdetails_cost_basis_inputs"]
    assert cbi["present"] is False
    assert cbi["rows"] == []


def test_snapshot_module_does_not_read_config_view_ids() -> None:
    # The DB-native path must select views from DB evidence only — never the config-file selector.
    src = Path(
        "src/hb_assistant/construction/analytics/forecast_db_native_source_snapshot.py"
    ).read_text()
    assert "_configured_budget_detail_view_ids" not in src
    assert "config/projects" not in src


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
