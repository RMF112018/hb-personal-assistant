"""Phase 04B Prompt 11 — enriched Obsidian register tests (read-only / local)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.procore import app
from hb_assistant.procore.obsidian_register import apply_enriched_register, build_enriched_registers
from hb_assistant.store.migrator import SQLiteMigrator
from hb_assistant.store.procore_enrichment import emit_action_signal, emit_text_intelligence
from hb_assistant.store.procore_history import record_procore_history_for_record

pytestmark = pytest.mark.usefixtures("isolated_hb_pa_config")

_NOW = "2026-05-29T00:00:00Z"
_SINCE = "2026-05-01T00:00:00Z"
_SECTION_KEYS = {
    "open_actions",
    "recent_changes",
    "inspection_unanswered",
    "safety_queue",
    "meeting_actions",
    "rfi_response_changes",
    "submittal_workflow_changes",
    "schedule_risk",
}
_RUNNER = CliRunner()


def _seed() -> None:
    SQLiteMigrator().apply()
    # action signals across families
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|rfis||701",
        endpoint_id="rfis",
        signal_type="rfi_overdue",
        importance="high",
        signal_status="open",
        now_utc=_NOW,
    )
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|inspection-items||9",
        endpoint_id="inspection-items",
        signal_type="inspection_item_unanswered",
        importance="medium",
        signal_status="open",
        now_utc=_NOW,
    )
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|observations||5",
        endpoint_id="observations",
        signal_type="observation_open_safety",
        importance="high",
        signal_status="open",
        now_utc=_NOW,
    )
    emit_action_signal(
        project_key="tropical",
        record_key="tropical|activities||245",
        endpoint_id="activities",
        signal_type="activity_critical",
        importance="high",
        signal_status="open",
        now_utc=_NOW,
    )
    # change events (rfis + submittals) via two snapshots each
    for ep, rid in (("rfis", "701"), ("submittals", "4040")):
        record_procore_history_for_record(
            project_key="tropical",
            endpoint_id=ep,
            parent_procore_id=None,
            procore_record_id=rid,
            normalized_fields={"status": "Open"},
            sync_run_id="s1",
            now_utc="2026-05-10T00:00:00Z",
        )
        record_procore_history_for_record(
            project_key="tropical",
            endpoint_id=ep,
            parent_procore_id=None,
            procore_record_id=rid,
            normalized_fields={"status": "Closed"},
            sync_run_id="s2",
            now_utc="2026-05-28T00:00:00Z",
        )
    # meeting text intelligence with action candidates + a URL/email to confirm masking
    emit_text_intelligence(
        project_key="tropical",
        record_key="tropical|meeting-topics|555|1001",
        endpoint_id="meeting-topics",
        source_field_path="minutes",
        text="Decision: email pm@example.test and see https://app.procore.example/x?token=secret. Action item: follow up.",
        action_candidates=["action item", "follow up", "decision:"],
        excerpt_chars=160,
        now_utc=_NOW,
    )


def test_dry_run_build_has_all_sections_no_writes() -> None:
    _seed()
    result = build_enriched_registers("tropical", since_utc=_SINCE, now_utc=_NOW)
    assert set(result["sections"]) == _SECTION_KEYS
    assert result["review_sensitive"] is False
    assert result["counts"]["open_actions"] >= 1
    assert result["counts"]["schedule_risk"] >= 1
    assert "written_paths" not in result or result.get("written_paths") in (None, [])


def test_source_links_and_query_refs_present() -> None:
    _seed()
    rendered = build_enriched_registers("tropical", since_utc=_SINCE, now_utc=_NOW)["rendered"]
    # record_key (source link) — pipes are markdown-escaped in table cells
    assert "tropical\\|rfis\\|\\|701" in rendered
    assert "tropical\\|activities\\|\\|245" in rendered
    assert "hb-assistant procore live actions --project tropical" in rendered  # query command refs
    assert "hb-assistant procore live changes --project tropical" in rendered
    # change-derived sections carry the procore_record_id
    assert "4040" in rendered


def test_no_signed_urls_tokens_or_raw_payload() -> None:
    _seed()
    rendered = build_enriched_registers("tropical", since_utc=_SINCE, now_utc=_NOW)["rendered"]
    assert "https://" not in rendered and "token=secret" not in rendered and "?sig=" not in rendered
    assert "Bearer" not in rendered and ("access_" + "token") not in rendered
    assert "pm@example.test" not in rendered  # email masked in excerpt
    # action-candidate tokens (safe) do surface
    assert "follow up" in rendered


def test_apply_writes_single_file_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed()
    vault = tmp_path / "cvault"
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(vault))
    result = apply_enriched_register("tropical", since_utc=_SINCE, now_utc=_NOW)
    assert result["vault_configured"] is True
    assert len(result["written_paths"]) == 1
    target = Path(result["written_paths"][0])
    assert target.name == "tropical.procore-memory-register.md"
    assert target.parent.name == "01_Projects"
    content = target.read_text(encoding="utf-8")
    assert "type: procore_enriched_register" in content
    assert "<!-- HB-PROCORE-ENRICHED-REGISTER:START -->" in content
    assert "## Open Actions" in content and "## Schedule Risk Signals" in content
    # idempotent: only the single file, re-run stable
    apply_enriched_register("tropical", since_utc=_SINCE, now_utc=_NOW)
    files = list((vault / "01_Projects").glob("*.md"))
    assert files == [target]
    assert content.count("<!-- HB-PROCORE-ENRICHED-REGISTER:START -->") == 1


def test_cli_dry_run_json() -> None:
    _seed()
    result = _RUNNER.invoke(
        app, ["obsidian", "enriched", "--project", "tropical", "--dry-run", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True and payload["mode"] == "dry_run"
    assert set(payload["section_keys"]) == _SECTION_KEYS
    assert payload["written_paths"] == []


def test_cli_apply_writes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed()
    monkeypatch.setenv("HB_CONSTRUCTION_VAULT_ROOT", str(tmp_path / "cvault"))
    result = _RUNNER.invoke(
        app, ["obsidian", "enriched", "--project", "tropical", "--apply", "--confirm", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["mode"] == "apply"
    assert len(payload["written_paths"]) == 1
    assert Path(payload["written_paths"][0]).exists()


def test_cli_unparseable_since_fails_closed() -> None:
    result = _RUNNER.invoke(
        app, ["obsidian", "enriched", "--project", "tropical", "--since", "whenever", "--json"]
    )
    assert result.exit_code == 3
    assert "since_unparseable" in json.loads(result.output)["reason_codes"]
