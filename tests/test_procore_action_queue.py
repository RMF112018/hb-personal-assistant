"""Tests for the Phase 06B overdue / action-queue read model + CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_action_queue import build_overdue_queue
from hb_assistant.store.procore_enrichment import emit_action_signal
from hb_assistant.store.procore_repositories import record_sync_run_start

_NOW = "2026-05-30T00:00:00+00:00"
_PAST = "2026-05-01T00:00:00+00:00"
_FUTURE = "2026-12-01T00:00:00+00:00"
_CANON_DUE = "2026-04-15T00:00:00+00:00"
_SECRET_TITLE = "CONFIDENTIAL settlement figure $4.2M"
_SECRET_AMOUNT = "4200000.00"


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


def _ins_record(
    db: Path | None, endpoint: str, rid: str, *, review: int, source: str, canonical: str
) -> None:
    """Insert a live record row directly (deterministic; independent of upsert redaction)."""
    conn = get_connection(db)
    conn.execute(
        """
        INSERT INTO procore_live_records (
          project_key, procore_project_id, endpoint_id, parent_procore_id, procore_record_id,
          procore_record_number, title_redacted, status, updated_at_utc, source_url_redacted,
          canonical_json_redacted, review_required, sensitive_reason, first_seen_at_utc,
          last_seen_at_utc, last_sync_run_id, raw_body_persisted
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
        """,
        (
            "tropical",
            "2525840",
            endpoint,
            "",
            rid,
            None,
            None,
            "open",
            _NOW,
            source,
            canonical,
            review,
            None,
            _NOW,
            _NOW,
            "run1",
        ),
    )
    conn.commit()


def _ins_amount(db: Path | None, record_key: str, endpoint: str, name: str, value: str) -> None:
    conn = get_connection(db)
    conn.execute(
        """
        INSERT INTO procore_financial_amount_facts (
          amount_fact_id, project_key, record_key, endpoint_id, amount_name, amount_value,
          source_field_path, created_at_utc, raw_body_persisted
        ) VALUES (?,?,?,?,?,?,?,?,0)
        """,
        (
            f"af|{record_key}|{name}",
            "tropical",
            record_key,
            endpoint,
            name,
            value,
            f"{endpoint}.{name}",
            _NOW,
        ),
    )
    conn.commit()


def _seed(db: Path | None) -> None:
    _start_run(db)
    # observations/55: review-required; secret only lives in the canonical blob (never emitted).
    _ins_record(
        db,
        "observations",
        "55",
        review=1,
        source="/x/55",
        canonical=json.dumps({"subject": _SECRET_TITLE, "status": "open"}),
    )
    # rfis/1: not review-required; carries a canonical due date used as a fallback.
    _ins_record(
        db,
        "rfis",
        "1",
        review=0,
        source="/rest/v1.0/projects/2525840/rfis/1",
        canonical=json.dumps({"due_date": _CANON_DUE, "status": "open"}),
    )
    # exposure fact on a commitment record (names/counts only; value must never leak).
    _ins_amount(db, "tropical|commitments||9", "commitments", "estimated_cost", _SECRET_AMOUNT)

    # explicitly overdue, high, with an owner key, on the rfis/1 record
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|rfis||1",
        endpoint_id="rfis",
        signal_type="rfi_overdue",
        importance="high",
        signal_status="open",
        due_at_utc=_PAST,
        owner_entity_key="user:pm1",
        reason_codes=["seed_reason"],
        now_utc=_NOW,
        db_path=db,
    )
    # no signal due date -> canonical-record fallback (rfis/1 due_date) -> overdue
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|rfis||1",
        endpoint_id="rfis",
        signal_type="rfi_response_due",
        importance="medium",
        signal_status="open",
        now_utc=_NOW,
        db_path=db,
    )
    # review-required, high, no due -> no_due_date_high_importance; safety dimension
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|observations||55",
        endpoint_id="observations",
        signal_type="observation_open_safety",
        importance="high",
        signal_status="open",
        now_utc=_NOW,
        db_path=db,
    )
    # cost exposure, high, no due; exposure fact present at this record_key
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|commitments||9",
        endpoint_id="commitments",
        signal_type="commitment_cost_impact_flagged",
        importance="high",
        signal_status="open",
        now_utc=_NOW,
        db_path=db,
    )
    # schedule exposure, medium, future due -> upcoming
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|deliveries||3",
        endpoint_id="deliveries",
        signal_type="delivery_due",
        importance="medium",
        signal_status="open",
        due_at_utc=_FUTURE,
        now_utc=_NOW,
        db_path=db,
    )
    # resolved -> excluded from the open queue
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|submittals||7",
        endpoint_id="submittals",
        signal_type="submittal_approved",
        importance="low",
        signal_status="resolved",
        now_utc=_NOW,
        db_path=db,
    )


def _q(db: Path | None, **kw):
    return build_overdue_queue("tropical", now_utc=_NOW, db_path=db, **kw)


def _item(out, signal_type):
    return next(i for i in out["queue"] if i["signal_type"] == signal_type)


def test_overdue_status_and_days() -> None:
    db = _db()
    _seed(db)
    it = _item(_q(db), "rfi_overdue")
    assert it["status"] == "overdue"
    assert it["days_overdue"] is not None and it["days_overdue"] > 0
    assert "past_due_date" in it["reason_codes"]
    assert "overdue_signal_type" in it["reason_codes"]
    assert "seed_reason" in it["reason_codes"]  # signal reason codes preserved
    assert it["owner_entity_key"] == "user:pm1"


def test_canonical_due_fallback_and_source_link() -> None:
    db = _db()
    _seed(db)
    it = _item(_q(db), "rfi_response_due")
    assert it["due_at_utc"] == _CANON_DUE  # taken from the canonical record
    assert it["status"] == "overdue"
    assert it["source_url_redacted"] == "/rest/v1.0/projects/2525840/rfis/1"


def test_upcoming_and_no_due_date() -> None:
    db = _db()
    _seed(db)
    out = _q(db)
    assert _item(out, "delivery_due")["status"] == "upcoming"
    assert _item(out, "delivery_due")["days_overdue"] is None
    cost = _item(out, "commitment_cost_impact_flagged")
    assert cost["status"] == "no_due_date"
    assert "no_due_date_high_importance" in cost["reason_codes"]


def test_review_flag_join() -> None:
    db = _db()
    _seed(db)
    obs = _item(_q(db), "observation_open_safety")
    assert obs["review_required"] is True
    assert obs["source_url_redacted"] == "/x/55"
    assert "review_required_record" in obs["reason_codes"]
    assert "safety_quality_compliance" in obs["dimensions"]
    # a record with no matching live record degrades gracefully
    cost = _item(_q(db), "commitment_cost_impact_flagged")
    assert cost["review_required"] is False
    assert cost["source_url_redacted"] is None


def test_exposure_names_only() -> None:
    db = _db()
    _seed(db)
    cost = _item(_q(db), "commitment_cost_impact_flagged")
    assert cost["exposure_present"] is True
    assert cost["exposure_amount_names"] == ["estimated_cost"]
    assert cost["exposure_fact_count"] == 1
    assert _SECRET_AMOUNT not in json.dumps(_q(db))  # value never leaks


def test_dimension_filter() -> None:
    db = _db()
    _seed(db)
    out = _q(db, dimension="cost_exposure")
    assert out["queue"]
    assert all("cost_exposure" in i["dimensions"] for i in out["queue"])


def test_importance_filter() -> None:
    db = _db()
    _seed(db)
    out = _q(db, importance="high")
    assert all(i["importance"] == "high" for i in out["queue"])
    assert {i["signal_type"] for i in out["queue"]} == {
        "rfi_overdue",
        "observation_open_safety",
        "commitment_cost_impact_flagged",
    }


def test_endpoint_filter() -> None:
    db = _db()
    _seed(db)
    out = _q(db, endpoint_id="rfis")
    assert all(i["endpoint_id"] == "rfis" for i in out["queue"])
    assert len(out["queue"]) == 2


def test_summary_counts() -> None:
    db = _db()
    _seed(db)
    s = _q(db)["summary"]
    assert s["total_open"] == 5  # resolved excluded
    assert s["overdue"] == 2
    assert s["upcoming"] == 1
    assert s["no_due_date"] == 2
    assert s["high_importance"] == 3
    assert s["review_required"] == 1
    assert s["by_dimension"]["cost_exposure"] == 1
    assert s["by_dimension"]["schedule_exposure"] == 1


def test_ordering_overdue_first() -> None:
    db = _db()
    _seed(db)
    assert _q(db)["queue"][0]["status"] == "overdue"


def test_unsupported_due_date_endpoints() -> None:
    db = _db()
    _seed(db)
    out = _q(db)
    assert "observations" in out["unsupported_due_date_endpoints"]
    assert "commitments" in out["unsupported_due_date_endpoints"]
    assert "rfis" not in out["unsupported_due_date_endpoints"]


def test_no_raw_values_or_secrets() -> None:
    db = _db()
    _seed(db)
    out = _q(db)
    blob = json.dumps(out)
    assert _SECRET_TITLE not in blob
    assert _SECRET_AMOUNT not in blob
    assert out["no_raw_values_persisted"] is True
    assert out["no_live_call_performed"] is True
    assert out["determinations_made"] is False


def test_empty_project() -> None:
    db = _db()
    out = _q(db)
    assert out["summary"]["total_open"] == 0
    assert out["queue"] == []
    assert out["unsupported_due_date_endpoints"] == []


def test_cli_json_shape() -> None:
    # CLI uses the default (isolated) DB path; seed it directly, then commit.
    SQLiteMigrator().apply()
    _seed(None)
    get_connection().commit()
    res = CliRunner().invoke(
        app,
        ["procore", "live", "overdue", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    for key in (
        "command",
        "ok",
        "phase",
        "project_key",
        "generated_at",
        "filters",
        "summary",
        "queue",
        "queue_truncated",
        "unsupported_due_date_endpoints",
        "no_live_call_performed",
        "no_raw_values_persisted",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["no_live_call_performed"] is True
    assert payload["determinations_made"] is False
    assert _SECRET_TITLE not in res.output
    assert _SECRET_AMOUNT not in res.output
