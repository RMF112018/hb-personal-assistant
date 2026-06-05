"""Phase 06B Prompt 06 — project-health read model (offline, synthetic SQLite).

Proves the deterministic read model aggregates freshness / open work / review-required /
cost / schedule / safety-quality-compliance / relationship dimensions from local SQLite,
surfaces review-required + high-risk facts explicitly (never hidden behind a score), and
never leaks raw values. No network, no live Procore, no DB writes by the read model.
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
from hb_assistant.store.procore_enrichment import emit_action_signal
from hb_assistant.store.procore_project_health import build_project_health
from hb_assistant.store.procore_repositories import (
    record_sync_run_start,
    update_watermark,
    upsert_procore_live_record,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-30T00:00:00+00:00"
_SECRET_TITLE = "SECRET_TITLE_DO_NOT_LEAK"


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _start_run(db: Path | None) -> None:
    record_sync_run_start(
        sync_run_id="run1",
        endpoint_id="rfis",
        command_endpoint="rfis",
        legacy_endpoint_alias=None,
        project_key="tropical",
        procore_project_id="2525840",
        company_id="5280",
        mode="live_apply",
        started_at_utc=_NOW,
        db_path=db,
    )


def _seed(db: Path) -> None:
    _start_run(db)
    # review-required, safety-classified observation record (no responsibility edge).
    upsert_procore_live_record(
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="observations",
        procore_record_id="55",
        parent_procore_id=None,
        normalized_fields={"subject": _SECRET_TITLE, "status": "open"},
        review_required=True,
        sensitive_reason="observation_safety",
        source_url_redacted="/rest/v1.0/projects/2525840/observations/55",
        last_sync_run_id="run1",
        now_utc=_NOW,
        db_path=db,
    )
    # rfi record WITH a responsibility edge (so it is not "missing").
    upsert_procore_live_record(
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="rfis",
        procore_record_id="1",
        parent_procore_id=None,
        normalized_fields={"number": "RFI-001", "status": "open"},
        review_required=False,
        sensitive_reason=None,
        source_url_redacted="/rest/v1.0/projects/2525840/rfis/1",
        last_sync_run_id="run1",
        now_utc=_NOW,
        db_path=db,
    )
    conn = sqlite3.connect(str(db))
    conn.execute(
        """INSERT INTO procore_record_edges (edge_id, project_key, from_record_key, to_record_key,
           to_entity_key, edge_type, source_endpoint_id, confidence, first_seen_at_utc, last_seen_at_utc, metadata_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "e1",
            "tropical",
            "tropical|rfis||1",
            None,
            "company:acme",
            "responsible_contractor",
            "rfis",
            1.0,
            _NOW,
            _NOW,
            None,
        ),
    )
    conn.commit()
    conn.close()
    # open signals across dimensions + one resolved (must be excluded).
    for st, imp, status in [
        ("rfi_overdue", "high", "open"),
        ("observation_open_safety", "high", "open"),
        ("rfi_cost_impact_flagged", "medium", "open"),
        ("rfi_schedule_impact_flagged", "medium", "open"),
        ("submittal_approved", "low", "resolved"),
    ]:
        emit_action_signal(
            project_key="tropical",
            record_key=f"tropical|x||{st}",
            endpoint_id="rfis",
            signal_type=st,
            importance=imp,
            signal_status=status,
            now_utc=_NOW,
            db_path=db,
        )
    # freshness: one stale watermark (2020), one fresh.
    update_watermark(
        company_id="5280",
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="rfis",
        cursor_redacted=None,
        receipt_id="r1",
        now_utc="2020-01-01T00:00:00+00:00",
        db_path=db,
    )
    update_watermark(
        company_id="5280",
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="observations",
        cursor_redacted=None,
        receipt_id="r2",
        now_utc=_NOW,
        db_path=db,
    )


def _health(db: Path):
    return build_project_health("tropical", now_utc=_NOW, stale_days=7, db_path=db)


