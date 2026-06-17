from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from construction_financial_review.procore_budget_details_db import parity_report

AMOUNT_FIELDS = (
    "original_budget_amount",
    "revised_budget",
    "projected_budget",
    "committed_costs",
    "direct_costs",
    "erp_direct_costs",
    "actual_cost",
    "job_to_date_costs",
    "projected_costs",
    "erp_job_to_date_costs",
    "forecast_to_complete",
    "estimated_cost_at_completion",
    "projected_over_under",
    "pending_budget_changes",
    "approved_change_orders",
)


def _write_package(root: Path, rows: list[dict]) -> Path:
    package_root = root / "ctx"
    package = package_root / "canonical"
    package.mkdir(parents=True)
    with (package / "budget_codes.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (package_root / "manifest.json").write_text(
        json.dumps({"generated_timestamp_local": "2026-06-14T08:45:10"}, sort_keys=True),
        encoding="utf-8",
    )
    return package_root


def _cfg(data_root: Path, db: Path, *, view_id: str | None = None) -> dict:
    cfg = {
        "default_data_root": str(data_root),
        "forecast_context_package": "ctx",
        "forecast_intelligence": {"db_path": str(db)},
    }
    if view_id is not None:
        cfg["forecast_intelligence"]["budget_view_id"] = view_id
    return cfg


