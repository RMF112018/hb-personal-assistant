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
from hb_assistant.launcher.profiles import (
    ProfileCollisionError,
    resolve_profile,
    snapshot_source_db,
)
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


@pytest.fixture(autouse=True)
def _stub_process_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic default: no OS process/port scanning (also protects the host machine).

    Individual tests override these via monkeypatch to inject fake processes/ports.
    """
    import hb_assistant.launcher.process_scan as ps

    monkeypatch.setattr(ps, "list_system_processes", lambda: [])
    monkeypatch.setattr(ps, "port_in_use", lambda port, host="127.0.0.1": False)
    monkeypatch.setattr(ps, "port_listener_pids", lambda port: [])


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


# --- launcher --open (frontend auto-open) ----------------------------------------


def _patch_open(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch the readiness wait + browser open so no network/browser is touched.

    Returns a dict that records the (url, timeout) the wait was called with and the
    url the browser open was called with.
    """
    import hb_assistant.launcher.frontend_open as fo_mod

    captured: dict[str, Any] = {}

    def _wait(url: str, *, timeout_seconds: int = 30, interval_seconds: float = 1.0) -> Any:
        captured["wait_url"] = url
        captured["wait_timeout"] = timeout_seconds
        return True, []

    def _open(url: str) -> Any:
        captured["open_url"] = url
        return True, "browser", []

    monkeypatch.setattr(fo_mod, "wait_for_frontend", _wait)
    monkeypatch.setattr(fo_mod, "open_browser", _open)
    return captured


