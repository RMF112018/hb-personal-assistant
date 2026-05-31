"""Phase 06B Prompt 07 — freshness / stale-data read model (offline, synthetic SQLite).

Proves per-endpoint freshness classification (current / stale / never_synced / unknown /
fail_closed), that held (fail-closed) endpoints never appear as stale operational endpoints,
recommended sync commands for stale endpoints, and no raw-value leakage. Read-only; no network.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.procore import app
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_freshness import build_freshness_report
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    update_watermark,
    upsert_procore_live_record,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-30T00:00:00+00:00"
_OLD = "2020-01-01T00:00:00+00:00"
_SECRET_TITLE = "SECRET_TITLE_DO_NOT_LEAK"
_HELD = {"purchase-order-detail-line-items", "budget-change-line-items", "budget-details"}


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _wm(db, endpoint_id: str, ts: str | None) -> None:
    if ts is None:
        conn = sqlite3.connect(str(db))
        conn.execute(
            """INSERT INTO procore_live_sync_watermarks
               (company_id, project_key, procore_project_id, endpoint_id, last_success_at_utc,
                last_receipt_id, cursor_redacted) VALUES (?,?,?,?,?,?,?)""",
            ("5280", "tropical", "2525840", endpoint_id, None, "r", None),
        )
        conn.commit()
        conn.close()
        return
    update_watermark(company_id="5280", project_key="tropical", procore_project_id="2525840",
                     endpoint_id=endpoint_id, cursor_redacted=None, receipt_id="r",
                     now_utc=ts, db_path=db)


def _seed(db: Path) -> None:
    _wm(db, "rfis", _NOW)            # current
    _wm(db, "submittals", _OLD)      # stale
    _wm(db, "meetings", None)        # unknown (watermark row, NULL last_success, no records)
    # observations + the rest: left untouched -> never_synced
    # a record under rfis (with a secret title) to exercise record_count + no-leak.
    record_sync_run_start(sync_run_id="run1", endpoint_id="rfis", command_endpoint="rfis",
                          legacy_endpoint_alias=None, project_key="tropical",
                          procore_project_id="2525840", company_id="5280", mode="live_apply",
                          started_at_utc=_NOW, db_path=db)
    upsert_procore_live_record(
        project_key="tropical", procore_project_id="2525840", endpoint_id="rfis",
        procore_record_id="1", parent_procore_id=None,
        normalized_fields={"number": "RFI-001", "subject": _SECRET_TITLE, "status": "open"},
        review_required=False, sensitive_reason=None, source_url_redacted="/x/1",
        last_sync_run_id="run1", now_utc=_NOW, db_path=db,
    )


def _report(db: Path):
    return build_freshness_report("tropical", now_utc=_NOW, stale_days=7, db_path=db)


def _by_id(report):
    return {e["endpoint_id"]: e for e in report["endpoints"]}


def test_each_status_classified() -> None:
    db = _db()
    _seed(db)
    by = _by_id(_report(db))
    assert by["rfis"]["status"] == "current" and by["rfis"]["age_days"] == 0
    assert by["rfis"]["source"] == "watermark" and by["rfis"]["record_count"] == 1
    assert by["submittals"]["status"] == "stale" and by["submittals"]["age_days"] > 7
    assert by["observations"]["status"] == "never_synced"
    assert by["meetings"]["status"] == "unknown"
    for held in _HELD:
        assert by[held]["status"] == "fail_closed"


def test_fail_closed_endpoints_are_not_stale_operational() -> None:
    db = _db()
    _seed(db)
    r = _report(db)
    stale_ids = {s["endpoint_id"] for s in r["stale_endpoints"]}
    assert not (_HELD & stale_ids)  # validation: held never appears as stale operational
    assert r["summary"]["fail_closed"] == 3
    # operational_total excludes the 3 held endpoints.
    assert r["summary"]["operational_total"] == len({e["endpoint_id"] for e in r["endpoints"]}) - 3


def test_recommended_sync_commands() -> None:
    db = _db()
    _seed(db)
    by = _by_id(_report(db))
    cmd = by["submittals"]["recommended_sync_command"]
    assert cmd is not None
    assert "--project tropical" in cmd and "--endpoint submittals" in cmd
    assert cmd.startswith("HB_PROCORE_LIVE=1 hb-assistant procore live sync")
    assert by["observations"]["recommended_sync_command"] is not None  # never_synced
    assert by["rfis"]["recommended_sync_command"] is None  # current
    assert by["meetings"]["recommended_sync_command"] is None  # unknown
    for held in _HELD:
        assert by[held]["recommended_sync_command"] is None


def test_no_raw_values_or_secrets() -> None:
    db = _db()
    _seed(db)
    r = _report(db)
    blob = json.dumps(r)
    assert _SECRET_TITLE not in blob
    assert r["no_raw_values_persisted"] is True
    assert r["no_live_call_performed"] is True
    assert r["determinations_made"] is False


def test_cli_json_shape() -> None:
    SQLiteMigrator().apply()
    update_watermark(company_id="5280", project_key="tropical", procore_project_id="2525840",
                     endpoint_id="submittals", cursor_redacted=None, receipt_id="r",
                     now_utc=_OLD)
    get_connection().commit()
    res = CliRunner().invoke(app, ["live", "stale", "--project", "tropical", "--json"],
                            catch_exceptions=False)
    assert res.exit_code == 0
    payload = json.loads(res.output)
    for key in ("command", "summary", "endpoints", "stale_endpoints", "stale_threshold_days",
                "no_live_call_performed", "determinations_made", "guardrails"):
        assert key in payload, f"missing {key}"
    assert payload["no_live_call_performed"] is True
    assert payload["summary"]["fail_closed"] == 3
    assert any(s["endpoint_id"] == "submittals" for s in payload["stale_endpoints"])
