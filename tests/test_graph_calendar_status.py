"""Phase 07B Prompt 03 — `hb-assistant graph calendar status --json` CLI.

Verifies the command parses, emits the read-only-readiness envelope with the
runtime mutation-lockout self-test passing, reports the write-capable scope as a
deferred-tightening residual risk (not a failure), and never leaks a token.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.main import app

runner = CliRunner()


def _invoke(tmp_path: Path, *args: str):
    return runner.invoke(
        app,
        list(args),
        env={"HB_APP_SUPPORT_DIR": str(tmp_path)},
        catch_exceptions=False,
    )


def test_graph_calendar_status_envelope_and_guardrails(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "calendar", "status", "--json", "--no-probe")
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    for key in (
        "command",
        "ok",
        "calendar_read_capability_present",
        "write_capable_calendar_scopes_present",
        "auth",
        "guard_self_test",
        "calendar_probe",
        "guardrails",
        "contract",
    ):
        assert key in payload, f"missing {key}"
    assert payload["command"] == "graph calendar status"
    assert payload["ok"] is True
    # Mutation lockout proven in-process, no network needed.
    assert payload["guard_self_test"]["passed"] is True
    assert payload["guard_self_test"]["anomalies"] == []
    g = payload["guardrails"]
    assert g["calendar_read_only"] is True
    assert g["mutation_endpoints_blocked"] is True
    assert g["event_body_excluded"] is True
    assert g["join_url_excluded"] is True
    assert g["permission_tightening"] == "deferred"
    assert g["residual_risk"]
    assert g["guardrail_status"] == "passed"
    assert payload["contract"]["allowed_methods"] == ["GET"]


def test_graph_calendar_status_reports_write_scope_as_deferred(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "calendar", "status", "--json", "--no-probe")
    payload = json.loads(res.output)
    # The write-capable scope is consented; it is FLAGGED, not fatal.
    assert "Calendars.ReadWrite.Shared" in payload["write_capable_calendar_scopes_present"]
    assert payload["calendar_read_capability_present"] is True
    assert payload["ok"] is True


def test_graph_calendar_status_no_token_leak(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "calendar", "status", "--json", "--no-probe")
    assert "access_token" not in res.output
    assert "Bearer " not in res.output


def test_graph_calendar_status_no_probe_marks_probe_not_attempted(tmp_path: Path) -> None:
    res = _invoke(tmp_path, "graph", "calendar", "status", "--json", "--no-probe")
    payload = json.loads(res.output)
    assert payload["calendar_probe"]["attempted"] is False


def test_configured_calendar_scopes_prefers_consented_scope() -> None:
    # The calendar token-getter must request the CONFIGURED Calendars.* scope, not a
    # hardcoded Calendars.Read that may never have been consented.
    from hb_assistant.cli.graph import _configured_calendar_scopes

    configured = ["User.Read", "Mail.Read", "Calendars.ReadWrite.Shared", "Files.ReadWrite.All"]
    assert _configured_calendar_scopes(configured) == ["Calendars.ReadWrite.Shared"]
    # Fallback only when no Calendars.* scope is configured.
    assert _configured_calendar_scopes(["User.Read"]) == ["Calendars.Read"]
