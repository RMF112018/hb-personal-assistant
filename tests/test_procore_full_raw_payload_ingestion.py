"""Full live Procore payload ingestion.

Proves the private local SQLite DB stores FULL Procore endpoint business payloads
(``procore_endpoint_raw_payloads.payload_json`` + ``procore_raw_*`` structured rows)
sourced from full endpoint response items rather than the redacted legacy projection,
while transport/auth secrets are never stored and no payload body leaks to the receipt.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR
from hb_assistant.procore import live_sync as live_sync_mod
from hb_assistant.procore.live_sync import run_live_sync
from hb_assistant.procore.structured_analytics import (
    SOURCE_QUALITY_FIXTURE_FULL,
    SOURCE_QUALITY_LEGACY,
    SOURCE_QUALITY_LIVE_FULL,
    backfill_from_live_records,
    reconcile_full_raw_landing,
    upsert_full_raw_payload_and_structured,
)
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "full_raw.sqlite"
    assert SQLiteMigrator(db_path=str(db)).apply() == LATEST_SCHEMA_VERSION
    return db


def _insert_live_record(
    db: Path,
    *,
    endpoint_id: str,
    record_id: str,
    payload: str,
    title: str = "RFI title",
    sync_run_id: str = "run-legacy",
) -> None:
    """Insert a redacted legacy projection row (the pre-change source) for fallback tests."""
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO procore_live_sync_runs (
          sync_run_id, company_id, project_key, procore_project_id, endpoint_id,
          command_endpoint, mode, started_at_utc, completed_at_utc, status, state
        ) VALUES (?, 'company-1', 'tropical', 'project-1', ?, ?, 'test',
          '2026-06-10T00:00:00Z', '2026-06-10T00:00:01Z', 'ok', 'completed')
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
        ) VALUES ('tropical', 'project-1', ?, '', ?, ?, ?, 'open',
          '2026-06-09T12:00:00Z', 'redacted', ?, 0, NULL,
          '2026-06-09T00:00:00Z', '2026-06-09T12:00:00Z', ?)
        """,
        (endpoint_id, record_id, record_id, title, payload, sync_run_id),
    )
    conn.commit()
    conn.close()


_RICH_CHANGE_ORDER = {
    "id": 7001,
    "number": "PCO-7001",
    "status": "open",
    "grand_total": "491383.15",
    "schedule_impact_amount": "5",  # schedule day-count, never the dollar amount
    "due_date": "2026-07-01",
    "created_by": {"id": 9, "name": "Jane PM", "login": "jane@example.com"},
    "wbs_code": {"id": 3, "flat_code": "03-100", "description": "Concrete"},
    "vendor": {"id": 55, "name": "Acme Concrete LLC"},
    "custom_fields": {"custom_field_1": {"value": "field-value"}},
    "attachments": [
        {"id": 1, "name": "co.pdf", "url": "https://storage.procore.com/co.pdf?page=1"}
    ],
}


# --- Full payload persistence ----------------------------------------------------


def test_full_payload_json_persists_business_fields(tmp_path: Path) -> None:
    db = _db(tmp_path)
    receipt = upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    assert receipt["raw_payload_rows_written"] == 1
    assert receipt["structured_rows_written"] == 1
    assert receipt["raw_procore_payload_persisted"] == 1
    assert receipt["source_quality"] == SOURCE_QUALITY_LIVE_FULL
    assert receipt["skipped_due_to_higher_quality"] == 0

    conn = sqlite3.connect(db)
    payload_json, sq, persisted = conn.execute(
        "SELECT payload_json, source_quality, raw_procore_payload_persisted "
        "FROM procore_endpoint_raw_payloads"
    ).fetchone()
    conn.close()
    stored = json.loads(payload_json)
    # Full nested business objects survive verbatim in the private DB.
    assert stored["grand_total"] == "491383.15"
    assert stored["created_by"]["name"] == "Jane PM"
    assert stored["vendor"]["name"] == "Acme Concrete LLC"
    assert stored["wbs_code"]["flat_code"] == "03-100"
    assert stored["custom_fields"]["custom_field_1"]["value"] == "field-value"
    assert stored["attachments"][0]["name"] == "co.pdf"
    assert sq == SOURCE_QUALITY_LIVE_FULL
    assert persisted == 1


