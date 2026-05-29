from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.main import app
from hb_assistant.procore import LIVE_ENV_ENABLER, LIVE_ENV_VAR

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")


class _AuthReady:
    ready_for_live_calls = True
    status = "ready"


class _FakeResponse:
    def __init__(self, status_code: int, payload: object, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = ""

    def json(self) -> object:
        return self._payload


def test_live_inspect_requires_confirm_raw_payload_dump(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    runner = CliRunner()
    out_dir = tmp_path / "payload-review"
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--max-pages",
            "1",
            "--max-items",
            "5",
            "--confirm-live-get",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3
    payload = json.loads(res.output)
    assert "confirm_raw_payload_dump_required" in payload["reason_codes"]


def test_live_inspect_rejects_repo_output_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--max-pages",
            "1",
            "--max-items",
            "5",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            "/Users/bobbyfetting/hb-personal-assistant/tmp",
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3
    payload = json.loads(res.output)
    assert "output_dir_inside_repo" in payload["reason_codes"]


def test_live_inspect_writes_only_output_file_and_returns_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-access-token")
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    calls = {"count": 0}

    def _fake_default_live_transport(self, method: str, url: str, headers: dict[str, str], params: dict | None = None):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        assert method == "GET"
        return _FakeResponse(
            200,
            [{"id": "rfi-1", "number": "RFI-1", "title": "Sample"}],
            headers={},
        )

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _fake_default_live_transport,
    )

    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--max-pages",
            "1",
            "--max-items",
            "5",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["record_count"] == 1
    assert payload["attempt_count"] == 1
    assert payload["retry_count"] == 0
    assert payload["no_sqlite_write"] is True
    assert payload["no_evidence_write"] is True
    assert payload["no_obsidian_write"] is True
    assert payload["output_file_path"].endswith(".json")
    assert payload["output_file_sha256"]
    assert "canonical_json_redacted" not in res.output
    assert calls["count"] == 1

    written = Path(payload["output_file_path"])
    assert written.exists()
    body = written.read_text(encoding="utf-8")
    assert "rfi-1" in body


def test_live_inspect_rate_limited_single_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-access-token")
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    calls = {"count": 0}

    def _fake_default_live_transport(self, method: str, url: str, headers: dict[str, str], params: dict | None = None):  # type: ignore[no-untyped-def]
        calls["count"] += 1
        return _FakeResponse(429, {"error": "rate_limited"}, headers={})

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _fake_default_live_transport,
    )

    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--max-pages",
            "1",
            "--max-items",
            "5",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3
    payload = json.loads(res.output)
    assert payload["reason_codes"] == ["transport_error:429_rate_limited"]
    assert payload["attempt_count"] == 1
    assert payload["request_count"] == 1
    assert payload["retry_count"] == 0
    assert calls["count"] == 1


def test_live_inspect_optional_redacted_derivative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-access-token")
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    def _fake_default_live_transport(self, method: str, url: str, headers: dict[str, str], params: dict | None = None):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            200,
            [{"id": "row-1", "access_token": "secret-token-value"}],
            headers={},
        )

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _fake_default_live_transport,
    )

    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfis",
            "--max-pages",
            "1",
            "--max-items",
            "5",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--redact-known-sensitive-fields",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["redacted_output_file_path"]
    redacted = Path(payload["redacted_output_file_path"])
    assert redacted.exists()
    redacted_body = redacted.read_text(encoding="utf-8")
    assert "[REDACTED]" in redacted_body


def test_live_inspect_child_endpoint_fails_when_parent_not_found_in_sqlite(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())
    monkeypatch.setattr(
        "hb_assistant.store.procore_repositories.get_first_procore_record_id",
        lambda **_: None,
    )
    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfi-responses",
            "--max-pages",
            "1",
            "--max-items",
            "1",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 3
    payload = json.loads(res.output)
    assert "parent_record_not_found_in_sqlite:rfis" in payload["reason_codes"]
    assert payload["parent_resolution_source"] == "unresolved"


