"""Phase I PR 1 — model-engines data + semantic readiness workflow tests (pure CFR, synthetic).

Covers time-series sufficiency branches, data-quality flags, the dollar/code coverage decision,
preflight refusals, determinism, and the semantic-gate integration (via an injected fake gate fn so
the suite needs no hb_assistant import): actual_cost-null tolerance, ERP exclusion, dynamic-column
non-leakage, gate-error blocks READY, gate-warnings carried, gates-not-available blocks READY.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from construction_financial_review.common.hashing import sha256_file
from construction_financial_review.common.io import write_jsonl
from construction_financial_review.workflows import model_engines_readiness as mer
from construction_financial_review.workflows.model_engines_readiness import (
    DECISION_INSUFFICIENT,
    DECISION_NOT_READY,
    DECISION_READY,
    ModelEnginesReadinessError,
    run_model_engines_readiness,
)

GATE_NAMES = (
    "forecast_double_count_prevention",
    "forecast_actuals_reconciliation",
    "forecast_projection_parity",
    "forecast_budget_dynamic_columns",
    "forecast_cost_type_guard",
)


# --------------------------------------------------------------------------- fake semantic gates


def _gate(name: str, w: int = 0, e: int = 0) -> dict:
    return {
        "gate": name,
        "ok": (w == 0 and e == 0),
        "finding_count": w + e,
        "warning_count": w,
        "error_count": e,
    }


def _gates_report(warn: int = 0, err: int = 0) -> dict:
    gates = [_gate(GATE_NAMES[0], w=warn, e=err)] + [_gate(n) for n in GATE_NAMES[1:]]
    wc = sum(g["warning_count"] for g in gates)
    ec = sum(g["error_count"] for g in gates)
    ok = ec == 0 and wc == 0
    status = "fail_blocking" if ec > 0 else ("warning" if (wc > 0 or not ok) else "pass")
    return {
        "ok": ok,
        "checked_at_utc": "x",
        "db_path": "x",
        "mode": "warn",
        "gates": gates,
        "summary": {
            "gate_count": len(gates),
            "passed_count": sum(1 for g in gates if g["ok"]),
            "warning_count": wc,
            "error_count": ec,
        },
        "gate_status": status,
        "readiness_note": "advisory",
    }


def clean_gate(**_kw) -> dict:
    return _gates_report(0, 0)


def warn_gate(**_kw) -> dict:
    return _gates_report(2, 0)


def err_gate(**_kw) -> dict:
    return _gates_report(0, 3)


def raising_gate(**_kw) -> dict:
    raise RuntimeError("boom: db unreadable")


# --------------------------------------------------------------------------- fixture builders


def _m(code, month, amount, bucket="through_may_2026", source="CostEntries") -> dict:
    return {
        "budget_code_key": code,
        "month": month,
        "amount_decimal_string": str(amount),
        "actual_period_bucket": bucket,
        "source": source,
        "entry_count": 1,
    }


def _bc(code, projected, extra=None) -> dict:
    amounts = {"projected_costs": str(projected)}
    if extra:
        amounts.update(extra)
    return {"budget_code_key": code, "amounts": amounts}


def _twelve(code, amount="1000.00"):
    return [_m(code, f"2025-{i:02d}", amount) for i in range(1, 13)]


def _make_pkg(tmp_path: Path, monthly_rows, bc_rows, name="ctx") -> Path:
    pkg = tmp_path / name
    (pkg / "canonical").mkdir(parents=True)
    write_jsonl(pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl", monthly_rows)
    write_jsonl(pkg / "canonical" / "budget_codes.jsonl", bc_rows)
    return pkg


@pytest.fixture()
def db_file(tmp_path: Path) -> Path:
    p = tmp_path / "fake.sqlite"
    p.write_bytes(b"")  # existence-only; the injected gate fn never opens it
    return p


def _run(pkg, db, work, **kw):
    return run_model_engines_readiness(
        context_package=pkg,
        db_path=db,
        work_root=work,
        semantic_gate_fn=kw.pop("semantic_gate_fn", clean_gate),
        **kw,
    )


# --------------------------------------------------------------------------- decision branches


def test_ready_decision(tmp_path, db_file):
    monthly = _twelve("a") + _twelve("b") + _twelve("c")
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00"), _bc("c", "50000.00")]
    pkg = _make_pkg(tmp_path, monthly, bcs)
    r = _run(pkg, db_file, tmp_path / "wr")
    assert r["decision"] == DECISION_READY
    assert r["aggregate"]["codes_eligible"] == 3
    assert r["coverage"]["code_coverage_fraction"] == "1.0000"
    assert r["coverage"]["dollar_coverage_fraction"] == "1.0000"
    assert r["statsforecast_candidate_code_count"] == 3
    assert r["fallback_to_existing_ensemble_count"] == 0


def test_insufficient_decision(tmp_path, db_file):
    # 1 eligible (small CTC) + 9 short-history (large CTC): code_cov 0.10>=0.05, dollar_cov<0.50.
    monthly = [_m("e", f"2025-{i:02d}", "10.00") for i in range(1, 13)]
    bcs = [_bc("e", "100.00")]
    for j in range(9):
        c = f"s{j}"
        monthly.append(_m(c, "2025-01", "5000.00"))  # 1 completed month -> short_history
        bcs.append(_bc(c, "100000.00"))
    pkg = _make_pkg(tmp_path, monthly, bcs)
    r = _run(pkg, db_file, tmp_path / "wr")
    assert r["decision"] == DECISION_INSUFFICIENT
    assert r["aggregate"]["codes_eligible"] == 1
    assert r["coverage"]["code_coverage_fraction"] == "0.1000"


def test_not_ready_no_actuals(tmp_path, db_file):
    monthly = [
        _m("a", "2026-08", "1000.00", bucket="after_june_2026"),
        _m("b", "2026-09", "1000.00", bucket="after_june_2026"),
    ]
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00")]
    pkg = _make_pkg(tmp_path, monthly, bcs)
    r = _run(pkg, db_file, tmp_path / "wr")
    assert r["decision"] == DECISION_NOT_READY
    assert r["aggregate"]["codes_with_any_actuals"] == 0
    assert any("no_completed_monthly_actuals" in b for b in r["readiness_blockers"])


def test_bucket_exclusion(tmp_path, db_file):
    monthly = _twelve("a") + [
        _m("a", "2026-06", "999.00", bucket="june_2026_to_date"),
        _m("a", "2026-08", "5.00", bucket="after_june_2026"),
        _m("a", None, "1.00", bucket="undated"),
    ]  # undated => null month, skipped
    pkg = _make_pkg(tmp_path, monthly, [_bc("a", "100000.00")])
    r = _run(pkg, db_file, tmp_path / "wr")
    code = r["per_code"][0]
    assert code["completed_month_count"] == 12  # only through_may_2026
    assert code["june_to_date_present"] is True
    assert code["after_june_dated_month_count"] == 1
    # cumulative = 12*1000 (completed) + 999 (june to date); after_june/undated excluded.
    assert code["cumulative_actual_to_date"] == "12999.00"


# --------------------------------------------------------------------------- data-quality flags


def test_flag_all_zero(tmp_path, db_file):
    monthly = [_m("z", f"2025-{i:02d}", "0.00") for i in range(1, 6)]
    pkg = _make_pkg(tmp_path, monthly, [_bc("z", "100.00")])
    code = _run(pkg, db_file, tmp_path / "wr")["per_code"][0]
    assert "all_zero" in code["data_quality_flags"]
    assert code["statsforecast_eligible"] is False


def test_flag_negative_months_still_eligible(tmp_path, db_file):
    monthly = [
        _m("n", "2025-01", "100.00"),
        _m("n", "2025-02", "-50.00"),
        _m("n", "2025-03", "200.00"),
    ]
    code = _run(_make_pkg(tmp_path, monthly, [_bc("n", "1000.00")]), db_file, tmp_path / "wr")[
        "per_code"
    ][0]
    assert "negative_or_credit_months" in code["data_quality_flags"]
    assert code["statsforecast_eligible"] is True  # negatives reported, do not disqualify


def test_flag_single_spike(tmp_path, db_file):
    monthly = [
        _m("k", "2025-01", "0.00"),
        _m("k", "2025-02", "5000.00"),
        _m("k", "2025-03", "0.00"),
        _m("k", "2025-04", "0.00"),
    ]
    code = _run(_make_pkg(tmp_path, monthly, [_bc("k", "9000.00")]), db_file, tmp_path / "wr")[
        "per_code"
    ][0]
    assert "single_spike" in code["data_quality_flags"]
    assert code["statsforecast_eligible"] is False


def test_flag_has_gaps_still_eligible(tmp_path, db_file):
    monthly = [
        _m("g", "2025-01", "100.00"),
        _m("g", "2025-02", "100.00"),
        _m("g", "2025-04", "100.00"),
    ]  # gap at 2025-03
    code = _run(_make_pkg(tmp_path, monthly, [_bc("g", "1000.00")]), db_file, tmp_path / "wr")[
        "per_code"
    ][0]
    assert code["gap_count"] == 1
    assert "has_gaps" in code["data_quality_flags"]
    assert code["statsforecast_eligible"] is True


def test_flag_source_contamination(tmp_path, db_file):
    monthly = _twelve("c") + [_m("c", "2025-06", "1.00", source="Procore")]  # contaminating row
    code = _run(_make_pkg(tmp_path, monthly, [_bc("c", "100000.00")]), db_file, tmp_path / "wr")[
        "per_code"
    ][0]
    assert "source_contamination" in code["data_quality_flags"]
    assert code["statsforecast_eligible"] is False


def test_histogram_counts_but_eligibility_excludes(tmp_path, db_file):
    # single-spike code has >=3 completed months: counted in histogram 3-5, excluded from eligible.
    monthly = [
        _m("k", "2025-01", "0.00"),
        _m("k", "2025-02", "5000.00"),
        _m("k", "2025-03", "0.00"),
    ]
    r = _run(_make_pkg(tmp_path, monthly, [_bc("k", "9000.00")]), db_file, tmp_path / "wr")
    assert r["aggregate"]["completed_month_histogram"]["3-5"] == 1
    assert r["aggregate"]["codes_ge3"] == 1
    assert r["aggregate"]["codes_eligible"] == 0


# --------------------------------------------------------------------------- semantic gates


def test_actual_cost_null_does_not_break_readiness(tmp_path, db_file):
    # The bundle never reads actual_cost; cumulative actual comes from CostEntries monthly.
    monthly = _twelve("a") + _twelve("b") + _twelve("c")
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00"), _bc("c", "50000.00")]
    r = _run(_make_pkg(tmp_path, monthly, bcs), db_file, tmp_path / "wr")
    assert r["decision"] == DECISION_READY
    assert "actual_cost is 100% null" in " ".join(r["actuals_basis_caveats"])
    assert "job_to_date_costs" in r["actuals_basis_used"]["db_semantic_cumulative_basis"]


def test_erp_fields_excluded_from_actuals(tmp_path, db_file):
    # ERP sidecar amounts must not change the CostEntries-derived cumulative actual.
    monthly = _twelve("a", amount="1000.00")
    bcs = [
        _bc(
            "a",
            "50000.00",
            extra={"erp_job_to_date_costs": "999999.00", "erp_direct_costs": "888888.00"},
        )
    ]
    code = _run(_make_pkg(tmp_path, monthly, bcs), db_file, tmp_path / "wr")["per_code"][0]
    assert code["cumulative_actual_to_date"] == "12000.00"  # 12*1000, ERP ignored
    r = _run(_make_pkg(tmp_path, monthly, bcs, name="ctx2"), db_file, tmp_path / "wr2")
    assert "compare-only" in r["erp_basis_handling"]


def test_unmapped_dynamic_column_not_a_feature(tmp_path, db_file):
    base = _run(
        _make_pkg(tmp_path, _twelve("a"), [_bc("a", "50000.00")], name="base"),
        db_file,
        tmp_path / "w1",
    )
    withcol = _run(
        _make_pkg(
            tmp_path,
            _twelve("a"),
            [_bc("a", "50000.00", extra={"some_custom_view_col": "42424242.00"})],
            name="withcol",
        ),
        db_file,
        tmp_path / "w2",
    )
    # An unknown numeric budget column changes neither eligibility nor coverage.
    assert base["aggregate"]["codes_eligible"] == withcol["aggregate"]["codes_eligible"]
    assert base["coverage"]["dollar_total"] == withcol["coverage"]["dollar_total"]
    assert "review_required" in withcol["dynamic_budget_column_policy"]


def test_semantic_gate_error_blocks_ready(tmp_path, db_file):
    monthly = _twelve("a") + _twelve("b") + _twelve("c")
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00"), _bc("c", "50000.00")]
    r = _run(_make_pkg(tmp_path, monthly, bcs), db_file, tmp_path / "wr", semantic_gate_fn=err_gate)
    assert r["decision"] == DECISION_NOT_READY
    assert any("semantic_gate_errors" in b for b in r["readiness_blockers"])
    assert r["forecast_gate_summary"]["status"] == "fail_blocking"


def test_semantic_gate_warnings_carried_still_ready(tmp_path, db_file):
    monthly = _twelve("a") + _twelve("b") + _twelve("c")
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00"), _bc("c", "50000.00")]
    r = _run(
        _make_pkg(tmp_path, monthly, bcs), db_file, tmp_path / "wr", semantic_gate_fn=warn_gate
    )
    assert r["decision"] == DECISION_READY
    assert r["forecast_gate_summary"]["warning_count"] == 2
    assert any("warning" in w for w in r["readiness_warnings"])
    assert not r["readiness_blockers"]


def test_semantic_gates_not_available_blocks_ready(tmp_path, db_file):
    monthly = _twelve("a") + _twelve("b") + _twelve("c")
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00"), _bc("c", "50000.00")]
    r = _run(
        _make_pkg(tmp_path, monthly, bcs), db_file, tmp_path / "wr", semantic_gate_fn=raising_gate
    )
    assert r["decision"] == DECISION_NOT_READY
    assert r["forecast_gate_summary"]["status"] == "not_available"
    assert any("semantic_gates_not_available" in b for b in r["readiness_blockers"])


# --------------------------------------------------------------------------- preflight refusals


def _ready_pkg(tmp_path):
    return _make_pkg(tmp_path, _twelve("a"), [_bc("a", "50000.00")])


def test_refuse_non_tropical(tmp_path, db_file):
    with pytest.raises(ModelEnginesReadinessError, match="project_key"):
        _run(_ready_pkg(tmp_path), db_file, tmp_path / "wr", project_key="other")


def test_refuse_missing_monthly_file(tmp_path, db_file):
    pkg = tmp_path / "ctx"
    (pkg / "canonical").mkdir(parents=True)
    write_jsonl(pkg / "canonical" / "budget_codes.jsonl", [_bc("a", "1.00")])
    with pytest.raises(ModelEnginesReadinessError, match="monthly_actuals"):
        _run(pkg, db_file, tmp_path / "wr")


def test_refuse_missing_budget_codes_file(tmp_path, db_file):
    pkg = tmp_path / "ctx"
    (pkg / "canonical").mkdir(parents=True)
    write_jsonl(pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl", _twelve("a"))
    with pytest.raises(ModelEnginesReadinessError, match="budget_codes"):
        _run(pkg, db_file, tmp_path / "wr")


def test_refuse_missing_db_path(tmp_path):
    with pytest.raises(ModelEnginesReadinessError, match="db_path not found"):
        _run(_ready_pkg(tmp_path), tmp_path / "nope.sqlite", tmp_path / "wr")


def test_refuse_work_root_under_live_root(tmp_path, db_file, monkeypatch):
    live = tmp_path / "live"
    live.mkdir()
    monkeypatch.setattr(mer, "_LIVE_ROOT", live)
    with pytest.raises(ModelEnginesReadinessError, match="live forecast root"):
        _run(_ready_pkg(tmp_path), db_file, live / "wr")


def test_refuse_nonempty_work_root(tmp_path, db_file):
    wr = tmp_path / "wr"
    (wr / "model_engines_readiness").mkdir(parents=True)
    (wr / "model_engines_readiness" / "stale.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelEnginesReadinessError, match="already contains output"):
        _run(_ready_pkg(tmp_path), db_file, wr)


# --------------------------------------------------------------------------- determinism


def test_determinism_and_input_hashes(tmp_path, db_file):
    monthly = _twelve("a") + _twelve("b")
    bcs = [_bc("a", "50000.00"), _bc("b", "50000.00")]
    pkg = _make_pkg(tmp_path, monthly, bcs)
    r1 = _run(pkg, db_file, tmp_path / "w1")
    r2 = _run(pkg, db_file, tmp_path / "w2")
    b1 = Path(r1["report_path"]).read_text(encoding="utf-8")
    b2 = Path(r2["report_path"]).read_text(encoding="utf-8")
    # Identical except the embedded work_root path; strip it before comparing.
    assert b1.replace(str(tmp_path / "w1"), "WR") == b2.replace(str(tmp_path / "w2"), "WR")
    assert r1["inputs"]["monthly_actuals_sha256"] == sha256_file(
        pkg / "canonical" / "monthly_actuals_by_budget_code.jsonl"
    )
    assert [c["budget_code_key"] for c in r1["per_code"]] == ["a", "b"]  # sorted
