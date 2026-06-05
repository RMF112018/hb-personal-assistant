"""Tests for the Phase 06B schedule exposure read model + CLI."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import emit_action_signal
from hb_assistant.store.procore_schedule_exposure import build_schedule_exposure

_NOW = "2026-05-29T00:00:00Z"
_PAST = "2026-05-01T00:00:00Z"  # before _NOW -> overdue
_FUTURE = "2026-06-30T00:00:00Z"  # after _NOW -> upcoming
runner = CliRunner()

# delay/claims determination language that MUST NOT appear in advisory *content* (stop condition).
# "determination" is intentionally excluded — its only occurrence is the structural attestation
# key ``determinations_made: false``; _content_blob() drops that key before scanning.
_BANNED_WORDS = (
    "liable",
    "liability",
    "entitled",
    "entitlement",
    "breach",
    "owes",
    "must pay",
    "at fault",
    "negligent",
    "delay caused by",
    "responsible for the delay",
    "days owed",
)


def _content_blob(report: dict) -> str:
    """Serialize only the human-facing content (items + summary + unsupported note), excluding the
    structural attestation keys (e.g. ``determinations_made``), then lower-case for scanning."""
    content = {
        "exposure": report.get("exposure"),
        "summary": report.get("summary"),
        "unsupported_categories": report.get("unsupported_categories"),
    }
    return json.dumps(content).lower()


def _db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        path = Path(tf.name)
    SQLiteMigrator(db_path=str(path)).apply()
    return path


def _signal(
    db: Path,
    *,
    record_key: str,
    endpoint_id: str,
    signal_type: str,
    importance: str = "medium",
    due: str | None = None,
) -> None:
    emit_action_signal(
        project_key="tropical",
        record_key=record_key,
        endpoint_id=endpoint_id,
        signal_type=signal_type,
        importance=importance,
        due_at_utc=due,
        now_utc=_NOW,
        db_path=db,
    )


def _live_record(
    db: Path,
    *,
    endpoint_id: str,
    record_id: str,
    review: bool = False,
    source_url: str | None = None,
    canonical: dict | None = None,
) -> str:
    """Insert a minimal procore_live_records row; returns its record_key."""
    conn = get_connection(str(db))
    conn.execute("PRAGMA foreign_keys=OFF")  # test seed: skip the sync-run FK (throwaway DB)
    conn.execute(
        """
        INSERT INTO procore_live_records (
          project_key, procore_project_id, endpoint_id, parent_procore_id, procore_record_id,
          canonical_json_redacted, source_url_redacted, review_required,
          first_seen_at_utc, last_seen_at_utc, last_sync_run_id, raw_body_persisted
        ) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            "tropical",
            "P1",
            endpoint_id,
            record_id,
            json.dumps(canonical or {}),
            source_url,
            1 if review else 0,
            _NOW,
            _NOW,
            "run-1",
        ),
    )
    conn.commit()
    return "|".join(["tropical", endpoint_id, "", record_id])


def _seed(db: Path) -> None:
    """One signal per exposure category, plus an unmapped signal that must be skipped."""
    _signal(
        db,
        record_key="tropical|rfis||1",
        endpoint_id="rfis",
        signal_type="rfi_overdue",
        importance="high",
        due=_PAST,
    )
    _signal(
        db,
        record_key="tropical|submittals||2",
        endpoint_id="submittals",
        signal_type="submittal_overdue",
        due=_PAST,
    )
    _signal(
        db,
        record_key="tropical|schedule-activities||3",
        endpoint_id="schedule-activities",
        signal_type="activity_zero_float",
    )
    _signal(
        db,
        record_key="tropical|meetings||4",
        endpoint_id="meetings",
        signal_type="meeting_topic_open_high_priority",
        importance="high",
    )
    _signal(
        db,
        record_key="tropical|inspections||5",
        endpoint_id="inspections",
        signal_type="inspection_overdue",
        due=_PAST,
    )
    _signal(
        db,
        record_key="tropical|punch-items||6",
        endpoint_id="punch-items",
        signal_type="punch_due_tomorrow",
        due=_FUTURE,
    )
    _signal(
        db,
        record_key="tropical|rfis||7",
        endpoint_id="rfis",
        signal_type="rfi_schedule_impact_flagged",
    )
    # unmapped (cost) signal — must not become a schedule-exposure item
    _signal(
        db,
        record_key="tropical|budget||8",
        endpoint_id="budget",
        signal_type="budget_change_posted",
    )


def _exp(db: Path | None, **kw):
    return build_schedule_exposure("tropical", now_utc=_NOW, db_path=db, **kw)


def test_classifies_all_expected_categories() -> None:
    db = _db()
    _seed(db)
    by_cat = _exp(db)["summary"]["by_category"]
    for c in (
        "overdue_rfi",
        "overdue_submittal",
        "critical_or_low_float_activity",
        "meeting_action_topic",
        "inspection_punch_blocking",
        "schedule_impact_flag",
        "daily_log_delay",
    ):
        assert c in by_cat
    assert by_cat["overdue_rfi"] == 1
    assert by_cat["overdue_submittal"] == 1
    assert by_cat["critical_or_low_float_activity"] == 1
    assert by_cat["meeting_action_topic"] == 1
    assert by_cat["inspection_punch_blocking"] == 2  # inspection + punch
    assert by_cat["schedule_impact_flag"] == 1