def _create_db(db: Path) -> None:
    conn = sqlite3.connect(db)
    try:
        amount_cols = ", ".join(f"{field} TEXT" for field in AMOUNT_FIELDS)
        conn.execute(
            f"""
            CREATE TABLE procore_ep_budget_detail_rows (
              record_key TEXT PRIMARY KEY,
              raw_payload_id TEXT,
              budget_view_id TEXT,
              row_id TEXT,
              wbs_flat_code TEXT,
              canonical_budget_code_key TEXT,
              cost_code_id TEXT,
              cost_code TEXT,
              cost_type_id TEXT,
              cost_type TEXT,
              {amount_cols},
              payload_hash TEXT,
              source_quality TEXT,
              payload_seen_first_utc TEXT,
              payload_seen_last_utc TEXT,
              project_key TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE procore_ep_budget_detail_row_cells (
              record_key TEXT,
              column_id TEXT,
              column_key TEXT,
              column_name TEXT,
              column_label TEXT,
              field_path TEXT,
              value_text TEXT,
              value_decimal_text TEXT,
              currency_iso_code TEXT
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _insert_row(
    db: Path,
    *,
    key: str,
    view_id: str,
    amounts: dict[str, str | None],
    source_quality: str = "live_full_payload",
) -> None:
    conn = sqlite3.connect(db)
    try:
        values = {field: amounts.get(field) for field in AMOUNT_FIELDS}
        cols = [
            "record_key",
            "raw_payload_id",
            "budget_view_id",
            "row_id",
            "wbs_flat_code",
            "canonical_budget_code_key",
            "cost_code_id",
            "cost_code",
            "cost_type_id",
            "cost_type",
            *AMOUNT_FIELDS,
            "payload_hash",
            "source_quality",
            "payload_seen_first_utc",
            "payload_seen_last_utc",
            "project_key",
        ]
        row = {
            "record_key": f"{view_id}-{key}",
            "raw_payload_id": f"raw-{view_id}-{key}",
            "budget_view_id": view_id,
            "row_id": f"row-{key}",
            "wbs_flat_code": key,
            "canonical_budget_code_key": key,
            "cost_code_id": "cc",
            "cost_code": "code",
            "cost_type_id": "ct",
            "cost_type": "MAT",
            **values,
            "payload_hash": f"hash-{view_id}-{key}",
            "source_quality": source_quality,
            "payload_seen_first_utc": "2026-06-17T00:00:00+00:00",
            "payload_seen_last_utc": "2026-06-17T00:00:00+00:00",
            "project_key": "tropical",
        }
        conn.execute(
            f"INSERT INTO procore_ep_budget_detail_rows ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
            tuple(row[col] for col in cols),
        )
        conn.commit()
    finally:
        conn.close()


def _package_row(key: str, amounts: dict[str, str | None]) -> dict:
    return {"budget_code_key": key, "amounts": amounts}


def test_decimal_equivalent_amounts_do_not_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    _write_package(
        tmp_path,
        [
            _package_row("1000.15-01-426.MAT", {"revised_budget": "0.0"}),
            _package_row("1000.15-01-427.MAT", {"revised_budget": "60000"}),
        ],
    )
    _insert_row(db, key="1000.15-01-426.MAT", view_id="5885", amounts={"revised_budget": "0.00"})
    _insert_row(db, key="1000.15-01-427.MAT", view_id="5885", amounts={"revised_budget": "60000.00"})

    report = parity_report(_cfg(tmp_path, db, view_id="5885"), project_key="tropical", db_path=db)

    assert report["amount_mismatch_count"] == 0
    assert report["selected_view_mismatch_class_counts"]["decimal_format_only"] == 2
    assert report["mismatch_class_counts_all_candidate_views"]["decimal_format_only"] == 2
    assert report["amount_mismatch_count_reconciles"] is True
    assert report["strict_ok"] is True


def test_missing_blank_values_are_not_coerced_to_zero(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    _write_package(tmp_path, [_package_row("1000.15-01-426.MAT", {"revised_budget": "0.00"})])
    _insert_row(db, key="1000.15-01-426.MAT", view_id="5885", amounts={"revised_budget": ""})

    report = parity_report(_cfg(tmp_path, db, view_id="5885"), project_key="tropical", db_path=db)

    assert report["amount_mismatch_count"] == 1
    assert report["selected_view_mismatch_class_counts"]["missing_vs_zero"] == 1
    assert report["strict_ok"] is False


def test_best_match_budget_view_diagnostics_and_body_free_output(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    _write_package(
        tmp_path,
        [
            _package_row("1000.15-01-426.MAT", {"revised_budget": "60000.00"}),
            _package_row("1000.15-01-427.MAT", {"revised_budget": "1.00"}),
        ],
    )
    _insert_row(db, key="1000.15-01-426.MAT", view_id="100", amounts={"revised_budget": "60000"})
    _insert_row(db, key="1000.15-01-427.MAT", view_id="100", amounts={"revised_budget": "2.00"})
    _insert_row(db, key="1000.15-01-426.MAT", view_id="200", amounts={"revised_budget": "60000.0"})
    _insert_row(db, key="1000.15-01-427.MAT", view_id="200", amounts={"revised_budget": "1.0"})

    report = parity_report(_cfg(tmp_path, db), project_key="tropical", db_path=db)
    encoded = json.dumps(report)

    assert report["budget_view_selection_mode"] == "best_match_no_configured_view"
    assert report["candidate_budget_view_ids"] == ["100", "200"]
    assert report["mismatch_count_by_budget_view_id"] == {"100": 1, "200": 0}
    assert report["best_match_budget_view_id"] == "200"
    assert report["recommended_configured_budget_view_id"] == "200"
    assert report["recommended_configured_budget_view_ids"] == []
    assert report["coverage_by_budget_view_id"]["200"]["matched_code_count"] == 2
    assert report["amount_mismatches"] == []
    assert "payload_json" not in encoded
    assert "value_text" not in encoded
    assert "60000" not in encoded


def test_strict_fails_on_tied_best_match_without_configured_view(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    _write_package(tmp_path, [_package_row("1000.15-01-426.MAT", {"revised_budget": "10.00"})])
    _insert_row(db, key="1000.15-01-426.MAT", view_id="100", amounts={"revised_budget": "10"})
    _insert_row(db, key="1000.15-01-426.MAT", view_id="200", amounts={"revised_budget": "10.0"})

    report = parity_report(_cfg(tmp_path, db), project_key="tropical", db_path=db)

    assert report["budget_view_selection_mode"] == "ambiguous_best_match_no_configured_view"
    assert report["best_match_tied_budget_view_ids"] == ["100", "200"]
    assert report["recommended_configured_budget_view_id"] is None
    assert report["recommended_configured_budget_view_ids"] == ["100", "200"]
    assert report["selected_view_mismatch_class_counts"]["view_selection_difference"] == 1
    assert report["strict_ok"] is False


def test_strict_fails_on_nonzero_normalized_mismatch(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    _write_package(tmp_path, [_package_row("1000.15-01-426.MAT", {"revised_budget": "10.00"})])
    _insert_row(db, key="1000.15-01-426.MAT", view_id="5885", amounts={"revised_budget": "11.00"})

    report = parity_report(_cfg(tmp_path, db, view_id="5885"), project_key="tropical", db_path=db)

    assert report["amount_mismatch_count"] == 1
    assert report["selected_view_mismatch_class_counts"]["value_difference"] == 1
    assert report["strict_ok"] is False


def test_temporal_lineage_warning_is_advisory(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    _write_package(tmp_path, [_package_row("1000.15-01-426.MAT", {"revised_budget": "10.00"})])
    _insert_row(db, key="1000.15-01-426.MAT", view_id="5885", amounts={"revised_budget": "11.00"})

    report = parity_report(_cfg(tmp_path, db, view_id="5885"), project_key="tropical", db_path=db)

    assert report["package_generated_at"] == "2026-06-14T08:45:10"
    assert report["package_generated_at_source"] == "manifest.generated_timestamp_local"
    assert report["db_payload_seen_last_utc_max"] == "2026-06-17T00:00:00+00:00"
    assert report["temporal_lineage_warning"] is True
    assert report["temporal_lineage_classification"] == "package_older_than_live_db"
    assert report["potentially_temporal_value_difference_count"] == 1
    assert report["strict_ok"] is False


def test_configured_authoritative_view_is_selected_and_target_diagnostics_emit(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    _create_db(db)
    package_amounts = {
        "revised_budget": "10.00",
        "projected_budget": "10.00",
        "committed_costs": "1.00",
        "direct_costs": "2.00",
        "erp_direct_costs": "3.00",
        "erp_job_to_date_costs": "4.00",
        "job_to_date_costs": "5.00",
        "projected_costs": "6.00",
        "forecast_to_complete": "7.00",
        "estimated_cost_at_completion": "8.00",
    }
    _write_package(tmp_path, [_package_row("1000.15-01-426.MAT", package_amounts)])
    _insert_row(db, key="1000.15-01-426.MAT", view_id="100", amounts={"revised_budget": "99.00"})
    _insert_row(
        db,
        key="1000.15-01-426.MAT",
        view_id="200",
        amounts={
            "revised_budget": "10",
            "projected_budget": "10",
            "committed_costs": "1",
            "direct_costs": "2",
            "erp_direct_costs": "3",
            "erp_job_to_date_costs": "4",
            "job_to_date_costs": "5",
            "projected_costs": "6",
            "forecast_to_complete": "7",
            "estimated_cost_at_completion": "8",
        },
    )

    cfg = _cfg(tmp_path, db, view_id="200")
    before = json.dumps(cfg, sort_keys=True)
    report = parity_report(cfg, project_key="tropical", db_path=db)

    assert json.dumps(cfg, sort_keys=True) == before
    assert report["budget_view_selection_mode"] == "configured_budget_view"
    assert report["selected_budget_view_id"] == "200"
    assert report["selected_view_mismatch_class_counts"]["decimal_format_only"] == 10
    assert report["amount_mismatch_count_included_classes"] == [
        "missing_vs_zero",
        "value_difference",
        "field_missing_in_db",
        "field_missing_in_package",
    ]
    assert report["amount_mismatch_count_excluded_classes"] == [
        "decimal_format_only",
        "view_selection_difference",
    ]
    assert report["amount_mismatch_count_reconciles"] is True
    assert report["strict_ok"] is True
    assert report["target_code_selected_view_queryable"] is True
    assert all(report["target_code_selected_view_amount_presence"].values())
