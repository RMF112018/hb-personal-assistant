"""DB-config-backed generation across all four generators (model_controls/monthly/probability + the
comprehensive back-compat path). Productionizes the Phase 17-20 proofs: each REAL generator runs
CONSUMING the materialized DB config snapshot through the CFR_CONFIG_ROOT bridge, fidelity-gated.

Reuses each phase proof's reduced CI fixture builder (``_setup``) — the real live DB is never touched.
Asserts CONFIG CONSUMPTION + the fidelity/quiescence/predecessor guards, NOT the generator's
validation verdict on the reduced fixtures (which legitimately reports validation_passed False — the
proofs assert parity, not validation, on the same fixtures).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_TESTS_DIR = _HERE.parent
_CFR_SRC = _HERE.parents[1] / "subrepos" / "construction-financial-review" / "src"
for _p in (str(_TESTS_DIR), str(_CFR_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from construction_financial_review.common import config_root as crootmod  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_db_config_backed_generation as genwf,
)
from construction_financial_review.workflows import (  # noqa: E402
    forecast_monthly_db_config_proof as moproof,
)

# Reuse the four phase proof fixtures (each self-bootstraps CFR on sys.path).
from test_forecast_comprehensive_db_config_phase20 import _setup as _setup_comprehensive  # noqa: E402
from test_forecast_model_controls_db_config_phase17 import SUBPROJ as _MC_SUBPROJ  # noqa: E402
from test_forecast_model_controls_db_config_phase17 import _setup as _setup_model_controls  # noqa: E402
from test_forecast_monthly_db_config_phase18 import _setup as _setup_monthly  # noqa: E402
from test_forecast_probability_db_config_phase19 import _setup as _setup_probability  # noqa: E402

STAMP = "20260101_000000"


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _gen(tmp_path, kind, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("preflight_stability_seconds", 0.0)
    return genwf.run_forecast_db_config_backed_generation_for_kind(
        generator_kind=kind,
        live_db_path=db,
        config_snapshot_id=snap_id,
        work_root=tmp_path / "work",
        run_stamp=STAMP,
        require_live_snapshot=False,
        data_root=data_root,
        source_config_root=cfg_root,
        **kw,
    )


def _assert_consumed(rep, kind, expected_domains):
    assert rep["generator_kind"] == kind
    assert rep["status"] in (genwf.STATUS_GENERATED, genwf.STATUS_VALIDATION_FAILED)
    assert rep["config_snapshot_consumed"] is True
    assert rep["fidelity_gate"]["passed"] is True
    assert rep["reads_materialized_config"] is True
    assert rep["cfr_config_root_restored"] is True
    assert Path(rep["output_package"]).is_dir()
    assert rep["live_db_integrity"]["unchanged"] is True
    assert rep["consumed_config_domains"] == expected_domains


# --- model_controls --------------------------------------------------------------------


def _setup_model_controls_nested(tmp_path):
    """Phase 17 places the temp DB directly under tmp_path; relocate it into a subdir so the work-root
    (tmp_path/work) is not under the live-DB directory (the core's containment guard is stricter than
    the Phase 17 proof's)."""
    db, snap, data_root = _setup_model_controls(tmp_path)
    dbdir = tmp_path / "dbdir"
    dbdir.mkdir(exist_ok=True)
    moved = dbdir / db.name
    for suffix in ("", "-wal", "-shm"):
        src = Path(str(db) + suffix)
        if src.exists():
            src.rename(Path(str(moved) + suffix))
    return moved, snap, data_root


def test_model_controls_generates_consuming_db_config(tmp_path):
    db, snap, data_root = _setup_model_controls_nested(tmp_path)
    rep = _gen(tmp_path, "model_controls", db, snap["config_snapshot_id"], data_root, _MC_SUBPROJ)
    _assert_consumed(rep, "model_controls", ["forecast_model_controls"])


def test_model_controls_fidelity_failure_refuses(tmp_path, monkeypatch):
    db, snap, data_root = _setup_model_controls_nested(tmp_path)
    real = genwf.cr.create_forecast_config_snapshot

    def _bad(**kw):
        out = real(**kw)
        return {**out, "snapshot_sha256": "deadbeef", "item_count": out["item_count"] + 1}

    monkeypatch.setattr(genwf.cr, "create_forecast_config_snapshot", _bad)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _gen(tmp_path, "model_controls", db, snap["config_snapshot_id"], data_root, _MC_SUBPROJ)
    assert str(exc.value).startswith(genwf.REASON_FIDELITY)


# --- monthly ---------------------------------------------------------------------------


def test_monthly_generates_consuming_db_config(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_monthly(tmp_path, monkeypatch)
    rep = _gen(tmp_path, "monthly", db, snap["config_snapshot_id"], data_root, cfg_root)
    _assert_consumed(
        rep,
        "monthly",
        ["forecast_controls", "forecast_model_controls", "forecast_staffing", "project"],
    )


def test_monthly_missing_predecessor_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_monthly(tmp_path, monkeypatch)
    ctx = next(Path(data_root).glob("forecast_context_package_tropical_*"))
    shutil.rmtree(ctx)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _gen(tmp_path, "monthly", db, snap["config_snapshot_id"], data_root, cfg_root)
    assert str(exc.value).startswith(genwf.REASON_PREDECESSOR)


def test_monthly_unsafe_integration_systemexit_becomes_refusal(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_monthly(tmp_path, monkeypatch)

    def _raise(**kw):
        raise SystemExit("integration unsafe")

    # The monthly descriptor binds moproof._run_monthly at generation time, so this patch is honored;
    # the core must convert the SystemExit into a controlled refusal (never kill the process).
    monkeypatch.setattr(moproof, "_run_monthly", _raise)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _gen(tmp_path, "monthly", db, snap["config_snapshot_id"], data_root, cfg_root)
    assert str(exc.value).startswith(genwf.REASON_GENERATOR_REFUSED)


# --- probability -----------------------------------------------------------------------


def test_probability_generates_consuming_db_config(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_probability(tmp_path, monkeypatch)
    rep = _gen(
        tmp_path, "probability", db, snap["config_snapshot_id"], data_root, cfg_root,
        runs=64, seed=20260614,
    )
    _assert_consumed(rep, "probability", ["owner_sov_crosswalk", "project"])


def test_probability_missing_monthly_package_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_probability(tmp_path, monkeypatch)
    monthly = next(Path(data_root).glob("forecast_monthly_package_tropical_*"))
    shutil.rmtree(monthly)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _gen(
            tmp_path, "probability", db, snap["config_snapshot_id"], data_root, cfg_root,
            runs=64, seed=20260614,
        )
    assert str(exc.value).startswith(genwf.REASON_PREDECESSOR)


# --- comprehensive back-compat through the for-kind entry ------------------------------


def test_comprehensive_via_for_kind(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_comprehensive(tmp_path, monkeypatch)
    rep = _gen(tmp_path, "comprehensive", db, snap["config_snapshot_id"], data_root, cfg_root)
    _assert_consumed(
        rep, "comprehensive", ["forecast_controls", "forecast_model_controls", "project"]
    )


# --- unsupported kind ------------------------------------------------------------------


def test_unsupported_kind_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup_comprehensive(tmp_path, monkeypatch)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _gen(tmp_path, "bogus", db, snap["config_snapshot_id"], data_root, cfg_root)
    assert str(exc.value).startswith(genwf.REASON_UNSUPPORTED_KIND)
