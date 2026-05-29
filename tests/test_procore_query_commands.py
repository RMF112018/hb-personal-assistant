"""Phase 04B Prompt 10 — read-only query command contract tests.

All assertions confirm the commands are local-only (no Procore call, no live gate,
no token) and emit stable JSON over the seeded tmp SQLite DB.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.procore import app
from hb_assistant.construction.fixtures.procore import SUBMITTAL_SAMPLE_PAYLOAD
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import emit_action_signal
from hb_assistant.store.procore_history import record_procore_history_for_record

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_RUNNER = CliRunner()


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _invoke(*args: str) -> dict:
    result = _RUNNER.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def _seed_record_change(record_id: str, t1: str, t2: str) -> None:
    SQLiteMigrator().apply()
    record_procore_history_for_record(
        project_key="tropical", endpoint_id="rfis", parent_procore_id=None,
        procore_record_id=record_id, normalized_fields={"status": "Open", "subject": "Footing"},
        sync_run_id="s1", now_utc=t1,
    )
    record_procore_history_for_record(
        project_key="tropical", endpoint_id="rfis", parent_procore_id=None,
        procore_record_id=record_id, normalized_fields={"status": "Closed", "subject": "Footing"},
        sync_run_id="s2", now_utc=t2,
    )


# --------------------------------------------------------------------------- #
# help output
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("cmd", ["history", "changes", "timeline", "actions", "coverage"])
def test_command_help(cmd: str) -> None:
    result = _RUNNER.invoke(app, ["live", cmd, "--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output


# --------------------------------------------------------------------------- #
# history — record reconstruction
# --------------------------------------------------------------------------- #


def test_history_record_reconstruction() -> None:
    _seed_record_change("26550708", "2026-05-01T00:00:00Z", "2026-05-28T00:00:00Z")
    payload = _invoke("live", "history", "--project", "tropical", "--endpoint", "rfis",
                      "--record-id", "26550708", "--json")
    assert payload["ok"] is True
    assert payload["record_key"] == "tropical|rfis||26550708"
    assert payload["snapshot_count"] >= 2
    assert payload["change_count"] >= 1
    cats = {c["change_category"] for c in payload["changes"]}
    assert cats  # at least one classified change


# --------------------------------------------------------------------------- #
# changes — project lookback + relative time
# --------------------------------------------------------------------------- #


def test_changes_relative_lookback_filters_old() -> None:
    now = datetime.now(timezone.utc)
    _seed_record_change("recent", _iso(now - timedelta(days=60)), _iso(now))
    _seed_record_change("old", _iso(now - timedelta(days=90)), _iso(now - timedelta(days=30)))
    payload = _invoke("live", "changes", "--project", "tropical", "--since", "7 days ago", "--json")
    assert payload["ok"] is True
    ids = {c["procore_record_id"] for c in payload["changes"]}
    assert "recent" in ids
    assert "old" not in ids  # 30 days ago is outside the 7-day window


def test_changes_endpoint_filter_and_iso_since() -> None:
    _seed_record_change("26550708", "2026-05-01T00:00:00Z", "2026-05-28T00:00:00Z")
    payload = _invoke("live", "changes", "--project", "tropical",
                      "--since", "2026-05-10T00:00:00Z", "--endpoint", "rfis", "--json")
    assert payload["ok"] is True
    assert all(c["endpoint_id"] == "rfis" for c in payload["changes"])


def test_changes_unparseable_since_fails_closed() -> None:
    result = _RUNNER.invoke(app, ["live", "changes", "--project", "tropical", "--since", "whenever", "--json"])
    assert result.exit_code == 3
    assert "since_unparseable" in json.loads(result.output)["reason_codes"]


# --------------------------------------------------------------------------- #
# timeline
# --------------------------------------------------------------------------- #


def test_timeline_shape() -> None:
    _seed_record_change("26550708", "2026-05-01T00:00:00Z", "2026-05-28T00:00:00Z")
    payload = _invoke("live", "timeline", "--project", "tropical", "--since", "2026-01-01T00:00:00Z", "--json")
    assert payload["ok"] is True
    assert isinstance(payload["timeline"], list)
    assert payload["event_count"] == len(payload["timeline"])


# --------------------------------------------------------------------------- #
# actions — filters
# --------------------------------------------------------------------------- #


def _seed_signals() -> None:
    SQLiteMigrator().apply()
    emit_action_signal(project_key="tropical", record_key="tropical|rfis||1", endpoint_id="rfis",
                       signal_type="rfi_overdue", importance="high", signal_status="open", now_utc="2026-05-28T00:00:00Z")
    emit_action_signal(project_key="tropical", record_key="tropical|punch-items||2", endpoint_id="punch-items",
                       signal_type="punch_overdue", importance="medium", signal_status="resolved", now_utc="2026-05-28T00:00:00Z")


def test_actions_lists_all_and_filters_by_status() -> None:
    _seed_signals()
    all_payload = _invoke("live", "actions", "--project", "tropical", "--json")
    assert all_payload["action_count"] == 2
    open_payload = _invoke("live", "actions", "--project", "tropical", "--status", "open", "--json")
    assert open_payload["action_count"] == 1
    assert open_payload["actions"][0]["signal_type"] == "rfi_overdue"


def test_actions_filters_by_endpoint() -> None:
    _seed_signals()
    payload = _invoke("live", "actions", "--project", "tropical", "--endpoint", "punch-items", "--json")
    assert payload["action_count"] == 1
    assert payload["actions"][0]["endpoint_id"] == "punch-items"


# --------------------------------------------------------------------------- #
# coverage — from a fixture payload (names/types only)
# --------------------------------------------------------------------------- #


def test_coverage_report_from_fixture(tmp_path) -> None:
    payload_file = tmp_path / "submittal.json"
    payload_file.write_text(json.dumps(SUBMITTAL_SAMPLE_PAYLOAD[0]), encoding="utf-8")
    payload = _invoke("live", "coverage", "--project", "tropical", "--endpoint", "submittals",
                      "--raw-payload", str(payload_file), "--json")
    assert payload["ok"] is True
    assert payload["raw_field_count"] > 0
    assert "number" in payload["captured"]
    assert isinstance(payload["uncaptured"], list)
    assert 0.0 <= payload["coverage_ratio"] <= 1.0
    assert payload["no_raw_values_persisted"] is True
    # evidence-safe: the raw title VALUE must never appear in the report output
    assert "Door hardware schedule" not in json.dumps(payload)


def test_coverage_unreadable_payload_fails_closed(tmp_path) -> None:
    missing = tmp_path / "nope.json"
    result = _RUNNER.invoke(app, ["live", "coverage", "--project", "tropical", "--endpoint", "submittals",
                                  "--raw-payload", str(missing), "--json"])
    assert result.exit_code == 3
    assert "raw_payload_unreadable" in json.loads(result.output)["reason_codes"]


def test_unknown_endpoint_fails_closed() -> None:
    result = _RUNNER.invoke(app, ["live", "history", "--project", "tropical", "--endpoint", "not-an-endpoint",
                                  "--record-id", "1", "--json"])
    assert result.exit_code == 3
    assert "endpoint_alias_unknown" in json.loads(result.output)["reason_codes"]
