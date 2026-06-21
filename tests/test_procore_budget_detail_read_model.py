import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.procore import app
from hb_assistant.procore.budget_detail_read_model import (
    project_budget_detail_read_model,
    target_code_summary,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _raw_payload_id(endpoint: str, record_id: str, parent_id: str | None = None) -> str:
    return f"raw-{endpoint}-{parent_id or 'none'}-{record_id}"


def _insert_raw(
    conn: sqlite3.Connection,
    *,
    endpoint: str,
    record_id: str,
    payload: dict,
    project_key: str = "tropical",
    parent_id: str | None = "5885",
    source_quality: str = "live_full_payload",
    company_id: str | None = "5280",
) -> str:
    raw_id = _raw_payload_id(endpoint, record_id, parent_id)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload_hash = f"hash-{endpoint}-{record_id}"
    conn.execute(
        """
        INSERT INTO procore_endpoint_raw_payloads (
          raw_payload_id, capture_run_id, endpoint_key, endpoint_family, endpoint_version,
          company_id, company_id_hash, project_id, project_id_hash, project_key, record_type, record_id, record_id_hash,
          parent_record_id, parent_record_id_hash, source_ref_hash, request_fingerprint_hash,
          payload_hash, payload_json, payload_size_bytes, payload_captured_at_utc,
          payload_seen_first_utc, payload_seen_last_utc, is_current, redaction_status,
          security_scrub_status, source_quality, raw_procore_payload_persisted,
          external_writeback_performed
        ) VALUES (?, 'run', ?, 'budget', 'live_v1', ?, ?, '2525840', 'pidhash', ?, ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?, '2026-06-17T00:00:00+00:00',
                  '2026-06-17T00:00:00+00:00', '2026-06-17T00:00:00+00:00', 1,
                  ?, ?, ?, ?, 0)
        """,
        (
            raw_id,
            endpoint,
            company_id,
            f"company-hash-{company_id}" if company_id else None,
            project_key,
            endpoint,
            record_id,
            f"rid-{record_id}",
            parent_id,
            f"pid-{parent_id}" if parent_id else None,
            f"source-{endpoint}-{record_id}",
            f"request-{endpoint}-{parent_id}",
            payload_hash,
            payload_json,
            len(payload_json),
            "full_business_payload"
            if source_quality == "live_full_payload"
            else "redacted_legacy_projection",
            "transport_secrets_removed"
            if source_quality == "live_full_payload"
            else "scrubbed",
            source_quality,
            1 if source_quality == "live_full_payload" else 0,
        ),
    )
    return raw_id


def test_v55_budget_detail_tables_and_guards(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    version = SQLiteMigrator(str(db)).apply()
    assert version == LATEST_SCHEMA_VERSION
    conn = sqlite3.connect(db)
    try:
        for table in (
            "procore_ep_budget_detail_rows",
            "procore_ep_budget_detail_row_cells",
            "procore_ep_budget_detail_columns",
        ):
            cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            assert "external_writeback_performed" in cols
            assert "raw_payload_emitted_to_evidence" in cols
            if table == "procore_ep_budget_detail_rows":
                assert "erp_direct_costs" in cols
                assert "job_to_date_costs" in cols
                assert "category" in cols
                assert "category_id" in cols
                assert "category_id_hash" in cols
            indexes = {row[1] for row in conn.execute(f"PRAGMA index_list({table})")}
            assert indexes
    finally:
        conn.close()


def test_projector_extracts_rows_cells_and_target_idempotently(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    conn = sqlite3.connect(db)
    try:
        _insert_raw(
            conn,
            endpoint="budget-detail-columns",
            record_id="c-projected",
            payload={"id": "c-projected", "name": "projected_costs", "label": "Projected Costs"},
        )
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r1",
            payload={
                "id": "r1",
                "wbs_code": {"id": 1, "flat_code": "1000.15-01-426.MAT"},
                "cost_code": {"id": 2, "code": "15-01-426"},
                "cost_type": {"id": 3, "abbreviation": "MAT"},
                "original_budget_amount": "10.00",
                "revised_budget": "11.00",
                "projected_budget": "12.00",
                "projected_costs": "13.00",
                "erp_job_to_date_costs": "4.00",
                "custom_dynamic_column": "custom-value",
            },
        )
        conn.commit()
    finally:
        conn.close()

    first = project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    second = project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    assert first["structured_budget_detail_row_rows_inserted_or_updated"] == 1
    assert second["structured_budget_detail_row_rows_inserted_or_updated"] == 1

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM procore_ep_budget_detail_rows").fetchone()[0] == 1
        cell_count = conn.execute("SELECT COUNT(*) FROM procore_ep_budget_detail_row_cells").fetchone()[0]
        assert cell_count > 1
    finally:
        conn.close()

    summary = target_code_summary(db_path=db, project_key="tropical")
    assert summary["queryable"] is True
    assert summary["amount_field_presence"]["projected_costs"] == 1
    assert summary["raw_payload_body_emitted"] is False


def test_projector_preserves_category_without_cost_type_compatibility_mapping(
    tmp_path: Path,
) -> None:
    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    conn = sqlite3.connect(db)
    try:
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r-category",
            payload={
                "id": "r-category",
                "wbs_code": {"flat_code": "1000.15-01-426.MAT"},
                "category": "Materials",
                "category_id": "MAT",
                "direct_costs": "123.45",
                "job_to_date_costs": "234.56",
                "erp_job_to_date_costs": "345.67",
                "erp_direct_costs": "456.78",
            },
        )
        conn.commit()
    finally:
        conn.close()

    project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT company_id, company_id_hash, category, category_id, category_id_hash,
                   cost_type, cost_type_id, actual_cost, line_item_type_id
            FROM procore_ep_budget_detail_rows
            """
        ).fetchone()
    finally:
        conn.close()
    assert row["company_id"] == "5280"
    assert row["company_id_hash"]
    assert row["category"] == "Materials"
    assert row["category_id"] == "MAT"
    assert row["category_id_hash"]
    assert row["cost_type"] is None
    assert row["cost_type_id"] is None
    assert row["actual_cost"] is None
    assert row["line_item_type_id"] is None


def test_projector_category_fallback_requires_exact_cell_identity(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    conn = sqlite3.connect(db)
    try:
        for record_id, name, label in (
            ("col-category", "category_cell", "Category"),
            ("col-category-id", "category_id_cell", "Category ID"),
            ("col-not-category", "category_description_cell", "Category Description"),
        ):
            _insert_raw(
                conn,
                endpoint="budget-detail-columns",
                record_id=record_id,
                payload={"id": record_id, "name": name, "label": label},
            )
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r-category-fallback",
            payload={
                "id": "r-category-fallback",
                "wbs_code": {"flat_code": "1000.15-01-426.MAT"},
                "category_cell": "Materials",
                "category_id_cell": "MAT",
                "category_description_cell": "Must not win",
            },
        )
        conn.commit()
    finally:
        conn.close()

    project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT category, category_id, cost_type, cost_type_id FROM procore_ep_budget_detail_rows"
        ).fetchone()
    finally:
        conn.close()
    assert row["category"] == "Materials"
    assert row["category_id"] == "MAT"
    assert row["cost_type"] is None
    assert row["cost_type_id"] is None


def test_projector_promotes_numeric_dynamic_cells_to_wide_amounts(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    dynamic_columns = {
        "revised_cell": ("Revised Budget", "60000.00"),
        "projected_budget_cell": ("Projected Budget", "60000.00"),
        "committed_cell": ("Committed Costs", "25000.00"),
        "direct_cell": ("Direct Costs", "1000.50"),
        "erp_direct_cell": ("ERP Direct Costs", "27778.50"),
        "erp_jtd_cell": ("ERP JTD Costs", "27778.50"),
        "jtd_cell": ("JTD Costs", "27778.50"),
        "projected_costs_cell": ("Projected Costs", "52778.50"),
        "ctc_cell": ("Cost to Complete", "32221.50"),
        "eac_cell": ("Estimated Cost at Completion", "60000.00"),
        "pou_cell": ("Projected Over/Under", "0.00"),
        "pending_cell": ("Pending Budget Changes", "5.00"),
        "approved_cell": ("Approved Change Orders", "7.00"),
    }
    conn = sqlite3.connect(db)
    try:
        for name, (label, _value) in dynamic_columns.items():
            _insert_raw(
                conn,
                endpoint="budget-detail-columns",
                record_id=f"col-{name}",
                payload={"id": f"col-{name}", "name": name, "label": label},
            )
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r-dynamic",
            payload={
                "id": "r-dynamic",
                "wbs_code": {"id": 1, "flat_code": "1000.15-01-426.MAT"},
                "cost_code": {"id": 2, "code": "15-01-426"},
                "cost_type": {"id": 3, "abbreviation": "MAT"},
                "original_budget_amount": "60000.00",
                **{name: value for name, (_label, value) in dynamic_columns.items()},
            },
        )
        conn.commit()
    finally:
        conn.close()

    receipt = project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    assert receipt["structured_budget_detail_row_rows_inserted_or_updated"] == 1

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT revised_budget, projected_budget, committed_costs, direct_costs,
                   erp_direct_costs, erp_job_to_date_costs, job_to_date_costs,
                   projected_costs, forecast_to_complete, estimated_cost_at_completion,
                   projected_over_under, pending_budget_changes, approved_change_orders
            FROM procore_ep_budget_detail_rows
            WHERE canonical_budget_code_key = '1000.15-01-426.MAT'
            """
        ).fetchone()
        assert dict(row) == {
            "revised_budget": "60000.00",
            "projected_budget": "60000.00",
            "committed_costs": "25000.00",
            "direct_costs": "1000.50",
            "erp_direct_costs": "27778.50",
            "erp_job_to_date_costs": "27778.50",
            "job_to_date_costs": "27778.50",
            "projected_costs": "52778.50",
            "forecast_to_complete": "32221.50",
            "estimated_cost_at_completion": "60000.00",
            "projected_over_under": "0.00",
            "pending_budget_changes": "5.00",
            "approved_change_orders": "7.00",
        }
        assert conn.execute("SELECT COUNT(*) FROM procore_ep_budget_detail_row_cells").fetchone()[0] > len(dynamic_columns)
    finally:
        conn.close()

    summary = target_code_summary(db_path=db, project_key="tropical")
    for field in (
        "erp_direct_costs",
        "job_to_date_costs",
        "pending_budget_changes",
        "approved_change_orders",
    ):
        assert summary["amount_field_presence"][field] == 1


