"""Canonical CLI grammar tests for Prompt 02 remediation.

Focus: parser/command-shape compatibility for required canonical commands.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.automation.launchd_manager import LaunchdManager
from hb_assistant.cli.main import app


runner = CliRunner()


def _invoke_in_isolated_app_support(args: list[str]):
    return runner.invoke(
        app,
        args,
        env={"HB_APP_SUPPORT_DIR": str(Path.cwd() / ".tmp-app-support-cli-tests")},
    )


def test_root_help_parses() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_auth_help_parses() -> None:
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0


def test_run_help_parses() -> None:
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0


def test_auth_login_parses() -> None:
    result = _invoke_in_isolated_app_support(["auth", "login", "--json"])
    assert result.exit_code in (0, 1)


def test_auth_status_parses() -> None:
    result = _invoke_in_isolated_app_support(["auth", "status", "--json"])
    assert result.exit_code in (0, 1)


def test_auth_logout_parses() -> None:
    result = _invoke_in_isolated_app_support(["auth", "logout", "--json"])
    assert result.exit_code in (0, 1)


def test_auth_clear_cache_parses() -> None:
    result = _invoke_in_isolated_app_support(["auth", "clear-cache", "--json"])
    assert result.exit_code in (0, 1)


def test_run_morning_dry_run_parses() -> None:
    result = _invoke_in_isolated_app_support(["run", "morning", "--dry-run", "--json"])
    assert result.exit_code in (0, 1)


def test_diagnostics_env_parses() -> None:
    result = _invoke_in_isolated_app_support(["diagnostics", "env", "--json"])
    assert result.exit_code == 0


def test_diagnostics_graph_safe_parses() -> None:
    result = _invoke_in_isolated_app_support(["diagnostics", "graph", "--safe", "--json"])
    assert result.exit_code in (0, 1)


def test_diagnostics_automation_parses() -> None:
    result = _invoke_in_isolated_app_support(["diagnostics", "automation", "--json"])
    assert result.exit_code == 0


def test_diagnostics_scan_sensitive_parses() -> None:
    result = _invoke_in_isolated_app_support(["diagnostics", "scan-sensitive", "--repo", ".", "--json"])
    assert result.exit_code == 0


def test_launchd_program_arguments_match_run_group_shape() -> None:
    mgr = LaunchdManager()
    args = mgr.render_plist()["ProgramArguments"]
    assert len(args) >= 3
    assert args[1] == "run"
    assert args[2] == "morning"