def test_structured_fields_populate_that_redacted_replay_leaves_null(tmp_path: Path) -> None:
    # Full payload → owner/amount/cost_code populated.
    full_db = _db(tmp_path)
    upsert_full_raw_payload_and_structured(
        db_path=full_db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(full_db)
    amount, owner, cost_code = conn.execute(
        "SELECT amount, owner_name, cost_code FROM procore_raw_change_orders"
    ).fetchone()
    conn.close()
    assert amount == "491383.15"
    assert owner == "Jane PM"
    assert cost_code == "03-100"

    # A redacted legacy projection of the same record leaves those fields NULL.
    legacy_db = tmp_path / "legacy.sqlite"
    assert SQLiteMigrator(db_path=str(legacy_db)).apply() == LATEST_SCHEMA_VERSION
    # A redacted projection omits the financial/owner business fields entirely.
    _insert_live_record(
        legacy_db,
        endpoint_id="prime-change-orders",
        record_id="7001",
        payload='{"id":7001,"status":"open"}',
    )
    backfill_from_live_records(db_path=legacy_db, apply=True, endpoint="prime-change-orders", limit=10)
    conn = sqlite3.connect(legacy_db)
    l_amount, l_owner = conn.execute(
        "SELECT amount, owner_name FROM procore_raw_change_orders"
    ).fetchone()
    conn.close()
    assert l_amount is None  # redacted replay leaves the dollar amount NULL
    assert l_owner is None  # ...and the owner NULL — both populated from the full payload


def test_auth_transport_fields_not_stored(tmp_path: Path) -> None:
    db = _db(tmp_path)
    item = {
        "id": 4242,
        "number": "RFI-4242",
        "status": "open",
        "authorization": "Bearer abc.def.ghijklmnop",
        "access_token": "AT-SECRET-VALUE",
        "refresh_token": "RT-SECRET-VALUE",
        "client_secret": "CS-SECRET-VALUE",
        "api_key": "AK-SECRET-VALUE",
        "password": "hunter2-secret",
        "owner": "Real Owner Name",
        "download_url": "https://storage.procore.com/files/9?X-Amz-Signature=DEADBEEF&token=zzz&page=2",
    }
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=item,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(db)
    payload_json, signed, secret_like = conn.execute(
        "SELECT payload_json, contains_signed_url, contains_secret_like_value "
        "FROM procore_endpoint_raw_payloads"
    ).fetchone()
    conn.close()
    for forbidden in (
        "AT-SECRET-VALUE",
        "RT-SECRET-VALUE",
        "CS-SECRET-VALUE",
        "AK-SECRET-VALUE",
        "hunter2-secret",
        "Bearer abc",
        "X-Amz-Signature",
        "token=zzz",
        "DEADBEEF",
    ):
        assert forbidden not in payload_json, forbidden
    # Business value + the non-credential URL parts survive.
    assert "Real Owner Name" in payload_json
    assert "storage.procore.com/files/9" in payload_json
    assert "page=2" in payload_json
    assert signed == 0
    assert secret_like == 0


def test_placeholder_strings_do_not_populate_scalars(tmp_path: Path) -> None:
    db = _db(tmp_path)
    item = {
        "id": 8001,
        "number": "RFI-8001",
        "owner": "[redacted]",
        "amount": "null",
        "cost_code": "",
        "status": {},
        "assignee": "[scrubbed]",
    }
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=item,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(db)
    owner, amount, cost_code, status, assignee = conn.execute(
        "SELECT owner_name, amount, cost_code, status, assignee_name FROM procore_raw_rfis"
    ).fetchone()
    payload_json = conn.execute(
        "SELECT payload_json FROM procore_endpoint_raw_payloads"
    ).fetchone()[0]
    conn.close()
    assert owner is None
    assert amount is None
    assert cost_code is None
    assert status is None
    assert assignee is None
    # The stored full payload still preserves the literal placeholders (not mutated).
    assert "[redacted]" in payload_json
    assert "[scrubbed]" in payload_json


def test_full_payload_writes_and_refreshes_company_context(tmp_path: Path) -> None:
    db = _db(tmp_path)
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        company_id="5280",
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        company_id="9999",
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        raw = conn.execute(
            """
            SELECT company_id, company_id_hash
            FROM procore_endpoint_raw_payloads
            WHERE raw_procore_payload_persisted = 1
            """
        ).fetchone()
        structured = conn.execute(
            "SELECT company_id, company_id_hash FROM procore_raw_change_orders"
        ).fetchone()
    finally:
        conn.close()
    assert raw["company_id"] == "9999"
    assert raw["company_id_hash"]
    assert structured["company_id"] == "9999"
    assert structured["company_id_hash"]


def test_full_raw_current_version_history_has_single_current_row(tmp_path: Path) -> None:
    db = _db(tmp_path)
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item={"id": "R1", "number": "RFI-R1", "status": "open"},
        company_id="5280",
        source_quality=SOURCE_QUALITY_LIVE_FULL,
        fetched_at_utc="2026-06-20T00:00:00+00:00",
    )
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item={"id": "R1", "number": "RFI-R1", "status": "closed"},
        company_id="5280",
        source_quality=SOURCE_QUALITY_LIVE_FULL,
        fetched_at_utc="2026-06-21T00:00:00+00:00",
    )
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="other-project",
        procore_project_id="2525841",
        raw_item={"id": "R1", "number": "RFI-R1", "status": "other"},
        company_id="5280",
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(db)
    try:
        tropical_versions, tropical_current = conn.execute(
            """
            SELECT COUNT(*), SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END)
            FROM procore_endpoint_raw_payloads
            WHERE endpoint_key = 'rfis'
              AND project_key = 'tropical'
              AND record_id = 'R1'
              AND raw_procore_payload_persisted = 1
            """
        ).fetchone()
        other_current = conn.execute(
            """
            SELECT SUM(CASE WHEN is_current = 1 THEN 1 ELSE 0 END)
            FROM procore_endpoint_raw_payloads
            WHERE endpoint_key = 'rfis'
              AND project_key = 'other-project'
              AND record_id = 'R1'
              AND raw_procore_payload_persisted = 1
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert tropical_versions == 2
    assert tropical_current == 1
    assert other_current == 1


def test_reconcile_full_raw_landing_requires_explicit_db_and_apply(tmp_path: Path) -> None:
    assert reconcile_full_raw_landing(db_path=None, apply=True)["status"] == "blocked_explicit_db_required"
    db = _db(tmp_path)
    assert reconcile_full_raw_landing(db_path=db, apply=False)["status"] == "blocked_apply_required"


def test_reconcile_full_raw_landing_cli_requires_db_and_apply(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from hb_assistant.cli.procore import app

    runner = CliRunner()
    missing_db = runner.invoke(
        app,
        ["analytics", "reconcile-full-raw-landing", "--apply", "--json"],
        catch_exceptions=False,
    )
    assert missing_db.exit_code == 2
    assert json.loads(missing_db.stdout)["status"] == "blocked_explicit_db_required"

    db = _db(tmp_path)
    missing_apply = runner.invoke(
        app,
        ["analytics", "reconcile-full-raw-landing", "--db", str(db), "--json"],
        catch_exceptions=False,
    )
    assert missing_apply.exit_code == 2
    assert json.loads(missing_apply.stdout)["status"] == "blocked_apply_required"


def test_reconcile_full_raw_landing_repairs_company_and_currentness(tmp_path: Path) -> None:
    db = _db(tmp_path)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            """
            INSERT INTO procore_live_sync_runs (
              sync_run_id, company_id, project_key, procore_project_id, endpoint_id,
              command_endpoint, mode, started_at_utc, completed_at_utc, status, state
            ) VALUES ('run-repair', '5280', 'tropical', '2525840', 'rfis', 'rfis', 'test',
              '2026-06-20T00:00:00Z', '2026-06-20T00:00:01Z', 'ok', 'completed')
            """
        )
        for raw_id, payload_hash, seen_last in (
            ("raw-old", "hash-old", "2026-06-20T00:00:00+00:00"),
            ("raw-new", "hash-new", "2026-06-21T00:00:00+00:00"),
        ):
            conn.execute(
                """
                INSERT INTO procore_endpoint_raw_payloads (
                  raw_payload_id, capture_run_id, endpoint_key, endpoint_family,
                  endpoint_version, project_id, project_id_hash, project_key,
                  record_type, record_id, record_id_hash, source_ref_hash,
                  request_fingerprint_hash, payload_hash, payload_json,
                  payload_size_bytes, payload_captured_at_utc,
                  payload_seen_first_utc, payload_seen_last_utc, is_current,
                  redaction_status, security_scrub_status, source_quality,
                  raw_procore_payload_persisted, external_writeback_performed
                ) VALUES (?, 'run-repair', 'rfis', 'field', 'live_v1', '2525840', 'pidhash',
                  'tropical', 'rfis', 'R1', 'rid', 'source', 'request', ?, '{}', 2,
                  ?, ?, ?, 1, 'full_business_payload', 'transport_secrets_removed',
                  ?, 1, 0)
                """,
                (raw_id, payload_hash, seen_last, seen_last, seen_last, SOURCE_QUALITY_LIVE_FULL),
            )
        conn.commit()
    finally:
        conn.close()

    receipt = reconcile_full_raw_landing(db_path=db, apply=True)
    assert receipt["ok"] is True
    assert receipt["company_rows_repaired"] == 2
    assert receipt["stable_keys_reconciled"] == 1
    conn = sqlite3.connect(db)
    try:
        current = conn.execute(
            "SELECT raw_payload_id FROM procore_endpoint_raw_payloads WHERE is_current = 1"
        ).fetchall()
        company_count = conn.execute(
            """
            SELECT COUNT(*) FROM procore_endpoint_raw_payloads
            WHERE company_id = '5280' AND company_id_hash IS NOT NULL
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert current == [("raw-new",)]
    assert company_count == 2


# --- Source-quality precedence ---------------------------------------------------


def test_source_quality_rank_upgrade_and_idempotency(tmp_path: Path) -> None:
    db = _db(tmp_path)
    # legacy first.
    _insert_live_record(
        db,
        endpoint_id="prime-change-orders",
        record_id="7001",
        payload='{"id":7001,"status":"open"}',
    )
    backfill_from_live_records(db_path=db, apply=True, endpoint="prime-change-orders", limit=10)
    conn = sqlite3.connect(db)
    assert (
        conn.execute("SELECT source_quality FROM procore_raw_change_orders").fetchone()[0]
        == SOURCE_QUALITY_LEGACY
    )
    conn.close()

    # full upgrades the structured row in place.
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT source_quality, amount FROM procore_raw_change_orders"
    ).fetchall()
    conn.close()
    assert rows == [(SOURCE_QUALITY_LIVE_FULL, "491383.15")]  # upgraded, single row

    # full twice = idempotent (single raw row per identity, single structured row).
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    conn = sqlite3.connect(db)
    struct_n = conn.execute("SELECT COUNT(*) FROM procore_raw_change_orders").fetchone()[0]
    full_raw_n = conn.execute(
        "SELECT COUNT(*) FROM procore_endpoint_raw_payloads WHERE raw_procore_payload_persisted = 1"
    ).fetchone()[0]
    conn.close()
    assert struct_n == 1
    assert full_raw_n == 1

    # fixture_full (rank 90) must NOT overwrite live_full (rank 100).
    receipt = upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item={**_RICH_CHANGE_ORDER, "grand_total": "1.00"},
        source_quality=SOURCE_QUALITY_FIXTURE_FULL,
    )
    assert receipt["skipped_due_to_higher_quality"] == 1
    conn = sqlite3.connect(db)
    sq, amount = conn.execute(
        "SELECT source_quality, amount FROM procore_raw_change_orders"
    ).fetchone()
    conn.close()
    assert sq == SOURCE_QUALITY_LIVE_FULL
    assert amount == "491383.15"  # unchanged by the lower-rank write


