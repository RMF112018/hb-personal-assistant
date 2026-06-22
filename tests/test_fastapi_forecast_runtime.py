"""FastAPI route tests for forecast runtime config wiring (Implementation Phase 6).

Asserts: GET status is viewer-readable and redaction-safe; GET config echoes raw paths and is
ADMIN-only (the documented carve-out — its body DOES carry paths); POST config is operator-gated,
refuses a write-root under data_root (400, nothing persisted), and on success returns the
redaction-safe status; and a settings-file-only (no env) config actually reaches the catalog
service so GET /api/forecast/projects serves data instead of failing closed (503).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics import forecast_runtime_config as rc  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402

ENV_VARS = (
    "HB_FORECAST_PACKAGE_ROOTS",
    "HB_FORECAST_DATA_ROOT",
    "HB_FORECAST_RUNS_ROOT",
    "HB_FORECAST_EVAL_ROOT",
    "HB_FORECAST_DB_PATH",
    "HB_FORECAST_CFR_SRC",
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    cfg = tmp_path / "forecast_runtime_config.json"
    monkeypatch.setattr(rc, "_config_path", lambda: cfg)
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    return TestClient(create_app(db_path=str(tmp_path / "x.sqlite")))


def _h(role: str) -> dict[str, str]:
    return {"X-HB-UI-Role": role}


# -- status (viewer, redaction-safe) ------------------------------------------


def test_status_viewer_readable_and_redaction_safe(client: TestClient) -> None:
    r = client.get("/api/forecast/runtime/status", headers=_h("viewer"))
    assert r.status_code == 200
    body = r.json()
    assert set(body["roots"]) == {
        "package_roots",
        "data_root",
        "runs_root",
        "eval_root",
        "db_path",
        "cfr_src",
        "config_edit_root",
    }
    assert find_redaction_leaks(body) == []


def test_invalid_role_rejected(client: TestClient) -> None:
    r = client.get("/api/forecast/runtime/status", headers=_h("superuser"))
    assert r.status_code == 403


# -- admin config echo (carve-out: DOES return paths) -------------------------


def test_config_echo_is_admin_only(client: TestClient) -> None:
    assert client.get("/api/forecast/runtime/config", headers=_h("viewer")).status_code == 403
    assert client.get("/api/forecast/runtime/config", headers=_h("operator")).status_code == 403
    r = client.get("/api/forecast/runtime/config", headers=_h("admin"))
    assert r.status_code == 200
    assert set(r.json()["config"]) >= {"package_roots", "data_root", "db_path"}


def test_config_echo_returns_raw_paths(
    client: TestClient, tmp_path: Path
) -> None:
    rc._config_path().write_text(json.dumps({"data_root": str(tmp_path / "data")}), encoding="utf-8")
    body = client.get("/api/forecast/runtime/config", headers=_h("admin")).json()
    assert body["config"]["data_root"] == str(tmp_path / "data")
    # Documented carve-out: this admin-only body intentionally carries a path (would otherwise leak).
    assert find_redaction_leaks(body) != []


# -- write (operator-gated, fail-closed) --------------------------------------


def test_write_requires_admin(client: TestClient) -> None:
    assert client.post("/api/forecast/runtime/config", headers=_h("viewer"), json={"data_root": "/x"}).status_code == 403
    assert client.post("/api/forecast/runtime/config", headers=_h("operator"), json={"data_root": "/x"}).status_code == 403


def test_write_refuses_write_root_under_data_root(client: TestClient, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    r = client.post(
        "/api/forecast/runtime/config",
        headers=_h("admin"),
        json={"data_root": str(data), "runs_root": str(data / "inside")},
    )
    assert r.status_code == 400
    assert r.json()["detail"].startswith("forecast_runtime_invalid:runs_root")
    assert not rc._config_path().exists()  # nothing persisted
    assert find_redaction_leaks(r.json()) == []  # the error detail is path-free


def test_write_success_returns_redaction_safe_status(client: TestClient, tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    r = client.post(
        "/api/forecast/runtime/config",
        headers=_h("admin"),
        json={
            "data_root": str(data),
            "runs_root": str(tmp_path / "runs"),
            "eval_root": str(tmp_path / "eval"),
            "package_roots": [str(pkg)],
        },
    )
    assert r.status_code == 200
    assert find_redaction_leaks(r.json()) == []
    # Persisted: the admin echo now reflects the submitted data_root.
    echo = client.get("/api/forecast/runtime/config", headers=_h("admin")).json()
    assert echo["config"]["data_root"] == str(data)


# -- end-to-end: settings file (no env) reaches the catalog service -----------


def test_repair_bootstraps_managed_storage(client: TestClient) -> None:
    r = client.post("/api/forecast/runtime/repair", headers=_h("operator"))
    assert r.status_code == 200
    body = r.json()
    assert body["storage_mode"] == "app_managed"
    assert find_redaction_leaks(body) == []


def test_reset_requires_admin_and_confirm(client: TestClient) -> None:
    assert client.post("/api/forecast/runtime/reset", headers=_h("operator"), json={"confirm": True}).status_code == 403
    r = client.post("/api/forecast/runtime/reset", headers=_h("admin"), json={"confirm": False})
    assert r.status_code == 400
    assert r.json()["detail"] == "forecast_runtime_reset_confirm_required"
    ok = client.post("/api/forecast/runtime/reset", headers=_h("admin"), json={"confirm": True})
    assert ok.status_code == 200
    assert ok.json()["storage_mode"] == "app_managed"


def test_settings_file_only_reaches_catalog(client: TestClient, tmp_path: Path) -> None:
    # No env vars set (fixture cleared them). Unconfigured → catalog fails closed.
    assert client.get("/api/forecast/projects", headers=_h("viewer")).status_code == 503

    # Configure package_roots via the settings file only; the catalog must now construct.
    pkg = tmp_path / "packages"
    pkg.mkdir()
    rc._config_path().write_text(json.dumps({"package_roots": [str(pkg)]}), encoding="utf-8")
    r = client.get("/api/forecast/projects", headers=_h("viewer"))
    assert r.status_code == 200  # settings-file root reached ForecastCatalogService
    assert find_redaction_leaks(r.json()) == []
