"""Phase 10 — deterministic calendar meeting-prep candidates (advisory, no writeback).

Covers calendar normalization/redaction (HTML→text, join-URL / dial-in / passcode / meeting-id
stripping, no full attendee list), bounded excerpts, the deterministic source-ref / project-key
fallbacks, dry-run zero writes, apply-requires-cap + max-persist, idempotent candidates,
guard-column invariants on daily_brief_action_candidates, the no-raw-content output proof, the
daily-brief calendar-section integration, and the CLI wiring.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import (
    build_calendar_prep_candidates,
    build_daily_brief_candidates,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

NOW = "2026-06-08T00:00:00+00:00"
BRIEF_DATE = "2026-06-08"

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
)

# A body that carries every artifact the normalizer must strip (join URL, Teams boilerplate,
# meeting id, passcode, dial-in/phone). None of these may survive into output or persisted rows.
_RICH_HTML = (
    "<p>Agenda: review submittals and schedule.</p>"
    "<a href='https://teams.microsoft.com/l/meetup-join/secretpath'>Join the meeting now</a>"
    " Phone Conference ID: 123 456 789# Passcode: hunter2"
    " Meeting ID: 999 888 777 Dial-in: +1 555-123-4567"
    # scheme-less link + email in visible body text (not inside a tag): must also be redacted.
    " Contact pm@hbcompany.com or visit teams.microsoft.com/l/meetup-join/abc for details."
)


def _seed_index(
    conn: sqlite3.Connection,
    *,
    event_index_id: str,
    start: str,
    end: str,
    subject_redacted: str = "[redacted-subject]",
    location_redacted: str | None = "[redacted-loc]",
    organizer_domain: str | None = "hbcompany.com",
    is_online_meeting: int = 0,
    online_meeting_provider: str | None = None,
    is_cancelled: int = 0,
    is_private: int = 0,
    project_key: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO calendar_event_index
            (event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc,
             subject_redacted, location_redacted, organizer_domain, is_online_meeting,
             online_meeting_provider, is_cancelled, is_private, project_key)
        VALUES (?, 'src1', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_index_id,
            f"gh-{event_index_id}",
            start,
            end,
            subject_redacted,
            location_redacted,
            organizer_domain,
            is_online_meeting,
            online_meeting_provider,
            is_cancelled,
            is_private,
            project_key,
        ),
    )


def _seed_raw(
    conn: sqlite3.Connection,
    *,
    event_index_id: str,
    start: str,
    end: str,
    body_html: str = "",
    join_url: str | None = None,
    online_meeting_provider: str | None = None,
    project_key: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO calendar_event_raw_content
            (raw_calendar_event_id, event_index_id, graph_event_id_hash, subject, body_html,
             join_url, online_meeting_provider, attendees_json, start_datetime_utc,
             end_datetime_utc, project_key)
        VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)
        """,
        (
            f"raw-{event_index_id}",
            event_index_id,
            f"gh-{event_index_id}",
            "Raw Secret Subject",  # raw subject must NEVER reach output
            body_html,
            join_url,
            online_meeting_provider,
            start,
            end,
            project_key,
        ),
    )


def _seed_attendees(conn: sqlite3.Connection, *, event_index_id: str, domains: list[str]) -> None:
    for i, dom in enumerate(domains):
        conn.execute(
            """
            INSERT INTO calendar_event_attendees
                (event_index_id, attendee_hash, attendee_domain, attendee_role, response_status)
            VALUES (?, ?, ?, 'required', 'accepted')
            """,
            (event_index_id, f"att-{event_index_id}-{i}", dom),
        )


def _store_with_events(db: str) -> ConstructionStore:
    """Two in-window events (one online w/ rich body + attendees, one in-person), one far-future,
    one cancelled-in-window, one private-in-window."""
    s = ConstructionStore(db_path=db)  # creates/migrates schema
    conn = sqlite3.connect(db)
    # ev1: tomorrow, online, rich redactable body, 3 attendees / 2 domains, no project_key.
    _seed_index(
        conn,
        event_index_id="ev1",
        start="2026-06-09T15:00:00.0000000",
        end="2026-06-09T16:00:00.0000000",
        is_online_meeting=1,
        online_meeting_provider="teamsForBusiness",
        project_key=None,
    )
    _seed_raw(
        conn,
        event_index_id="ev1",
        start="2026-06-09T15:00:00.0000000",
        end="2026-06-09T16:00:00.0000000",
        body_html=_RICH_HTML,
        join_url="https://teams.microsoft.com/l/meetup-join/secretpath",
        online_meeting_provider="teamsForBusiness",
    )
    _seed_attendees(
        conn, event_index_id="ev1", domains=["hbcompany.com", "hbcompany.com", "sub.com"]
    )
    # ev2: in 7 days, in-person, has project_key, no raw content row (index-only path).
    _seed_index(
        conn,
        event_index_id="ev2",
        start="2026-06-15T12:00:00.0000000",
        end="2026-06-15T13:00:00.0000000",
        project_key="PROJ-2",
    )
    _seed_attendees(conn, event_index_id="ev2", domains=["hbcompany.com"])
    # ev3: far future (outside 14d window) → excluded.
    _seed_index(
        conn,
        event_index_id="ev3",
        start="2026-07-20T12:00:00.0000000",
        end="2026-07-20T13:00:00.0000000",
    )
    # ev_cancelled: in window but cancelled → excluded.
    _seed_index(
        conn,
        event_index_id="evc",
        start="2026-06-10T12:00:00.0000000",
        end="2026-06-10T13:00:00.0000000",
        is_cancelled=1,
    )
    # ev_private: in window but private → excluded.
    _seed_index(
        conn,
        event_index_id="evp",
        start="2026-06-10T12:00:00.0000000",
        end="2026-06-10T13:00:00.0000000",
        is_private=1,
    )
    conn.commit()
    conn.close()
    return s


