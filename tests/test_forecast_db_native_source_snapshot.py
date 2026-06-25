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


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