def test_projector_amount_promotion_respects_numeric_direct_precedence(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    conn = sqlite3.connect(db)
    try:
        for name, label in {
            "projected_costs_cell": "Projected Costs",
            "revised_budget_cell": "Revised Budget",
            "committed_costs_cell": "Committed Costs",
        }.items():
            _insert_raw(
                conn,
                endpoint="budget-detail-columns",
                record_id=f"col-{name}",
                payload={"id": f"col-{name}", "name": name, "label": label},
            )
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r-precedence",
            payload={
                "id": "r-precedence",
                "wbs_code": {"flat_code": "1000.15-01-426.MAT"},
                "projected_costs": "13.00",
                "projected_costs_cell": "99.00",
                "revised_budget": "not-a-number",
                "revised_budget_cell": "11.00",
                "committed_costs_cell": "not-a-number",
            },
        )
        conn.commit()
    finally:
        conn.close()

    project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT projected_costs, revised_budget, committed_costs
            FROM procore_ep_budget_detail_rows
            """
        ).fetchone()
        assert row["projected_costs"] == "13.00"
        assert row["revised_budget"] == "11.00"
        assert row["committed_costs"] is None
    finally:
        conn.close()


def test_lower_quality_redacted_rows_do_not_overwrite_live(tmp_path: Path) -> None:
    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    conn = sqlite3.connect(db)
    try:
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r1",
            payload={
                "id": "r1",
                "wbs_code": {"flat_code": "1000.15-01-426.MAT"},
                "projected_costs": "13.00",
            },
            source_quality="live_full_payload",
        )
        _insert_raw(
            conn,
            endpoint="budget-detail-rows",
            record_id="r1-legacy",
            payload={
                "id": "r1",
                "wbs_code": {"flat_code": "1000.15-01-426.MAT"},
                "projected_costs": "REDACTED",
            },
            source_quality="redacted_legacy_projection",
        )
        conn.commit()
    finally:
        conn.close()

    live = project_budget_detail_read_model(db_path=db, project_key="tropical", apply=True)
    legacy = project_budget_detail_read_model(
        db_path=db, project_key="tropical", require_live_full=False, apply=True
    )
    assert live["structured_budget_detail_row_rows_inserted_or_updated"] == 1
    assert legacy["skipped_lower_quality"] >= 1
    conn = sqlite3.connect(db)
    try:
        value = conn.execute(
            "SELECT projected_costs FROM procore_ep_budget_detail_rows"
        ).fetchone()[0]
        assert value == "13.00"
    finally:
        conn.close()


def test_seed_command_requires_explicit_guardrails() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["live", "seed-budget-details", "--project", "tropical", "--dry-run", "--json"],
    )
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["local_db_write_performed"] is False
    assert payload["external_writeback_performed"] == 0


def test_project_budget_detail_read_model_command_requires_db_and_apply(tmp_path: Path) -> None:
    runner = CliRunner()
    missing_db = runner.invoke(
        app,
        ["analytics", "project-budget-detail-read-model", "--apply", "--json"],
        catch_exceptions=False,
    )
    assert missing_db.exit_code == 2
    assert json.loads(missing_db.stdout)["status"] == "blocked_explicit_db_required"

    db = tmp_path / "store.sqlite"
    SQLiteMigrator(str(db)).apply()
    missing_apply = runner.invoke(
        app,
        ["analytics", "project-budget-detail-read-model", "--db", str(db), "--json"],
        catch_exceptions=False,
    )
    assert missing_apply.exit_code == 2
    assert json.loads(missing_apply.stdout)["status"] == "blocked_apply_required"