# --- windowing / shape / fallbacks ---------------------------------------------


def test_window_excludes_cancelled_private_and_far_future(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, lookahead_days=14)
    assert out["ok"] is True
    assert out["summary"]["events_in_window"] == 2  # ev1, ev2 only
    assert out["summary"]["events_considered"] == 2
    ids = {e["event_index_id"] for e in out["events"]}
    assert ids == {"ev1", "ev2"}


def test_deterministic_source_ref_and_project_fallback(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    a = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    b = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    assert a["summary"] == b["summary"]
    ev1 = next(e for e in a["events"] if e["event_index_id"] == "ev1")
    ev2 = next(e for e in a["events"] if e["event_index_id"] == "ev2")
    assert ev1["source_ref"].startswith("cal:")
    assert ev1["project_key"] == "__unassigned__"  # deterministic fallback (index had none)
    assert ev2["project_key"] == "PROJ-2"


def test_missing_source_ref_skipped_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    _seed_index(
        conn,
        event_index_id="",
        start="2026-06-09T12:00:00.0000000",
        end="2026-06-09T13:00:00.0000000",
    )
    conn.commit()
    conn.close()
    out = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=5
    )
    assert out["summary"]["skipped_no_source_refs"] == 1
    assert out["summary"]["persisted"] == 0


# --- normalization / redaction -------------------------------------------------


def test_join_url_and_meeting_artifacts_redacted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    ev1 = next(e for e in out["events"] if e["event_index_id"] == "ev1")
    excerpt = ev1["prep_excerpt"]
    # The agenda survives; every join/dial-in/passcode/meeting-id artifact (incl. scheme-less
    # links and email addresses in visible body text) is stripped.
    assert "Agenda" in excerpt
    for forbidden in (
        "teams.microsoft.com",
        "http",
        "secretpath",
        "hunter2",
        "123 456 789",
        "999 888 777",
        "555-123-4567",
        "Join the meeting now",
        "pm@hbcompany.com",
        "@",
    ):
        assert forbidden not in excerpt, forbidden
    # has_join_url is surfaced as a metadata flag (never the URL itself).
    assert ev1["has_join_url"] is True


def test_html_body_becomes_bounded_text(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    ev1 = next(e for e in out["events"] if e["event_index_id"] == "ev1")
    assert "<p>" not in ev1["prep_excerpt"]
    assert "</a>" not in ev1["prep_excerpt"]


def test_oversized_body_is_bounded(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    huge = "<p>" + ("agenda item ok " * 2000) + "</p>"  # >> 1200 char budget
    _seed_index(
        conn,
        event_index_id="big",
        start="2026-06-09T12:00:00.0000000",
        end="2026-06-09T13:00:00.0000000",
    )
    _seed_raw(
        conn,
        event_index_id="big",
        start="2026-06-09T12:00:00.0000000",
        end="2026-06-09T13:00:00.0000000",
        body_html=huge,
    )
    conn.commit()
    conn.close()
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    excerpt = out["events"][0]["prep_excerpt"]
    assert len(excerpt) <= 1200
    assert "…[truncated]" in excerpt


def test_no_full_attendee_list_or_emails_emitted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    ev1 = next(e for e in out["events"] if e["event_index_id"] == "ev1")
    # Only count + DISTINCT domains — no attendee array, names, or emails.
    assert ev1["attendee_count"] == 3
    assert ev1["participant_domains"] == ["hbcompany.com", "sub.com"]
    blob = json.dumps(out)
    assert "att-ev1" not in blob  # attendee hashes never surface
    assert "@" not in blob  # no email addresses anywhere


def test_raw_subject_never_in_output(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    blob = json.dumps(out)
    assert "Raw Secret Subject" not in blob  # title comes from index subject_redacted only
    assert out["events"][0]["title_redacted"] == "[redacted-subject]"


# --- dry-run / apply posture ---------------------------------------------------


def test_dry_run_writes_zero_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    assert out["applied"] is False
    assert out["summary"]["persisted"] == 0
    assert out["summary"]["would_persist"] == 2
    assert s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE) == []


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    try:
        build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "max_persist" in str(e)


def test_max_persist_caps_writes(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=1
    )
    assert out["summary"]["persisted"] == 1
    assert out["summary"]["would_persist"] == 2
    assert len(s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE)) == 1


def test_apply_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    out2 = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10
    )
    assert out2["summary"]["persisted"] == 0
    assert out2["summary"]["skipped_existing"] == 2
    assert len(s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE)) == 2


