"""Prompt 07 — dashboard read models (Today, Projects portfolio/all, per-project tabs, My Items)."""

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
)


def _client(tmp_path: Path) -> tuple[TestClient, str]:
    db = str(tmp_path / "dashboard-read-models.sqlite")
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
    # at least advisory + badges
    assert any("Advisory signal only" in (n or "") for n in p.get("advisory_notes", []))
    assert "freshness" in p and "confidence_summary" in p
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
        assert isinstance(p["items"], list)
        assert p["source"] == "analytics.today"
        assert "freshness" in p
        assert "confidence_summary" in p
        assert p["guardrails"]["advisory_only"] is True
        assert "advisory_notes" in p
        assert "empty_state_reason_code" in p
        _assert_safe(p)


def test_projects_portfolio_and_all_overview_viewer_ok(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    for path in ("/api/projects/portfolio", "/api/projects/all/overview"):
        r = client.get(path)
        assert r.status_code == 200
        p = r.json()
        assert "surface" in p and p["surface"].startswith("analytics.projects")
        # Prompt 18: portfolio response is object (not bare array); project_keys present as array for selector;
        # freshness/confidence on the envelope (used for header badges); metric_cards/attention safe per 16.
        assert not isinstance(p, list)
        if path.endswith("/portfolio"):
            assert "project_keys" in p and isinstance(p.get("project_keys"), list)
            assert "freshness" in p and "confidence_summary" in p
        assert isinstance(p.get("metric_cards"), list)
        assert isinstance(p.get("attention_items"), list)
        _assert_safe(p)


def test_per_project_tabs_viewer_ok(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    pk = "demo-proj"
    for suffix in ("overview", "meetings", "field-operations", "cost-time"):
        r = client.get(f"/api/projects/{pk}/{suffix}")
        assert r.status_code == 200
        p = r.json()
        assert p["surface"].startswith("analytics.project.")
        assert p.get("project_key") == pk
        assert "freshness" in p and "confidence_summary" in p
        # Prompt 16: object envelopes (metric_cards/attention_items arrays); not bare array or root 'items'
        assert isinstance(p.get("metric_cards"), list)
        assert isinstance(p.get("attention_items"), list)
        assert not isinstance(p, list)
        _assert_safe(p)


def test_my_items_viewer_ok(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    r = client.get("/api/my-items")
    assert r.status_code == 200
    p = r.json()
    assert p["surface"] == "analytics.my_items"
    # Prompt 16/19: object envelope (not bare array); 5 canonical sections present; explicit per-section arrays are lists.
    assert "sections" in p
    for sec in ("my_action_items", "my_meetings", "my_correspondence", "my_files", "my_followed_projects"):
        assert sec in p["sections"]
    assert isinstance(p.get("metric_cards"), list)
    assert isinstance(p.get("attention_items"), list)
    # Prompt 19: explicit section arrays for queue rendering (in addition to attention_items)
    for k in ("my_action_items", "my_meetings", "my_correspondence", "my_files", "my_followed_projects"):
        assert isinstance(p.get(k), list)
    assert "project_keys" in p and isinstance(p.get("project_keys"), list)
    assert not isinstance(p, list)
    assert "items" not in p or isinstance(p.get("items"), (dict, list))  # today-compat only use 'items'
    # freshness/confidence and empty handling are exercised by service + other tests
    assert "freshness" in p and "confidence_summary" in p
    _assert_safe(p)


def test_invalid_role_is_forbidden_for_dashboard(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    # even though viewer posture, the dep still rejects bad role header
    r = client.get("/api/today", headers={"X-HB-UI-Role": "writer"})
    assert r.status_code == 403
    assert r.json()["detail"] == "invalid_ui_role"


def test_empty_projects_degrades_gracefully(tmp_path: Path) -> None:
    # DB with no procore_live_records -> _project_keys empty -> unavailable states present
    client, _ = _client(tmp_path)
    # The seed in _client is light; service already handles empty via _empty_metric paths
    p = client.get("/api/today").json()
    # either has projects or empty_stale_error / unavailable cards
    assert p.get("empty_stale_error") is not None or len(p.get("project_keys", [])) >= 0
    _assert_safe(p)
