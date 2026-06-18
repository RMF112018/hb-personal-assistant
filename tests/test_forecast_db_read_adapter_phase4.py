"""Phase 4 — forecast context-generator DB-backed read-adapter tests.

Proves: the CFR-local adapter is file-backed and byte-equivalent by default (no hb_assistant
import); DB-backed mode (HB_FORECAST_DB_BACKED_READS=1 + HB_FORECAST_DB_PATH) reads the v59
source-domain rows in the original JSONL shape; and adapter-boundary parity holds
(load_*(file) == load_*(DB) for all three sources). Fail-closed guards are exercised:
missing DB path, live/default DB path, and missing rows. A subprocess test proves the
toggle-off path imports no hb_assistant.

Adapter-boundary parity is the Phase 4 proof; full context-package run comparison is
deferred (see ADR 260) because the generator is an unparameterized monolith hardcoded to
the live data root. Synthetic fixtures only — nothing here touches the live DB.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.forecast import source_domain_engine as engine
from hb_assistant.store.migrator import SQLiteMigrator

# The adapter lives in the vendored CFR subrepo; add its src to the path to import it
# (root pytest does not install/discover CFR). Importing the adapter module does NOT import
# the generator (context/__init__.py is a docstring only).
CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review.context.db_source_adapter import (  # noqa: E402
    ForecastDbReadError,
    db_backed_reads_active,
    load_forecast_source_rows,
)

# --- synthetic source rows (real TWN JSONL shapes, trimmed) ------------------------------

_BUDGET_DETAILS = [
    {
        "source_row": 2,
        "budget_code_key": "0000.03-01-025.MAT",
        "cost_code": "03-01-025",
        "category": "MAT",
        "amounts": {"projected_costs": 1032.4},
        "notes": None,
    },
    {
        "source_row": 3,
        "budget_code_key": "1000.15-16-110.SUB",
        "cost_code": "15-16-110",
        "category": "SUB",
        "amounts": {"projected_costs": 5000.0},
        "notes": "active",
    },
]
_COST_ENTRIES = [
    {
        "source_row": 2,
        "budget_code_key": "0000.03-01-025.MAT",
        "accounting_month": "2024-06",
        "amount": 172.02,
    },
    {
        "source_row": 3,
        "budget_code_key": "0000.03-01-025.MAT",
        "accounting_month": "2024-07",
        "amount": 50.0,
    },
    {
        "source_row": 4,
        "budget_code_key": "1000.15-16-110.SUB",
        "accounting_month": "2024-06",
        "amount": 5000.0,
    },
]
_MONTHLY_ACTUALS = [
    {
        "budget_code_key": "0000.03-01-025.MAT",
        "month": "2024-06",
        "type": "actual",
        "amount": 172.02,
        "entry_count": 1,
    },
    {
        "budget_code_key": "1000.15-16-110.SUB",
        "month": "2024-06",
        "type": "actual",
        "amount": 5000.0,
        "entry_count": 1,
    },
]
_SOURCES = {
    "budget_details": ("budget_details.jsonl", _BUDGET_DETAILS),
    "cost_entries": ("cost_entries.jsonl", _COST_ENTRIES),
    "monthly_actuals": ("monthly_actuals_by_budget_code.jsonl", _MONTHLY_ACTUALS),
}


def _read_jsonl(path):
    """Minimal stand-in for the generator's local read_jsonl (yields one dict per line)."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _make_package(root: Path, name: str = "twn_cost_forecast_json_package") -> Path:
    pkg = root / name
    data = pkg / "data"
    data.mkdir(parents=True)
    for _, (filename, rows) in _SOURCES.items():
        _write_jsonl(data / filename, rows)
    return pkg


def _migrated_and_projected_db(td: str, pkg: Path) -> str:
    db = Path(td) / "v59.db"
    SQLiteMigrator(db_path=str(db)).apply()
    receipt = engine.project_source_domain(
        source_package=pkg, project_key="tropical", db_path=db, apply=True
    )
    assert receipt["ok"] is True
    return str(db)


def _jsonl_path(pkg: Path, source_name: str) -> Path:
    return pkg / "data" / _SOURCES[source_name][0]