def test_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    rows = conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall()
    assert rows
    for row in rows:
        assert all(v == 0 for v in row)
    conn.close()


def test_persisted_rows_carry_no_raw_content(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    rows = s.list_daily_brief_action_candidates(brief_date=BRIEF_DATE, section="calendar")
    assert rows
    blob = json.dumps(rows)
    for forbidden in (
        "Raw Secret Subject",
        "Agenda",
        "teams.microsoft.com",
        "http",
        "secretpath",
        "hunter2",
        "@",
        "<p>",
    ):
        assert forbidden not in blob, forbidden
    for r in rows:
        assert r["section"] == "calendar"
        assert r["recommended_next_action"] == "review"


def test_calendar_does_not_mutate_event_tables(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    conn = sqlite3.connect(db)
    before = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("calendar_event_index", "calendar_event_raw_content", "calendar_event_attendees")
    }
    conn.close()
    build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    conn = sqlite3.connect(db)
    after = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("calendar_event_index", "calendar_event_raw_content", "calendar_event_attendees")
    }
    conn.close()
    assert before == after  # advisory only — never touches calendar source tables


# --- optional synthesis --------------------------------------------------------


def test_synthesize_off_by_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db)
    assert out["synthesis"] == {"requested": False}


def test_synthesize_without_client_fails_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    out = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, synthesize=True, client=None
    )
    assert out["synthesis"]["requested"] is True
    assert out["synthesis"]["ok"] is False
    assert out["synthesis"]["reason"] == "no_local_model_client"


def test_synthesize_rejects_malformed_model_output(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)

    class _BadClient:
        def generate_json(self, *, system: str, prompt: str) -> str:
            return "this is not json{"

    out = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, synthesize=True, client=_BadClient()
    )
    assert out["synthesis"]["requested"] is True
    assert out["synthesis"]["ok"] is False
    assert out["synthesis"]["reason"].startswith("synthesis_failed")


def test_synthesize_feeds_only_redacted_aggregates(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)

    class _SpyClient:
        captured = {}

        def generate_json(self, *, system: str, prompt: str) -> str:
            _SpyClient.captured = {"prompt": prompt}
            return json.dumps({"narrative": "prep", "prep_flags": ["external attendees"]})

    out = build_calendar_prep_candidates(
        store=s, now_utc=NOW, db_path=db, synthesize=True, client=_SpyClient()
    )
    assert out["synthesis"]["ok"] is True
    sent = _SpyClient.captured["prompt"]
    # only counts + domains — never event ids, raw subjects, excerpts, attendee hashes.
    for forbidden in ("ev1", "ev2", "Raw Secret Subject", "Agenda", "att-", "cal:"):
        assert forbidden not in sent, forbidden


# --- daily-brief convergence integration ---------------------------------------


def test_daily_brief_surfaces_calendar_section(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _store_with_events(db)
    build_calendar_prep_candidates(store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist=10)
    brief = build_daily_brief_candidates(store=s, now_utc=NOW)
    assert "calendar" in brief["brief"]
    assert len(brief["brief"]["calendar"]) == 2
    for item in brief["brief"]["calendar"]:
        assert item["title_redacted"] == "[redacted-subject]"


# --- CLI -----------------------------------------------------------------------


def test_cli_dry_run_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _store_with_events(db)
    res = runner.invoke(
        app,
        [
            "calendar-prep",
            "build",
            "--db",
            db,
            "--as-of",
            NOW,
            "--lookahead-days",
            "14",
            "--summary",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["applied"] is False
    assert payload["summary"]["persisted"] == 0
    assert payload["summary"]["would_persist"] == 2
    assert len(payload["events"]) == 2


def test_cli_non_summary_drops_event_excerpts(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _store_with_events(db)
    res = runner.invoke(app, ["calendar-prep", "build", "--db", db, "--as-of", NOW])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["events"] == []  # no per-event excerpts unless --summary
    assert "Agenda" not in res.output


def test_cli_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _store_with_events(db)
    res = runner.invoke(app, ["calendar-prep", "build", "--db", db, "--apply"])
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "apply_requires_max_persist"


def test_cli_apply_capped(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _store_with_events(db)
    res = runner.invoke(
        app,
        ["calendar-prep", "build", "--db", db, "--apply", "--max-persist", "1", "--as-of", NOW],
    )
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["summary"]["persisted"] == 1
