"""Phase 10 — daily-brief rendering / consumption (read-only, advisory, no writeback).

Covers rendering the convergence table into a redacted brief (JSON + Markdown), deterministic
ordering, section/project filtering, the empty-brief path, no-mutation/no-re-persist, both file-write
modes (governed vault dir + explicit non-repo path) with path-safety + marker-bounded preservation,
redaction (no raw bodies/URLs/emails/tokens), and CLI wiring. Registry stays at 13 agents.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.daily_brief.output import SECTION_START
from hb_assistant.construction.second_brain.local_ai import (
    render_daily_brief,
    write_rendered_brief_to_path,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

NOW = "2026-06-08T00:00:00+00:00"
DATE = "2026-06-08"

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


def _seed(db: str) -> ConstructionStore:
    """One candidate per section (actions/waiting/follow_up/procore/calendar) across two projects."""
    s = ConstructionStore(db_path=db)
    rows = [
        ("actions", "Reply to RFI", "PROJ-A", 60, "open commitment"),
        ("waiting", "Awaiting owner sign-off", "PROJ-A", 20, "waiting_on_others"),
        ("follow_up", "Stale follow-up", "PROJ-B", 30, "stale 14d"),
        ("procore", "12 open invoice_payment_due signals", "PROJ-B", 10, "financial"),
        ("calendar", "[redacted-subject]", None, 10, "3 attendees · 2 domains · online"),
    ]
    for i, (section, title, proj, prio, reason) in enumerate(rows):
        s.insert_daily_brief_action_candidate(
            brief_date=DATE,
            section=section,
            title_redacted=title,
            confidence=1.0,
            project_key=proj,
            priority=prio,
            reason_redacted=reason,
            recommended_next_action="review",
            group_key=f"{section}|{i}",
        )
    return s


def _row_count(db: str) -> int:
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM daily_brief_action_candidates").fetchone()[0]
    conn.close()
    return n


# --- render shape / sections / determinism -------------------------------------


def test_render_reads_convergence_table(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = render_daily_brief(store=s, brief_date=DATE)
    assert out["ok"] is True
    assert out["summary"]["total_for_date"] == 5
    assert out["summary"]["rendered"] == 5
    assert out["guardrails"]["read_only"] is True


def test_empty_candidate_set_is_valid_empty_brief(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    out = render_daily_brief(store=s, brief_date=DATE)
    assert out["ok"] is True
    assert out["summary"]["rendered"] == 0
    assert out["sections"] == []
    assert "No review candidates" in out["markdown"]


def test_sections_grouped_into_display_headings(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = render_daily_brief(store=s, brief_date=DATE)
    displays = [sec["display"] for sec in out["sections"]]
    # All five internal sections map to distinct display headings, in canonical order.
    assert displays == [
        "Today's Actions",
        "Waiting / Follow-Up",
        "Risks / Watch Items",
        "Procore Project Signals",
        "Calendar Prep",
    ]


def test_unknown_section_routes_to_unassigned(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    s.insert_daily_brief_action_candidate(
        brief_date=DATE,
        section="mystery",
        title_redacted="Odd item",
        confidence=1.0,
        group_key="mystery|1",
    )
    out = render_daily_brief(store=s, brief_date=DATE)
    displays = [sec["display"] for sec in out["sections"]]
    assert "Unassigned / Needs Review" in displays


def test_deterministic_ordering(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    a = render_daily_brief(store=s, brief_date=DATE)
    b = render_daily_brief(store=s, brief_date=DATE)
    assert a["markdown"] == b["markdown"]
    assert a["sections"] == b["sections"]


def test_section_filter(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = render_daily_brief(store=s, brief_date=DATE, sections=["calendar", "procore"])
    assert out["summary"]["rendered"] == 2
    assert out["summary"]["skipped_by_filter"] == 3
    displays = {sec["display"] for sec in out["sections"]}
    assert displays == {"Procore Project Signals", "Calendar Prep"}


def test_project_filter(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = render_daily_brief(store=s, brief_date=DATE, project_key="PROJ-A")
    assert out["summary"]["rendered"] == 2  # actions + waiting
    for sec in out["sections"]:
        for it in sec["items"]:
            assert it["project_key"] == "PROJ-A"


def test_limit_caps_and_reports_skip(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = render_daily_brief(store=s, brief_date=DATE, limit=2)
    assert out["summary"]["rendered"] == 2
    assert out["summary"]["skipped_by_limit"] == 3


# --- no mutation / no re-persist -----------------------------------------------


def test_render_does_not_mutate_or_repersist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    before = _row_count(db)
    render_daily_brief(store=s, brief_date=DATE)
    render_daily_brief(store=s, brief_date=DATE)
    assert _row_count(db) == before == 5
    # guard columns remain zero (nothing was written).
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    for row in conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall():
        assert all(v == 0 for v in row)
    conn.close()


# --- redaction -----------------------------------------------------------------


def test_no_raw_content_in_output(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = render_daily_brief(store=s, brief_date=DATE)
    blob = json.dumps(out)
    for forbidden in ("http", "@", "<", "join_url", "body_html", "token", "secret", "passcode"):
        assert forbidden not in blob, forbidden


# --- explicit-path write mode --------------------------------------------------


def test_explicit_write_dry_run_writes_nothing(tmp_path: Path) -> None:
    target = tmp_path / "brief.md"
    out = write_rendered_brief_to_path(inner_markdown="# x", output_path=str(target), dry_run=True)
    assert out["ok"] is True and out["written"] is False
    assert out["would_write_bytes"] > 0
    assert not target.exists()


def test_explicit_write_apply_creates_marker_bounded_file(tmp_path: Path) -> None:
    target = tmp_path / "brief.md"
    out = write_rendered_brief_to_path(
        inner_markdown="# Daily Brief — 2026-06-08", output_path=str(target), dry_run=False
    )
    assert out["written"] is True
    text = target.read_text(encoding="utf-8")
    assert SECTION_START in text
    assert "Daily Brief" in text


def test_explicit_write_relative_path_rejected(tmp_path: Path) -> None:
    out = write_rendered_brief_to_path(
        inner_markdown="x", output_path="rel/brief.md", dry_run=False
    )
    assert out["ok"] is False
    assert out["error"] == "output_path_must_be_absolute"


def test_explicit_write_inside_repo_rejected() -> None:
    from hb_assistant.config.path_policy import PathPolicy

    repo = PathPolicy().resolve_repo_root()
    out = write_rendered_brief_to_path(
        inner_markdown="x", output_path=str(repo / "should_not_write.md"), dry_run=False
    )
    assert out["ok"] is False
    assert out["error"] == "output_path_inside_repo_refused"


def test_explicit_write_refuses_foreign_file(tmp_path: Path) -> None:
    target = tmp_path / "user_notes.md"
    target.write_text("# My own notes\nimportant user content\n", encoding="utf-8")
    out = write_rendered_brief_to_path(inner_markdown="x", output_path=str(target), dry_run=False)
    assert out["ok"] is False
    assert out["error"] == "refuse_overwrite_foreign_file"
    # user file untouched
    assert "important user content" in target.read_text(encoding="utf-8")


def test_explicit_write_marker_bounded_preserves_outside_block(tmp_path: Path) -> None:
    target = tmp_path / "brief.md"
    # First write seeds the owned block; then add user content OUTSIDE the markers.
    write_rendered_brief_to_path(inner_markdown="first", output_path=str(target), dry_run=False)
    text = target.read_text(encoding="utf-8")
    target.write_text(text + "\n## User Appendix\nkeep me\n", encoding="utf-8")
    # Re-write replaces only the owned block.
    write_rendered_brief_to_path(inner_markdown="second", output_path=str(target), dry_run=False)
    final = target.read_text(encoding="utf-8")
    assert "keep me" in final  # out-of-block content preserved
    assert "second" in final
    assert "first" not in final


# --- CLI -----------------------------------------------------------------------


def test_cli_render_default_reads_and_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    before = _row_count(db)
    res = runner.invoke(app, ["daily-brief", "render", "--db", db, "--date", DATE, "--summary"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["summary"]["rendered"] == 5
    assert "write" not in payload
    assert _row_count(db) == before  # read-only


def test_cli_markdown_included(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    res = runner.invoke(app, ["daily-brief", "render", "--db", db, "--date", DATE, "--markdown"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["markdown"].startswith("# Daily Brief — 2026-06-08")
    assert "## Today's Actions" in payload["markdown"]


def test_cli_explicit_write(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    target = tmp_path / "out.md"
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "render",
            "--db",
            db,
            "--date",
            DATE,
            "--markdown",
            "--write",
            "--output-path",
            str(target),
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["write"]["mode"] == "explicit_path"
    assert payload["write"]["written"] is True
    assert target.exists()
    # no raw content / urls in the written file
    blob = target.read_text(encoding="utf-8")
    for forbidden in ("http", "join_url", "token", "<a "):
        assert forbidden not in blob


def test_cli_governed_write_to_temp_vault_dir(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    vault_dir = tmp_path / "vault_briefs"
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "render",
            "--db",
            db,
            "--date",
            DATE,
            "--write",
            "--vault-brief-dir",
            str(vault_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["write"]["mode"] == "governed_vault"
    assert payload["write"]["written"] is True
    written = vault_dir / f"{DATE}_daily_brief.md"
    assert written.exists()
    assert SECTION_START in written.read_text(encoding="utf-8")


def test_cli_write_inside_repo_rejected(tmp_path: Path) -> None:
    from hb_assistant.config.path_policy import PathPolicy

    db = str(tmp_path / "t.sqlite")
    _seed(db)
    repo = PathPolicy().resolve_repo_root()
    res = runner.invoke(
        app,
        [
            "daily-brief",
            "render",
            "--db",
            db,
            "--date",
            DATE,
            "--write",
            "--output-path",
            str(repo / "nope.md"),
        ],
    )
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "output_path_inside_repo_refused"


# --- raw local-consumption enrichment (--raw) ----------------------------------

import hashlib  # noqa: E402

_PROCORE_COLS = (
    "action_signal_id, project_key, record_key, endpoint_id, signal_type, signal_status, "
    "importance, due_at_utc, owner_entity_key, title_redacted, summary_redacted, "
    "reason_codes_json, first_detected_at_utc, last_seen_at_utc, resolved_at_utc, "
    "source_change_event_id, metadata_json"
)


def _seed_calendar_raw(db: str, *, event_index_id: str, subject: str, location: str) -> str:
    """Seed a raw calendar row + a matching calendar candidate; return the real subject."""
    conn = sqlite3.connect(db)
    conn.execute(
        """
        INSERT INTO calendar_event_raw_content
            (raw_calendar_event_id, event_index_id, graph_event_id_hash, subject, location_display,
             organizer_name, attendees_json, start_datetime_utc, end_datetime_utc)
        VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)
        """,
        (
            f"raw-{event_index_id}",
            event_index_id,
            f"gh-{event_index_id}",
            subject,
            location,
            "Jane PM",
            "2026-06-09T15:00:00",
            "2026-06-09T16:00:00",
        ),
    )
    conn.commit()
    conn.close()
    return "cal:" + hashlib.sha256(event_index_id.encode("utf-8")).hexdigest()[:32]


def test_raw_default_off_keeps_redacted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    sref = _seed_calendar_raw(
        db, event_index_id="ev1", subject="Owner Coordination Meeting", location="Conf Room A"
    )
    s.insert_daily_brief_action_candidate(
        brief_date=DATE,
        section="calendar",
        title_redacted="[redacted-subject]",
        confidence=1.0,
        group_key=sref,
    )
    out = render_daily_brief(store=s, brief_date=DATE)  # default: include_raw False
    assert out["include_raw"] is False
    assert out["guardrails"]["redacted_fields_only"] is True
    assert "Owner Coordination Meeting" not in json.dumps(out)
    assert out["sections"][0]["items"][0]["display_title"] == "[redacted-subject]"


def test_raw_calendar_shows_real_subject_and_location(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    sref = _seed_calendar_raw(
        db, event_index_id="ev1", subject="Owner Coordination Meeting", location="Conf Room A"
    )
    s.insert_daily_brief_action_candidate(
        brief_date=DATE,
        section="calendar",
        title_redacted="[redacted-subject]",
        confidence=1.0,
        group_key=sref,
    )
    out = render_daily_brief(store=s, brief_date=DATE, include_raw=True)
    item = out["sections"][0]["items"][0]
    assert item["display_title"] == "Owner Coordination Meeting"
    assert item["raw_title"] == "Owner Coordination Meeting"
    assert "Conf Room A" in item["raw_detail"]
    assert "Owner Coordination Meeting" in out["markdown"]
    assert out["include_raw"] is True
    assert out["guardrails"]["raw_local_consumption_only"] is True
    assert out["guardrails"]["redacted_fields_only"] is False


def test_raw_procore_shows_real_signal_titles(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)

    def sig(sid: str, title: str) -> tuple:
        return (
            sid,
            "alpha",
            f"alpha|ep|{sid}",
            "ep",
            "inspection_item_unanswered",
            "open",
            "high",
            None,
            "oh",
            title,
            "sum",
            "[]",
            "2026-05-01",
            "2026-06-01",
            None,
            None,
            "{}",
        )

    conn.executemany(
        f"INSERT INTO procore_action_signals ({_PROCORE_COLS}) VALUES ({', '.join(['?'] * 17)})",
        [sig("s1", "Footing inspection overdue"), sig("s2", "Rebar inspection pending")],
    )
    conn.commit()
    conn.close()
    s.insert_daily_brief_action_candidate(
        brief_date=DATE,
        section="procore",
        title_redacted="2 open inspection_item_unanswered signals",
        confidence=1.0,
        project_key="alpha",
        group_key="alpha|inspection_item_unanswered",
    )
    out = render_daily_brief(store=s, brief_date=DATE, include_raw=True)
    item = next(it for sec in out["sections"] for it in sec["items"] if it["section"] == "procore")
    assert "Footing inspection overdue" in item["raw_detail"]
    assert "Rebar inspection pending" in item["raw_detail"]


def test_raw_does_not_mutate_or_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    sref = _seed_calendar_raw(db, event_index_id="ev1", subject="Real Subject", location="Loc")
    s.insert_daily_brief_action_candidate(
        brief_date=DATE,
        section="calendar",
        title_redacted="[redacted-subject]",
        confidence=1.0,
        group_key=sref,
    )
    before = _row_count(db)
    render_daily_brief(store=s, brief_date=DATE, include_raw=True)
    # persisted candidate row is untouched (still redacted) and count unchanged.
    assert _row_count(db) == before
    rows = s.list_daily_brief_action_candidates(brief_date=DATE)
    assert rows[0]["title_redacted"] == "[redacted-subject]"


def test_cli_raw_flag_and_explicit_write_still_repo_safe(tmp_path: Path) -> None:
    from hb_assistant.config.path_policy import PathPolicy

    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    sref = _seed_calendar_raw(db, event_index_id="ev1", subject="Real Meeting", location="Room 1")
    s.insert_daily_brief_action_candidate(
        brief_date=DATE,
        section="calendar",
        title_redacted="[redacted-subject]",
        confidence=1.0,
        group_key=sref,
    )
    # --raw surfaces real content to local stdout
    res = runner.invoke(
        app, ["daily-brief", "render", "--db", db, "--date", DATE, "--raw", "--markdown"]
    )
    assert res.exit_code == 0, res.output
    assert "Real Meeting" in json.loads(res.output)["markdown"]
    # --raw must NOT weaken path safety: writing raw into the repo is still refused.
    repo = PathPolicy().resolve_repo_root()
    res2 = runner.invoke(
        app,
        [
            "daily-brief",
            "render",
            "--db",
            db,
            "--date",
            DATE,
            "--raw",
            "--markdown",
            "--write",
            "--output-path",
            str(repo / "raw_nope.md"),
        ],
    )
    assert res2.exit_code == 2
    assert json.loads(res2.output)["error"] == "output_path_inside_repo_refused"
    assert not (repo / "raw_nope.md").exists()
