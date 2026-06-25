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


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, enabled: bool = True) -> TestClient:
    db = _app_db(tmp_path)
    if enabled:
        monkeypatch.setenv(ENV_RUN_OUTPUT_DB_WRITE_ENABLED, "1")
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, db))
    _install_generation_mock(tmp_path, monkeypatch)
    return TestClient(create_app(db_path=str(db))), db


def test_opt_in_on_persists_to_db_and_returns_safe_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db = _client(tmp_path, monkeypatch, enabled=True)
    resp = client.post(
        "/api/forecast/runs/db-config",
        headers=_op(),
        json={"project_key": "tropical", "generator_kind": "comprehensive"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["db_persisted"] is True
    assert body["package_generated"] is False
    assert body["request_status"] == "completed"
    assert body["forecast_output_id"]
    assert body["generation_mode"] == "db_config"
    for k in _FORBIDDEN:
        assert k not in body, f"forbidden field leaked: {k}"
    assert find_redaction_leaks(body) == []

    # DB rows actually landed; no package manifests / evidence packages.
    v = svc.verify_run_output_persistence(db, "tropical")
    assert v["forecast_outputs_count"] >= 1
    assert v["budget_code_rows_count"] >= 1
    assert v["package_manifest_rows_created"] == 0
    assert v["evidence_package_rows_created"] == 0

    # Request history reflects the completed request for the project.
    reqs = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"]
    assert any(r["request_status"] == "completed" for r in reqs)


def test_persistence_failure_marks_request_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, db = _client(tmp_path, monkeypatch, enabled=True)

    def _boom(*, project_key: str, work_root: Path) -> svc.GenerationPackages:
        raise RuntimeError("calc failed")

    monkeypatch.setattr(svc, "_run_generation", _boom)
    resp = client.post(
        "/api/forecast/runs/db-config",
        headers=_op(),
        json={"project_key": "tropical", "generator_kind": "comprehensive"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["db_persisted"] is False
    assert body["request_status"] == "failed"
    assert body["package_generated"] is False
    assert body["failure_code"] == "generation_calculation_failed"
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0
    assert find_redaction_leaks(body) == []


def test_generate_and_persist_source_package_missing_returns_precise_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty data root (no *cost_forecast_json_package) → precise source_package_missing code.

    Persistence-service unit level: the missing-source-package branch runs before any CFR import
    or DB access, so no live DB is touched. The coded failure message stays path-free.
    """
    empty_data_root = tmp_path / "data"
    empty_data_root.mkdir()
    monkeypatch.setattr(runtime_cfg, "resolve_data_root", lambda _=None: str(empty_data_root))

    receipt = svc.generate_and_persist(
        project_key="tropical",
        db_path=tmp_path / "throwaway.sqlite",
        work_root=tmp_path / "work",
    )
    assert receipt.db_persisted is False
    assert receipt.failure_code == "source_package_missing"
    assert receipt.failure_message  # curated, populated
    # No local path / data_root token leaks through the safe message.
    assert str(empty_data_root) not in (receipt.failure_message or "")
    assert "data_root" not in (receipt.failure_message or "")
    assert find_redaction_leaks({"failure_message": receipt.failure_message}) == []


def test_db_config_run_source_package_missing_surfaces_precise_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """API regression: both flags on + empty data_root → request_status failed with the precise,
    safe source_package_missing code/message on BOTH the POST response and the listed request row.
    """
    db = _app_db(tmp_path)
    empty_data_root = tmp_path / "data"
    empty_data_root.mkdir()
    monkeypatch.setenv(ENV_RUN_OUTPUT_DB_WRITE_ENABLED, "1")
    monkeypatch.setenv(ENV_DB_CONFIG_RUN_ENABLED, "1")
    monkeypatch.setenv("HB_FORECAST_DB_PATH", str(db))
    # Real _run_generation (not mocked): resolves to an empty data root and finds no source package.
    monkeypatch.setattr(runtime_cfg, "resolve_data_root", lambda _=None: str(empty_data_root))
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: _same(p, db))
    client = TestClient(create_app(db_path=str(db)))

    resp = client.post(
        "/api/forecast/runs/db-config",
        headers=_op(),
        json={"project_key": "tropical", "generator_kind": "comprehensive"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["request_status"] == "failed"
    assert body["failure_code"] == "source_package_missing"
    assert body["failure_message"]
    assert body["db_persisted"] is False
    assert body["package_generated"] is False
    for k in _FORBIDDEN:
        assert k not in body, f"forbidden field leaked: {k}"
    assert find_redaction_leaks(body) == []
    assert str(empty_data_root) not in resp.text

    # No rows persisted; the live DB write never ran.
    assert svc.verify_run_output_persistence(db, "tropical")["forecast_outputs_count"] == 0

    # The persisted + listed request row exposes the precise code + safe message.
    reqs = client.get(
        "/api/forecast/generation/requests", params={"project_key": "tropical"}, headers=_viewer()
    ).json()["requests"]
    failed = [r for r in reqs if r["request_status"] == "failed"]
    assert failed, "expected a failed request row in the history"
    assert failed[0]["failure_code"] == "source_package_missing"
    assert failed[0]["failure_message"]
    assert find_redaction_leaks({"requests": reqs}) == []
