"""Tests for the cross-platform launcher + daily source-refresh scheduler.

Uses the autouse ``isolated_hb_pa_config`` fixture (temp app-support). Real processes
are never spawned (ProcessManager is monkeypatched); the orchestrator is patched for
run-capture tests; ``due`` is fed a fixed ``now``.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import hb_assistant.launcher.profiles as profiles_mod
import hb_assistant.scheduler.daily_source_refresh as dsr_mod
from hb_assistant.cli.main import app
from hb_assistant.config.loader import load_config
from hb_assistant.launcher.models import ProcessRecord
from hb_assistant.launcher.process_manager import ProcessManager
from hb_assistant.launcher.profiles import ProfileCollisionError, resolve_profile, snapshot_source_db
from hb_assistant.launcher.service import LauncherService, _hb_executable
from hb_assistant.launcher.session_state import SessionState
from hb_assistant.scheduler.daily_source_refresh import DailySourceRefreshJob
from hb_assistant.scheduler.due import compute_next_run, decide_catch_up
from hb_assistant.scheduler.runner import SchedulerRunner
from hb_assistant.scheduler.state import SchedulerState
from hb_assistant.source_refresh.orchestrator import SourceRefreshOrchestrator
from hb_assistant.store.migrator import SQLiteMigrator

runner = CliRunner()


def _migrate(db: Path) -> None:
    db.parent.mkdir(parents=True, exist_ok=True)
    SQLiteMigrator(db).apply()


def _canned_summary(**over: Any) -> dict[str, Any]:
    base = {
        "status": "ok",
        "sqlite_upsert_summary": {"total": {"inserted": 0, "updated": 0}},
        "guardrails": {
            "no_procore_writeback": True,
            "no_m365_writeback": True,
            "no_vectors_in_sqlite": True,
        },
    }
    base.update(over)
    return base


# --- profiles / isolation --------------------------------------------------------


def test_dev_prod_db_isolation() -> None:
    dev = resolve_profile("dev")
    prod = resolve_profile("production")
    assert dev.db_path != prod.db_path
    assert prod.db_path != dev.db_path
    assert "(Dev)" in str(dev.app_support_root)


def test_collision_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    prod_root = resolve_profile("production").app_support_root
    monkeypatch.setattr(profiles_mod, "_dev_root", lambda _root: prod_root)
    with pytest.raises(ProfileCollisionError):
        resolve_profile("dev")


def test_dev_resolves_repo_and_executable() -> None:
    dev = resolve_profile("dev")
    repo = dev.path_policy.resolve_repo_root()
    assert (repo / "pyproject.toml").exists()
    exe = _hb_executable()
    assert isinstance(exe, str) and exe


def test_production_resolves_executable() -> None:
    resolve_profile("production")
    assert _hb_executable()


# --- launcher status / start (plan) ----------------------------------------------


def test_launcher_status_reports_fields() -> None:
    result = runner.invoke(app, ["launcher", "status", "--environment", "dev", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    for key in ("build_sha", "db_path", "executable_path", "python_path", "config_profile",
                "environment_mode", "scheduler_status"):
        assert key in d
    assert d["environment"] == "dev"


def test_launcher_dev_plan_does_not_spawn(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(self: Any, spec: Any) -> Any:  # spawn must not be called in plan mode
        raise AssertionError("spawn called during --plan")

    monkeypatch.setattr(ProcessManager, "spawn", _boom)
    result = runner.invoke(app, ["launcher", "dev", "--plan", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    statuses = {p["name"]: p["status"] for p in d["processes"]}
    assert all(s in ("planned", "skipped") for s in statuses.values())


# --- close policy ----------------------------------------------------------------


def _seed_session(env: str, records: list[ProcessRecord]) -> Path:
    profile = resolve_profile(env)  # type: ignore[arg-type]
    state = SessionState(environment=profile.environment, processes=records)
    state.save(profile.launcher_session_path)
    return profile.launcher_session_path


def _rec(name: str, *, keep: bool) -> ProcessRecord:
    return ProcessRecord(
        name=name,  # type: ignore[arg-type]
        pid=424242,
        started_at="2026-06-07T00:00:00+00:00",
        argv=["x"],
        status="running",
        keep_in_background=keep,
    )


def test_close_quit_terminates_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: True)
    killed: list[str] = []
    monkeypatch.setattr(
        ProcessManager,
        "terminate",
        lambda self, rec, **k: (killed.append(rec.name) or "exited"),  # type: ignore[func-returns-value]
    )
    _seed_session("production", [_rec("frontend", keep=False), _rec("mcp", keep=True)])
    result = runner.invoke(app, ["launcher", "close", "--environment", "production",
                                 "--action", "quit", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert set(d["terminated"]) == {"frontend", "mcp"}
    assert d["background_active"] is False
    assert "frontend" in killed and "mcp" in killed


def test_close_background_keeps_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: True)
    monkeypatch.setattr(ProcessManager, "terminate", lambda self, rec, **k: "exited")
    _seed_session(
        "production",
        [_rec("frontend", keep=False), _rec("mcp", keep=True), _rec("scheduler", keep=True)],
    )
    result = runner.invoke(app, ["launcher", "close", "--environment", "production",
                                 "--action", "background", "--json"])
    d = json.loads(result.stdout)
    assert d["terminated"] == ["frontend"]
    assert set(d["kept_alive"]) == {"mcp", "scheduler"}
    assert d["background_active"] is True
    assert d["scheduler_active"] is True


def test_background_then_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: True)
    stopped: list[str] = []
    monkeypatch.setattr(
        ProcessManager,
        "terminate",
        lambda self, rec, **k: (stopped.append(rec.name) or "exited"),  # type: ignore[func-returns-value]
    )
    _seed_session("production", [_rec("mcp", keep=True)])
    runner.invoke(app, ["launcher", "close", "--environment", "production",
                        "--action", "background", "--json"])
    result = runner.invoke(app, ["launcher", "stop", "--environment", "production", "--json"])
    d = json.loads(result.stdout)
    assert "mcp" in d["stopped"]


# --- due / catch-up --------------------------------------------------------------


def test_compute_next_run_before_and_after() -> None:
    before = datetime(2026, 6, 7, 14, 0, tzinfo=timezone.utc)  # 10:00 ET
    nxt = compute_next_run(before, "20:00", "America/New_York")
    assert nxt.hour == 20 and nxt.date() == date(2026, 6, 7)
    after = datetime(2026, 6, 8, 3, 0, tzinfo=timezone.utc)  # 11:00pm ET Jun 7
    nxt2 = compute_next_run(after, "20:00", "America/New_York")
    assert nxt2.date() == date(2026, 6, 8)


def test_catch_up_runs_once_after_missed() -> None:
    st = SchedulerState(environment="production", last_successful_schedule_date="2026-06-05")
    now = datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc)  # 9pm ET Jun 7
    d = decide_catch_up(now, st, schedule_time_local="20:00", timezone="America/New_York",
                        catch_up_on_wake=True)
    assert d.should_run is True
    assert d.schedule_date == "2026-06-07"


def test_no_double_run_same_date() -> None:
    st = SchedulerState(environment="production", last_successful_schedule_date="2026-06-07")
    now = datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc)
    d = decide_catch_up(now, st, schedule_time_local="20:00", timezone="America/New_York",
                        catch_up_on_wake=True)
    assert d.should_run is False
    assert d.reason == "already_succeeded_for_date"


# --- backends: dry-run writes nothing + valid artifacts --------------------------


def test_install_dry_run_writes_no_os_files() -> None:
    from hb_assistant.scheduler.backends import get_backend

    profile = resolve_profile("production")
    for name in ("launchd", "windows", "systemd", "foreground"):
        impl = get_backend(name, profile)  # type: ignore[arg-type]
        res = impl.install(dry_run=True)
        assert res["installed"] is False
        if name == "launchd":
            assert not Path(impl.plist_path).exists()  # type: ignore[attr-defined]
        elif name == "windows":
            assert not Path(impl.xml_path).exists()  # type: ignore[attr-defined]
        elif name == "systemd":
            assert not Path(impl.timer_path).exists()  # type: ignore[attr-defined]


def test_launchd_plist_valid() -> None:
    from hb_assistant.scheduler.backends import get_backend

    impl = get_backend("launchd", resolve_profile("production"))
    plist = impl.preview()["plist"]  # type: ignore[index]
    assert plist["StartCalendarInterval"]["Hour"] == 20
    assert plist["ProgramArguments"][1:5] == ["scheduler", "run", "daily-source-refresh", "--environment"]


def test_windows_task_valid() -> None:
    from hb_assistant.scheduler.backends import get_backend

    xml = get_backend("windows", resolve_profile("production")).preview()["xml"]  # type: ignore[index]
    assert "20:00:00" in xml and "<Command>" in xml


def test_systemd_units_valid() -> None:
    from hb_assistant.scheduler.backends import get_backend

    pv = get_backend("systemd", resolve_profile("production")).preview()
    assert "OnCalendar=*-*-* 20:00:00" in pv["timer"]  # type: ignore[index]
    assert "Persistent=true" in pv["timer"]  # type: ignore[index]
    assert "ExecStart=" in pv["service"]  # type: ignore[index]


# --- scheduled job options + live gating -----------------------------------------


def _prod_profile_with(monkeypatch: pytest.MonkeyPatch, **flags: bool) -> Any:
    cfg = load_config().model_copy(deep=True)
    for k, v in flags.items():
        setattr(cfg.automation.scheduler, k, v)
    return resolve_profile("production", config=cfg)


def test_scheduled_dev_uses_mock() -> None:
    opts = DailySourceRefreshJob(resolve_profile("dev")).build_options(date(2026, 6, 7))
    assert opts.mock_data is True
    assert opts.allow_procore_live is False and opts.allow_graph_live is False
    assert opts.live_reads_enabled is False


def test_scheduled_production_default_local_only() -> None:
    opts = DailySourceRefreshJob(resolve_profile("production")).build_options(date(2026, 6, 7))
    assert opts.live_reads_enabled is False
    assert opts.mock_data is False  # production is never "mock"
    assert opts.allow_procore_live is False
    assert opts.allow_graph_live is False


def test_production_default_no_hb_procore_live(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = resolve_profile("production")
    _migrate(profile.db_path)
    seen: dict[str, Any] = {}

    def fake_run(self: Any, *, options: Any) -> dict[str, Any]:
        seen["live"] = os.environ.get("HB_PROCORE_LIVE")
        seen["options"] = options
        return _canned_summary()

    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", fake_run)
    receipt = DailySourceRefreshJob(profile).execute(schedule_date=date(2026, 6, 7), trigger="test")
    assert seen["live"] is None  # never armed for a local-only run
    assert seen["options"].mock_data is False  # production default is not mock
    assert receipt.mode == "local_only"
    assert receipt.live_reads_enabled is False


def test_enable_procore_live_sets_env_only_for_run(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _prod_profile_with(
        monkeypatch, enable_live_reads=True, enable_procore_live_reads=True
    )
    _migrate(profile.db_path)
    seen: dict[str, Any] = {}

    def fake_run(self: Any, *, options: Any) -> dict[str, Any]:
        seen["live"] = os.environ.get("HB_PROCORE_LIVE")
        seen["options"] = options
        return _canned_summary()

    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", fake_run)
    assert os.environ.get("HB_PROCORE_LIVE") is None
    receipt = DailySourceRefreshJob(profile).execute(schedule_date=date(2026, 6, 7), trigger="test")
    assert seen["live"] == "1"  # armed for the run
    assert os.environ.get("HB_PROCORE_LIVE") is None  # restored afterward
    assert receipt.mode == "live_source"
    assert receipt.procore_live is True
    assert receipt.mock_data is False
    assert receipt.live_reads_enabled is True


def test_receipts_distinguish_local_vs_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _canned_summary())
    prof_local = resolve_profile("production")
    _migrate(prof_local.db_path)
    local = DailySourceRefreshJob(prof_local).execute(schedule_date=date(2026, 6, 7), trigger="t")
    assert local.mode == "local_only" and local.live_reads_enabled is False

    prof_live = _prod_profile_with(monkeypatch, enable_live_reads=True, enable_graph_live_reads=True)
    _migrate(prof_live.db_path)
    live = DailySourceRefreshJob(prof_live).execute(schedule_date=date(2026, 6, 7), trigger="t")
    assert live.mode == "live_source" and live.graph_live is True
    # distinct modes: dev mock vs production local-only vs production live-source
    dev = DailySourceRefreshJob(resolve_profile("dev")).build_options(date(2026, 6, 7))
    assert (dev.mock_data, dev.live_reads_enabled) == (True, False)
    assert (local.mock_data, local.live_reads_enabled) == (False, False)
    assert (live.mock_data, live.live_reads_enabled) == (False, True)


def test_production_default_no_live_auth_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real production-default run must never call live Procore auth or the Graph probe."""
    import hb_assistant.source_refresh.orchestrator as orch_mod

    def _boom_auth() -> Any:
        raise AssertionError("check_auth_status called during production local-only run")

    def _boom_graph(self: Any) -> Any:
        raise AssertionError("_graph_status (Graph probe) called during production local-only run")

    monkeypatch.setattr(orch_mod, "check_auth_status", _boom_auth)
    monkeypatch.setattr(orch_mod.SourceRefreshOrchestrator, "_graph_status", _boom_graph)

    profile = resolve_profile("production")
    receipt = DailySourceRefreshJob(profile).execute(schedule_date=date(2026, 6, 8), trigger="t")
    assert receipt.status == "ok"
    assert receipt.mode == "local_only"
    assert receipt.mock_data is False
    assert receipt.live_reads_enabled is False


