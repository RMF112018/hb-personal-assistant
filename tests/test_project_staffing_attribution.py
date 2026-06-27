"""Phase 2b cost_code+category attribution tests (manual rules, review bucket, MAT summary)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from hb_assistant.construction.forecast.staffing import attribution
from hb_assistant.construction.forecast.staffing.repositories import (
    AttributionReviewRepository,
    AttributionRuleRepository,
    StaffingActualsRepository,
    StaffingConfigRepository,
)
from hb_assistant.store.migrator import SQLiteMigrator

_PROJECT = "tropical"


def _db(td: str) -> str:
    path = Path(td) / "attr.db"
    SQLiteMigrator(db_path=str(path)).apply()
    return str(path)


def _seed(db: str, rows: list[dict]) -> None:
    with sqlite3.connect(db) as conn:
        for i, r in enumerate(rows, start=1):
            raw = {
                "cost_code": r["cost_code"], "category": r["category"], "tran_type": "AP cost",
                "accounting_date": f"{r['month']}-15", "accounting_month": r["month"],
                "amount": r["amount"], "description": r.get("description"),
                "application_of_origin": "AP",
                "budget_code_key": f"0000.{r['cost_code']}.{r['category']}",
            }
            conn.execute(
                "INSERT INTO forecast_cost_entries (cost_entry_id, project_key, source_package, "
                "source_row_number, budget_code_key, accounting_month, raw_json, created_utc) "
                "VALUES (?, ?, 'pkg', ?, ?, ?, ?, 't')",
                (f"ce-{i}", _PROJECT, i, raw["budget_code_key"], r["month"], json.dumps(raw)),
            )
        conn.commit()


def _config(db: str) -> str:
    row = StaffingConfigRepository(db_path=db).create(
        {"project_key": _PROJECT, "role_title": "Super", "employment_type": "Full Time",
         "cost_code": "15-01-530", "rate_unit": "weekly", "lab_rate": "2500.00",
         "start_date": "2026-06-01", "finish_date": "2026-12-31"}
    )
    return row["staffing_config_id"]


_ROWS = [
    {"cost_code": "15-01-530", "category": "LAB", "amount": 1000.0, "month": "2026-06",
     "description": "TWN.LABOR.Labor"},
    {"cost_code": "15-01-530", "category": "LAB", "amount": 500.0, "month": "2026-07"},
    {"cost_code": "03-01-025", "category": "MAT", "amount": 300.0, "month": "2026-06"},
    {"cost_code": "03-01-025", "category": "MAT", "amount": 200.0, "month": "2026-07"},
]


def test_unmatched_lab_creates_review_item() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        attribution.rebuild(db, _PROJECT)
        bucket = attribution.list_unmatched_actuals(db, _PROJECT)
        assert len(bucket) == 1
        item = bucket[0]
        assert (item["cost_code"], item["category"]) == ("15-01-530", "LAB")
        assert item["actual_amount"] == "1500.00"
        assert item["actuals_start_month"] == "2026-06"
        assert item["actuals_through_month"] == "2026-07"
        assert "raw_json" not in item
        # MAT never enters the review bucket
        assert all(b["category"] != "MAT" for b in AttributionReviewRepository(db_path=db).list(_PROJECT))


def test_rule_matches_and_clears_review() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        cid = _config(db)
        attribution.rebuild(db, _PROJECT)
        assert len(attribution.list_unmatched_actuals(db, _PROJECT)) == 1
        AttributionRuleRepository(db_path=db).upsert_rule(
            project_key=_PROJECT, cost_code="15-01-530", category="LAB", staffing_config_id=cid
        )
        attribution.refresh_attribution(db, _PROJECT)
        assert attribution.list_unmatched_actuals(db, _PROJECT) == []
        lab = StaffingActualsRepository(db_path=db).list(_PROJECT, category="LAB")
        assert all(a["attribution_status"] == "matched_rule" and a["staffing_config_id"] == cid
                   for a in lab)


def test_mat_summary_by_cost_code_never_attributed() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        attribution.rebuild(db, _PROJECT)
        summary = StaffingActualsRepository(db_path=db).mat_summary(_PROJECT)
        assert len(summary) == 1
        assert summary[0]["cost_code"] == "03-01-025"
        assert summary[0]["category"] == "MAT"
        assert summary[0]["actual_amount"] == "500.00"
        mat = StaffingActualsRepository(db_path=db).list(_PROJECT, category="MAT")
        assert all(a["staffing_config_id"] is None for a in mat)


def test_resolve_review_creates_rule_and_matches() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        _seed(db, _ROWS)
        cid = _config(db)
        attribution.rebuild(db, _PROJECT)
        item = attribution.list_unmatched_actuals(db, _PROJECT)[0]
        attribution.resolve_review_item(
            db, item["review_item_id"], staffing_config_id=cid, resolved_by_role="operator"
        )
        # rule now exists, actuals matched, bucket empty
        assert attribution.list_unmatched_actuals(db, _PROJECT) == []
        rules = AttributionRuleRepository(db_path=db).list(_PROJECT)
        assert len(rules) == 1 and rules[0]["cost_code"] == "15-01-530"
        resolved = AttributionReviewRepository(db_path=db).get(item["review_item_id"])
        assert resolved["review_status"] == "resolved"


def test_rule_active_uniqueness() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = _db(td)
        cid = _config(db)
        repo = AttributionRuleRepository(db_path=db)
        repo.upsert_rule(project_key=_PROJECT, cost_code="15-01-530", category="LAB",
                         staffing_config_id=cid)
        repo.upsert_rule(project_key=_PROJECT, cost_code="15-01-530", category="LAB",
                         staffing_config_id=cid)
        active = repo.list(_PROJECT, active_only=True)
        assert len(active) == 1
        assert len(repo.list(_PROJECT, active_only=False)) == 2  # prior one deactivated
