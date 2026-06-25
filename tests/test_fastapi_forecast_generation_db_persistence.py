"""FastAPI tests for P-E gated run-output DB persistence (opt-in ON).

POST /api/forecast/runs/db-config with the run-output DB-write opt-in ON persists forecast_outputs +
child rows to a temp "app" DB (real gated projection; generation mocked to fixtures) and returns a
DB-persistence-aware, path-free response. The real live DB is never touched.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics import (  # noqa: E402
    forecast_run_output_persistence_service as svc,
)
from hb_assistant.construction.analytics import (  # noqa: E402
    forecast_runtime_config as runtime_cfg,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.analytics.forecast_runtime_config import (  # noqa: E402
    ENV_DB_CONFIG_RUN_ENABLED,
    ENV_RUN_OUTPUT_DB_WRITE_ENABLED,
)
from hb_assistant.construction.forecast import source_domain_engine as dbeng  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402
from tests.schedule_project_test_helpers import seed_procore_ep_project  # noqa: E402
from tests.test_forecast_live_db_run_output_projection import (  # noqa: E402
    STAMP,
    _analysis_pkg,
    _downstream_pkgs,
    _twn_source,
)

CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos/construction-financial-review/src"
if str(CFR_SRC) not in sys.path:
    sys.path.insert(0, str(CFR_SRC))

_FORBIDDEN = (
    "output_package",
    "package_path",
    "work_root",
    "data_root",
    "cfr_src",
    "source_path",
    "raw_json",
    "manifest_path",
    "evidence_package_path",
    "run_id",
)


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def _op() -> dict[str, str]:
    return {"X-HB-UI-Role": "operator"}


def _viewer() -> dict[str, str]:
    return {"X-HB-UI-Role": "viewer"}


def _app_db(tmp_path: Path) -> Path:
    """A temp 'app' DB migrated + seeded with tropical identity + v59 source domain."""
    src = _twn_source(tmp_path / "src")
    db = tmp_path / "app" / "hb.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db_path=str(db)).apply()
    seed_procore_ep_project(db, project_key="tropical", display_name="Tropical Resort")
    rec = dbeng.project_source_domain(
        source_package=src, project_key="tropical", db_path=db, apply=True
    )
    assert rec["ok"] is True
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    return db


def _install_generation_mock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock the heavy CFR generation seam to emit fixture packages (persistence stays real)."""
    apkg = _analysis_pkg(tmp_path / "pkgs")
    src = tmp_path / "src" / "twn_cost_forecast_json_package"
    downstream = _downstream_pkgs(tmp_path / "pkgs")

    def _fake_generation(*, project_key: str, work_root: Path) -> svc.GenerationPackages:
        return svc.GenerationPackages(
            analysis_package=apkg,
            source_package=src,
            work_root=work_root,
            context_stamp=STAMP,
            **downstream,
        )

    monkeypatch.setattr(svc, "_run_generation", _fake_generation)


def _db_native_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, data_root: Path | None = None
) -> tuple[TestClient, Path]:
    """A TestClient with both DB-output-write flags on. The DB-native route fails closed up front,
    so _run_generation must never run — we monkeypatch it to assert that and guard against fallback."""
    db = _app_db(tmp_path)
    monkeypatch.setenv(ENV_RUN_OUTPUT_DB_WRITE_ENABLED, "1")
    monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(db))
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, db))
    if data_root is not None:
        monkeypatch.setattr(runtime_cfg, "resolve_data_root", lambda _=None: str(data_root))

    def _must_not_run(*, project_key: str, work_root: Path) -> svc.GenerationPackages:
        raise AssertionError("file-backed generation must not run on the DB-native API route")

    monkeypatch.setattr(svc, "_run_generation", _must_not_run)
    return TestClient(create_app(db_path=str(db))), db


# --- DB-native-intended path: fails closed up front (no file lookup, no CFR, no fallback) ----------


def test_db_native_intended_fails_closed_without_calling_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """generate_and_persist(db_native_intended=True) fails closed BEFORE any _run_generation/CFR call."""

    def _must_not_run(*, project_key: str, work_root: Path) -> svc.GenerationPackages:
        raise AssertionError("_run_generation must not be called on the DB-native-intended path")

    monkeypatch.setattr(svc, "_run_generation", _must_not_run)
    receipt = svc.generate_and_persist(
        project_key="tropical",
        db_path=tmp_path / "throwaway.sqlite",
        work_root=tmp_path / "work",
    )  # db_native_intended defaults True
    assert receipt.db_persisted is False
    assert receipt.package_generated is False
    assert receipt.failure_code == "db_native_generation_not_implemented"
    assert receipt.failure_message
    assert find_redaction_leaks({"failure_message": receipt.failure_message}) == []