def test_unmapped_signal_skipped() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    assert all(it["signal_type"] != "budget_change_posted" for it in out["exposure"])
    assert out["summary"]["total"] == 7


def test_daily_log_unsupported() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    assert out["summary"]["by_category"]["daily_log_delay"] == 0
    cats = [u["category"] for u in out["unsupported_categories"]]
    assert "daily_log_delay" in cats


def test_overdue_status_and_days() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    overdue = [it for it in out["exposure"] if it["status"] == "overdue"]
    assert overdue
    for it in overdue:
        assert it["days_overdue"] is not None and it["days_overdue"] >= 1
        assert "past_due_date" in it["reason_codes"]
    assert out["summary"]["overdue"] == len(overdue)


def test_upcoming_status() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    punch = [it for it in out["exposure"] if it["signal_type"] == "punch_due_tomorrow"]
    assert punch and punch[0]["status"] == "upcoming"
    assert punch[0]["days_overdue"] is None


def test_review_required_high_sensitivity() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    sensitive = [
        it
        for it in out["exposure"]
        if it["exposure_category"]
        in (
            "overdue_rfi",
            "overdue_submittal",
            "critical_or_low_float_activity",
            "inspection_punch_blocking",
        )
    ]
    assert sensitive
    for it in sensitive:
        assert it["review_required"] is True
        assert "review_required_high_sensitivity" in it["reason_codes"]
    assert out["summary"]["review_required"] >= len(sensitive)


def test_review_required_record_flag_and_source() -> None:
    db = _db()
    rk = _live_record(
        db,
        endpoint_id="meetings",
        record_id="4",
        review=True,
        source_url="https://app.procore.com/REDACTED",
    )
    _signal(
        db, record_key=rk, endpoint_id="meetings", signal_type="meeting_topic_open_high_priority"
    )
    out = _exp(db)
    item = next(it for it in out["exposure"] if it["record_key"] == rk)
    assert item["review_required"] is True
    assert "review_required_record" in item["reason_codes"]
    assert item["source_url_redacted"] == "https://app.procore.com/REDACTED"


def test_canonical_due_fallback() -> None:
    db = _db()
    rk = _live_record(db, endpoint_id="submittals", record_id="9", canonical={"due_date": _PAST})
    # signal carries no due date -> falls back to the canonical record's normalized due date
    _signal(db, record_key=rk, endpoint_id="submittals", signal_type="submittal_overdue")
    out = _exp(db)
    item = next(it for it in out["exposure"] if it["record_key"] == rk)
    assert item["status"] == "overdue"
    assert item["due_at_utc"] is not None


def test_category_filter() -> None:
    db = _db()
    _seed(db)
    out = _exp(db, exposure_category="inspection_punch_blocking")
    assert out["exposure"]
    assert all(it["exposure_category"] == "inspection_punch_blocking" for it in out["exposure"])


def test_importance_filter() -> None:
    db = _db()
    _seed(db)
    out = _exp(db, importance="high")
    assert out["exposure"]
    assert all(it["importance"] == "high" for it in out["exposure"])


def test_ordering_overdue_first() -> None:
    db = _db()
    _seed(db)
    items = _exp(db)["exposure"]
    rank = {"overdue": 0, "upcoming": 1, "no_due_date": 2}
    seq = [rank.get(it["status"], 3) for it in items]
    assert seq == sorted(seq)


def test_no_determination_language() -> None:
    db = _db()
    _seed(db)
    out = _exp(db)
    blob = _content_blob(out)
    for word in _BANNED_WORDS:
        assert word not in blob, f"determination word leaked: {word}"
    assert out["determinations_made"] is False
    assert out["no_raw_values_persisted"] is True
    assert out["no_live_call_performed"] is True


def test_empty_project() -> None:
    db = _db()
    out = _exp(db)
    assert out["summary"]["total"] == 0
    assert out["exposure"] == []
    assert out["summary"]["by_category"]["overdue_rfi"] == 0


def _patch_conn(monkeypatch: pytest.MonkeyPatch, db: Path) -> None:
    import hb_assistant.store.connection as conn_mod
    import hb_assistant.store.migrator as mig_mod
    import hb_assistant.store.procore_enrichment as enr_mod
    import hb_assistant.store.procore_schedule_exposure as exp_mod

    real = conn_mod.get_connection

    def _get(_: object = None) -> sqlite3.Connection:
        return real(str(db))

    for mod in (conn_mod, mig_mod, enr_mod, exp_mod):
        monkeypatch.setattr(mod, "get_connection", _get, raising=False)


def test_cli_json_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "sched.sqlite"
    SQLiteMigrator(db_path=str(db)).apply()
    _seed(db)
    _patch_conn(monkeypatch, db)
    res = runner.invoke(
        app,
        ["procore", "live", "schedule", "exposure", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in (
        "command",
        "ok",
        "phase",
        "project_key",
        "generated_at",
        "filters",
        "summary",
        "exposure",
        "exposure_truncated",
        "unsupported_categories",
        "no_live_call_performed",
        "no_raw_values_persisted",
        "determinations_made",
        "guardrails",
    ):
        assert key in payload, f"missing {key}"
    assert payload["ok"] is True
    assert payload["determinations_made"] is False
    blob = _content_blob(payload)
    for word in _BANNED_WORDS:
        assert word not in blob, f"determination word leaked: {word}"