def _load(source_name: str, pkg: Path, project_key: str = "tropical") -> list[dict]:
    return load_forecast_source_rows(
        source_name,
        jsonl_path=_jsonl_path(pkg, source_name),
        source_package_name=pkg.name,
        project_key=project_key,
        read_jsonl_fn=_read_jsonl,
    )


@pytest.fixture(autouse=True)
def _clear_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_FORECAST_DB_BACKED_READS", raising=False)
    monkeypatch.delenv("HB_FORECAST_DB_PATH", raising=False)


# --- 1. toggle off (default) -------------------------------------------------------------


def test_toggle_default_false_reads_files() -> None:
    assert db_backed_reads_active() is False
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        for source_name, (_, rows) in _SOURCES.items():
            assert _load(source_name, pkg) == rows  # exact file rows, no DB path needed


# --- 2 & 3. toggle on fail-closed guards -------------------------------------------------


def test_toggle_on_without_db_path_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        with pytest.raises(ForecastDbReadError, match="HB_FORECAST_DB_PATH"):
            _load("budget_details", pkg)


def test_toggle_on_with_live_db_path_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(PathPolicy().get_db_path()))
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        with pytest.raises(ForecastDbReadError, match="live/default DB"):
            _load("budget_details", pkg)


# --- 4, 5, 7. toggle on reads v59 rows in JSONL shape ------------------------------------


def test_toggle_on_reads_rows_in_jsonl_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        db = _migrated_and_projected_db(td, pkg)
        monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
        monkeypatch.setenv("HB_FORECAST_DB_PATH", db)
        for source_name, (_, rows) in _SOURCES.items():
            got = _load(source_name, pkg)
            assert got == rows  # original JSONL shape; no lineage/DB fields merged in
            assert all("source_row_number" not in r and "raw_json" not in r for r in got)


# --- 6. missing rows fail closed (no silent fallback) ------------------------------------


def test_toggle_on_missing_rows_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        db = _migrated_and_projected_db(td, pkg)
        monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
        monkeypatch.setenv("HB_FORECAST_DB_PATH", db)
        # Same temp DB, but a project_key that was never projected -> zero rows -> fail closed.
        with pytest.raises(ForecastDbReadError, match="no DB rows"):
            _load("budget_details", pkg, project_key="not_tropical")


# --- 8. adapter-boundary parity ----------------------------------------------------------


def test_adapter_boundary_parity_file_vs_db(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as td:
        pkg = _make_package(Path(td))
        db = _migrated_and_projected_db(td, pkg)
        for source_name in _SOURCES:
            monkeypatch.delenv("HB_FORECAST_DB_BACKED_READS", raising=False)
            file_rows = _load(source_name, pkg)
            monkeypatch.setenv("HB_FORECAST_DB_BACKED_READS", "1")
            monkeypatch.setenv("HB_FORECAST_DB_PATH", db)
            db_rows = _load(source_name, pkg)
            assert db_rows == file_rows, f"{source_name}: DB rows must equal file rows in order"


# --- 9. toggle-off imports no hb_assistant (subprocess, clean sys.modules) ----------------


def test_toggle_off_does_not_import_hb_assistant() -> None:
    with tempfile.TemporaryDirectory() as td:
        jsonl = Path(td) / "budget_details.jsonl"
        _write_jsonl(jsonl, _BUDGET_DETAILS)
        code = (
            "import sys, json\n"
            f"sys.path.insert(0, {str(CFR_SRC)!r})\n"
            "from construction_financial_review.context.db_source_adapter import load_forecast_source_rows\n"
            "def rj(p):\n"
            "    with open(p) as fh:\n"
            "        for ln in fh:\n"
            "            ln = ln.strip()\n"
            "            if ln:\n"
            "                yield json.loads(ln)\n"
            f"rows = load_forecast_source_rows('budget_details', jsonl_path={str(jsonl)!r}, "
            "source_package_name='twn_cost_forecast_json_package', project_key='tropical', read_jsonl_fn=rj)\n"
            "hb = sorted(m for m in sys.modules if m == 'hb_assistant' or m.startswith('hb_assistant.'))\n"
            "assert not hb, 'unexpected hb_assistant import: %r' % hb\n"
            "print('OK', len(rows))\n"
        )
        env = {
            k: v for k, v in __import__("os").environ.items() if k != "HB_FORECAST_DB_BACKED_READS"
        }
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
        assert proc.returncode == 0, f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        assert "OK 2" in proc.stdout