def test_legacy_replay_cannot_overwrite_or_downgrade_full_rows(tmp_path: Path) -> None:
    db = _db(tmp_path)
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="prime-change-orders",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item=_RICH_CHANGE_ORDER,
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    # A redacted legacy record for the SAME identity arrives afterwards.
    _insert_live_record(
        db,
        endpoint_id="prime-change-orders",
        record_id="7001",
        payload='{"id":7001,"status":"closed","created_by":"[scrubbed]"}',
    )
    receipt = backfill_from_live_records(
        db_path=db, apply=True, endpoint="prime-change-orders", limit=10
    )
    assert receipt["skipped_due_to_higher_quality"] == 1
    assert receipt["structured_written"] == 0
    assert receipt["raw_landing_written"] == 0
    conn = sqlite3.connect(db)
    sq, amount, owner, status = conn.execute(
        "SELECT source_quality, amount, owner_name, status FROM procore_raw_change_orders"
    ).fetchone()
    persisted = conn.execute(
        "SELECT raw_procore_payload_persisted FROM procore_endpoint_raw_payloads "
        "WHERE raw_procore_payload_persisted = 1"
    ).fetchone()[0]
    conn.close()
    assert sq == SOURCE_QUALITY_LIVE_FULL  # not downgraded
    assert amount == "491383.15"  # full value retained
    assert owner == "Jane PM"
    assert status == "open"  # legacy "closed" never overwrote the full value
    assert persisted == 1


