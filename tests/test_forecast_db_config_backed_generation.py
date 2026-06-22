"""Tests for the DB-config-backed comprehensive generation workflow (productionizes Phase 20).

Reuses the Phase 20 proof's reduced CI fixture (_setup builds a temp v60 DB with a 5-item snapshot,
a data_root with the required predecessor packages, and monkeypatches the generators' SUBPROJECT_ROOT
+ the inventory DB). The real live DB is never touched. Asserts: the comprehensive package is
generated CONSUMING the DB snapshot (config_snapshot_consumed True), the materialization-fidelity gate
passes/refuses correctly, and the cost-frequency / predecessor / unsafe-work-root guards fail closed.
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

# Reuse the Phase 20 proof fixture builders (self-bootstraps CFR on sys.path).
import json  # noqa: E402

from construction_financial_review import cli  # noqa: E402
from construction_financial_review import config_registry as cr  # noqa: E402
from construction_financial_review.common import config_root as crootmod  # noqa: E402
from construction_financial_review.workflows import (  # noqa: E402
    forecast_db_config_backed_generation as genwf,
)
from test_forecast_comprehensive_db_config_phase20 import (  # noqa: E402
    STAMP,
    _setup,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv(crootmod.ENV_CONFIG_ROOT, raising=False)


def _run(tmp_path, db, snap_id, data_root, cfg_root, **kw):
    kw.setdefault("preflight_stability_seconds", 0.0)
    return genwf.run_forecast_db_config_backed_generation(
        live_db_path=db,
        config_snapshot_id=snap_id,
        work_root=tmp_path / "work",
        run_stamp=STAMP,
        require_live_snapshot=False,
        data_root=data_root,
        source_config_root=cfg_root,
        **kw,
    )


def test_generates_consuming_db_config(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    # This phase proves CONFIG CONSUMPTION, not the generator's validation verdict on the reduced
    # 1-code fixture (which legitimately reports validation_passed False — the Phase 20 proof asserts
    # parity, not validation, on the same fixture).
    assert rep["status"] in (genwf.STATUS_GENERATED, genwf.STATUS_VALIDATION_FAILED)
    assert rep["config_snapshot_consumed"] is True
    assert rep["fidelity_gate"]["passed"] is True
    assert rep["reads_materialized_config"] is True
    assert rep["cfr_config_root_restored"] is True
    assert Path(rep["output_package"]).is_dir()
    assert rep["live_db_integrity"]["unchanged"] is True
    # consumed accounting comes from the materialized manifest (the 3 domains comprehensive reads).
    assert rep["consumed_config_domains"] == [
        "forecast_controls",
        "forecast_model_controls",
        "project",
    ]


def test_latest_snapshot_selected_when_id_omitted(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rep = _run(tmp_path, db, None, data_root, cfg_root)  # no config_snapshot_id → latest
    assert rep["config_snapshot_id"] == snap["config_snapshot_id"]
    assert rep["config_snapshot_consumed"] is True


def test_fidelity_failure_refuses_and_emits_no_package(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    # Corrupt the round-trip result so the materialized tree does not match the stored snapshot digest.
    real = cr.create_forecast_config_snapshot

    def _bad(**kw):
        out = real(**kw)
        return {**out, "snapshot_sha256": "deadbeef", "item_count": out["item_count"] + 1}

    monkeypatch.setattr(genwf.cr, "create_forecast_config_snapshot", _bad)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert str(exc.value).startswith(genwf.REASON_FIDELITY)
    assert not (tmp_path / "work" / genwf.DB_BACKED_SUBDIR).exists()


def test_cost_frequency_guard_refuses_without_writing_data_root(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch, with_cost_freq=False)
    before = sorted(p.name for p in Path(data_root).iterdir())
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert str(exc.value).startswith(genwf.REASON_COST_FREQ)
    # The read-only data root must be untouched (no cost_frequency package generated into it).
    after = sorted(p.name for p in Path(data_root).iterdir())
    assert before == after
    assert not any("cost_frequency" in n for n in after)


def test_missing_predecessor_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    monthly = next(Path(data_root).glob("forecast_monthly_package_tropical_*"))
    shutil.rmtree(monthly)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        _run(tmp_path, db, snap["config_snapshot_id"], data_root, cfg_root)
    assert str(exc.value).startswith(genwf.REASON_PREDECESSOR)


def test_unsafe_work_root_under_data_root_refuses(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    with pytest.raises(genwf.ForecastDbConfigGenerationError) as exc:
        genwf.run_forecast_db_config_backed_generation(
            live_db_path=db,
            config_snapshot_id=snap["config_snapshot_id"],
            work_root=Path(data_root) / "work",  # under the data root → refused
            run_stamp=STAMP,
            require_live_snapshot=False,
            data_root=data_root,
            source_config_root=cfg_root,
            preflight_stability_seconds=0.0,
        )
    assert "work_root is at/under" in str(exc.value)


def _cli_args(tmp_path, db, snap_id, cfg_root, data_root):
    return [
        "forecast-db-config-backed-generate",
        "--live-db-path", str(db),
        "--config-snapshot-id", snap_id,
        "--work-root", str(tmp_path / "cli_work"),
        "--run-stamp", STAMP,
        "--data-root", str(data_root),
        "--source-config-root", str(cfg_root),
        "--no-require-live-snapshot",
        "--preflight-stability-seconds", "0",
    ]


def test_cli_generated_rc(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, snap["config_snapshot_id"], cfg_root, data_root))
    assert rc in (0, 1)  # generated; the validation verdict depends on the reduced fixture
    out = json.loads(capsys.readouterr().out)
    assert out["config_snapshot_consumed"] is True
    assert out["command"] == "forecast-db-config-backed-generate"


def test_cli_refusal_rc3(tmp_path, monkeypatch, capsys):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    rc = cli.main(_cli_args(tmp_path, db, "missing-snapshot", cfg_root, data_root))
    assert rc == 3
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "refused"


def test_readonly_materialize_does_not_write_main_db(tmp_path, monkeypatch):
    db, snap, data_root, cfg_root = _setup(tmp_path, monkeypatch)
    import hashlib

    def _sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    before = _sha(Path(db))
    mat = cr.materialize_forecast_config_snapshot_readonly(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "ro_mat"
    )
    after = _sha(Path(db))
    assert before == after  # mode=ro never writes the main DB
    assert Path(mat["materialized_config_root"]).is_dir()
    # The RO helper produces the same manifest hashes as the read-write helper.
    rw = cr.materialize_forecast_config_snapshot(
        db_path=db, config_snapshot_id=snap["config_snapshot_id"], out_root=tmp_path / "rw_mat"
    )
    assert mat["hashes"] == rw["hashes"] and mat["snapshot_sha256"] == rw["snapshot_sha256"]