def test_live_inspect_rfi_responses_accepts_rfi_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-access-token")
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    seen_url: dict[str, str] = {}

    def _fake_default_live_transport(self, method: str, url: str, headers: dict[str, str], params: dict | None = None):  # type: ignore[no-untyped-def]
        seen_url["value"] = url
        return _FakeResponse(200, [{"id": "reply-1"}], headers={})

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _fake_default_live_transport,
    )

    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "rfi-responses",
            "--rfi-id",
            "12345",
            "--max-pages",
            "1",
            "--max-items",
            "1",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["parent_resolution_source"] == "explicit_flag"
    assert payload["resolved_parent_endpoint_id"] == "rfis"
    assert payload["resolved_parent_id"] == "12345"
    assert "/rfis/12345/replies" in seen_url["value"]


def test_live_inspect_activities_accepts_schedule_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-access-token")
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())

    seen_url: dict[str, str] = {}

    def _fake_default_live_transport(self, method: str, url: str, headers: dict[str, str], params: dict | None = None):  # type: ignore[no-untyped-def]
        seen_url["value"] = url
        return _FakeResponse(200, {"data": [{"id": "act-1"}]}, headers={})

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _fake_default_live_transport,
    )

    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            "activities",
            "--schedule-id",
            "200",
            "--max-pages",
            "1",
            "--max-items",
            "1",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["parent_resolution_source"] == "explicit_flag"
    assert payload["resolved_parent_endpoint_id"] == "schedules"
    assert payload["resolved_parent_id"] == "200"
    assert "/companies/5280/projects/2525840/schedules/200/activities" in seen_url["value"]


@pytest.mark.parametrize(
    ("endpoint", "parent_endpoint", "expected_path"),
    [
        ("rfi-responses", "rfis", "/rfis/700/replies"),
        ("submittal-responses", "submittals", "/submittals/700/responses"),
        ("meeting-detail", "meetings", "/meetings/700"),
        ("activities", "schedules", "/schedules/700/activities"),
    ],
)
def test_live_inspect_auto_resolves_child_parent_id_from_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    endpoint: str,
    parent_endpoint: str,
    expected_path: str,
) -> None:
    monkeypatch.setenv(LIVE_ENV_VAR, LIVE_ENV_ENABLER)
    monkeypatch.setenv("PROCORE_ACCESS_TOKEN", "synthetic-access-token")
    monkeypatch.setattr("hb_assistant.cli.procore.check_auth_status", lambda: _AuthReady())
    monkeypatch.setattr(
        "hb_assistant.store.procore_repositories.get_first_procore_record_id",
        lambda **kwargs: "700" if kwargs["endpoint_id"] == parent_endpoint else None,
    )

    seen_url: dict[str, str] = {}

    def _fake_default_live_transport(self, method: str, url: str, headers: dict[str, str], params: dict | None = None):  # type: ignore[no-untyped-def]
        seen_url["value"] = url
        payload: object = [{"id": "row-1"}]
        if endpoint == "activities":
            payload = {"data": [{"id": "row-1"}]}
        return _FakeResponse(200, payload, headers={})

    monkeypatch.setattr(
        "hb_assistant.procore.http_client.ProcoreHTTPClient._default_live_transport",
        _fake_default_live_transport,
    )

    out_dir = tmp_path / "payload-review"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "procore",
            "live",
            "inspect",
            "--project",
            "tropical",
            "--endpoint",
            endpoint,
            "--max-pages",
            "1",
            "--max-items",
            "1",
            "--confirm-live-get",
            "--confirm-raw-payload-dump",
            "--output-dir",
            str(out_dir),
            "--json",
        ],
        catch_exceptions=False,
    )
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["parent_resolution_source"] == "sqlite_first_occurrence"
    assert payload["resolved_parent_endpoint_id"] == parent_endpoint
    assert payload["resolved_parent_id"] == "700"
    assert expected_path in seen_url["value"]
