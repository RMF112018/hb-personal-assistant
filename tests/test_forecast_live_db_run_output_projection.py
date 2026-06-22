"""Phase 3 — controlled live DB run-output + decision-support projection (gated live write).

Exercises the workflow against a SYNTHETIC "live" DB (a migrated temp DB whose path is
monkeypatched to be treated as the live/default DB, pre-populated with v59 like the real live DB
post-Phase-14). Covers preflight refusals, the WAL/backup gate, the temp projection chain
(v59 -> forecast_runs anchor -> v63 -> v66), the expected-count gate, the tropical-only
transactional replace across the run graph (preserving non-tropical rows), post-write
re-projection certification, and CLI rc 0/3. Everything runs under tmp_path; the real live DB is
never touched.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.store.migrator import SQLiteMigrator

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

from construction_financial_review import cli  # noqa: E402
from construction_financial_review.workflows import live_db_certification as certmod  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    live_db_run_output_projection as proj,
)
from construction_financial_review.workflows.live_db_run_output_projection import (  # noqa: E402
    DECISION_CERTIFIED,
    LiveDbRunOutputProjectionError,
    run_controlled_live_db_run_output_projection,
)

BCK = "0000.03-01-025.MAT"
STAMP = "20260101_000000"
RUN_ID = "20260101_000000"
V63 = proj.V63_TABLES
V66 = proj.V66_TABLES


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _flag_live(monkeypatch, live_path: Path) -> None:
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, live_path))


def _checkpoint(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _wj(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _wjson(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _twn_source(root: Path) -> Path:
    """Minimal twn_cost_forecast_json_package consumed by source_domain_engine."""
    twn = root / "twn_cost_forecast_json_package"
    _wj(twn / "data" / "budget_details.jsonl", [{"budget_code_key": BCK, "cost_code": "03-01-025"}])
    _wj(
        twn / "data" / "cost_entries.jsonl",
        [
            {"source_row": 2, "budget_code_key": BCK, "accounting_month": "2024-06", "amount": 300.0},
            {"source_row": 3, "budget_code_key": BCK, "accounting_month": "2026-06", "amount": 200.0},
        ],
    )
    _wj(
        twn / "data" / "monthly_actuals_by_budget_code.jsonl",
        [
            {"budget_code_key": BCK, "month": "2024-06", "type": "actual", "amount": 300.0},
            {"budget_code_key": BCK, "month": "2026-06", "type": "actual", "amount": 200.0},
        ],
    )
    return twn


def _analysis_pkg(root: Path) -> Path:
    pkg = root / "forecast_analysis_package_tropical_20260101_000000"
    (pkg / "summaries").mkdir(parents=True)
    _wjson(pkg / "manifest.json", {"project_key": "tropical", "stamp": STAMP})
    _wjson(pkg / "summaries" / "project_forecast_analysis.json", {"total_budget_codes": 1})
    _wj(pkg / "forecast_recommendations_by_budget_code.jsonl", [
        {"budget_code_key": BCK, "cost_code": "03-01-025", "category": "MAT",
         "forecast_action": "hold", "recommended_projected_cost": "500.00",
         "recommended_cost_to_complete": "0.00", "confidence": "high"},
    ])
    _wj(pkg / "forecast_risk_register.jsonl", [
        {"risk_id": "R-0001", "severity": "low", "budget_code_key": BCK, "risk_type": "x"},
    ])
    _wjson(pkg / "confidence_rollup.json", {"count_by_confidence": {"high": 1}})
    return pkg


def _downstream_pkgs(root: Path) -> dict:
    monthly = root / "forecast_monthly_package_tropical_s"
    _wj(monthly / "monthly_forecast_by_budget_code.jsonl", [
        {"budget_code_key": BCK, "forecast_month": "2026-07", "recommended_month_cost": "100.00"},
    ])
    prob = root / "forecast_probability_package_tropical_s"
    _wj(prob / "probabilistic_final_cost_by_budget_code.jsonl", [
        {"budget_code_key": BCK, "simulated_p10": "90.00", "simulated_p50": "100.00", "simulated_p90": "120.00"},
    ])
    comp = root / "forecast_comprehensive_package_tropical_s"
    _wj(comp / "integrated_change_explanation.jsonl", [
        {"budget_code_key": BCK, "change_amount": "10.00"},
    ])
    staff = root / "forecast_staffing_plan_package_tropical_s"
    _wj(staff / "staffing_plan_monthly_by_budget_code.jsonl", [
        {"budget_code_key": BCK,
         "staffing_plan_implied_monthly_forecast": [{"forecast_month": "2026-07", "amount": "50.00"}]},
    ])
    acc = root / "forecast_accuracy_package_tropical_s"
    _wj(acc / "eac_estimates_by_budget_code.jsonl", [
        {"budget_code_key": BCK, "estimates": [{"method": "burn_rate", "applicable": True, "reliability": "medium"}]},
    ])
    _wj(acc / "forecast_reconciliation_by_budget_code.jsonl", [
        {"budget_code_key": BCK, "contributions": [{"method": "burn_rate", "effective_weight": "0.7000"}]},
    ])
    return {
        "monthly_package": monthly,
        "probability_package": prob,
        "comprehensive_package": comp,
        "staffing_package": staff,
        "accuracy_package": acc,
    }


def _build_live_db(path: Path, *, with_v59: bool, source_package: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(path)).apply()
    if with_v59:
        assert source_package is not None
        rec = dbeng.project_source_domain(
            source_package=source_package, project_key="tropical", db_path=path, apply=True
        )
        assert rec["ok"] is True
    _checkpoint(path)


def _setup(tmp_path):
    src = _twn_source(tmp_path / "src")
    apkg = _analysis_pkg(tmp_path / "pkgs")
    downstream = _downstream_pkgs(tmp_path / "pkgs")
    live = tmp_path / "live" / "hb.sqlite"
    return src, apkg, downstream, live


def _run(tmp_path, monkeypatch, *, with_v59=True, **kwargs):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=with_v59, source_package=src)
    _flag_live(monkeypatch, live)
    return run_controlled_live_db_run_output_projection(
        analysis_package=apkg, source_package=src, work_root=tmp_path / "work",
        context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, allow_live_db_write=True,
        **downstream, **kwargs,
    )


def _tropical(live: Path, table: str) -> int:
    conn = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE project_key='tropical'").fetchone()[0]
    finally:
        conn.close()


def test_happy_path_certified_and_writes_run_graph(tmp_path, monkeypatch):
    report = _run(tmp_path, monkeypatch)
    assert report["decision"] == DECISION_CERTIFIED and report["status"] == "ready"
    assert report["write_result"]["transaction_committed"] is True
    live = tmp_path / "live" / "hb.sqlite"
    assert _tropical(live, "forecast_runs") == 1  # anchor
    assert _tropical(live, "forecast_outputs") == 1
    assert _tropical(live, "forecast_output_budget_codes") == 1
    assert _tropical(live, "forecast_output_monthly") == 1
    assert _tropical(live, "forecast_output_probability") == 1
    assert _tropical(live, "forecast_output_changes") == 1
    assert _tropical(live, "forecast_output_staffing") == 1
    assert _tropical(live, "forecast_project_maturity_snapshots") == 1
    assert _tropical(live, "forecast_method_eligibility") == 1
    # v59 untouched
    assert _tropical(live, "forecast_budget_details") == 1
    # all digest tables certified
    assert all(report["post_write_certification"]["tables"][t]["match"] for t in (*V63, *V66))


def test_refuses_without_allow(tmp_path, monkeypatch):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=True, source_package=src)
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbRunOutputProjectionError, match="allow_live_db_write"):
        run_controlled_live_db_run_output_projection(
            analysis_package=apkg, source_package=src, work_root=tmp_path / "work",
            context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, **downstream,
        )


def test_refuses_when_live_v59_empty(tmp_path, monkeypatch):
    with pytest.raises(LiveDbRunOutputProjectionError, match="no tropical v59"):
        _run(tmp_path, monkeypatch, with_v59=False)


def test_refuses_nonzero_wal_no_backup(tmp_path, monkeypatch):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=True, source_package=src)
    _flag_live(monkeypatch, live)
    real_prov = certmod._file_provenance
    monkeypatch.setattr(certmod, "_file_provenance",
                        lambda p: {**real_prov(p), "wal_size_bytes": 4096})
    with pytest.raises(LiveDbRunOutputProjectionError, match="nonzero WAL"):
        run_controlled_live_db_run_output_projection(
            analysis_package=apkg, source_package=src, work_root=tmp_path / "work",
            context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, allow_live_db_write=True,
            **downstream,
        )
    assert not (tmp_path / "work" / "backups").exists()


def test_expected_counts_mismatch_fails_before_write(tmp_path, monkeypatch):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=True, source_package=src)
    _flag_live(monkeypatch, live)
    with pytest.raises(LiveDbRunOutputProjectionError, match="expected temp-projection row counts"):
        run_controlled_live_db_run_output_projection(
            analysis_package=apkg, source_package=src, work_root=tmp_path / "work",
            context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, allow_live_db_write=True,
            expected_counts={"forecast_outputs": 999}, **downstream,
        )
    assert _tropical(live, "forecast_outputs") == 0
    assert not (tmp_path / "work" / "backups").exists()


def test_preserves_non_tropical_rows(tmp_path, monkeypatch):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=True, source_package=src)
    conn = sqlite3.connect(str(live))
    conn.execute(
        "INSERT INTO forecast_outputs (output_id, project_key, source_package, raw_json, created_utc) "
        "VALUES ('o-other','other','p','{}','t')"
    )
    conn.commit()
    conn.close()
    _checkpoint(live)
    _flag_live(monkeypatch, live)
    run_controlled_live_db_run_output_projection(
        analysis_package=apkg, source_package=src, work_root=tmp_path / "work",
        context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, allow_live_db_write=True, **downstream,
    )
    conn = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM forecast_outputs WHERE project_key='other'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_refuses_existing_tropical_without_replace_then_allows(tmp_path, monkeypatch):
    report = _run(tmp_path, monkeypatch)
    assert report["decision"] == DECISION_CERTIFIED
    live = tmp_path / "live" / "hb.sqlite"
    _checkpoint(live)
    src = tmp_path / "src" / "twn_cost_forecast_json_package"
    apkg = tmp_path / "pkgs" / "forecast_analysis_package_tropical_20260101_000000"
    downstream = _downstream_pkgs(tmp_path / "pkgs")  # idempotent dir writes
    _flag_live(monkeypatch, live)
    # second run without replace -> refuse
    with pytest.raises(LiveDbRunOutputProjectionError, match="already has"):
        run_controlled_live_db_run_output_projection(
            analysis_package=apkg, source_package=src, work_root=tmp_path / "work2",
            context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, allow_live_db_write=True,
            **downstream,
        )
    # with replace -> certified, counts stable (idempotent)
    report2 = run_controlled_live_db_run_output_projection(
        analysis_package=apkg, source_package=src, work_root=tmp_path / "work3",
        context_stamp=STAMP, run_id=RUN_ID, live_db_path=live, allow_live_db_write=True,
        allow_replace_existing=True, **downstream,
    )
    assert report2["decision"] == DECISION_CERTIFIED
    assert _tropical(live, "forecast_output_budget_codes") == 1


def test_cli_success_rc0(tmp_path, monkeypatch, capsys):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=True, source_package=src)
    _flag_live(monkeypatch, live)
    rc = cli.main([
        "live-db-run-output-project", "--project", "tropical",
        "--analysis-package", str(apkg), "--source-package", str(src),
        "--work-root", str(tmp_path / "work"), "--context-stamp", STAMP, "--run-id", RUN_ID,
        "--live-db-path", str(live), "--allow-live-db-write",
        "--monthly-package", str(downstream["monthly_package"]),
        "--probability-package", str(downstream["probability_package"]),
        "--comprehensive-package", str(downstream["comprehensive_package"]),
        "--staffing-package", str(downstream["staffing_package"]),
        "--accuracy-package", str(downstream["accuracy_package"]),
    ])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["decision"] == DECISION_CERTIFIED


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    src, apkg, downstream, live = _setup(tmp_path)
    _build_live_db(live, with_v59=True, source_package=src)
    _flag_live(monkeypatch, live)
    rc = cli.main([
        "live-db-run-output-project", "--project", "tropical",
        "--analysis-package", str(apkg), "--source-package", str(src),
        "--work-root", str(tmp_path / "work"), "--context-stamp", STAMP, "--run-id", RUN_ID,
        "--live-db-path", str(live),  # no --allow-live-db-write
    ])
    assert rc == 3
    assert json.loads(capsys.readouterr().out)["status"] == "refused"
