"""Phase D — package-free DB-native context builder (CFR).

Proves the new CFR builder produces a typed, in-memory forecast context from a Phase C snapshot's
public dict — with no package directory, no manifest, no SRC_FILES / TWN constants, and no
hb_assistant import in the module — fails closed only on required-basis issues, marks owner/procore
families unavailable (not crash), and is deterministic + redaction-safe. The legacy package-backed
builder is exercised by its own existing tests (run separately in validation).
"""

from __future__ import annotations

import ast
import json
import sqlite3
import sys
from pathlib import Path

import pytest

# CFR src on path for direct invocation (the forecasting bundle sets PYTHONPATH itself).
_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from construction_financial_review.context.db_native_context_builder import (  # noqa: E402
    DbNativeContextError,
    build_db_native_context,
    context_input_from_snapshot_public,
)

from hb_assistant.config.path_policy import PathPolicy  # noqa: E402
from hb_assistant.construction.analytics.forecast_db_native_source_snapshot import (  # noqa: E402
    build_db_native_source_snapshot,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.forecast.source_domain_repository import (  # noqa: E402
    upsert_budget_detail,
    upsert_cost_entry,
    upsert_monthly_actual,
)
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402

_MODULE = (
    _CFR_SRC / "construction_financial_review/context/db_native_context_builder.py"
)
_PKG = "twn_cost_forecast_json_package"  # package-like batch name — must never reach context output

_BUDGET = [
    {
        "budget_code_key": "01-100",
        "cost_code": "01-100",
        "category": "labor",
        "revised_budget": "1000.00",
        "projected_costs": "1200.00",
    },
    {
        "budget_code_key": "02-200",
        "cost_code": "02-200",
        "category": "material",
        "revised_budget": "0.00",  # a real zero, not missing
    },
]
_COST = [
    {"budget_code_key": "01-100", "accounting_month": "2026-05", "amount": "250.00"},
    {"budget_code_key": "01-100", "accounting_month": "2026-06", "amount": "100.00"},
]
_MONTHLY = [
    {"budget_code_key": "01-100", "month": "2026-05", "type": "actual", "amount": "250.00", "entry_count": 1}
]


def _db() -> str:
    db = Path(PathPolicy().get_db_path())
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _seed_v59(db: str, project_key: str, *, source_package: str, budget=None, cost=None, monthly=None) -> None:
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


def _full_project(db: str, project_key: str, display_name: str, *, source_package: str = _PKG) -> None:
    seed_procore_ep_project(db, project_key=project_key, display_name=display_name)
    _seed_v59(db, project_key, source_package=source_package, budget=_BUDGET, cost=_COST, monthly=_MONTHLY)


def _context_public(project_key: str, db: str) -> dict:
    snap = build_db_native_source_snapshot(project_key, db_path=db)
    ctx = build_db_native_context(context_input_from_snapshot_public(snap.public()))
    return ctx.public()


# -- 1. package-free build from a snapshot fixture ----------------------------


def test_builds_from_snapshot_public_fixture() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    pub = _context_public("tropical", db)
    assert pub["project_key"] == "tropical"
    assert pub["display_name"] == "Tropical Resort"
    assert pub["budget_codes"] == ["01-100", "02-200"]
    assert pub["conclusion"] == "forecast_context_ready_db_native_with_warnings"
    by_key = {r["budget_code_key"]: r for r in pub["budget_code_context"]}
    # Actuals summed deterministically (250 + 100); revised_budget passed through.
    assert by_key["01-100"]["actuals"]["actual_cost_to_date"] == "350.00"
    assert by_key["01-100"]["actuals"]["actual_entry_count"] == 2
    assert by_key["01-100"]["budget_amounts"]["revised_budget"] == "1000.00"
    # Missing-vs-zero: an absent amount is null; an explicit "0.00" is a real zero.
    assert by_key["02-200"]["budget_amounts"]["revised_budget"] == "0.00"
    assert by_key["02-200"]["budget_amounts"]["committed_costs"] is None
    assert pub["project_totals"]["total_revised_budget"] == "1000.00"
    assert pub["project_totals"]["total_actual_cost_to_date"] == "350.00"


# -- 2/3. no package directory created or read; no manifest required ----------


def test_no_package_directory_or_manifest_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    workdir = tmp_path / "work"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    _context_public("tropical", db)  # build under an empty cwd
    # The builder writes nothing: no package dir, no manifest.json, nothing under cwd.
    assert list(workdir.iterdir()) == []


# -- 4. no hard-coded Tropical/TWN constants; non-tropical project works ------


def test_module_has_no_legacy_constants_or_hb_import() -> None:
    names: set[str] = set()
    for node in ast.walk(ast.parse(_MODULE.read_text())):
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
        "hb_assistant",
        "twn_cost_forecast_json_package",
        "TWN_DIR",
        "OWNER_DIR",
        "PROCORE_DIR",
        "SRC_FILES",
        "_DEFAULT_DATA_ROOT",
        "generate_forecast_context_package",
    )
    leaked = [tok for tok in forbidden if any(tok in name for name in names)]
    assert leaked == [], f"context builder references legacy/HB symbols: {leaked}"


def test_non_tropical_project_builds() -> None:
    db = _db()
    _full_project(db, "harbor", "Harbor Tower", source_package="harbor_batch_alpha")
    pub = _context_public("harbor", db)
    assert pub["project_key"] == "harbor"
    assert pub["display_name"] == "Harbor Tower"
    assert pub["budget_codes"] == ["01-100", "02-200"]


# -- 5. missing optional families -> structured warnings, not crash -----------


def test_optional_families_unavailable_warn_not_crash() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    pub = _context_public("tropical", db)
    avail = pub["optional_source_availability"]
    assert set(avail) == {"owner_pay_app", "procore_pay_app", "owner_crosswalk"}
    assert all(b["available"] is False and b["row_count"] == 0 for b in avail.values())
    for code in ("owner_pay_app_source_unavailable", "procore_pay_app_source_unavailable", "owner_crosswalk_unavailable"):
        assert code in pub["data_quality"]["warnings"]
    assert pub["provenance"]["source_families_unavailable"] == [
        "owner_pay_app_source_unavailable",
        "procore_pay_app_source_unavailable",
        "owner_crosswalk_unavailable",
    ]


# -- 6. required financial basis absence fails closed -------------------------


def test_no_financial_basis_fails_closed() -> None:
    db = _db()
    seed_procore_ep_project(db, project_key="barren", display_name="Barren Site")  # identity only
    snap = build_db_native_source_snapshot("barren", db_path=db)
    with pytest.raises(DbNativeContextError) as exc:
        build_db_native_context(context_input_from_snapshot_public(snap.public()))
    msg = str(exc.value)
    assert msg == "forecast_context_no_financial_basis"
    assert "/Users/" not in msg and _PKG not in msg


# -- redaction + determinism --------------------------------------------------


def test_context_public_is_redaction_safe() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    pub = _context_public("tropical", db)
    assert find_redaction_leaks(pub) == []
    blob = json.dumps(pub)
    for forbidden in (_PKG, "cost_forecast_json_package", "source_package", "source_path", "raw_json", "/Users/"):
        assert forbidden not in blob


def test_build_is_deterministic() -> None:
    db = _db()
    _full_project(db, "tropical", "Tropical Resort")
    assert _context_public("tropical", db) == _context_public("tropical", db)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