def test_launcher_dev_open_opens_resolved_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_open(monkeypatch)
    result = runner.invoke(app, ["launcher", "dev", "--open", "--plan", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["command"] == "launcher open"
    assert d["frontend_opened"] is True
    assert d["frontend_reachable"] is True
    assert d["open_method"] == "browser"
    assert d["frontend_url"] == captured["open_url"] == "http://127.0.0.1:5173"


def test_launcher_production_open_opens_resolved_url(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_open(monkeypatch)
    result = runner.invoke(app, ["launcher", "production", "--open", "--plan", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["command"] == "launcher open"
    assert d["frontend_opened"] is True
    assert captured["open_url"] == d["frontend_url"]


def test_launcher_status_reports_frontend_url() -> None:
    for env in ("dev", "production"):
        result = runner.invoke(app, ["launcher", "status", "--environment", env, "--json"])
        assert result.exit_code == 0
        d = json.loads(result.stdout)
        assert d["frontend_url"] == "http://127.0.0.1:5173"
        assert d["frontend_url_source"] == "fallback"


def test_launcher_open_waits_for_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_open(monkeypatch)
    result = runner.invoke(
        app,
        ["launcher", "dev", "--open", "--open-timeout-seconds", "7", "--plan", "--json"],
    )
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert captured["wait_url"] == "http://127.0.0.1:5173"
    assert captured["wait_timeout"] == 7
    assert d["timeout_seconds"] == 7


def test_launcher_open_timeout_warns_but_does_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    import hb_assistant.launcher.frontend_open as fo_mod

    monkeypatch.setattr(
        fo_mod, "wait_for_frontend", lambda url, **k: (False, ["frontend not reachable"])
    )
    monkeypatch.setattr(fo_mod, "open_browser", lambda url: (True, "browser", []))
    result = runner.invoke(app, ["launcher", "dev", "--open", "--plan", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["frontend_reachable"] is False
    assert d["frontend_url"] == "http://127.0.0.1:5173"
    assert any("not reachable" in w for w in d["warnings"])


def test_launcher_open_browser_mode_no_close_intercept(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_open(monkeypatch)
    result = runner.invoke(app, ["launcher", "dev", "--open", "--plan", "--json"])
    d = json.loads(result.stdout)
    assert d["window_close_intercept_supported"] is False
    assert d["lifecycle_control"] == "cli_or_ui_action_required"
    assert d["requested_shell"] == "browser"
    assert d["actual_shell"] == "browser"


def test_browser_open_is_non_blocking_and_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    import hb_assistant.launcher.frontend_open as fo_mod

    def _boom(url: str, new: int = 0) -> bool:
        raise RuntimeError("no browser")

    monkeypatch.setattr(fo_mod.webbrowser, "open", _boom)
    opened, method, warnings = fo_mod.open_browser("http://127.0.0.1:5173")
    assert opened is False
    assert method == "browser"
    assert warnings and "failed to open browser" in warnings[0]


def test_wait_for_frontend_timeout_returns_warning() -> None:
    import hb_assistant.launcher.frontend_open as fo_mod

    # Port 1 is never listening; timeout 0 means the deadline is already past.
    reachable, warnings = fo_mod.wait_for_frontend(
        "http://127.0.0.1:1", timeout_seconds=0, interval_seconds=0.01
    )
    assert reachable is False
    assert warnings and "not reachable" in warnings[0]


def test_pywebview_lazy_optional_falls_back_to_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    import hb_assistant.launcher.webview_shell as webview_shell

    _patch_open(monkeypatch)
    monkeypatch.setattr(webview_shell, "pywebview_available", lambda: False)
    result = runner.invoke(
        app, ["launcher", "dev", "--open", "--shell", "pywebview", "--plan", "--json"]
    )
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["open_method"] == "browser_fallback"
    assert d["requested_shell"] == "pywebview"
    assert d["actual_shell"] == "browser"
    assert d["window_close_intercept_supported"] is False
    assert any("pywebview requested but not installed" in w for w in d["warnings"])


def test_pywebview_module_has_no_top_level_webview_import() -> None:
    import sys

    import hb_assistant.launcher.webview_shell  # noqa: F401

    # Importing the shell module must not import the optional `webview` package.
    assert "webview" not in sys.modules


def test_dev_prod_frontend_urls_can_differ_via_config() -> None:
    from hb_assistant.config.models import AppConfig, LauncherConfig, LauncherEnvConfig

    cfg = AppConfig(
        launcher=LauncherConfig(
            dev=LauncherEnvConfig(frontend_url="http://127.0.0.1:5173"),
            production=LauncherEnvConfig(frontend_url="http://127.0.0.1:4173"),
        )
    )
    dev = resolve_profile("dev", config=cfg)
    prod = resolve_profile("production", config=cfg)
    assert dev.frontend_url == "http://127.0.0.1:5173"
    assert prod.frontend_url == "http://127.0.0.1:4173"
    assert dev.frontend_url != prod.frontend_url
    assert dev.frontend_url_source == "config"
    assert prod.frontend_url_source == "config"


def test_frontend_url_falls_back_when_unset() -> None:
    for env in ("dev", "production"):
        profile = resolve_profile(env)  # type: ignore[arg-type]
        assert profile.frontend_url == "http://127.0.0.1:5173"
        assert profile.frontend_url_source == "fallback"


# --- frontend display alias ------------------------------------------------------


def _patch_open_per_url(monkeypatch: pytest.MonkeyPatch, reachable: set[str]) -> dict[str, Any]:
    """Patch the readiness wait/browser open so each URL resolves per ``reachable``."""
    import hb_assistant.launcher.frontend_open as fo_mod

    cap: dict[str, Any] = {"waits": []}

    def _wait(url: str, *, timeout_seconds: int = 30, interval_seconds: float = 1.0) -> Any:
        cap["waits"].append(url)
        ok = url in reachable
        return ok, ([] if ok else [f"frontend not reachable at {url}"])

    def _open(url: str) -> Any:
        cap["open_url"] = url
        return True, "browser", []

    monkeypatch.setattr(fo_mod, "wait_for_frontend", _wait)
    monkeypatch.setattr(fo_mod, "open_browser", _open)
    return cap


def _alias_cfg(alias: str | None) -> Any:
    from hb_assistant.config.models import AppConfig, LauncherConfig, LauncherEnvConfig

    return AppConfig(
        launcher=LauncherConfig(
            dev=LauncherEnvConfig(
                frontend_url="http://127.0.0.1:5173",
                frontend_alias_url=alias,
                frontend_display_name="HB Assistant Dev UI",
            )
        )
    )


def test_alias_reachable_opens_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    alias = "http://hb-dev.localhost:5173"
    cap = _patch_open_per_url(monkeypatch, {"http://127.0.0.1:5173", alias})
    svc = LauncherService(resolve_profile("dev", config=_alias_cfg(alias)))
    d = svc.open_session(plan_only=True)
    assert d["opened_url"] == alias
    assert cap["open_url"] == alias
    assert d["alias_resolution_status"] == "resolved"
    assert d["frontend_url"] == "http://127.0.0.1:5173"  # routable URL unchanged
    assert d["frontend_alias_url"] == alias
    assert d["frontend_display_name"] == "HB Assistant Dev UI"
    # The routable URL is health-checked first.
    assert cap["waits"][0] == "http://127.0.0.1:5173"


def test_alias_unreachable_falls_back_to_routable(monkeypatch: pytest.MonkeyPatch) -> None:
    alias = "http://hb-dev.localhost:5173"
    cap = _patch_open_per_url(monkeypatch, {"http://127.0.0.1:5173"})  # alias not reachable
    svc = LauncherService(resolve_profile("dev", config=_alias_cfg(alias)))
    d = svc.open_session(plan_only=True)
    assert d["opened_url"] == "http://127.0.0.1:5173"
    assert cap["open_url"] == "http://127.0.0.1:5173"
    assert d["alias_resolution_status"] == "unreachable"
    assert d["frontend_reachable"] is True  # routable URL still healthy
    assert any("not reachable" in w for w in d["warnings"])


def test_alias_not_configured_opens_routable(monkeypatch: pytest.MonkeyPatch) -> None:
    cap = _patch_open_per_url(monkeypatch, {"http://127.0.0.1:5173"})
    svc = LauncherService(resolve_profile("dev", config=_alias_cfg(None)))
    d = svc.open_session(plan_only=True)
    assert d["alias_resolution_status"] == "not_configured"
    assert d["opened_url"] == d["frontend_url"] == "http://127.0.0.1:5173"
    assert cap["open_url"] == "http://127.0.0.1:5173"
    assert d["frontend_display_name"] == "HB Assistant Dev UI"


def test_launcher_status_reports_alias_fields() -> None:
    result = runner.invoke(app, ["launcher", "status", "--environment", "dev", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    for key in (
        "frontend_display_name",
        "frontend_url",
        "frontend_alias_url",
        "opened_url",
        "alias_resolution_status",
        "warnings",
    ):
        assert key in d
    assert d["frontend_display_name"] == "HB Assistant (Dev)"  # default when unset
    assert d["alias_resolution_status"] == "not_configured"
    assert d["frontend_alias_url"] is None


def test_open_result_includes_display_name(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_open(monkeypatch)
    result = runner.invoke(app, ["launcher", "dev", "--open", "--plan", "--json"])
    d = json.loads(result.stdout)
    assert d["frontend_display_name"] == "HB Assistant (Dev)"
    assert d["alias_resolution_status"] == "not_configured"
    assert d["opened_url"] == d["frontend_url"]


# --- preflight / ports / cleanup / output isolation ------------------------------


def _patch_scan(
    monkeypatch: pytest.MonkeyPatch,
    *,
    processes: list[Any] | None = None,
    ports_in_use: tuple[int, ...] = (),
    listeners: dict[int, list[int]] | None = None,
) -> None:
    import hb_assistant.launcher.process_scan as ps

    procs = list(processes or [])
    in_use = set(ports_in_use)
    lis = listeners or {}
    monkeypatch.setattr(ps, "list_system_processes", lambda: list(procs))
    monkeypatch.setattr(ps, "port_in_use", lambda port, host="127.0.0.1": port in in_use)
    monkeypatch.setattr(ps, "port_listener_pids", lambda port: list(lis.get(port, [])))


def _fake_spawn_factory(calls: list[str]) -> Any:
    def _spawn(self: Any, spec: Any) -> ProcessRecord:
        calls.append(spec.name)
        return ProcessRecord(
            name=spec.name,
            pid=4242,
            started_at="2026-06-07T00:00:00+00:00",
            argv=spec.argv,
            status="running",
            keep_in_background=spec.keep_in_background,
            port=spec.port,
            log_path="/tmp/log",
        )

    return _spawn


def test_preflight_frees_launcher_owned_stale_backend_port(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.launcher.process_scan import ProcInfo
    from hb_assistant.launcher.service import LauncherService

    stale = ProcInfo(
        999, "python -m uvicorn hb_assistant.construction.analytics.api:create_app --port 8000"
    )
    _patch_scan(monkeypatch, processes=[stale], ports_in_use=(8000,), listeners={8000: [999]})
    freed: list[int] = []
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: False)
    monkeypatch.setattr(
        ProcessManager, "terminate_pid", lambda self, pid, **k: (freed.append(pid) or "exited")
    )
    calls: list[str] = []
    monkeypatch.setattr(ProcessManager, "spawn", _fake_spawn_factory(calls))

    result = LauncherService(resolve_profile("dev")).start()
    assert result["status"] == "ok"
    assert 999 in freed
    pf = result["preflight"]
    assert any(f["port"] == 8000 and f["pid"] == 999 for f in pf["freed_ports"])
    assert "backend" in calls and "frontend" in calls  # session actually started


def test_preflight_unknown_port_conflict_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.launcher.process_scan import ProcInfo

    unknown = ProcInfo(777, "/some/random/server --port 5173")
    _patch_scan(monkeypatch, processes=[unknown], ports_in_use=(5173,), listeners={5173: [777]})
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: False)

    def _boom_spawn(self: Any, spec: Any) -> Any:
        raise AssertionError("spawn must not run on an unknown port conflict")

    monkeypatch.setattr(ProcessManager, "spawn", _boom_spawn)
    result = runner.invoke(app, ["launcher", "dev", "--json"])
    assert result.exit_code == 2
    d = json.loads(result.stdout)
    assert d["status"] == "port_conflict"
    assert any(c["port"] == 5173 and c["pid"] == 777 for c in d["port_conflicts"])


def test_preflight_reuses_healthy_session_unless_force_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hb_assistant.launcher.service import LauncherService

    _seed_session("dev", [_rec("backend", keep=True), _rec("frontend", keep=False)])
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: True)
    calls: list[str] = []
    monkeypatch.setattr(ProcessManager, "spawn", _fake_spawn_factory(calls))

    reused = LauncherService(resolve_profile("dev")).start()
    assert reused.get("reused") is True
    assert calls == []  # no respawn

    monkeypatch.setattr(ProcessManager, "terminate", lambda self, rec, **k: "exited")
    restarted = LauncherService(resolve_profile("dev")).start(force_restart=True)
    assert restarted["preflight"]["stopped_prior"]
    assert "backend" in calls  # respawned


def test_dev_frontend_spec_uses_strict_port(monkeypatch: pytest.MonkeyPatch) -> None:
    import hb_assistant.launcher.service as svc_mod
    from hb_assistant.launcher.service import LauncherService

    monkeypatch.setattr(svc_mod.shutil, "which", lambda name: "/usr/bin/npm")
    profile = resolve_profile("dev")
    specs = {s.name: s for s in LauncherService(profile).build_specs()}
    fe = specs["frontend"]
    assert "--strictPort" in fe.argv
    assert "--port" in fe.argv and str(profile.frontend_port) in fe.argv
    assert fe.port == profile.frontend_port == 5173
    assert profile.frontend_url.endswith(":5173")  # opened URL matches the bound port


def test_spawn_redirects_child_output_to_logfile(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    import hb_assistant.launcher.process_manager as pm_mod
    from hb_assistant.launcher.models import ManagedProcessSpec

    captured: dict[str, Any] = {}

    class _FakeProc:
        pid = 5151

    def _fake_popen(argv: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(pm_mod.subprocess, "Popen", _fake_popen)
    pm = ProcessManager(resolve_profile("dev"))
    spec = ManagedProcessSpec(name="backend", argv=["x"], cwd=".", port=8000)
    rec = pm.spawn(spec)
    assert captured["stdin"] == subprocess.DEVNULL
    assert captured["stderr"] == subprocess.STDOUT
    assert captured["stdout"] is not None  # a real file handle, not the terminal
    assert rec.log_path and rec.log_path.endswith("dev-backend.log")
    assert rec.port == 8000


def test_json_output_is_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    # Plan mode: no real spawn; stdout must be valid JSON only (Automator-safe).
    result = runner.invoke(app, ["launcher", "dev", "--plan", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.stdout)  # raises if any child log were appended
    assert parsed["command"] == "launcher status"


def test_quit_sweeps_stale_launcher_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.launcher.close_policy import ClosePolicy
    from hb_assistant.launcher.process_scan import ProcInfo

    stale_sched = ProcInfo(
        888, "hb-assistant scheduler run daily-source-refresh --environment production --loop"
    )
    _patch_scan(monkeypatch, processes=[stale_sched])
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: True)
    monkeypatch.setattr(ProcessManager, "terminate", lambda self, rec, **k: "exited")
    killed: list[int] = []
    monkeypatch.setattr(
        ProcessManager, "terminate_pid", lambda self, pid, **k: (killed.append(pid) or "exited")
    )
    _seed_session("production", [_rec("frontend", keep=False), _rec("mcp", keep=True)])
    profile = resolve_profile("production")
    receipt = ClosePolicy(profile, ProcessManager(profile)).apply("quit")
    assert set(receipt["terminated_current_session"]) == {"frontend", "mcp"}
    assert any(s["pid"] == 888 and s["role"] == "scheduler" for s in receipt["terminated_stale"])
    assert 888 in killed


def test_cleanup_dry_run_skips_foreign_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.launcher.process_scan import ProcInfo

    foreign_mcp = ProcInfo(555, "hb-assistant second-brain mcp serve --stdio")
    stale_sched = ProcInfo(
        666, "hb-assistant scheduler run daily-source-refresh --environment dev --loop"
    )
    _patch_scan(monkeypatch, processes=[foreign_mcp, stale_sched])
    killed: list[int] = []
    monkeypatch.setattr(
        ProcessManager, "terminate_pid", lambda self, pid, **k: (killed.append(pid) or "exited")
    )
    result = runner.invoke(app, ["launcher", "cleanup", "--environment", "dev", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    pids = {c["pid"] for c in d["candidates"]}
    assert 666 in pids  # stale scheduler identified
    assert 555 not in pids  # foreign MCP NOT a candidate
    assert killed == []  # dry-run terminates nothing


def test_cleanup_apply_terminates_candidates_including_tracked_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: True)
    killed: list[int] = []
    monkeypatch.setattr(
        ProcessManager, "terminate_pid", lambda self, pid, **k: (killed.append(pid) or "exited")
    )
    mcp_rec = _rec("mcp", keep=True)  # tracked → launcher-owned even though MCP
    _seed_session("dev", [mcp_rec])
    result = runner.invoke(app, ["launcher", "cleanup", "--environment", "dev", "--apply", "--json"])
    d = json.loads(result.stdout)
    assert d["applied"] is True
    assert mcp_rec.pid in killed  # a TRACKED mcp is swept (it is launcher-owned)


# --- MCP lifecycle (stdio is external-client-managed) ----------------------------


def test_stdio_mcp_not_spawned_or_recorded() -> None:
    result = runner.invoke(app, ["launcher", "dev", "--plan", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    names = {p["name"] for p in d["processes"]}
    assert "mcp" not in names  # stdio MCP is never a managed record
    assert {"backend", "frontend", "scheduler"} <= names  # others unchanged


def test_status_reports_external_stdio_mcp() -> None:
    result = runner.invoke(app, ["launcher", "status", "--environment", "dev", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["mcp_status"] == "external_client_managed"
    assert d["mcp_mode"] == "stdio"
    assert d["mcp_managed_by_launcher"] is False
    assert "Claude/Cursor" in d["mcp_reason"]


def test_open_result_reports_external_stdio_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_open(monkeypatch)
    result = runner.invoke(app, ["launcher", "dev", "--open", "--plan", "--json"])
    d = json.loads(result.stdout)
    assert d["mcp_status"] == "external_client_managed"
    assert d["mcp_managed_by_launcher"] is False


def test_quit_does_not_terminate_external_stdio_mcp(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.launcher.close_policy import ClosePolicy

    calls: list[str] = []
    monkeypatch.setattr(ProcessManager, "spawn", _fake_spawn_factory(calls))
    monkeypatch.setattr(ProcessManager, "is_alive", lambda self, pid: False)
    monkeypatch.setattr(ProcessManager, "terminate", lambda self, rec, **k: "exited")
    profile = resolve_profile("dev")
    LauncherService(profile).start()  # real (non-seeded) session: no mcp record
    assert "mcp" not in calls  # mcp never spawned
    receipt = ClosePolicy(profile, ProcessManager(profile)).apply("quit")
    assert "mcp" not in receipt["terminated_current_session"]
    assert all(s.get("role") != "mcp" for s in receipt["terminated_stale"])


def test_classify_never_matches_mcp_signature() -> None:
    from hb_assistant.launcher.process_scan import ProcInfo, classify

    profile = resolve_profile("dev")
    proc = ProcInfo(321, "hb-assistant second-brain mcp serve --stdio")
    assert classify(proc, profile) is None  # external IDE MCP is never launcher-owned


def test_shortcut_helpers_invoke_launcher_open() -> None:
    repo = resolve_profile("dev").path_policy.resolve_repo_root()
    shortcuts = repo / "scripts" / "shortcuts"
    dev = (shortcuts / "hb-launcher-dev.command").read_text()
    prod = (shortcuts / "hb-launcher-production.command").read_text()
    assert "launcher dev --open" in dev
    assert "launcher production --open" in prod
    for text in (dev, prod):
        assert "vite" not in text
        assert "npm run dev" not in text
        assert "uvicorn" not in text
        assert "open http" not in text


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


def test_production_scheduler_resolves_all_mapped_project_scope() -> None:
    opts = DailySourceRefreshJob(resolve_profile("production")).build_options(date(2026, 6, 7))
    assert opts.procore_project_scope == "all_mapped"
    assert opts.procore_project_keys == ()


def test_scheduled_production_default_local_only() -> None:
    profile = _prod_profile_with(
        pytest.MonkeyPatch(),
        enable_live_reads=False,
        enable_procore_live_reads=False,
        enable_graph_live_reads=False,
    )
    opts = DailySourceRefreshJob(profile).build_options(date(2026, 6, 7))
    assert opts.live_reads_enabled is False
    assert opts.mock_data is False  # production is never "mock"
    assert opts.allow_procore_live is False
    assert opts.allow_graph_live is False
    assert opts.procore_project_scope == "all_mapped"
    assert opts.procore_project_keys == ()


def test_production_default_no_hb_procore_live(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _prod_profile_with(
        monkeypatch,
        enable_live_reads=False,
        enable_procore_live_reads=False,
        enable_graph_live_reads=False,
    )
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
    assert seen["options"].procore_project_scope == "all_mapped"
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
    assert seen["options"].procore_project_scope == "all_mapped"


def test_receipts_distinguish_local_vs_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _canned_summary())
    prof_local = _prod_profile_with(
        monkeypatch,
        enable_live_reads=False,
        enable_procore_live_reads=False,
        enable_graph_live_reads=False,
    )
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

    profile = _prod_profile_with(
        monkeypatch,
        enable_live_reads=False,
        enable_procore_live_reads=False,
        enable_graph_live_reads=False,
    )
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


# --- future-date guard + recovery -------------------------------------------------

_FUTURE = "2099-01-01"


def test_run_future_date_rejected() -> None:
    result = runner.invoke(app, ["scheduler", "run", "daily-source-refresh",
                                 "--environment", "production", "--date", _FUTURE, "--json"])
    assert result.exit_code != 0
    d = json.loads(result.stdout)
    assert d["status"] == "not_ready"
    assert d["error"] == "future_schedule_date_not_allowed"
    assert d["requested_date"] == _FUTURE
    assert "current_local_date" in d and d["ran"] is False


def test_future_date_does_not_call_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(self: Any, *, options: Any) -> Any:
        raise AssertionError("SourceRefreshOrchestrator.run called for a rejected future date")

    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", _boom)
    result = runner.invoke(app, ["scheduler", "run", "daily-source-refresh",
                                 "--environment", "production", "--date", _FUTURE, "--json"])
    assert result.exit_code != 0
    assert json.loads(result.stdout)["error"] == "future_schedule_date_not_allowed"


def test_future_date_does_not_mutate_state_or_write_receipt() -> None:
    prof = resolve_profile("production")
    state_path = prof.scheduler_state_path
    scheduled_dir = prof.evidence_path / "scheduled"
    assert not state_path.exists()
    runner.invoke(app, ["scheduler", "run", "daily-source-refresh",
                        "--environment", "production", "--date", _FUTURE, "--json"])
    assert not state_path.exists()  # no state mutation
    receipts = list(scheduled_dir.glob("*.json")) if scheduled_dir.exists() else []
    assert not any(_FUTURE in p.name for p in receipts)  # no success receipt


def test_due_reports_missed_with_future_success_date() -> None:
    st = SchedulerState(environment="production", last_successful_schedule_date=_FUTURE)
    now = datetime(2026, 6, 8, 1, 0, tzinfo=timezone.utc)  # 9pm ET Jun 7
    d = decide_catch_up(now, st, schedule_time_local="20:00",
                        timezone="America/New_York", catch_up_on_wake=True)
    assert d.should_run is True
    assert d.schedule_date == "2026-06-07"  # correct missed target, not the future date


def test_run_today_and_past_date_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import date as _date
    from zoneinfo import ZoneInfo

    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _canned_summary())
    today = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date()
    for d in (today, today - timedelta_days(2)):
        result = runner.invoke(app, ["scheduler", "run", "daily-source-refresh",
                                     "--environment", "production", "--date", d.isoformat(), "--json"])
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["schedule_date"] == d.isoformat()
    assert isinstance(today, _date)


def test_allow_future_date_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dsr_mod.SourceRefreshOrchestrator, "run", lambda self, *, options: _canned_summary())
    result = runner.invoke(app, ["scheduler", "run", "daily-source-refresh",
                                 "--environment", "production", "--date", _FUTURE,
                                 "--allow-future-date", "--json"])
    assert result.exit_code == 0
    d = json.loads(result.stdout)
    assert d["status"] == "ok" and d["schedule_date"] == _FUTURE


def test_status_flags_future_success_date() -> None:
    prof = resolve_profile("production")
    SchedulerState(environment="production", last_successful_schedule_date=_FUTURE).save(
        prof.scheduler_state_path
    )
    result = runner.invoke(app, ["scheduler", "status", "daily-source-refresh",
                                 "--environment", "production", "--json"])
    d = json.loads(result.stdout)
    assert d["future_last_successful_schedule_date"] is True
    assert d["state_health"] == "future_success_date_detected"


def test_scheduler_reset() -> None:
    prof = resolve_profile("production")
    SchedulerState(environment="production", last_successful_schedule_date=_FUTURE).save(
        prof.scheduler_state_path
    )
    no_confirm = runner.invoke(app, ["scheduler", "reset", "daily-source-refresh",
                                     "--environment", "production", "--json"])
    assert json.loads(no_confirm.stdout)["status"] == "confirmation_required"
    assert SchedulerState.load(prof.scheduler_state_path, environment="production").last_successful_schedule_date == _FUTURE
    confirmed = runner.invoke(app, ["scheduler", "reset", "daily-source-refresh",
                                    "--environment", "production", "--confirm", "--json"])
    assert json.loads(confirmed.stdout)["status"] == "ok"
    assert SchedulerState.load(prof.scheduler_state_path, environment="production").last_successful_schedule_date is None


def timedelta_days(n: int) -> Any:
    from datetime import timedelta

    return timedelta(days=n)
