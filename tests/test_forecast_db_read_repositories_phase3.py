"""v59 — Forecast DB-transition SOURCE-DOMAIN read-parity tests (Phase 3).

Covers: the v59 additive migration applies/idempotent; the lifecycle contract count +
classification stay consistent; dry-run projection writes zero rows / never opens the DB;
apply to an explicit temp DB writes the expected rows and is idempotent; DB-backed read
repositories return the original JSONL row shape for all three sources; the missing/blank
source-hash fallback is deterministic and never collapses distinct files; and the apply
guards fail closed (no explicit --db-path, and the live/default DB path).

Synthetic fixtures only — no Synology path, no network, no Ollama. Forecast model reads
remain file-backed; nothing here touches the live DB.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.forecast import source_domain_engine as engine
from hb_assistant.construction.forecast import source_domain_repository as repo
from hb_assistant.construction.forecast import source_reader
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

V59_SOURCE_DOMAIN_TABLES = [
    "forecast_budget_details",
    "forecast_cost_entries",
    "forecast_monthly_actuals_by_budget_code",
]

# --- synthetic source rows (real TWN JSONL shapes, trimmed) ------------------------------

_BUDGET_DETAILS = [
    {
        "source_sheet": "BudgetDetails",
        "source_row": 2,
        "budget_code_key": "0000.03-01-025.MAT",
        "cost_code": "03-01-025",
        "category": "MAT",
        "amounts": {"projected_costs": 1032.4, "costentries_entry_count": 10},
        "notes": None,
    },
    {
        "source_sheet": "BudgetDetails",
        "source_row": 3,
        "budget_code_key": "1000.15-16-110.SUB",
        "cost_code": "15-16-110",
        "category": "SUB",
        "amounts": {"projected_costs": 5000.0, "costentries_entry_count": 1},
        "notes": "active",
    },
]

_COST_ENTRIES = [
    {
        "source_sheet": "CostEntries",
        "source_row": 2,
        "budget_code_key": "0000.03-01-025.MAT",
        "accounting_month": "2024-06",
        "amount": 172.02,
        "description": None,
    },
    {
        "source_sheet": "CostEntries",
        "source_row": 3,
        "budget_code_key": "0000.03-01-025.MAT",
        "accounting_month": "2024-07",
        "amount": 50.0,
        "description": "second",
    },
    {
        "source_sheet": "CostEntries",
        "source_row": 4,
        "budget_code_key": "1000.15-16-110.SUB",
        "accounting_month": "2024-06",
        "amount": 5000.0,
        "description": None,
    },
]

_MONTHLY_ACTUALS = [
    {
        "budget_code_key": "0000.03-01-025.MAT",
        "month": "2024-06",
        "type": "actual",
        "amount": 172.02,
        "entry_count": 1,
        "source": "CostEntries",
    },
    {
        "budget_code_key": "1000.15-16-110.SUB",
        "month": "2024-06",
        "type": "actual",
        "amount": 5000.0,
        "entry_count": 1,
        "source": "CostEntries",
    },
]

_EXPECTED_COUNTS = {"budget_details": 2, "cost_entries": 3, "monthly_actuals": 2}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _make_package(root: Path, name: str = "twn_cost_forecast_json_package") -> Path:
    pkg = root / name
    data = pkg / "data"
    data.mkdir(parents=True)
    _write_jsonl(data / "budget_details.jsonl", _BUDGET_DETAILS)
    _write_jsonl(data / "cost_entries.jsonl", _COST_ENTRIES)
    _write_jsonl(data / "monthly_actuals_by_budget_code.jsonl", _MONTHLY_ACTUALS)
    return pkg


def _migrated_db(td: str) -> str:
    db = Path(td) / "v59.db"
    SQLiteMigrator(db_path=str(db)).apply()
    return str(db)


def _norm(rows: list[dict]) -> list[str]:
    return sorted(json.dumps(r, sort_keys=True) for r in rows)


# --- 1. migration ------------------------------------------------------------------------


def test_v59_migration_applies_and_is_idempotent() -> None:
    assert LATEST_SCHEMA_VERSION >= 59
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "v59.db"
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
        assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION  # idempotent
        conn = sqlite3.connect(str(db))
        try:
            names = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            n59 = conn.execute(
                "SELECT COUNT(*) FROM schema_migrations WHERE version=59"
            ).fetchone()[0]
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()
        assert all(t in names for t in V59_SOURCE_DOMAIN_TABLES)
        assert n59 == 1
        assert integrity == "ok"


# --- 2. lifecycle contract ---------------------------------------------------------------


def test_lifecycle_contract_count_and_classification() -> None:
    contract_path = (
        Path(__file__).resolve().parents[1]
        / "src/hb_assistant/resources/json/table_lifecycle_status_contract.json"
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["table_count"] == 477  # live table lifecycle contract count (was 439; 451 before V76 staffing)
    assert contract["table_count"] == len(contract["tables"])
    for t in V59_SOURCE_DOMAIN_TABLES:
        entry = contract["tables"][t]
        assert entry["table_family"] == "forecast_source_domain_v59"
        assert entry["lifecycle_status"] == "operational_empty_expected"
        assert entry["expected_population_status"] == "empty"
        assert entry["phase_owner"] == "forecast_db_transition"
        assert entry["blocking_for_phase"] == "none"
        assert entry["v"] == "V59"


# --- 3. dry-run writes nothing -----------------------------------------------------------


def test_dry_run_plans_rows_without_touching_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        receipt = engine.project_source_domain(
            source_package=pkg,
            project_key="tropical",
            apply=False,
            now_utc="2026-06-18T00:00:00+00:00",
        )
        assert receipt["ok"] is True
        assert receipt["mode"] == "dry_run"
        assert receipt["counts"] == _EXPECTED_COUNTS
        assert "written" not in receipt
        # No DB file was created anywhere under the temp dir.
        assert not list(Path(td).glob("*.db"))


# --- 4 & 5. apply writes expected rows + idempotent --------------------------------------


def test_apply_writes_expected_rows_and_is_idempotent() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        db = _migrated_db(td)
        first = engine.project_source_domain(
            source_package=pkg, project_key="tropical", db_path=Path(db), apply=True
        )
        assert first["ok"] is True
        assert first["mode"] == "apply"
        assert first["written"] == _EXPECTED_COUNTS

        conn = sqlite3.connect(db)
        try:
            counts1 = {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in V59_SOURCE_DOMAIN_TABLES
            }
        finally:
            conn.close()
        assert counts1 == {
            "forecast_budget_details": 2,
            "forecast_cost_entries": 3,
            "forecast_monthly_actuals_by_budget_code": 2,
        }

        # Re-project: upserts, never duplicates.
        engine.project_source_domain(
            source_package=pkg, project_key="tropical", db_path=Path(db), apply=True
        )
        conn = sqlite3.connect(db)
        try:
            counts2 = {
                t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in V59_SOURCE_DOMAIN_TABLES
            }
        finally:
            conn.close()
        assert counts2 == counts1


# --- 6. DB read repositories match the source JSONL --------------------------------------


def test_read_repositories_match_source_jsonl() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        db = _migrated_db(td)
        engine.project_source_domain(
            source_package=pkg, project_key="tropical", db_path=Path(db), apply=True
        )
        conn = sqlite3.connect(db)
        try:
            bd = repo.read_budget_details_from_db(conn, project_key="tropical")
            ce = repo.read_cost_entries_from_db(conn, project_key="tropical")
            ma = repo.read_monthly_actuals_from_db(conn, project_key="tropical")
        finally:
            conn.close()
        # Returned dicts are the ORIGINAL JSONL rows — no lineage/index fields merged in.
        assert _norm(bd) == _norm(_BUDGET_DETAILS)
        assert _norm(ce) == _norm(_COST_ENTRIES)
        assert _norm(ma) == _norm(_MONTHLY_ACTUALS)
        assert all("source_row_number" not in r and "raw_json" not in r for r in bd + ce + ma)


def test_parity_flag_proves_round_trip_on_apply() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        db = _migrated_db(td)
        receipt = engine.project_source_domain(
            source_package=pkg,
            project_key="tropical",
            db_path=Path(db),
            apply=True,
            parity=True,
        )
        assert receipt["ok"] is True
        assert receipt["parity"]["proven"] is True
        for kind, exp in _EXPECTED_COUNTS.items():
            assert receipt["parity"]["by_table"][kind]["db_rows"] == exp
            assert receipt["parity"]["by_table"][kind]["match"] is True


def test_parity_without_apply_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        receipt = engine.project_source_domain(
            source_package=pkg, project_key="tropical", apply=False, parity=True
        )
        assert receipt["ok"] is False
        assert receipt["parity"]["proven"] is False
        assert receipt["parity"]["reason"] == "parity_requires_applied_db"


# --- 7. source-hash fallback determinism -------------------------------------------------


def test_source_sha_fallback_is_deterministic_and_distinct_per_path() -> None:
    missing_a = Path("/nonexistent/pkg/data/budget_details.jsonl")
    missing_b = Path("/nonexistent/pkg/data/cost_entries.jsonl")
    sha_a1, fb_a1 = source_reader.resolve_source_sha256(missing_a, "twn_cost_forecast_json_package")
    sha_a2, fb_a2 = source_reader.resolve_source_sha256(missing_a, "twn_cost_forecast_json_package")
    sha_b, fb_b = source_reader.resolve_source_sha256(missing_b, "twn_cost_forecast_json_package")
    assert fb_a1 is fb_a2 is fb_b is True  # all fell back
    assert sha_a1 == sha_a2  # deterministic for the same path
    assert sha_a1 != sha_b  # distinct files never collapse


def test_real_files_use_content_hash_not_fallback() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        receipt = engine.project_source_domain(
            source_package=pkg, project_key="tropical", apply=False
        )
        # All three real files hashed by content (no fallback warnings).
        assert all(h is not None for h in receipt["source_hashes"].values())
        assert not any("fallback" in w for w in receipt["warnings"])
        # Distinct files → distinct content hashes.
        assert len(set(receipt["source_hashes"].values())) == 3


# --- 8 & 9. apply guards fail closed -----------------------------------------------------


def test_apply_without_db_path_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        receipt = engine.project_source_domain(
            source_package=pkg, project_key="tropical", apply=True, db_path=None
        )
        assert receipt["ok"] is False
        assert receipt["reason"] == "apply_requires_explicit_db_path"
        assert "written" not in receipt


def test_apply_to_live_default_db_fails_closed() -> None:
    live = PathPolicy().get_db_path()
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        receipt = engine.project_source_domain(
            source_package=pkg, project_key="tropical", apply=True, db_path=live
        )
        assert receipt["ok"] is False
        assert receipt["reason"] == "apply_refuses_live_db"
        assert "written" not in receipt


def test_is_live_db_path_fails_closed_on_unresolvable(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(self: PathPolicy) -> Path:
        raise RuntimeError("cannot resolve app support root")

    monkeypatch.setattr(PathPolicy, "get_db_path", _boom)
    # Resolution failure must be treated as live (refuse), not as a safe temp path.
    assert engine.is_live_db_path(Path("/tmp/whatever.db")) is True
