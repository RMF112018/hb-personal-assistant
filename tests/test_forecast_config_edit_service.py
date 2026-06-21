"""Service tests for forecast config editing — isolated proposals (Implementation Phase E).

Builds a non-live config-registry DB fixture (via the CFR import+snapshot pipeline), points the
service's live source DB at it (opened mode=ro), and proves: per-domain edits round-trip with a
passing parity proof and a redaction-clean report; the project whitelist-merge preserves but never
exposes dev-internals; forecast_controls is rejected; Decimal money is enforced; fail-closed when the
config-edit root is unset or under the data root; and the live DB / live data root are never written.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

# Make the CFR subrepo importable for the fixture builder (mirrors the service's injection).
_CFR_SRC = Path(__file__).resolve().parents[1] / "subrepos" / "construction-financial-review" / "src"
if str(_CFR_SRC) not in sys.path:
    sys.path.insert(0, str(_CFR_SRC))

from hb_assistant.construction.analytics import forecast_config_edit_dto as dto  # noqa: E402
from hb_assistant.construction.analytics.forecast_config_edit_service import (  # noqa: E402
    ForecastConfigEditError,
    ForecastConfigEditService,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks  # noqa: E402

ENV_DATA_ROOT = "HB_FORECAST_DATA_ROOT"
# A dev-internal that must be PRESERVED on disk but NEVER surfaced in any payload.
_SECRET_DATA_ROOT = "/Users/secret/internal/forecast/data"


def _build_sample_tree(root: Path) -> None:
    cfg = root / "config"
    (cfg / "projects").mkdir(parents=True)
    (cfg / "forecast_model_controls" / "tropical").mkdir(parents=True)
    (cfg / "forecast_staffing" / "tropical").mkdir(parents=True)
    project = {
        "project_key": "tropical",
        "project_name": "TWN",
        "job_reference": "2023-TWN",
        "forecast_period": "2026-June",
        "materiality_absolute": "25000.00",
        "materiality_percent": "10",
        "budget_amount_field": "revised_budget",
        "current_projected_cost_field": "projected_cost",
        "budget_details": {"budget_view_id": "bv1"},
        # Dev-internals (must round-trip on disk, never appear in any payload):
        "default_data_root": _SECRET_DATA_ROOT,
        "llm": {"endpoint": "http://localhost:11434"},
        "owner_sov_scope_crosswalk": "config/owner_sov.jsonl",
    }
    (cfg / "projects" / "tropical.json").write_text(json.dumps(project), encoding="utf-8")
    (cfg / "forecast_model_controls" / "tropical" / "code_forecast_model_controls.jsonl").write_text(
        json.dumps({"project_key": "tropical", "control_id": "C-001", "explicit_value_amount": "1000.00"})
        + "\n",
        encoding="utf-8",
    )
    (cfg / "forecast_staffing" / "tropical" / "staffing_budget_code_mapping.jsonl").write_text(
        json.dumps(
            {"project_key": "tropical", "source_cost_code": "01-100", "target_budget_code_key": "01-100.LAB", "allocation_share": "0.50"}
        )
        + "\n",
        encoding="utf-8",
    )
    (cfg / "owner_sov.jsonl").write_text(
        json.dumps({"crosswalk_id": "XW-1", "owner_sov_code": "100", "scope_relationship": "1:1"}) + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def live_db_and_snapshot(tmp_path: Path):
    """Return (db_path, snapshot_id) for a non-live fixture built via the CFR pipeline."""
    from construction_financial_review.config_registry import (
        create_forecast_config_snapshot,
        import_forecast_config_to_db,
    )

    sample = tmp_path / "sample"
    _build_sample_tree(sample)
    db = tmp_path / "fixture.sqlite"
    import_forecast_config_to_db(config_root=sample, db_path=db, project_key="tropical")
    snap = create_forecast_config_snapshot(
        db_path=db, project_key="tropical", snapshot_name="base", snapshot_reason="fixture"
    )
    return db, snap["config_snapshot_id"]


@pytest.fixture
def service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, live_db_and_snapshot):
    db, _ = live_db_and_snapshot
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data_root))  # config-edit root must be OUTSIDE this
    edit_root = tmp_path / "config_edits"  # sibling of data_root
    return ForecastConfigEditService(config_edit_root=str(edit_root), db_path=str(db))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# -- parity-fail rendering (path-free even when CFR reports differences) -------


def test_summarize_parity_fail_is_path_free() -> None:
    # CFR differences embed absolute materialized paths; the summary must never carry them.
    parity = {
        "status": "fail",
        "domains": {
            "project": {"match": True, "file_count": 1, "db_count": 1},
            "owner_sov_crosswalk": {"match": False, "file_count": 2, "db_count": 1},
        },
        "differences": ["materialized file missing (/Users/x/materialized_config/config/owner_sov.csv)"],
    }
    summary = dto.summarize_parity(parity)
    assert summary["status"] == "fail"
    assert summary["differing_domains"] == ["owner_sov_crosswalk"]
    assert find_redaction_leaks(summary) == []


# -- happy paths --------------------------------------------------------------


def test_project_edit_parity_pass_and_leak_free(service, live_db_and_snapshot) -> None:
    db, snap = live_db_and_snapshot
    before = _sha(db)
    result = service.propose_config_edit(
        snap, [{"domain": "project", "op": "modify", "item_key": "tropical", "fields": {"materiality_absolute": "30000.00"}}]
    )
    assert result["status"] == "succeeded"
    assert result["parity"]["status"] == "pass"
    assert find_redaction_leaks(result) == []
    assert _sha(db) == before  # live DB untouched (mode=ro)
    changed = result["changed_items"]
    assert changed[0]["domain"] == "project"
    assert changed[0]["values"] == {"materiality_absolute": "30000.00"}


def test_project_whitelist_preserves_but_hides_dev_internals(service, live_db_and_snapshot, tmp_path: Path) -> None:
    db, snap = live_db_and_snapshot
    result = service.propose_config_edit(
        snap, [{"domain": "project", "op": "modify", "item_key": "tropical", "fields": {"project_name": "TWN-Renamed"}}]
    )
    assert find_redaction_leaks(result) == []  # no dev-internal path/endpoint leaks
    # On disk, the edited project JSON STILL contains the preserved dev-internals.
    edited = next((tmp_path / "config_edits" / "edits").glob("*/edited_config/config/projects/tropical.json"))
    on_disk = json.loads(edited.read_text(encoding="utf-8"))
    assert on_disk["default_data_root"] == _SECRET_DATA_ROOT
    assert on_disk["llm"]["endpoint"] == "http://localhost:11434"
    assert on_disk["project_name"] == "TWN-Renamed"


def test_model_controls_and_staffing_and_crosswalk_edits(service, live_db_and_snapshot) -> None:
    db, snap = live_db_and_snapshot
    edits = [
        {"domain": "forecast_model_controls", "op": "modify", "item_key": "C-001", "fields": {"explicit_value_amount": "2000.00"}},
        {"domain": "forecast_staffing", "op": "modify", "item_key": "01-100|01-100.LAB", "fields": {"allocation_share": "0.75"}},
        {"domain": "owner_sov_crosswalk", "op": "modify", "item_key": "XW-1", "fields": {"scope_relationship": "1:many"}},
    ]
    result = service.propose_config_edit(snap, edits)
    assert result["status"] == "succeeded"
    assert result["parity"]["status"] == "pass"
    assert find_redaction_leaks(result) == []
    assert {c["domain"] for c in result["changed_items"]} == {
        "forecast_model_controls",
        "forecast_staffing",
        "owner_sov_crosswalk",
    }


# -- rejections / fail-closed -------------------------------------------------


def test_forecast_controls_rejected(service, live_db_and_snapshot) -> None:
    _, snap = live_db_and_snapshot
    with pytest.raises(ForecastConfigEditError, match="deprecated"):
        service.propose_config_edit(
            snap, [{"domain": "forecast_controls", "item_key": "x", "fields": {"a": "1"}}]
        )


def test_float_money_rejected(service, live_db_and_snapshot) -> None:
    _, snap = live_db_and_snapshot
    with pytest.raises(ForecastConfigEditError):
        service.propose_config_edit(
            snap, [{"domain": "project", "item_key": "tropical", "fields": {"materiality_absolute": 30000.0}}]
        )


def test_non_whitelisted_project_field_rejected(service, live_db_and_snapshot) -> None:
    _, snap = live_db_and_snapshot
    with pytest.raises(ForecastConfigEditError, match="not editable"):
        service.propose_config_edit(
            snap, [{"domain": "project", "item_key": "tropical", "fields": {"default_data_root": "/x"}}]
        )


def test_unknown_snapshot_rejected(service) -> None:
    with pytest.raises(ForecastConfigEditError, match="unknown snapshot_id"):
        service.propose_config_edit(
            "nope", [{"domain": "project", "item_key": "tropical", "fields": {"project_name": "X"}}]
        )


def test_config_edit_root_unset_fails_closed(live_db_and_snapshot, monkeypatch: pytest.MonkeyPatch) -> None:
    db, snap = live_db_and_snapshot
    monkeypatch.delenv("HB_FORECAST_CONFIG_EDIT_ROOT", raising=False)
    svc = ForecastConfigEditService(config_edit_root=None, db_path=str(db))
    with pytest.raises(ForecastConfigEditError, match="not configured"):
        svc.propose_config_edit(snap, [{"domain": "project", "item_key": "tropical", "fields": {"project_name": "X"}}])


def test_config_edit_root_under_data_root_refused(live_db_and_snapshot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db, snap = live_db_and_snapshot
    data_root = tmp_path / "data"
    data_root.mkdir()
    monkeypatch.setenv(ENV_DATA_ROOT, str(data_root))
    svc = ForecastConfigEditService(config_edit_root=str(data_root / "edits"), db_path=str(db))
    with pytest.raises(ForecastConfigEditError, match="must not be under the live data root"):
        svc.propose_config_edit(snap, [{"domain": "project", "item_key": "tropical", "fields": {"project_name": "X"}}])


# -- list / read --------------------------------------------------------------


def test_list_and_read_round_trip(service, live_db_and_snapshot) -> None:
    _, snap = live_db_and_snapshot
    created = service.propose_config_edit(
        snap, [{"domain": "project", "item_key": "tropical", "fields": {"project_name": "X"}}]
    )
    edit_id = created["edit_id"]
    listing = service.list_edits()
    assert find_redaction_leaks(listing) == []
    assert any(e["edit_id"] == edit_id for e in listing["edits"])
    detail = service.read_edit(edit_id)
    assert detail["edit_id"] == edit_id
    assert find_redaction_leaks(detail) == []
    with pytest.raises(ForecastConfigEditError, match="unknown edit_id"):
        service.read_edit("deadbeef")
