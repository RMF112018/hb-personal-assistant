"""Service tests for the read-only forecast configuration viewer (Implementation Phase 2).

Builds a migrated temp DB and seeds a synthetic v60 config snapshot, then covers the happy
path plus the adversarial cases: fail-closed (missing DB / schema < 60 / tables absent),
project-domain redaction, dual-source owner-SOV, Decimal preservation, malformed raw_json,
and unknown snapshot/item.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from hb_assistant.construction.analytics.forecast_config_catalog import (
    ForecastConfigCatalogService,
    ForecastConfigError,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks
from hb_assistant.store.migrator import SQLiteMigrator

SNAP = "c3b4a67d22db47c74e696ae562fbf1c555e365fc66bb003a7b3312754415b698"

# A project item whose raw_json carries every dev-internal landmine the viewer must redact.
PROJECT_RAW = {
    "project_key": "tropical",
    "project_name": "Tropical World Nursery Senior Living Facility",
    "job_reference": "23-435-01",
    "forecast_period": "2026-June",
    "materiality_absolute": "25000.00",
    "materiality_percent": "0.10",
    "budget_amount_field": "budget_amounts.revised_budget",
    "current_projected_cost_field": "budget_amounts.projected_costs",
    "budget_details": {"budget_view_id": "713474"},
    # --- must NOT reach the UI ---
    "default_data_root": "/Users/bobbyfetting/Library/CloudStorage/SynologyDrive/Work/NAS/2026-June",
    "forecast_context_package": "forecast_context_package_tropical_20260614_084510",
    "owner_sov_scope_crosswalk": "config/crosswalks/tropical/owner_sov_scope_crosswalk_final.jsonl",
    "schedule_package": "project_schedule_json_package",
    "llm": {"model": "qwen2.5:14b", "endpoint": "http://localhost:11434"},
}

CONTROL_RAW = {
    "project_key": "tropical",
    "control_id": "tropical-10-01-340-stop-2026-06",
    "cost_code": "10-01-340",
    "description": "SCHEDULING",
    "control_type": "forecast_stop_date",
    "forecast_stop_date": "2031-11-01",
    "post_stop_monthly_forecast": "0.00",
    "accepted_final_cost": "123456.78",
    "acceptance_status": "accepted",
    "accepted_by": "Bobby Fetting",
}

OWNER_RAW = {
    "crosswalk_id": "TROPICAL-OWNER-SOV-0001",
    "project_key": "tropical",
    "owner_sov_code": "10-XX-XXX",
    "scope_relationship": "one_to_many",
    "approved_by": "Bobby Fetting",
}


def _seed(db: Path) -> None:
    SQLiteMigrator(db_path=str(db)).apply()
    conn = sqlite3.connect(str(db))
    try:
        # sources: one each for project/controls, TWO for owner_sov (jsonl + csv duplicate)
        sources = [
            ("src-project", "project", "tropical", "config/projects/tropical.json", "json"),
            ("src-controls", "forecast_controls", "tropical", "config/forecast_controls/x.jsonl", "jsonl"),
            ("src-owner-jsonl", "owner_sov_crosswalk", "tropical", "config/crosswalks/x.jsonl", "jsonl"),
            ("src-owner-csv", "owner_sov_crosswalk", "tropical", "config/crosswalks/x.csv", "csv"),
        ]
        for i, (sid, domain, proj, path, fmt) in enumerate(sources):
            conn.execute(
                "INSERT INTO forecast_config_sources (config_source_id, project_key, config_domain, "
                "config_name, source_path, source_format, source_sha256, content_sha256, row_count, "
                "imported_at_utc, import_run_id, is_active, created_utc, updated_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sid, proj, domain, domain, path, fmt, f"s{i}", f"c{i}", 1,
                 "2026-06-19T08:00:00+00:00", "run-1", 1, "2026-06-19T08:00:00+00:00",
                 "2026-06-19T08:00:00+00:00"),
            )
        items = [
            ("it-project", "project", "project", PROJECT_RAW, 0),
            ("it-ctrl-1", "forecast_controls", "forecast_controls", CONTROL_RAW, 0),
            ("it-ctrl-2", "forecast_controls", "forecast_controls", {**CONTROL_RAW, "control_id": "c2"}, 1),
            ("it-owner-1", "owner_sov_crosswalk", "owner_sov_crosswalk", OWNER_RAW, 0),
            ("it-owner-2", "owner_sov_crosswalk", "owner_sov_crosswalk", {**OWNER_RAW, "crosswalk_id": "o2"}, 1),
        ]
        conn.execute(
            "INSERT INTO forecast_config_snapshots (config_snapshot_id, project_key, snapshot_name, "
            "snapshot_created_utc, snapshot_reason, source_mode, item_count, snapshot_sha256, created_by, "
            "created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (SNAP, "tropical", "tropical-phase16-live-config", "2026-06-19T08:54:42+00:00",
             "Phase 16 live import", "db_current", len(items), "snap-sha", None,
             "2026-06-19T08:54:42+00:00"),
        )
        for iid, domain, name, raw, order in items:
            conn.execute(
                "INSERT INTO forecast_config_snapshot_items (config_snapshot_id, config_item_id, "
                "project_key, config_domain, config_name, item_key, item_order, raw_json, "
                "canonical_json_sha256) VALUES (?,?,?,?,?,?,?,?,?)",
                (SNAP, iid, "tropical", domain, name, iid, order, json.dumps(raw), f"h-{iid}"),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_db(tmp_path: Path) -> str:
    db = tmp_path / "config.sqlite"
    _seed(db)
    return str(db)


# -- happy path ---------------------------------------------------------------


def test_list_snapshots_and_read_snapshot(seeded_db: str) -> None:
    svc = ForecastConfigCatalogService(db_path=seeded_db)
    snaps = svc.list_snapshots()
    assert snaps["guardrails"]["read_only"] is True
    assert snaps["guardrails"]["no_db_write"] is True
    assert snaps["snapshots"][0]["snapshot_id"] == SNAP
    assert snaps["snapshots"][0]["created_display"] == "Jun 19, 2026"

    snap = svc.read_snapshot(SNAP)
    counts = {d["domain"]: d for d in snap["domains"]}
    assert counts["project"]["item_count"] == 1
    assert counts["forecast_controls"]["item_count"] == 2
    assert counts["owner_sov_crosswalk"]["item_count"] == 2
    # dual-source owner-SOV (jsonl + csv) surfaces as source_count 2
    assert counts["owner_sov_crosswalk"]["source_count"] == 2
    assert counts["project"]["display_label"] == "Project settings"


def test_read_domain_controls_business_fields(seeded_db: str) -> None:
    svc = ForecastConfigCatalogService(db_path=seeded_db)
    dom = svc.read_domain(SNAP, "forecast_controls")
    assert dom["item_count"] == 2
    fields = dom["items"][0]["fields"]
    assert fields["cost_code"] == "10-01-340"
    assert fields["accepted_final_cost"] == "123456.78"  # Decimal string preserved
    assert find_redaction_leaks(dom) == []


def test_read_item(seeded_db: str) -> None:
    svc = ForecastConfigCatalogService(db_path=seeded_db)
    item = svc.read_item(SNAP, "it-owner-1")
    assert item["domain"] == "owner_sov_crosswalk"
    assert item["fields"]["owner_sov_code"] == "10-XX-XXX"


# -- correction-style adversarial cases ---------------------------------------


def test_project_domain_whitelist_and_redaction(seeded_db: str) -> None:
    svc = ForecastConfigCatalogService(db_path=seeded_db)
    dom = svc.read_domain(SNAP, "project")
    fields = dom["items"][0]["fields"]
    # only whitelisted business keys survive
    assert set(fields) == {
        "project_name", "job_reference", "forecast_period",
        "materiality_absolute", "materiality_percent",
        "budget_amount_field", "current_projected_cost_field", "budget_view_id",
    }
    blob = json.dumps(dom)
    assert "default_data_root" not in blob
    assert "/Users/" not in blob
    assert "localhost" not in blob
    assert "20260614_084510" not in blob
    assert "config/crosswalks" not in blob
    assert find_redaction_leaks(dom) == []


def test_no_leaks_across_all_payloads(seeded_db: str) -> None:
    svc = ForecastConfigCatalogService(db_path=seeded_db)
    payloads = [
        svc.list_snapshots(),
        svc.read_snapshot(SNAP),
        svc.read_domain(SNAP, "project"),
        svc.read_domain(SNAP, "forecast_controls"),
        svc.read_domain(SNAP, "owner_sov_crosswalk"),
        svc.read_item(SNAP, "it-project"),
    ]
    for p in payloads:
        assert find_redaction_leaks(p) == [], f"leak: {find_redaction_leaks(p)}"


def test_missing_db_fails_closed(tmp_path: Path) -> None:
    svc = ForecastConfigCatalogService(db_path=str(tmp_path / "nope.sqlite"))
    with pytest.raises(ForecastConfigError):
        svc.list_snapshots()


def test_schema_below_60_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "old.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE schema_migrations (version INTEGER, name TEXT, applied_utc TEXT)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (59)")
    conn.commit()
    conn.close()
    with pytest.raises(ForecastConfigError):
        ForecastConfigCatalogService(db_path=str(db)).list_snapshots()


def test_tables_absent_fails_closed(tmp_path: Path) -> None:
    db = tmp_path / "v60-no-tables.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE schema_migrations (version INTEGER, name TEXT, applied_utc TEXT)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (60)")
    conn.commit()
    conn.close()
    with pytest.raises(ForecastConfigError):
        ForecastConfigCatalogService(db_path=str(db)).list_snapshots()


def test_unknown_snapshot_and_item(seeded_db: str) -> None:
    svc = ForecastConfigCatalogService(db_path=seeded_db)
    with pytest.raises(ForecastConfigError, match="unknown snapshot_id"):
        svc.read_snapshot("does-not-exist")
    with pytest.raises(ForecastConfigError, match="unknown item_id"):
        svc.read_item(SNAP, "no-such-item")


def test_malformed_raw_json_does_not_crash(tmp_path: Path) -> None:
    db = tmp_path / "bad.sqlite"
    _seed(db)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO forecast_config_snapshot_items (config_snapshot_id, config_item_id, project_key, "
        "config_domain, config_name, item_key, item_order, raw_json, canonical_json_sha256) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (SNAP, "it-bad", "tropical", "forecast_controls", "forecast_controls", "bad", 9,
         "{not valid json", "h-bad"),
    )
    conn.commit()
    conn.close()
    svc = ForecastConfigCatalogService(db_path=str(db))
    dom = svc.read_domain(SNAP, "forecast_controls")
    bad = [i for i in dom["items"] if i["item_id"] == "it-bad"][0]
    assert bad["fields"] == {}  # unparseable -> empty, no crash
