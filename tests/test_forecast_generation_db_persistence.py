"""P-E — run-output DB persistence service tests (real gated projection on a temp app DB).

Generation is out of scope here: we reuse the live-write fixtures to stand in for the ephemeral
internal packages, and exercise the REAL gated projection (persist_run_output) writing the run graph
into a temp "app" DB. The real live DB is never touched.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from hb_assistant.construction.forecast import source_domain_engine as dbeng
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.construction.analytics.forecast_run_output_persistence_service import (
    GenerationPackages,
    persist_run_output,
    verify_run_output_persistence,
)
from hb_assistant.store.migrator import SQLiteMigrator

# Reuse the live-write fixture builders (synthetic source + analysis + downstream packages).
from tests.test_forecast_live_db_run_output_projection import (  # noqa: E402
    STAMP,
    _analysis_pkg,
    _build_live_db,
    _downstream_pkgs,
    _twn_source,
)

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _packages(tmp_path: Path) -> GenerationPackages:
    src = _twn_source(tmp_path / "src")
    apkg = _analysis_pkg(tmp_path / "pkgs")
    downstream = _downstream_pkgs(tmp_path / "pkgs")
    return GenerationPackages(
        analysis_package=apkg,
        source_package=src,
        work_root=tmp_path / "work",
        context_stamp=STAMP,
        **downstream,
    )


def _live_db(tmp_path: Path) -> Path:
    src = tmp_path / "src" / "twn_cost_forecast_json_package"
    live = tmp_path / "live" / "hb.sqlite"
    _build_live_db(live, with_v59=True, source_package=src)
    return live


def test_persist_writes_run_graph_and_returns_safe_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packages = _packages(tmp_path)
    live = _live_db(tmp_path)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, live))

    receipt = persist_run_output(project_key="tropical", db_path=live, packages=packages)

    assert receipt.db_persisted is True
    assert receipt.package_generated is False
    assert receipt.certified is True
    assert receipt.forecast_output_id  # opaque output id
    assert receipt.failure_code is None
    # Receipt is redaction-safe (no paths / run stamps / raw json).
    assert find_redaction_leaks(
        {
            "forecast_output_id": receipt.forecast_output_id,
            "counts": receipt.counts,
            "db_persisted": receipt.db_persisted,
        }
    ) == []

    v = verify_run_output_persistence(live, "tropical")
    assert v["forecast_outputs_count"] >= 1
    assert v["budget_code_rows_count"] >= 1
    assert v["monthly_rows_count"] >= 1
    assert v["probability_rows_count"] >= 1
    assert v["risk_rows_count"] >= 1
    assert v["schedule_phasing_rows_count"] >= 1
    # Generate Forecast never writes package manifests or evidence packages.
    assert v["package_manifest_rows_created"] == 0
    assert v["evidence_package_rows_created"] == 0


def test_persist_failure_returns_coded_reason_no_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A bogus analysis package (missing required JSONL) makes the projection fail closed.
    live = _live_db(tmp_path)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, live))
    bad = GenerationPackages(
        analysis_package=tmp_path / "does_not_exist",
        source_package=tmp_path / "src" / "twn_cost_forecast_json_package",
        work_root=tmp_path / "work",
        context_stamp=STAMP,
    )
    receipt = persist_run_output(project_key="tropical", db_path=live, packages=bad)
    assert receipt.db_persisted is False
    assert receipt.failure_code in {"db_persistence_failed", "forecast_output_write_failed"}
    assert receipt.forecast_output_id is None
    assert verify_run_output_persistence(live, "tropical")["forecast_outputs_count"] == 0