# --- Financial amount extraction (non-regression from full payloads) -------------


def test_financial_amount_extraction_from_full_payload(tmp_path: Path) -> None:
    db = _db(tmp_path)
    cases = [
        (
            "subcontractor-invoice-contract-detail-items",
            {
                "id": 5001,
                "scheduled_value": "120000.00",
                "work_completed_this_period": "14000.00",
            },
            "procore_raw_invoice_items",
            "14000.00",
        ),
        (
            "subcontractor-invoices",
            {"id": 6001, "total_claimed_amount": "3103000.00"},
            "procore_raw_invoices",
            "3103000.00",
        ),
        (
            "prime-change-orders",
            {"id": 7002, "grand_total": "491383.15", "schedule_impact_amount": "5"},
            "procore_raw_change_orders",
            "491383.15",
        ),
    ]
    for endpoint_id, item, table, expected in cases:
        upsert_full_raw_payload_and_structured(
            db_path=db,
            endpoint_id=endpoint_id,
            project_key="tropical",
            procore_project_id="2525840",
            raw_item=item,
            source_quality=SOURCE_QUALITY_LIVE_FULL,
        )
        conn = sqlite3.connect(db)
        amount = conn.execute(
            f"SELECT amount FROM {table} WHERE record_id = ?", (str(item["id"]),)
        ).fetchone()[0]
        conn.close()
        assert amount == expected, endpoint_id