def test_db_config_run_api_fails_closed_db_native(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API: both flags on → db_native_generation_not_implemented on the POST response + request row."""
    client, db = _db_native_client(tmp_path, monkeypatch)
    resp = client.post(
        "/api/forecast/runs/db-config",
        headers=_op(),
        json={"project_key": "tropical", "generator_kind": "comprehensive"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["request_status"] == "failed"
    assert body["failure_code"] == "db_native_generation_not_implemented"
    assert body["failure_message"]
    assert body["db_persisted"] is False
    assert body["package_generated"] is False
    for k in _FORBIDDEN:
        assert k not in body, f"forbidden field leaked: {k}"
    assert find_redaction_leaks(body) == []

    # No forecast-output rows written; the file-backed path never ran.
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0

    reqs = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"]
    failed = [r for r in reqs if r["request_status"] == "failed"]
    assert failed, "expected a failed request row in the history"
    assert failed[0]["failure_code"] == "db_native_generation_not_implemented"
    assert failed[0]["failure_message"]
    assert find_redaction_leaks({"requests": reqs}) == []


def test_db_config_run_api_fails_closed_even_with_source_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The DB-native route must fail closed even when a *cost_forecast_json_package EXISTS — proving it
    never silently falls back to file-backed generation."""
    data_root = tmp_path / "data"
    (data_root / "twn_cost_forecast_json_package").mkdir(parents=True)
    client, db = _db_native_client(tmp_path, monkeypatch, data_root=data_root)
    resp = client.post(
        "/api/forecast/runs/db-config",
        headers=_op(),
        json={"project_key": "tropical", "generator_kind": "comprehensive"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["request_status"] == "failed"
    assert body["failure_code"] == "db_native_generation_not_implemented"
    assert body["db_persisted"] is False
    assert body["package_generated"] is False
    # No file-backed fallback: zero output rows even though a source package is present.
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0
    assert find_redaction_leaks(body) == []
    assert str(data_root) not in resp.text


# --- Internal/legacy file-backed path (db_native_intended=False): NOT the DB-native route ----------


def test_file_backed_mode_persists_to_db(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """db_native_intended=False runs file-backed generation + real persistence (mocked generation)."""
    db = _app_db(tmp_path)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, db))
    _install_generation_mock(tmp_path, monkeypatch)
    receipt = svc.generate_and_persist(
        project_key="tropical",
        db_path=db,
        work_root=tmp_path / "work",
        db_native_intended=False,
    )
    assert receipt.db_persisted is True
    assert receipt.package_generated is False
    assert receipt.forecast_output_id
    v = svc.verify_run_output_persistence(db, "tropical")
    assert v["forecast_outputs_count"] >= 1
    assert v["budget_code_rows_count"] >= 1
    assert v["package_manifest_rows_created"] == 0
    assert v["evidence_package_rows_created"] == 0


def test_file_backed_mode_source_package_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """db_native_intended=False + empty data root → precise source_package_missing, path-free."""
    empty_data_root = tmp_path / "data"
    empty_data_root.mkdir()
    monkeypatch.setattr(runtime_cfg, "resolve_data_root", lambda _=None: str(empty_data_root))
    receipt = svc.generate_and_persist(
        project_key="tropical",
        db_path=tmp_path / "throwaway.sqlite",
        work_root=tmp_path / "work",
        db_native_intended=False,
    )
    assert receipt.db_persisted is False
    assert receipt.failure_code == "source_package_missing"
    assert receipt.failure_message
    assert str(empty_data_root) not in (receipt.failure_message or "")
    assert "data_root" not in (receipt.failure_message or "")
    assert find_redaction_leaks({"failure_message": receipt.failure_message}) == []


def test_file_backed_mode_generic_failure_is_calculation_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """db_native_intended=False + generation raises → generic generation_calculation_failed."""
    db = _app_db(tmp_path)

    def _boom(*, project_key: str, work_root: Path) -> svc.GenerationPackages:
        raise RuntimeError("calc failed")

    monkeypatch.setattr(svc, "_run_generation", _boom)
    receipt = svc.generate_and_persist(
        project_key="tropical",
        db_path=db,
        work_root=tmp_path / "work",
        db_native_intended=False,
    )
    assert receipt.db_persisted is False
    assert receipt.failure_code == "generation_calculation_failed"
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0
