"""FastAPI route + service tests for forecast config promotion (Implementation Phase E2).

A synthetic config DB is treated as "live" (monkeypatched ``is_live_db_path``) so the gated live-write
path executes against a FIXTURE — the real live DB is never touched. Proves the opt-in + confirm +
parity-pass gating, role gating, the certified promotion writing the fixture, redaction-cleanliness,
and the persisted promotion record.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos" / "construction-financial-review" / "src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from construction_financial_review.config_registry import (  # noqa: E402
    create_forecast_config_snapshot,
    import_forecast_config_to_db,
)
from fastapi.testclient import TestClient  # noqa: E402

from hb_assistant.construction.analytics import create_app  # noqa: E402
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402
from hb_assistant.construction.forecast import source_domain_engine as dbeng  # noqa: E402
from hb_assistant.store.migrator import SQLiteMigrator  # noqa: E402

ENV_DATA_ROOT = "HB_FORECAST_DATA_ROOT"
ENV_CONFIG_EDIT_ROOT = "HB_FORECAST_CONFIG_EDIT_ROOT"
ENV_PROMOTION_ENABLED = "HB_FORECAST_PROMOTION_ENABLED"


def _build_config_tree(root: Path) -> None:
    cfg = root / "config"
    (cfg / "projects").mkdir(parents=True)
    (cfg / "forecast_model_controls" / "tropical").mkdir(parents=True)
    (cfg / "projects" / "tropical.json").write_text(
        json.dumps({"project_key": "tropical", "project_name": "TWN", "materiality_absolute": "25000.00"}),
        encoding="utf-8",
    )
    (cfg / "forecast_model_controls" / "tropical" / "code_forecast_model_controls.jsonl").write_text(
        json.dumps({"project_key": "tropical", "control_id": "C-001", "explicit_value_amount": "1000.00"}) + "\n",
        encoding="utf-8",
    )


def _seed_proposal(edits_root: Path, edit_id: str, tmp_path: Path, *, parity: str = "pass") -> None:
    """Write a proposal (edit_record.json + edited_config) whose recorded hashes match its config."""
    edit_dir = edits_root / edit_id
    edited = edit_dir / "edited_config"
    _build_config_tree(edited)
    # Compute the approved snapshot's item_count + hashes via a throwaway temp DB.
    db = tmp_path / f"expect_{edit_id}.sqlite"
    import_forecast_config_to_db(config_root=edited, db_path=db, project_key="tropical")
    snap = create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name=f"promotion_{edit_id}", snapshot_reason="r"
    )
    edit_dir.joinpath("edit_record.json").write_text(
        json.dumps(
            {
                "edit_id": edit_id,
                "created_stamp": "20260621_110000",
                "project_key": "tropical",
                "status": "succeeded",
                "parity": {"status": parity},
                "snapshot_item_count": snap["item_count"],
                "snapshot_hashes_by_domain": snap["hashes_by_domain"],
            }
        ),
        encoding="utf-8",
    )


def _checkpoint(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


@pytest.fixture
def ctx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_root = tmp_path / "data"
    data_root.mkdir()
    config_edit_root = tmp_path / "config_edits"
    (config_edit_root / "edits").mkdir(parents=True)
    live = tmp_path / "live.sqlite"
    SQLiteMigrator(db_path=str(live)).apply()
    _checkpoint(live)
    monkeypatch.setattr(dbeng, "is_live_db_path", lambda p: Path(p).resolve() == live.resolve())
    monkeypatch.setenv(ENV_DATA_ROOT, str(data_root))
    monkeypatch.setenv(ENV_CONFIG_EDIT_ROOT, str(config_edit_root))
    monkeypatch.delenv(ENV_PROMOTION_ENABLED, raising=False)
    _seed_proposal(config_edit_root / "edits", "edit01", tmp_path)
    client = TestClient(create_app(db_path=str(live)))
    return {"client": client, "live": live, "edits_root": config_edit_root / "edits", "tmp": tmp_path}


def _h(role: str) -> dict[str, str]:
    return {"X-HB-UI-Role": role}


def _snapshots(live: Path) -> int:
    conn = sqlite3.connect(f"file:{live.resolve()}?mode=ro", uri=True)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM forecast_config_snapshots").fetchone()[0])
    finally:
        conn.close()


def _post(ctx, edit_id="edit01", role="operator", confirm=True):
    return ctx["client"].post(
        f"/api/forecast/config/edits/{edit_id}/promote", headers=_h(role), json={"confirm": confirm}
    )


# -- gating -------------------------------------------------------------------


def test_disabled_opt_in_refused(ctx) -> None:
    r = _post(ctx)  # HB_FORECAST_PROMOTION_ENABLED not set
    assert r.status_code == 503
    assert r.json()["detail"] == "forecast_config_promotion_disabled"
    assert _snapshots(ctx["live"]) == 0


def test_confirm_false_refused(ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PROMOTION_ENABLED, "1")
    r = _post(ctx, confirm=False)
    assert r.status_code == 400
    assert r.json()["detail"] == "forecast_config_promotion_not_confirmed"
    assert _snapshots(ctx["live"]) == 0


def test_not_parity_pass_refused(ctx, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PROMOTION_ENABLED, "1")
    _seed_proposal(ctx["edits_root"], "failp", tmp_path, parity="fail")
    r = _post(ctx, edit_id="failp")
    assert r.status_code == 400
    assert r.json()["detail"] == "forecast_config_promotion_not_eligible"


def test_unknown_edit_id_404(ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PROMOTION_ENABLED, "1")
    r = _post(ctx, edit_id="nope")
    assert r.status_code == 404


def test_viewer_forbidden(ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PROMOTION_ENABLED, "1")
    assert _post(ctx, role="viewer").status_code == 403


# -- happy path (writes the FIXTURE live DB, not the real one) ----------------


def test_promote_writes_fixture_and_is_leak_free(ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_PROMOTION_ENABLED, "1")
    r = _post(ctx)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "promoted"
    assert body["certification"]["decision"] == "certified_match"
    assert body["backup_created"] is True
    assert isinstance(body["promoted_snapshot_id"], str)
    assert find_redaction_leaks(body) == []
    # The fixture live DB gained exactly one snapshot.
    assert _snapshots(ctx["live"]) == 1
    # A redacted promotion block was persisted on the proposal.
    record = json.loads((ctx["edits_root"] / "edit01" / "edit_record.json").read_text(encoding="utf-8"))
    assert record["promotion"]["status"] == "promoted"
    assert record["promotion"]["backup_created"] is True