# --- reprocess source order ------------------------------------------------------


def test_reprocess_prefers_full_then_legacy(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from hb_assistant.cli.procore import app

    db = _db(tmp_path)
    # Record A: a full raw payload row only (no live record).
    upsert_full_raw_payload_and_structured(
        db_path=db,
        endpoint_id="rfis",
        project_key="tropical",
        procore_project_id="2525840",
        raw_item={"id": "A1", "number": "RFI-A1", "status": "open", "owner": "Full Owner"},
        source_quality=SOURCE_QUALITY_LIVE_FULL,
    )
    # Record B: legacy redacted live record only (no full raw).
    _insert_live_record(
        db, endpoint_id="rfis", record_id="B2", payload='{"id":"B2","status":"open"}'
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["analytics", "reprocess", "--db", str(db), "--endpoint", "rfis", "--apply", "--json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["source"] == "auto"
    assert payload["full_raw_structured_written"] >= 1
    assert payload["legacy_structured_written"] >= 1
    assert payload["structured_written"] == (
        payload["full_raw_structured_written"] + payload["legacy_structured_written"]
    )
    conn = sqlite3.connect(db)
    by_quality = dict(
        conn.execute("SELECT source_quality, COUNT(*) FROM procore_raw_rfis GROUP BY source_quality")
    )
    conn.close()
    assert by_quality.get(SOURCE_QUALITY_LIVE_FULL, 0) >= 1
    assert by_quality.get(SOURCE_QUALITY_LEGACY, 0) >= 1


# --- live sync integration (fixture transport) -----------------------------------


class _FakeResponse:
    def __init__(self, body: Any, status_code: int = 200, headers: Optional[Dict[str, str]] = None):
        self._json_body = body
        self.status_code = status_code
        self.headers = headers or {}
        self.text = ""

    def json(self) -> Any:
        return self._json_body


class _FakeTransport:
    def __init__(self, payload: Any) -> None:
        self.payload = payload
        self.calls: List[Dict[str, Any]] = []

    def __call__(
        self, method: str, url: str, headers: Dict[str, str], params: Optional[Dict[str, Any]]
    ) -> _FakeResponse:
        self.calls.append({"method": method, "url": url})
        if len(self.calls) == 1:
            return _FakeResponse(self.payload)
        return _FakeResponse([])


_RFI_PAYLOAD = [
    {
        "id": 201,
        "number": "RFI-201",
        "subject": "Door schedule clarification",
        "status": "open",
        "updated_at": "2026-01-01T00:00:00Z",
        "assignee_id": 42,
        "access_token": "LIVE-SECRET-TOKEN",
    },
    {
        "id": 202,
        "number": "RFI-202",
        "subject": "Slab edge detail",
        "status": "open",
        "updated_at": "2026-01-02T00:00:00Z",
        "assignee_id": 43,
    },
]


def _live_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-bearer-token")


def test_live_sync_writes_full_raw_and_structured_no_body_in_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_env(monkeypatch)
    db = _live_db()
    transport = _FakeTransport(_RFI_PAYLOAD)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        max_pages=3,
        max_items=100,
        db_path=db,
        transport=transport,
    )
    assert receipt["full_raw_persistence_enabled"] is True
    assert receipt["raw_payload_rows_written"] == 2
    assert receipt["structured_rows_written"] == 2
    assert receipt["raw_persist_error_count"] == 0
    assert receipt["raw_payload_body_emitted_to_stdout"] is False
    assert receipt["ok"] is True
    # No business payload body leaks into the receipt.
    receipt_json = json.dumps(receipt, default=str)
    assert "Door schedule clarification" not in receipt_json
    assert "LIVE-SECRET-TOKEN" not in receipt_json

    conn = sqlite3.connect(db)
    raw_rows = conn.execute(
        "SELECT payload_json, source_quality, raw_procore_payload_persisted, company_id, company_id_hash "
        "FROM procore_endpoint_raw_payloads WHERE endpoint_key = 'rfis'"
    ).fetchall()
    struct_n = conn.execute("SELECT COUNT(*) FROM procore_raw_rfis").fetchone()[0]
    conn.close()
    assert len(raw_rows) == 2
    for payload_json, sq, persisted, company_id, company_id_hash in raw_rows:
        assert sq == SOURCE_QUALITY_LIVE_FULL
        assert persisted == 1
        assert company_id == "5280"
        assert company_id_hash
        assert "LIVE-SECRET-TOKEN" not in payload_json  # transport secret stripped
    assert struct_n == 2


def test_raw_persisted_before_live_record_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raw-first: even if the lossy live-record projection fails, full raw is persisted."""
    _setup_env(monkeypatch)
    db = _live_db()

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic live-record upsert failure")

    monkeypatch.setattr(live_sync_mod, "upsert_procore_live_record", _boom)
    transport = _FakeTransport(_RFI_PAYLOAD)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    # The lossy projection failed for every item, yet the full raw payload landed first.
    assert receipt["raw_payload_rows_written"] == 2
    conn = sqlite3.connect(db)
    raw_n = conn.execute(
        "SELECT COUNT(*) FROM procore_endpoint_raw_payloads WHERE raw_procore_payload_persisted = 1"
    ).fetchone()[0]
    live_n = conn.execute("SELECT COUNT(*) FROM procore_live_records").fetchone()[0]
    conn.close()
    assert raw_n == 2
    assert live_n == 0  # lossy projection never succeeded


def test_raw_persist_failure_degrades_run_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_env(monkeypatch)
    db = _live_db()

    def _boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("synthetic full-raw persist failure")

    monkeypatch.setattr(live_sync_mod, "upsert_full_raw_payload_and_structured", _boom)
    transport = _FakeTransport(_RFI_PAYLOAD)
    receipt = run_live_sync(
        project_key="tropical",
        endpoint="rfis",
        apply=True,
        sqlite_only=True,
        confirm_live_get=True,
        db_path=db,
        transport=transport,
    )
    assert receipt["raw_persist_error_count"] == 2
    assert receipt["ok"] is False
    assert receipt["state"] == "degraded_raw_persistence"