def test_dimension_score_components() -> None:
    db = _db()
    _seed(db)
    sc = _health(db)["score_components"]
    assert sc["open_work"] == {"open_signals": 4, "high_importance": 2}
    assert sc["cost_exposure"]["open_signals"] == 1
    assert sc["schedule_exposure"]["open_signals"] == 1
    assert sc["safety_quality_compliance"]["open_signals"] == 1
    assert sc["overdue"]["open_signals"] == 1
    assert sc["review_required"]["records"] == 1


def test_review_required_and_top_risks_not_hidden() -> None:
    db = _db()
    _seed(db)
    r = _health(db)
    # the stop condition: review-required + high-risk facts are explicit, not collapsed.
    assert r["health_status"] == "review_recommended"
    assert {
        "review_required_records",
        "high_importance_signals",
        "safety_quality_compliance_signals",
        "overdue_signals",
        "stale_endpoints",
    } <= set(r["status_reason"])
    assert len(r["review_required_items"]) == 1
    assert r["review_required_items"][0]["endpoint_id"] == "observations"
    assert len(r["top_risks"]) == 4
    assert any(t["importance"] == "high" for t in r["top_risks"])


def test_freshness_detects_stale_endpoint() -> None:
    db = _db()
    _seed(db)
    stale = _health(db)["stale_endpoints"]
    ids = {s["endpoint_id"]: s for s in stale}
    assert "rfis" in ids and ids["rfis"]["state"] == "stale" and ids["rfis"]["age_days"] > 7
    assert "observations" not in ids  # fresh watermark


def test_relationship_quality_missing_responsibility_edge() -> None:
    db = _db()
    _seed(db)
    rq = _health(db)["score_components"]["relationship_quality"]
    # observations||55 has no responsibility edge; rfis||1 has one.
    assert rq["records_missing_responsibility_edge"] == 1
    assert rq["distinct_responsible_parties"] == 1


def test_no_raw_values_or_secrets_in_output() -> None:
    db = _db()
    _seed(db)
    blob = json.dumps(_health(db))
    assert _SECRET_TITLE not in blob
    assert _health(db)["no_raw_values_persisted"] is True
    assert _health(db)["determinations_made"] is False
    assert _health(db)["no_live_call_performed"] is True


def test_empty_project_is_no_data() -> None:
    db = _db()
    r = build_project_health("tropical", now_utc=_NOW, stale_days=7, db_path=db)
    assert r["health_status"] == "no_data"
    assert r["counts"]["total_records"] == 0
    assert r["top_risks"] == [] and r["review_required_items"] == []


def test_cli_json_shape() -> None:
    # CLI uses the default (isolated) DB path; seed it directly.
    SQLiteMigrator().apply()
    _start_run(None)
    upsert_procore_live_record(
        project_key="tropical",
        procore_project_id="2525840",
        endpoint_id="observations",
        procore_record_id="55",
        parent_procore_id=None,
        normalized_fields={"subject": _SECRET_TITLE, "status": "open"},
        review_required=True,
        sensitive_reason="observation_safety",
        source_url_redacted="/x/55",
        last_sync_run_id="run1",
        now_utc=_NOW,
    )
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|obs||55",
        endpoint_id="observations",
        signal_type="observation_open_safety",
        importance="high",
        signal_status="open",
        now_utc=_NOW,
    )
    # ensure the default-path writes are visible to the command's connection.
    get_connection().commit()
    res = CliRunner().invoke(
        app, ["live", "project-health", "--project", "tropical", "--json"], catch_exceptions=False
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    for key in (
        "command",
        "health_status",
        "score_components",
        "counts",
        "top_risks",
        "stale_endpoints",
        "review_required_items",
        "evidence_references",
        "no_live_call_performed",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["no_live_call_performed"] is True
    assert payload["determinations_made"] is False
    assert _SECRET_TITLE not in res.output
