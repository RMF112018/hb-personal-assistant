"""Phase 10 — MCP context packet hardening (contract envelope + fail-closed forbidden-content gate).

Proves the hardened packet wraps the existing context builder in an explicit MCP contract (purpose,
source window, caps, omitted-raw categories, redaction flags, source-ref summary, freshness warnings),
stays raw-free, fails closed (withholds context) when a forbidden pattern reaches the payload, and that
the `daily-brief mcp-packet` CLI verb works.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import hb_assistant.construction.second_brain.local_ai.mcp_packet_hardening as mph
from hb_assistant.cli.main import app
from hb_assistant.construction.second_brain.local_ai.mcp_packet_hardening import (
    OMITTED_RAW_CATEGORIES,
    build_hardened_mcp_packet,
    render_hardened_mcp_packet_markdown,
    scan_for_forbidden_content,
)
from hb_assistant.construction.store import ConstructionStore
from typer.testing import CliRunner

runner = CliRunner()
NOW = "2026-06-09T05:00:00-04:00"


def test_scan_detects_forbidden_patterns_not_labels() -> None:
    assert scan_for_forbidden_content({"x": "https://evil.example/path"}) == ["url"]
    # Build the synthetic bearer value at runtime so no literal token string is committed to source
    # (keeps the repo sensitive-scan clean while still exercising the gate's bearer detection).
    synthetic_bearer = "Bearer " + ("a" * 24)
    assert "bearer" in scan_for_forbidden_content({"x": synthetic_bearer})
    assert scan_for_forbidden_content({"x": "a@b.com"}) == ["email"]
    # The contract's category labels (e.g. "bearer_tokens", "signed_urls") are NOT forbidden content.
    assert scan_for_forbidden_content({"omitted": list(OMITTED_RAW_CATEGORIES)}) == []


def test_clean_packet_has_contract_envelope(tmp_path: Path) -> None:
    store = ConstructionStore(db_path=str(tmp_path / "p.db"))
    packet = build_hardened_mcp_packet(store=store, now_utc=NOW, db_path=str(tmp_path / "p.db"))
    assert packet["ok"] is True
    assert packet["redaction_triggered"] is False
    for key in ("packet_contract_version", "purpose", "generated_at", "source_window",
                "candidate_summaries", "source_ref_summary", "caps_applied",
                "omitted_raw_categories", "redaction_flags", "freshness_quality_warnings",
                "guardrails", "context"):
        assert key in packet, key
    assert packet["guardrails"]["fail_closed_on_forbidden_content"] is True
    assert packet["guardrails"]["no_external_writeback"] is True
    # Raw-free.
    blob = json.dumps(packet) + render_hardened_mcp_packet_markdown(packet)
    for bad in ("Bearer ", "https://", "-----BEGIN"):
        assert bad not in blob


def test_packet_fails_closed_on_forbidden_content(tmp_path: Path, monkeypatch) -> None:
    # Force the context builder to return a payload containing a URL → gate must withhold.
    def _leaky(**_kw):
        return {"date_window": {"run_date": "2026-06-09"}, "open_commitments": {},
                "candidates_by_section": {}, "relationships": [], "procore_signals": [],
                "calendar": [{"prep": "join https://teams.microsoft.com/x"}], "data_gaps": [],
                "caps": {}}
    monkeypatch.setattr(mph, "build_daily_brief_context_packet", _leaky)
    store = ConstructionStore(db_path=str(tmp_path / "p.db"))
    packet = build_hardened_mcp_packet(store=store, now_utc=NOW, db_path=str(tmp_path / "p.db"))
    assert packet["ok"] is False
    assert packet["redaction_triggered"] is True
    assert packet["withheld_reason"] == "forbidden_content_detected"
    assert "url" in packet["leak_categories"]
    assert packet["context"] is None  # raw payload withheld
    assert "WITHHELD" in render_hardened_mcp_packet_markdown(packet)


def test_cli_mcp_packet_emits_json(tmp_path: Path) -> None:
    db = str(tmp_path / "p.db")
    ConstructionStore(db_path=db)
    res = runner.invoke(app, ["second-brain", "daily-brief", "mcp-packet", "--db", db,
                              "--as-of", NOW, "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["packet_contract_version"] == "phase10-mcp-1.0"
    assert payload["guardrails"]["no_raw_content"] is True


def test_cli_mcp_packet_no_json_emits_markdown(tmp_path: Path) -> None:
    # --no-json must be accepted (post-merge hardening) and print operator Markdown, not JSON.
    db = str(tmp_path / "p.db")
    ConstructionStore(db_path=db)
    res = runner.invoke(app, ["second-brain", "daily-brief", "mcp-packet", "--db", db,
                              "--as-of", NOW, "--no-json"])
    assert res.exit_code == 0, res.output
    assert res.output.lstrip().startswith("# MCP Context Packet")
    # It is Markdown, not JSON.
    with pytest.raises(json.JSONDecodeError):
        json.loads(res.output)
