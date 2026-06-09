"""Phase 10 Checkpoint 6 — production-like daily run wrapper.

Covers conservative-cap defaults, status-file writing, latest-successful preservation on failure,
partial degraded brief, browser HTML outside the repo, repo-path refusal, raw-content boundary
(raw only in Obsidian/browser; never in status/persisted rows), forbidden-egress scrubbing,
governed/confirmed Obsidian write, no browser auto-open, guard-column invariants, and weekday-aware
date-policy threading (calendar window + carryover/next-week labels). Registry stays at 13 agents.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import daily_run as dr
from hb_assistant.construction.second_brain.local_ai import pipeline as pipeline_mod
from hb_assistant.construction.second_brain.local_ai import (
    DailyRunLaunchdManager,
    run_daily_local_agent,
)
from hb_assistant.construction.store import ConstructionStore

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

MON = "2026-06-15T05:00:00-04:00"  # Monday
WED = "2026-06-17T05:00:00-04:00"  # Wednesday
FRI = "2026-06-19T05:00:00-04:00"  # Friday


def _seed(
    db: str, *, n: int = 6, raw_subject: str | None = None, days_out: int = 0
) -> ConstructionStore:
    """Seed N upcoming calendar events (+ optional adversarial raw subject for one of them)."""
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    day = 15 + days_out
    for i in range(n):
        eid = f"ev{i}"
        conn.execute(
            """INSERT INTO calendar_event_index
               (event_index_id, source_id, graph_event_id_hash, start_datetime_utc,
                end_datetime_utc, subject_redacted, organizer_domain, is_online_meeting,
                is_cancelled, is_private, project_key)
               VALUES (?, 'src1', ?, ?, ?, ?, 'hb.com', 0, 0, 0, ?)""",
            (
                eid,
                f"gh{i}",
                f"2026-06-{day:02d}T15:00:00.0000000",
                f"2026-06-{day:02d}T16:00:00.0000000",
                f"[redacted-{i}]",
                f"PROJ-{i % 2}",
            ),
        )
    if raw_subject is not None:
        conn.execute(
            """INSERT INTO calendar_event_raw_content
               (raw_calendar_event_id, event_index_id, graph_event_id_hash, source_ref_hash,
                subject, location_display, organizer_name, start_datetime_utc, end_datetime_utc)
               VALUES (?, 'ev0', 'gh0', 'srh0', ?, 'Room 1', 'Jane Doe', ?, ?)""",
            ("raw0", raw_subject, "2026-06-15T15:00:00.0000000", "2026-06-15T16:00:00.0000000"),
        )
    conn.commit()
    conn.close()
    return s


def _dirs(tmp_path: Path) -> dict[str, str]:
    return {
        "browser_output_dir": str(tmp_path / "html"),
        "status_dir": str(tmp_path / "status"),
        "vault_brief_dir": str(tmp_path / "vault"),
    }


def _candidate_titles(db: str) -> list[str]:
    conn = sqlite3.connect(db)
    rows = [r[0] for r in conn.execute("SELECT title_redacted FROM daily_brief_action_candidates")]
    conn.close()
    return rows


# --- dry-run / status ----------------------------------------------------------


def test_dry_run_writes_status_no_browser(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    d = _dirs(tmp_path)
    out = run_daily_local_agent(store=s, now_utc=MON, db_path=db, dry_run=True, **d)
    assert out["status"] == "success" and out["dry_run"] is True
    assert (tmp_path / "status" / "latest-status.json").exists()
    assert not (tmp_path / "html" / "daily-brief-latest.html").exists()
    assert out["date_policy"]["label"] == "monday_carryover"


def test_status_file_has_date_policy_and_counts(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **_dirs(tmp_path)
    )
    blob = (tmp_path / "status" / "latest-status.json").read_text()
    assert '"date_policy"' in blob and '"monday_carryover"' in blob
    assert '"summary"' in blob and '"stages"' in blob


# --- caps / success / browser --------------------------------------------------


def test_conservative_caps_bound_persists(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, n=15)
    out = run_daily_local_agent(store=s, now_utc=MON, db_path=db, dry_run=False, **_dirs(tmp_path))
    cal = next(r for r in out["stages"] if r["stage"] == "calendar_prep")
    assert cal["persisted"] == 10  # default max_persist_per_stage


def test_success_writes_latest_and_pointer(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **_dirs(tmp_path)
    )
    assert out["status"] == "success"
    assert (tmp_path / "html" / "daily-brief-latest.html").exists()
    assert (tmp_path / "html" / "daily-brief-2026-06-15.html").exists()
    assert (tmp_path / "status" / "last-successful.json").exists()


def test_browser_output_is_outside_repo(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **_dirs(tmp_path)
    )
    repo = Path(__file__).resolve().parents[1]
    html_path = (tmp_path / "html" / "daily-brief-latest.html").resolve()
    assert repo not in html_path.parents


def test_repo_contained_output_refused(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    repo = str(Path(__file__).resolve().parents[1] / "scratch_x")
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=True,
        browser_output_dir=repo,
        status_dir=str(tmp_path / "status"),
    )
    assert out["status"] == "failure" and out["error"] == "output_path_inside_repo_refused"


# --- failure / partial preservation --------------------------------------------


def test_failure_preserves_last_good(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    d = _dirs(tmp_path)
    run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **d
    )
    latest = tmp_path / "html" / "daily-brief-latest.html"
    good_bytes = latest.read_bytes()
    # Force the render stage to fail on the next run.
    monkeypatch.setattr(
        pipeline_mod,
        "render_daily_brief",
        lambda **_k: (_ for _ in ()).throw(RuntimeError("render boom")),
    )
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **d
    )
    assert out["status"] == "failure" and out["ok"] is False
    assert latest.read_bytes() == good_bytes  # last good preserved, not clobbered
    assert (tmp_path / "status" / "latest-status.json").exists()


def test_partial_marks_degraded_attempted_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    monkeypatch.setattr(
        pipeline_mod,
        "run_follow_up_watch_scan",
        lambda **_k: (_ for _ in ()).throw(RuntimeError("fu boom")),
    )
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **_dirs(tmp_path)
    )
    assert out["status"] == "partial"
    attempted = tmp_path / "html" / "daily-brief-latest-attempted.html"
    assert attempted.exists() and "Partial" in attempted.read_text()
    assert not (tmp_path / "html" / "daily-brief-latest.html").exists()  # latest not updated


# --- raw boundary / egress -----------------------------------------------------


def test_raw_only_in_browser_not_status_or_persisted(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, raw_subject="ZEBRAQUARTERLY review")
    run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        include_raw=True,
        **_dirs(tmp_path),
    )
    html = (tmp_path / "html" / "daily-brief-2026-06-15.html").read_text()
    status = (tmp_path / "status" / "latest-status.json").read_text()
    assert "ZEBRAQUARTERLY" in html  # raw allowed in browser
    assert "ZEBRAQUARTERLY" not in status  # never in status file
    assert all("ZEBRAQUARTERLY" not in t for t in _candidate_titles(db))  # persisted redacted


def test_browser_egress_scrubbed(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(
        db, raw_subject="Sync https://evil.com/x?sig=tok join teams.microsoft.com/l/m a@b.com"
    )
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        include_raw=True,
        **_dirs(tmp_path),
    )
    assert out["egress_scan"]["clean"] is True
    html = (tmp_path / "html" / "daily-brief-2026-06-15.html").read_text()
    for forbidden in ("https://", "evil.com", "teams.microsoft.com", "sig=tok", "a@b.com"):
        assert forbidden not in html


# --- governed Obsidian ---------------------------------------------------------


def test_obsidian_requires_confirmation(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        write_obsidian=True,
        confirm_vault_write=False,
        **_dirs(tmp_path),
    )
    assert not (tmp_path / "vault" / "2026-06-15_daily_brief.md").exists()
    assert any("vault_write_requires_confirmation" in w for w in out["warnings"])


def test_obsidian_confirmed_writes_note(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    run_daily_local_agent(
        store=s,
        now_utc=MON,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=10,
        write_obsidian=True,
        confirm_vault_write=True,
        **_dirs(tmp_path),
    )
    assert (tmp_path / "vault" / "2026-06-15_daily_brief.md").exists()


# --- guardrails / no auto-open -------------------------------------------------


def test_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **_dirs(tmp_path)
    )
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    rows = conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall()
    conn.close()
    assert rows and all(all(v == 0 for v in row) for row in rows)


def test_no_browser_auto_open() -> None:
    # The wrapper must never open a browser — no webbrowser import / open invocation.
    src = Path(dr.__file__).read_text()
    assert "webbrowser" not in src
    assert "open_new" not in src


# --- date-policy threading -----------------------------------------------------


def test_friday_window_includes_next_week_events(tmp_path: Path) -> None:
    # Event 6 days out (next week) is inside Friday's next-week window but outside Wednesday's.
    db = str(tmp_path / "t.sqlite")
    s = _seed(db, n=3, days_out=6)  # events on 2026-06-21 (Sunday) → use a weekday next week
    # seed an explicit next-week weekday event
    conn = sqlite3.connect(db)
    conn.execute(
        """INSERT INTO calendar_event_index
           (event_index_id, source_id, graph_event_id_hash, start_datetime_utc, end_datetime_utc,
            subject_redacted, organizer_domain, is_online_meeting, is_cancelled, is_private, project_key)
           VALUES ('evNX', 'src1', 'ghNX', '2026-06-24T15:00:00.0000000',
                   '2026-06-24T16:00:00.0000000', '[redacted-nx]', 'hb.com', 0, 0, 0, 'PROJ-9')""",
    )
    conn.commit()
    conn.close()
    fri = run_daily_local_agent(store=s, now_utc=FRI, db_path=db, dry_run=True, **_dirs(tmp_path))
    assert fri["date_policy"]["label"] == "friday_next_week"
    fri_would = next(r for r in fri["stages"] if r["stage"] == "calendar_prep")["would_persist"]
    wed = run_daily_local_agent(
        store=s,
        now_utc=WED,
        db_path=db,
        dry_run=True,
        browser_output_dir=str(tmp_path / "h2"),
        status_dir=str(tmp_path / "s2"),
    )
    wed_would = next(r for r in wed["stages"] if r["stage"] == "calendar_prep")["would_persist"]
    assert fri_would > wed_would  # next-week event surfaced Friday, not mid-week


def test_receipt_carries_date_policy(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(store=s, now_utc=FRI, db_path=db, dry_run=True, **_dirs(tmp_path))
    dp = out["date_policy"]
    assert dp["label"] == "friday_next_week"
    assert dp["calendar_prep_end"].startswith("2026-06-26")


# --- launchd scheduler (weekday 5AM) -------------------------------------------

_TEST_LABEL = "com.hb.test.daily-local-agent-ckpt6"


def _mgr(**kw: object) -> DailyRunLaunchdManager:
    return DailyRunLaunchdManager(label=_TEST_LABEL, **kw)  # type: ignore[arg-type]


def test_plist_encodes_weekday_5am() -> None:
    plist = _mgr(time="05:00", weekdays_only=True).render_plist()
    sci = plist["StartCalendarInterval"]
    assert isinstance(sci, list) and len(sci) == 5  # Mon–Fri, no weekend entries
    assert [e["Weekday"] for e in sci] == [1, 2, 3, 4, 5]
    assert all(e["Hour"] == 5 and e["Minute"] == 0 for e in sci)


def test_plist_program_arguments() -> None:
    args = _mgr().render_plist()["ProgramArguments"]
    assert args[1:4] == ["second-brain", "daily-run", "run"]
    for flag in ("--apply", "--raw", "--write-obsidian", "--confirm-vault-write",
                 "--no-open-browser", "--weekdays-only"):
        assert flag in args


def test_all_days_uses_single_interval() -> None:
    sci = _mgr(weekdays_only=False).render_plist()["StartCalendarInterval"]
    assert isinstance(sci, dict) and sci["Hour"] == 5


def test_install_dry_run_writes_no_plist() -> None:
    mgr = _mgr()
    res = mgr.install(dry_run=True)
    assert res["action"] == "preview_install"
    assert not mgr.plist_path.exists()  # plan/dry-run never writes the plist
    assert "launchctl load" in res["commands"][0]


def test_uninstall_dry_run_writes_nothing() -> None:
    mgr = _mgr()
    res = mgr.uninstall(dry_run=True)
    assert res["action"] == "preview_uninstall"
    assert not mgr.plist_path.exists()


def test_status_reports_weekday_and_catchup() -> None:
    st = _mgr(time="05:00").status()
    assert st["weekdays_only"] is True
    assert st["catch_up_on_wake"] is True
    assert st["schedule_time_local"] == "05:00"


# --- CLI -----------------------------------------------------------------------

runner = CliRunner()


def test_cli_run_dry_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    res = runner.invoke(
        app,
        ["daily-run", "run", "--db", db, "--as-of", MON,
         "--browser-output-dir", str(tmp_path / "h"), "--status-dir", str(tmp_path / "s")],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["status"] == "success" and payload["dry_run"] is True
    assert payload["date_policy"]["label"] == "monday_carryover"


def test_cli_run_vault_write_requires_confirm(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed(db)
    res = runner.invoke(
        app,
        ["daily-run", "run", "--db", db, "--as-of", MON, "--apply", "--write-obsidian",
         "--browser-output-dir", str(tmp_path / "h"), "--status-dir", str(tmp_path / "s"),
         "--vault-brief-dir", str(tmp_path / "v")],
    )
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "vault_write_requires_confirmation"


def test_cli_scheduler_install_plan_encodes_weekdays() -> None:
    res = runner.invoke(app, ["daily-run", "scheduler", "install", "--confirm-vault-write"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["action"] == "preview_install"
    assert len(payload["plist"]["StartCalendarInterval"]) == 5


def test_cli_scheduler_install_requires_vault_confirm() -> None:
    res = runner.invoke(app, ["daily-run", "scheduler", "install"])  # write_obsidian default True
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "vault_write_requires_confirmation"


def test_cli_scheduler_status() -> None:
    res = runner.invoke(app, ["daily-run", "scheduler", "status"])
    assert res.exit_code == 0
    assert json.loads(res.output)["weekdays_only"] is True


# --- relationship-candidate stage opt-in (default off → scheduled run unchanged) ----------------


def test_default_schedule_excludes_relationship_stage(tmp_path: Path) -> None:
    """The scheduled run is unchanged: no relationship stage by default."""
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10, **_dirs(tmp_path)
    )
    stages = [r["stage"] for r in out["stages"]]
    assert "relationship_candidates" not in stages


def test_optin_runs_relationship_stage_before_render(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    out = run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10,
        include_relationship_candidates=True, **_dirs(tmp_path),
    )
    stages = [r["stage"] for r in out["stages"]]
    assert "relationship_candidates" in stages
    assert stages.index("relationship_candidates") < stages.index("daily_brief_render")


def test_scheduler_install_default_omits_relationship_flag() -> None:
    res = runner.invoke(app, ["daily-run", "scheduler", "install", "--confirm-vault-write"])
    assert res.exit_code == 0, res.output
    args = json.loads(res.output)["plist"]["ProgramArguments"]
    assert "--include-relationship-candidates" not in args


def test_scheduler_install_optin_includes_relationship_flag() -> None:
    res = runner.invoke(
        app,
        ["daily-run", "scheduler", "install", "--confirm-vault-write",
         "--include-relationship-candidates"],
    )
    assert res.exit_code == 0, res.output
    args = json.loads(res.output)["plist"]["ProgramArguments"]
    assert "--include-relationship-candidates" in args


# --- relationship scan-window controls (default off; defaults preserved) ------------------------


def test_scheduler_install_omits_scan_window_by_default() -> None:
    """Opt-in without scan options → plist omits the scan-window flags (stage defaults apply)."""
    res = runner.invoke(
        app,
        ["daily-run", "scheduler", "install", "--confirm-vault-write",
         "--include-relationship-candidates"],
    )
    assert res.exit_code == 0, res.output
    args = json.loads(res.output)["plist"]["ProgramArguments"]
    assert "--relationship-scan-threads" not in args
    assert "--relationship-scan-events" not in args


def test_scheduler_install_includes_scan_window_when_provided() -> None:
    res = runner.invoke(
        app,
        ["daily-run", "scheduler", "install", "--confirm-vault-write",
         "--include-relationship-candidates",
         "--relationship-scan-threads", "200", "--relationship-scan-events", "200"],
    )
    assert res.exit_code == 0, res.output
    args = json.loads(res.output)["plist"]["ProgramArguments"]
    assert args[args.index("--relationship-scan-threads") + 1] == "200"
    assert args[args.index("--relationship-scan-events") + 1] == "200"


def test_daily_run_passes_scan_window_into_relationship_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_daily_local_agent threads scan-window values into the relationship stage builder."""
    db = str(tmp_path / "t.sqlite")
    s = _seed(db)
    captured: dict[str, int] = {}

    def _spy(**kwargs):  # type: ignore[no-untyped-def]
        captured["scan_threads"] = kwargs.get("scan_threads")
        captured["scan_events"] = kwargs.get("scan_events")
        return {"ok": True, "applied": not kwargs.get("dry_run", True),
                "summary": {"would_persist": 0, "persisted": 0}}

    monkeypatch.setattr(pipeline_mod, "build_relationship_candidates", _spy)
    run_daily_local_agent(
        store=s, now_utc=MON, db_path=db, dry_run=False, max_persist_per_stage=10,
        include_relationship_candidates=True,
        relationship_scan_threads=200, relationship_scan_events=200, **_dirs(tmp_path),
    )
    assert captured == {"scan_threads": 200, "scan_events": 200}


def test_cli_daily_run_invalid_scan_window_fails_closed(tmp_path: Path) -> None:
    # ``--opt=value`` form so a negative value is parsed as the value, not a flag.
    # (write_obsidian defaults off → no need to pass it.)
    for bad in ("--relationship-scan-threads=0", "--relationship-scan-events=-5"):
        res = runner.invoke(
            app,
            ["daily-run", "run", "--db", str(tmp_path / "t.sqlite"), "--date", "2026-06-15",
             "--dry-run", "--no-generate-browser", "--status-dir", str(tmp_path / "s"), bad],
        )
        assert res.exit_code == 2
        assert json.loads(res.output)["error"] == "relationship_scan_window_must_be_positive"
