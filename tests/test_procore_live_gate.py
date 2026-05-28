"""Tests for the Phase 04A Prompt 01 HB_PROCORE_LIVE env-var gate.

Covers helper semantics (exact ``"1"`` enabler), CLI fail-closed behavior
on ``audit execute`` and ``sync run --apply`` when the env-var is absent,
and the strict mapping check at the live boundary. No live HTTP. All
env-var manipulation goes through ``monkeypatch``.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore import (
    LIVE_ENV_ENABLER,
    LIVE_ENV_VAR,
    LiveEnvNotSet,
    assert_live_mapping_strict,
    live_env_active,
    require_live_env,
)
from hb_assistant.procore.errors import ProcoreAPIError
from hb_assistant.procore.models import (
    ProcoreProjectMapping,
    ProcoreProjectsRegistry,
)

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


# ----------------------------------------------------------------------------
# live_env_active / require_live_env
# ----------------------------------------------------------------------------


def test_live_env_active_false_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    assert live_env_active() is False


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "on", "TRUE", "1 ", " 1"])
def test_live_env_active_false_for_non_enabler_values(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, value)
    assert live_env_active() is False


def test_live_env_active_true_only_for_exact_enabler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    assert live_env_active() is True


def test_require_live_env_raises_when_inactive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    with pytest.raises(LiveEnvNotSet) as exc_info:
        require_live_env(command="procore audit execute")
    assert exc_info.value.code == "live_env_not_set"
    assert "HB_PROCORE_LIVE" in exc_info.value.message
    assert exc_info.value.command == "procore audit execute"


def test_require_live_env_silent_when_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    require_live_env(command="procore sync run --apply")


# ----------------------------------------------------------------------------
# assert_live_mapping_strict
# ----------------------------------------------------------------------------


def _registry(rows: list[tuple[str, str, str]]) -> ProcoreProjectsRegistry:
    return ProcoreProjectsRegistry(
        company_id="5280",
        projects=[
            ProcoreProjectMapping(
                hb_project_key=key,
                procore_project_id=pid,
                procore_project_name="x" if pid else "",
                status=status,
            )
            for key, pid, status in rows
        ],
    )


def test_assert_live_mapping_strict_passes_for_mapped_pilots() -> None:
    reg = _registry(
        [
            ("tropical", "2525840", "pilot"),
            ("pga-modern-garage", "2091445", "pilot"),
        ]
    )
    assert_live_mapping_strict(reg, ["tropical", "pga-modern-garage"])


def test_assert_live_mapping_strict_rejects_pending() -> None:
    reg = _registry(
        [
            ("tropical", "2525840", "pilot"),
            ("hilltop", "", "pending"),
        ]
    )
    with pytest.raises(ProcoreAPIError) as exc_info:
        assert_live_mapping_strict(reg, ["tropical", "hilltop"])
    assert exc_info.value.code == "live_mapping_strict_violation"
    assert "hilltop" in exc_info.value.message


def test_assert_live_mapping_strict_rejects_unknown_key() -> None:
    reg = _registry([("tropical", "2525840", "pilot")])
    with pytest.raises(ProcoreAPIError) as exc_info:
        assert_live_mapping_strict(reg, ["does-not-exist"])
    assert "unknown_key" in exc_info.value.message


def test_assert_live_mapping_strict_aggregates_multiple_offenders() -> None:
    reg = _registry(
        [
            ("tropical", "2525840", "pilot"),
            ("hilltop", "", "pending"),
        ]
    )
    with pytest.raises(ProcoreAPIError) as exc_info:
        assert_live_mapping_strict(reg, ["hilltop", "does-not-exist"])
    assert "hilltop" in exc_info.value.message
    assert "does-not-exist" in exc_info.value.message


# ----------------------------------------------------------------------------
# CLI wire-up: gate blocks audit execute / sync run --apply without env var
# ----------------------------------------------------------------------------


def test_cli_audit_execute_blocks_without_live_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "audit", "execute", "--project", "tropical", "--confirm"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2
    assert "live_env_not_set" in res.output.lower() or "hb_procore_live" in res.output.lower()


def test_cli_audit_execute_blocks_with_non_enabler_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, "true")
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "audit", "execute", "--project", "tropical", "--confirm"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2


def test_cli_sync_run_apply_blocks_without_live_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "sync", "run", "--apply", "--confirm", "--project", "tropical"],
        catch_exceptions=False,
    )
    assert res.exit_code == 2
    assert "live_env_not_set" in res.output.lower() or "hb_procore_live" in res.output.lower()


def test_cli_sync_run_dry_run_default_unaffected_by_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default dry-run path must not require the live env var."""
    monkeypatch.delenv(LIVE_ENV_VAR, raising=False)
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "sync", "run", "--project", "tropical", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    assert "live_env_not_set" not in res.output.lower()


def test_live_env_and_live_enabled_still_require_confirm_live_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "sync",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--apply",
            "--sqlite-only",
            "--max-pages",
            "3",
            "--max-items",
            "100",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3
    assert "confirm_live_get_required" in res.output


def test_live_sync_unverified_endpoint_fails_closed_without_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unverified canonical endpoints must return not_live_verified without
    touching the live transport, even when every other gate is satisfied."""
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-live-token")
    called = {"hit": False}

    def _boom(*args: object, **kwargs: object) -> object:  # noqa: ARG001
        called["hit"] = True
        raise AssertionError("transport must not be invoked for unverified endpoint")

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _boom,
    )

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "sync",
            "--project",
            "tropical",
            "--endpoint",
            "meeting-topics",
            "--apply",
            "--sqlite-only",
            "--max-pages",
            "1",
            "--max-items",
            "10",
            "--confirm-live-get",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert called["hit"] is False
    assert res.exit_code == 2
    payload = json.loads(res.output)
    assert payload["state"] == "not_live_verified"
    assert payload["no_live_call_performed"] is True
    assert payload["request_count"] == 0
    assert "endpoint_unverified_for_live" in payload["reason_codes"]


def test_live_endpoints_list_emits_canonical_phase04a_rows() -> None:
    runner = CliRunner()
    res = runner.invoke(
        app,
        ["procore", "live", "endpoints", "list", "--json"],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    rows = payload.get("endpoints", [])
    rfis = next(r for r in rows if r["endpoint_id"] == "rfis")
    assert rfis["command_endpoint"] == "rfis"
    assert rfis["legacy_endpoint_alias"] == "list-rfis"
    assert rfis["live_verified"] is True
    topics_row = next(r for r in rows if r["endpoint_id"] == "meeting-topics")
    assert topics_row["live_verified"] is False
