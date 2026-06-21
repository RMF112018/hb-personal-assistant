"""FastAPI route tests for forecast config editing — isolated proposals (Implementation Phase E).

Asserts: POST is operator-gated and GET is viewer-readable; forecast_controls / bad decimal → 400;
unknown snapshot → 404; unconfigured config-edit root → 503; and every response is redaction-clean.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos" / "construction-financial-review" / "src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402

ENV_DATA_ROOT = "HB_FORECAST_DATA_ROOT"
ENV_CONFIG_EDIT_ROOT = "HB_FORECAST_CONFIG_EDIT_ROOT"


def _build_fixture_db(tmp_path: Path) -> tuple[Path, str]:
    from construction_financial_review.config_registry import (
        create_forecast_config_snapshot,
        import_forecast_config_to_db,
    )

    cfg = tmp_path / "sample" / "config"
    (cfg / "projects").mkdir(parents=True)
    (cfg / "forecast_model_controls" / "tropical").mkdir(parents=True)
    project = {
        "project_key": "tropical",
        "project_name": "TWN",
        "materiality_absolute": "25000.00",
        "default_data_root": "/Users/secret/internal",
        "llm": {"endpoint": "http://localhost:11434"},
    }
    (cfg / "projects" / "tropical.json").write_text(json.dumps(project), encoding="utf-8")
    (cfg / "forecast_model_controls" / "tropical" / "code_forecast_model_controls.jsonl").write_text(
        json.dumps({"project_key": "tropical", "control_id": "C-001", "explicit_value_amount": "1000.00"}) + "\n",
        encoding="utf-8",
    )
    db = tmp_path / "fixture.sqlite"
    import_forecast_config_to_db(config_root=tmp_path / "sample", db_path=db, project_key="tropical")
    snap = create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="base", snapshot_reason="fixture"
    )
    return db, snap["config_snapshot_id"]


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db, snap = _build_fixture_db(tmp_path)
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data_root))
    monkeypatch.setenv(ENV_CONFIG_EDIT_ROOT, str(tmp_path / "config_edits"))
    client = TestClient(create_app(db_path=str(db)))
    return client, snap


def _h(role: str) -> dict[str, str]:
    return {"X-HB-UI-Role": role}


def _edit(snap: str) -> dict:
    return {
        "base_snapshot_id": snap,
        "edits": [{"domain": "project", "op": "modify", "item_key": "tropical", "fields": {"materiality_absolute": "30000.00"}}],
    }


def test_post_requires_operator(ctx) -> None:
    client, snap = ctx
    assert client.post("/api/forecast/config/edits", headers=_h("viewer"), json=_edit(snap)).status_code == 403


def test_post_success_is_leak_free(ctx) -> None:
    client, snap = ctx
    r = client.post("/api/forecast/config/edits", headers=_h("operator"), json=_edit(snap))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded"
    assert body["parity"]["status"] == "pass"
    assert find_redaction_leaks(body) == []


def test_forecast_controls_edit_is_400(ctx) -> None:
    client, snap = ctx
    r = client.post(
        "/api/forecast/config/edits",
        headers=_h("operator"),
        json={"base_snapshot_id": snap, "edits": [{"domain": "forecast_controls", "item_key": "x", "fields": {"a": "1"}}]},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "forecast_config_edit_invalid_input"


def test_unknown_snapshot_is_404(ctx) -> None:
    client, _ = ctx
    r = client.post(
        "/api/forecast/config/edits",
        headers=_h("operator"),
        json={"base_snapshot_id": "nope", "edits": [{"domain": "project", "item_key": "tropical", "fields": {"project_name": "X"}}]},
    )
    assert r.status_code == 404


def test_list_and_detail_viewer_readable(ctx) -> None:
    client, snap = ctx
    created = client.post("/api/forecast/config/edits", headers=_h("operator"), json=_edit(snap)).json()
    edit_id = created["edit_id"]
    listing = client.get("/api/forecast/config/edits", headers=_h("viewer"))
    assert listing.status_code == 200
    assert find_redaction_leaks(listing.json()) == []
    detail = client.get(f"/api/forecast/config/edits/{edit_id}", headers=_h("viewer"))
    assert detail.status_code == 200
    assert find_redaction_leaks(detail.json()) == []
    manifest = client.get(f"/api/forecast/config/edits/{edit_id}/manifest", headers=_h("viewer"))
    assert manifest.status_code == 200
    assert find_redaction_leaks(manifest.json()) == []


def test_unconfigured_is_503(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, snap = _build_fixture_db(tmp_path)
    monkeypatch.delenv(ENV_CONFIG_EDIT_ROOT, raising=False)
    client = TestClient(create_app(db_path=str(db)))
    r = client.post("/api/forecast/config/edits", headers=_h("operator"), json=_edit(snap))
    assert r.status_code == 503


def test_invalid_role_rejected(ctx) -> None:
    client, _ = ctx
    assert client.get("/api/forecast/config/edits", headers=_h("root")).status_code == 403