def test_no_raw_guardrails_in_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _canned_summary())
    profile = resolve_profile("dev")
    _migrate(profile.db_path)
    receipt = DailySourceRefreshJob(profile).execute(schedule_date=date(2026, 6, 7), trigger="t")
    assert receipt.guardrails.get("no_procore_writeback") is True
    blob = json.dumps(receipt.model_dump())
    for bad in ('"access_token"', '"refresh_token"', "Bearer ", "BEGIN PRIVATE KEY"):
        assert bad not in blob


# --- runner foreground tick: due + no-double-run ---------------------------------


def test_foreground_loop_respects_due(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _canned_summary())
    profile = resolve_profile("production")
    _migrate(profile.db_path)
    runner_obj = SchedulerRunner(profile)
    now = datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc)  # 9pm ET Jun 7
    first = runner_obj.tick(now)
    assert first["ran"] is True
    second = runner_obj.tick(now)
    assert second["ran"] is False  # same schedule date ⇒ no double-run


# --- snapshot copy ---------------------------------------------------------------


def test_snapshot_copy_source_unmutated_and_confirm_gate(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite"
    _migrate(source)
    before = source.stat().st_mtime_ns
    dev = resolve_profile("dev")
    r1 = snapshot_source_db(dev, source_db=source, confirm=False)
    assert r1["status"] == "ok"
    assert dev.db_path.exists()
    assert r1["source_mutated"] is False
    assert source.stat().st_mtime_ns == before  # source untouched
    # second snapshot over existing dev DB requires confirm
    r2 = snapshot_source_db(dev, source_db=source, confirm=False)
    assert r2["status"] == "confirmation_required"
    r3 = snapshot_source_db(dev, source_db=source, confirm=True)
    assert r3["status"] == "ok"


# --- CLI smokes ------------------------------------------------------------------


def test_cli_scheduler_due_production() -> None:
    result = runner.invoke(app, ["scheduler", "due", "daily-source-refresh",
                                 "--environment", "production", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert "should_run" in d and "schedule_date" in d


def test_cli_scheduler_install_dry_run_production() -> None:
    result = runner.invoke(app, ["scheduler", "install", "daily-source-refresh", "--time", "20:00",
                                 "--catch-up-on-wake", "--environment", "production",
                                 "--backend", "launchd", "--dry-run", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["installed"] is False and d["writes_files"] is False


# --- DB isolation: scheduled refresh binds every local store to the env DB ---------


def _opened_paths(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every sqlite3.connect target during a block."""
    import sqlite3

    opened: list[str] = []
    orig = sqlite3.connect

    def traced(database: Any, *a: Any, **k: Any) -> Any:
        opened.append(str(database))
        return orig(database, *a, **k)

    monkeypatch.setattr(sqlite3, "connect", traced)
    return opened


def test_dev_scheduled_does_not_touch_production_db(monkeypatch: pytest.MonkeyPatch) -> None:
    dev = resolve_profile("dev")
    prod = resolve_profile("production")
    opened = _opened_paths(monkeypatch)
    receipt = DailySourceRefreshJob(dev).execute(schedule_date=date(2026, 6, 8), trigger="t")
    assert receipt.mode == "local_only"
    assert dev.db_path.exists()
    # Production DB is never opened or created.
    assert str(prod.db_path) not in opened
    assert not prod.db_path.exists()
    assert any(str(dev.db_path) == p for p in opened)


def test_production_scheduled_does_not_touch_dev_db(monkeypatch: pytest.MonkeyPatch) -> None:
    dev = resolve_profile("dev")
    prod = resolve_profile("production")
    opened = _opened_paths(monkeypatch)
    DailySourceRefreshJob(prod).execute(schedule_date=date(2026, 6, 8), trigger="t")
    assert prod.db_path.exists()
    assert str(dev.db_path) not in opened
    assert not dev.db_path.exists()


def test_get_connection_with_db_path_never_opens_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.config.path_policy import PathPolicy
    from hb_assistant.store.connection import get_connection

    default_db = str(PathPolicy().get_db_path())
    dev = resolve_profile("dev")
    opened = _opened_paths(monkeypatch)
    conn = get_connection(dev.db_path)
    conn.close()
    assert default_db not in opened  # explicit db_path must not probe the default DB


def _spy_construction_store(monkeypatch: pytest.MonkeyPatch) -> list[str | None]:
    import hb_assistant.construction.store.repositories as repo

    captured: list[str | None] = []

    class _Spy:
        def __init__(self, db_path: str | None = None) -> None:
            captured.append(db_path)

    monkeypatch.setattr(repo, "ConstructionStore", _Spy)
    return captured


def test_graph_mail_thread_summary_binds_db(monkeypatch: pytest.MonkeyPatch) -> None:
    import hb_assistant.construction.calendar as cal
    import hb_assistant.construction.email as email_mod

    captured = _spy_construction_store(monkeypatch)

    class _Mat:
        def __init__(self, store: Any, *, policy: Any = None) -> None:
            pass

        def materialize(self, *, dry_run: bool) -> Any:
            return type("R", (), {"model_dump": lambda self: {}})()

    monkeypatch.setattr(email_mod, "EmailThreadSummaryMaterializer", _Mat)
    monkeypatch.setattr(cal, "load_email_thread_summary_policy", lambda: object())

    dev = resolve_profile("dev")
    SourceRefreshOrchestrator(db_path=dev.db_path)._graph_mail_thread_summary(dry_run=True)
    assert captured == [str(dev.db_path)]


def test_graph_calendar_binds_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import hb_assistant.construction.calendar.event_indexer as ei
    import hb_assistant.construction.calendar.policy as calpol
    import hb_assistant.graph.calendar_endpoint_guard as guard
    import hb_assistant.graph.calendar_readonly_client as roc

    captured = _spy_construction_store(monkeypatch)
    monkeypatch.setattr(ei, "CalendarEventIndexer", lambda reader, store: SimpleNamespace())
    monkeypatch.setattr(roc, "ReadOnlyCalendarClient", lambda client, contract: SimpleNamespace())
    monkeypatch.setattr(guard, "load_calendar_endpoint_contract", lambda: SimpleNamespace())
    monkeypatch.setattr(
        calpol, "load_calendar_source_policy",
        lambda: SimpleNamespace(defaults=SimpleNamespace(enabled=False), sources=[]),
    )
    dev = resolve_profile("dev")
    orch = SourceRefreshOrchestrator(db_path=dev.db_path)
    monkeypatch.setattr(orch, "_graph_client", lambda: SimpleNamespace(close=lambda: None))
    orch._graph_calendar(dry_run=True)
    assert captured == [str(dev.db_path)]


def test_graph_files_binds_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    import hb_assistant.construction.config as cfgmod

    captured = _spy_construction_store(monkeypatch)
    monkeypatch.setattr(cfgmod, "load_source_registry", lambda: SimpleNamespace(sources=[]))
    dev = resolve_profile("dev")
    orch = SourceRefreshOrchestrator(db_path=dev.db_path)
    orch._graph_files(dry_run=False)  # store constructed only when not dry_run
    assert captured == [str(dev.db_path)]
