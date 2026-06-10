from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.procore import app
from hb_assistant.procore.structured_analytics import (
    RAW_LANDING_TABLE,
    STRUCTURED_TABLES,
    _amount_with_source,
    backfill_from_live_records,
    contract_inventory,
    no_raw_leak_scan,
    payload_has_forbidden_security_artifact,
    scrubbed_payload_json,
    structured_coverage,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "structured.sqlite"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    return db


_DEFAULT_PAYLOAD = (
    '{"id":1001,"number":"RFI-1001","status":"open","due_date":"2026-06-12",'
    '"cost_code":"03-100","amount":"1250.00",'
    '"private_url":"https://example.invalid/rest/v1.0/private?token=abc"}'
)


def _insert_live_record(
    db: Path,
    *,
    endpoint_id: str = "rfis",
    record_id: str = "1001",
    payload: str | None = None,
    sync_run_id: str = "run-1",
) -> None:
    canonical = _DEFAULT_PAYLOAD if payload is None else payload
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO procore_live_sync_runs (
          sync_run_id, company_id, project_key, procore_project_id, endpoint_id,
          command_endpoint, mode, started_at_utc, completed_at_utc, status, state
        ) VALUES (
          ?, 'company-1', 'tropical', 'project-1', ?, ?, 'test',
          '2026-06-10T00:00:00Z', '2026-06-10T00:00:01Z', 'ok', 'completed'
        )
        """,
        (sync_run_id, endpoint_id, endpoint_id),
    )
    conn.execute(
        """
        INSERT INTO procore_live_records (
          project_key, procore_project_id, endpoint_id, parent_procore_id,
          procore_record_id, procore_record_number, title_redacted, status,
          updated_at_utc, source_url_redacted, canonical_json_redacted,
          review_required, sensitive_reason, first_seen_at_utc, last_seen_at_utc,
          last_sync_run_id
        ) VALUES (
          'tropical', 'project-1', ?, '', ?, 'RFI-1001', 'RFI title', 'open',
          '2026-06-09T12:00:00Z', 'redacted',
          ?,
          0, NULL, '2026-06-09T00:00:00Z', '2026-06-09T12:00:00Z', ?
        )
        """,
        (endpoint_id, record_id, canonical, sync_run_id),
    )
    conn.commit()
    conn.close()


def test_v46_migration_creates_raw_landing_and_structured_tables(tmp_path: Path) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
    assert RAW_LANDING_TABLE in tables
    assert "procore_endpoint_capture_runs" in tables
    required = {
        "procore_raw_rfis",
        "procore_raw_rfi_responses",
        "procore_raw_submittals",
        "procore_raw_meetings",
        "procore_raw_daily_logs",
        "procore_raw_inspection_items",
        "procore_raw_schedule_activities",
        "procore_raw_contracts",
        "procore_raw_budget_rows",
        "procore_raw_invoices",
        "procore_raw_payment_applications",
        "procore_raw_project_dimensions",
        "procore_raw_company_dimensions",
        "procore_raw_person_dimensions",
        "procore_raw_cost_code_dimensions",
        "procore_raw_location_dimensions",
        "procore_raw_status_dimensions",
        "procore_raw_date_dimensions",
    }
    assert required <= tables
    version = conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0]
    assert version == LATEST_SCHEMA_VERSION == 46
    conn.close()


def test_contract_maps_live_endpoints_to_raw_and_structured_or_defer() -> None:
    payload = contract_inventory()
    assert payload["raw_landing_table"] == RAW_LANDING_TABLE
    assert payload["raw_json_only_is_sufficient"] is False
    assert payload["missing_structured_endpoint_count"] == 0
    assert payload["structured_table_count"] == len(STRUCTURED_TABLES)
    for row in payload["rows"]:
        assert row["raw_landing_target"] == RAW_LANDING_TABLE
        if row["analytics_eligible"]:
            assert row["structured_table"]
            assert row["source_ref_supported"] is True
        else:
            assert row["defer_reason"] or row["structured_table"]


def test_backfill_dry_run_writes_nothing_and_reports_structured_targets(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(db)
    payload = backfill_from_live_records(db_path=db, apply=False, endpoint="rfis", limit=10)
    assert payload["mode"] == "dry_run"
    assert payload["would_write_raw_landing"] == 1
    assert payload["would_write_structured"] == 1
    conn = sqlite3.connect(db)
    assert conn.execute(f"SELECT COUNT(*) FROM {RAW_LANDING_TABLE}").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM procore_raw_rfis").fetchone()[0] == 0
    conn.close()


def test_backfill_apply_populates_raw_landing_and_structured_bronze(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(db)
    payload = backfill_from_live_records(db_path=db, apply=True, endpoint="rfis", limit=10)
    assert payload["raw_landing_written"] == 1
    assert payload["structured_written"] == 1
    assert payload["source_quality"] == "redacted_legacy_projection"
    conn = sqlite3.connect(db)
    raw = conn.execute(f"SELECT payload_json, source_quality FROM {RAW_LANDING_TABLE}").fetchone()
    assert raw[1] == "redacted_legacy_projection"
    assert "token=abc" not in raw[0]
    row = conn.execute(
        "SELECT endpoint_key, project_key, record_number, status, cost_code, amount, raw_payload_linked FROM procore_raw_rfis"
    ).fetchone()
    assert row == ("rfis", "tropical", "RFI-1001", "open", "03-100", "1250.00", 1)
    assert conn.execute("SELECT COUNT(*) FROM procore_raw_project_dimensions").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM procore_raw_cost_code_dimensions").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM procore_raw_date_dimensions").fetchone()[0] == 1
    conn.close()


def test_coverage_requires_structured_rows_not_raw_landing_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(db)
    before = structured_coverage(db_path=db, family="rfis")
    assert before["total_live_record_rows"] == 1
    assert before["total_structured_rows"] == 0
    assert before["structured_acceptance_gate"] is False
    backfill_from_live_records(db_path=db, apply=True, family="rfis", limit=10)
    after = structured_coverage(db_path=db, family="rfis")
    assert after["total_structured_rows"] == 1
    assert after["structured_acceptance_gate"] is True


def test_scrubber_removes_tokens_and_signed_urls_without_hashing_business_fields() -> None:
    scrubbed = scrubbed_payload_json(
        '{"title":"Keep business title","access_' + 'token":"secret","download_url":"https://example.com/file?X-Amz-' + 'Signature=abc"}'
    )
    assert "Keep business title" in scrubbed
    assert "secret" not in scrubbed
    assert "X-Amz-" + "Signature" not in scrubbed
    assert payload_has_forbidden_security_artifact(scrubbed) is False


def test_cli_contract_and_reprocess_are_local_only(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(db)
    runner = CliRunner()
    contract = runner.invoke(app, ["analytics", "contract", "--json"], catch_exceptions=False)
    assert contract.exit_code == 0
    contract_payload = json.loads(contract.output)
    assert contract_payload["guardrails"]["writeback"] == "none"
    dry = runner.invoke(
        app,
        ["analytics", "reprocess", "--db", str(db), "--endpoint", "rfis", "--dry-run", "--json"],
        catch_exceptions=False,
    )
    assert dry.exit_code == 0
    dry_payload = json.loads(dry.output)
    assert dry_payload["live_procore_calls"] == 0
    apply = runner.invoke(
        app,
        ["analytics", "reprocess", "--db", str(db), "--endpoint", "rfis", "--apply", "--json"],
        catch_exceptions=False,
    )
    assert apply.exit_code == 0
    apply_payload = json.loads(apply.output)
    assert apply_payload["structured_written"] == 1


def test_no_raw_leak_scan_flags_forbidden_patterns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.txt"
    bad.write_text("Bear" + "er abc123", encoding="utf-8")
    payload = no_raw_leak_scan([tmp_path])
    assert payload["ok"] is False
    assert payload["unsafe_finding_count"] == 1


# --- Financial amount extraction remediation -------------------------------------

def test_amount_invoice_item_prefers_work_completed_this_period() -> None:
    payload = {
        "work_completed_this_period": "100.00",
        "total_completed_and_stored_to_date": "200.00",
        "subcontractor_claimed_amount": "300.00",
        "scheduled_value": "400.00",
    }
    assert _amount_with_source(payload, "subcontractor-invoice-contract-detail-items") == (
        "100.00",
        "work_completed_this_period",
    )
    # change-order invoice items share the same precedence
    assert _amount_with_source(payload, "subcontractor-invoice-change-order-items") == (
        "100.00",
        "work_completed_this_period",
    )


def test_amount_invoice_item_falls_back_to_scheduled_value() -> None:
    payload = {"scheduled_value": "120000.00"}
    assert _amount_with_source(payload, "subcontractor-invoice-contract-detail-items") == (
        "120000.00",
        "scheduled_value",
    )


def test_amount_invoice_prefers_total_claimed_amount() -> None:
    payload = {
        "total_claimed_amount": "3103000.00",
        "summary": {"current_payment_due": "999.00"},
    }
    assert _amount_with_source(payload, "subcontractor-invoices") == (
        "3103000.00",
        "total_claimed_amount",
    )


def test_amount_invoice_uses_nested_summary_current_payment_due() -> None:
    payload = {"summary": {"current_payment_due": "3103000.00", "total_retainage": "0.00"}}
    assert _amount_with_source(payload, "subcontractor-invoices") == (
        "3103000.00",
        "summary.current_payment_due",
    )


def test_amount_change_order_uses_grand_total_and_excludes_schedule_impact() -> None:
    # grand_total wins; a co-present schedule day-count never participates
    full = {"grand_total": "491383.15", "schedule_impact_amount": "5"}
    assert _amount_with_source(full, "prime-change-orders") == ("491383.15", "grand_total")
    assert _amount_with_source(full, "commitment-change-orders") == ("491383.15", "grand_total")
    # schedule_impact_amount alone must NOT populate the dollar amount column
    schedule_only = {"schedule_impact_amount": "5"}
    assert _amount_with_source(schedule_only, "prime-change-orders") == (None, None)


def test_amount_generic_fallback_preserved_for_existing_tables() -> None:
    # rfis (existing test fixture) keeps the plain ``amount`` key path
    assert _amount_with_source({"amount": "1250.00"}, "rfis") == ("1250.00", "amount")
    # change-order line items already expose ``amount``
    assert _amount_with_source({"amount": "14000.0"}, "prime-change-order-line-items") == (
        "14000.0",
        "amount",
    )
    # budget rows expose ``original_budget_amount``
    assert _amount_with_source({"original_budget_amount": "500.00"}, "budget-detail-rows") == (
        "500.00",
        "original_budget_amount",
    )
    # unknown endpoint with no monetary field -> no amount
    assert _amount_with_source({"status": "open"}, "subcontractor-invoices") == (None, None)


def test_backfill_populates_invoice_item_amount_from_real_fields(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(
        db,
        endpoint_id="subcontractor-invoice-contract-detail-items",
        record_id="5001",
        payload='{"id":5001,"scheduled_value":"120000.00","subcontractor_claimed_amount":"0.0",'
        '"total_completed_and_stored_to_date":"0.00","work_completed_this_period":"14000.00"}',
    )
    receipt = backfill_from_live_records(
        db_path=db, apply=True, endpoint="subcontractor-invoice-contract-detail-items", limit=10
    )
    assert receipt["structured_written"] == 1
    assert receipt["live_procore_calls"] == 0
    assert receipt["external_writeback_performed"] == 0
    conn = sqlite3.connect(db)
    amount = conn.execute("SELECT amount FROM procore_raw_invoice_items").fetchone()[0]
    conn.close()
    assert amount == "14000.00"


def test_backfill_populates_invoice_and_change_order_amounts(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(
        db,
        endpoint_id="subcontractor-invoices",
        record_id="6001",
        sync_run_id="run-inv",
        payload='{"id":6001,"total_claimed_amount":"3103000.00",'
        '"summary":{"current_payment_due":"3103000.00"}}',
    )
    _insert_live_record(
        db,
        endpoint_id="prime-change-orders",
        record_id="7001",
        sync_run_id="run-co",
        payload='{"id":7001,"grand_total":"491383.15","schedule_impact_amount":"5"}',
    )
    backfill_from_live_records(db_path=db, apply=True, limit=100)
    conn = sqlite3.connect(db)
    invoice_amount = conn.execute("SELECT amount FROM procore_raw_invoices").fetchone()[0]
    co_amount = conn.execute("SELECT amount FROM procore_raw_change_orders").fetchone()[0]
    conn.close()
    assert invoice_amount == "3103000.00"
    assert co_amount == "491383.15"  # grand_total, not the "5" schedule day-count


def test_backfill_financial_amount_is_idempotent(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(
        db,
        endpoint_id="subcontractor-invoice-contract-detail-items",
        record_id="5002",
        payload='{"id":5002,"work_completed_this_period":"14000.00","scheduled_value":"120000.00"}',
    )
    first = backfill_from_live_records(
        db_path=db, apply=True, endpoint="subcontractor-invoice-contract-detail-items", limit=10
    )
    second = backfill_from_live_records(
        db_path=db, apply=True, endpoint="subcontractor-invoice-contract-detail-items", limit=10
    )
    assert first["structured_written"] == 1
    assert second["structured_written"] == 1
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT amount FROM procore_raw_invoice_items").fetchall()
    conn.close()
    assert rows == [("14000.00",)]  # re-run upserts in place, no duplicate row


def test_coverage_reports_amount_coverage_pct(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_live_record(
        db,
        endpoint_id="subcontractor-invoice-contract-detail-items",
        record_id="5003",
        payload='{"id":5003,"work_completed_this_period":"14000.00"}',
    )
    backfill_from_live_records(
        db_path=db, apply=True, endpoint="subcontractor-invoice-contract-detail-items", limit=10
    )
    coverage = structured_coverage(db_path=db)
    invoice_rows = [
        r
        for r in coverage["rows"]
        if r["structured_table"] == "procore_raw_invoice_items" and r["structured_rows"]
    ]
    assert invoice_rows
    assert all(r["non_null_amount_rows"] == r["structured_rows"] for r in invoice_rows)
    assert all(r["amount_coverage_pct"] == 100.0 for r in invoice_rows)
