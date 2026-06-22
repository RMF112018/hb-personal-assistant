"""Phase I PR 1 — model-engines readiness CLI wiring (repo-root, real hb_assistant gates).

Proves the ``model-engines-readiness`` CLI end-to-end against the REAL
``hb_assistant.forecasting`` semantic gates (no monkeypatch) using a hermetic temp empty SQLite
(empty DB => all gates pass) and a synthetic context package under ``tmp_path``. Asserts the rc
0/1/3 convention, the clean-stdout JSON contract, and the read-only posture. The exhaustive
time-series + decision-branch coverage lives in the CFR subrepo suite
(``test_model_engines_readiness.py``); this file only proves the wiring + real-gate integration.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402


def _wjsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _twelve(code):
    return [
        {
            "budget_code_key": code,
            "month": f"2025-{i:02d}",
            "amount_decimal_string": "1000.00",
            "actual_period_bucket": "through_may_2026",
            "source": "CostEntries",
            "entry_count": 1,
        }
        for i in range(1, 13)
    ]


def _pkg(tmp_path: Path, monthly) -> Path:
    pkg = tmp_path / "ctx"
    _wjsonl(pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl", monthly)
    _wjsonl(
        pkg / "canonical" / "budget_codes.jsonl",
        [
            {"budget_code_key": "a", "amounts": {"projected_costs": "50000.00"}},
            {"budget_code_key": "b", "amounts": {"projected_costs": "50000.00"}},
            {"budget_code_key": "c", "amounts": {"projected_costs": "50000.00"}},
        ],
    )
    return pkg


def _empty_db(tmp_path: Path) -> Path:
    db = tmp_path / "empty.sqlite"
    sqlite3.connect(str(db)).close()  # empty => all forecasting gates pass
    return db


def _argv(pkg, db, work, project="tropical"):
    return [
        "model-engines-readiness",
        "--project",
        project,
        "--context-package",
        str(pkg),
        "--db-path",
        str(db),
        "--work-root",
        str(work),
    ]


def test_cli_ready_rc0(tmp_path, capsys):
    pkg = _pkg(tmp_path, _twelve("a") + _twelve("b") + _twelve("c"))
    rc = cli.main(_argv(pkg, _empty_db(tmp_path), tmp_path / "work"))
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["command"] == "model-engines-readiness"
    assert out["decision"] == "model_engines_data_ready"
    assert out["forecast_gate_summary"]["status"] == "pass"  # real gates, empty DB
    assert out["forecast_gate_summary"]["gate_count"] == 5
    assert out["semantic_catalog_version"]["semantic_catalog"] is not None
    assert out["deferral"]["forecast_core_edited"] is False
    assert Path(out["report_path"]).is_file()


def test_cli_not_ready_rc1(tmp_path, capsys):
    # All actuals are future-dated => no completed history => not_ready.
    monthly = [
        {
            "budget_code_key": "a",
            "month": "2026-08",
            "amount_decimal_string": "10.00",
            "actual_period_bucket": "after_june_2026",
            "source": "CostEntries",
        }
    ]
    pkg = _pkg(tmp_path, monthly)
    rc = cli.main(_argv(pkg, _empty_db(tmp_path), tmp_path / "work"))
    assert rc == 1
    out = json.loads(capsys.readouterr().out)
    assert out["decision"] == "not_ready"


def test_cli_refusal_rc3(tmp_path, capsys):
    # Missing context package (tropical) => workflow preflight refuses => rc 3 controlled refusal.
    rc = cli.main(_argv(tmp_path / "nonexistent_pkg", _empty_db(tmp_path), tmp_path / "work"))
    assert rc == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "refused"
    assert "context_package not found" in out["reason"]
