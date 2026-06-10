"""Phase 10 — daily-run scheduler hardening (offline; never runs launchctl).

Proves the install preview / status surface the effective default-on Model Enriched Intelligence +
V45 email raw enrichment posture, that ProgramArguments grammar is valid and never auto-opens the
browser, that readiness reports the expanded diagnostic fields, and that a repo-contained browser
output dir is refused by the daily run (output-path guard).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai.daily_run import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.daily_run_scheduler import (
    DailyRunLaunchdManager,
)
from hb_assistant.construction.store import ConstructionStore


def test_program_arguments_include_default_on_posture_and_no_auto_open() -> None:
    mgr = DailyRunLaunchdManager()
    args = mgr.render_plist()["ProgramArguments"]
    assert args[1:4] == ["second-brain", "daily-run", "run"]
    assert "--model-enriched-intelligence" in args
    assert "--email-raw-enrichment" in args
    assert "--no-open-browser" in args
    assert "--open-browser" not in args


def test_disabled_posture_emits_negated_flags() -> None:
    mgr = DailyRunLaunchdManager(model_enriched_intelligence=False, email_raw_enrichment=False)
    args = mgr.render_plist()["ProgramArguments"]
    assert "--no-model-enriched-intelligence" in args
    assert "--no-email-raw-enrichment" in args


def test_install_preview_effective_config_and_readiness_fields() -> None:
    preview = DailyRunLaunchdManager().preview_install()
    eff = preview["effective_config"]
    assert eff["model_enriched_intelligence"] is True
    assert eff["email_raw_enrichment"] is True
    assert eff["browser_auto_open"] is False
    assert eff["browser_generation"] is True
    r = preview["readiness"]
    for key in (
        "executable_ready", "executable_path_redacted", "working_directory_ready",
        "command_grammar_valid", "log_directories_writable", "plist_exists",
        "blocking", "blocking_diagnostics",
    ):
        assert key in r
    # Redacted paths must not leak the absolute home prefix.
    assert str(Path.home()) not in r["executable_path_redacted"]


def test_status_reports_posture_and_catch_up_and_last_run() -> None:
    status = DailyRunLaunchdManager().status()
    assert status["effective_config"]["model_enriched_intelligence"] is True
    assert status["catch_up_on_wake"] is True
    assert "catch_up_on_wake_explanation" in status
    assert "weekday_intervals" in status
    assert "last_run" in status
    # weekday-only schedule → five Mon–Fri intervals
    assert isinstance(status["start_calendar_interval"], list)
    assert len(status["start_calendar_interval"]) == 5


def test_repo_contained_browser_dir_refused_by_daily_run() -> None:
    with tempfile.TemporaryDirectory() as t:
        store = ConstructionStore(db_path=str(Path(t) / "b.db"))
        repo_root = Path(__file__).resolve().parents[1]
        res = run_daily_local_agent(
            store=store,
            now_utc="2026-06-09T05:00:00-04:00",
            dry_run=False,
            browser_output_dir=str(repo_root / "build" / "evil-html"),
            status_dir=str(Path(t) / "status"),
        )
        assert res["ok"] is False
        assert res["status"] == "failure"
        assert res["error"] == "output_path_inside_repo_refused"
