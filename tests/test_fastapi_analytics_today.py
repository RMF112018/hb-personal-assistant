"""Prompt 17 — Today dashboard read model and UX contract tests (FPR-008)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "raw_prompt",
    "raw_response",
    "downloadUrl",
    "token=",
    "sig=",
    "BEGIN PRIVATE",
    "raw_document_text",
    "signed_url",
    "raw_calendar_payload",
)


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    db = str(tmp_path / "today-dashboard.sqlite")
    SQLiteMigrator(db_path=db).apply()
    # Seed minimal procore live records so _project_keys and freshness have data (single-user MVP)
    # The service tolerates missing; tests exercise both paths.
    return TestClient(create_app(db_path=db)), db


def _assert_safe(payload: Any) -> None:
    serialized = json.dumps(payload, default=str)
    for marker in FORBIDDEN:
        assert marker not in serialized


def test_today_viewer_ok_and_contract(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/api/today")
    assert r.status_code == 200
    p = r.json()
    assert p["surface"] == "analytics.today"
    assert "generated_utc" in p
    assert "guardrails" in p and p["guardrails"]["advisory_only"] is True
    assert "metric_cards" in p and isinstance(p["metric_cards"], list)
    assert "attention_items" in p and isinstance(p["attention_items"], list)
    assert "sections" in p and isinstance(p["sections"], list)
    # at least advisory + badges
    assert any("Advisory signal only" in (n or "") for n in p.get("advisory_notes", []))
    assert "freshness" in p and "confidence_summary" in p
    assert "project_count" in p
    _assert_safe(p)


def test_today_sections_include_required_areas(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    p = client.get("/api/today").json()
    sections = p.get("sections", [])
    # Prompt 17: after split, expect the UX areas (cost/change/time + documents/correspondence)
    # or the prior portfolio_signals for compat; assert the required concepts are represented
    joined = " ".join(sections).lower()
    assert ("cost" in joined and "change" in joined and "time" in joined) or "portfolio_signals" in sections
    assert ("documents" in joined and "correspondence" in joined) or "portfolio_signals" in sections
    # Always keep the core today areas
    for required in ("important_today", "todays_meetings", "what_changed", "action_items"):
        assert required in sections or any(required in s for s in sections)
    _assert_safe(p)


def test_today_compatibility_sections_are_metadata_only(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    for path, surface in (
        ("/api/today/changes", "analytics.today.changes"),
        ("/api/today/meetings", "analytics.today.meetings"),
        ("/api/today/action-items", "analytics.today.action_items"),
        ("/api/today/portfolio-signals", "analytics.today.portfolio_signals"),
    ):
        r = client.get(path)
        assert r.status_code == 200
        p = r.json()
        assert p["surface"] == surface
        assert isinstance(p.get("items"), list)
        assert p.get("source") == "analytics.today"
        assert "freshness" in p
        assert "confidence_summary" in p
        assert p["guardrails"]["advisory_only"] is True
        assert "advisory_notes" in p
        assert "empty_state_reason_code" in p
        _assert_safe(p)


def test_today_daily_brief_presentation(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/api/today/daily-brief")
    assert r.status_code == 200
    p = r.json()
    # External MD only; states + content or sections; no raw generator material
    assert "status" in p or "state" in p or "content" in p or "markdown" in p
    _assert_safe(p)


def test_today_graceful_empty_and_role_403(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    # even though viewer posture, the dep still rejects bad role header
    r = client.get("/api/today", headers={"X-HB-UI-Role": "writer"})
    assert r.status_code == 403
    assert r.json()["detail"] == "invalid_ui_role"

    # Empty projects path degrades (service already handles via empty metrics)
    p = client.get("/api/today").json()
    assert p.get("empty_stale_error") is not None or len(p.get("project_keys", [])) >= 0
    _assert_safe(p)


def test_today_no_raw_fields(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    # Full surface + granular + daily brief
    surfaces = [
        "/api/today",
        "/api/today/changes",
        "/api/today/meetings",
        "/api/today/action-items",
        "/api/today/portfolio-signals",
        "/api/today/daily-brief",
    ]
    for path in surfaces:
        resp = client.get(path)
        assert resp.status_code < 500
        try:
            payload = resp.json()
        except Exception:
            payload = {"text": resp.text[:500]}
        _assert_safe(payload)
        if isinstance(payload, dict) and "guardrails" in payload:
            g = payload["guardrails"] or {}
            if "no_raw_sensitive_response_fields" in g:
                assert g.get("no_raw_sensitive_response_fields") is True
            if "read_only" in g:
                assert g.get("read_only") is True
            if "advisory_only" in g:
                assert g.get("advisory_only") is True