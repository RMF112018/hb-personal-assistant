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
    assert payload["no_sqlite_write"] is True
    assert payload["no_evidence_write"] is True
    assert payload["no_obsidian_write"] is True
    assert payload["output_file_path"].endswith(".json")
    assert payload["output_file_sha256"]
    assert "canonical_json_redacted" not in res.output
    assert calls["count"] >= 1

    written = Path(payload["output_file_path"])
    assert written.exists()
    body = written.read_text(encoding="utf-8")
    assert "rfi-1" in body


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
