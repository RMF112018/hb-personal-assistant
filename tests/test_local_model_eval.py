"""Phase 10 — local model evaluation harness tests (offline, hermetic, no daemon, no raw egress)."""

from __future__ import annotations

import json

import pytest

from hb_assistant.construction.second_brain.local_ai import model_eval
from hb_assistant.construction.second_brain.local_ai.model_eval import (
    TASK_FAMILY_SCHEMAS,
    run_model_eval,
)
from hb_assistant.construction.second_brain.local_ai.model_eval_fixtures import (
    ModelEvalFixture,
    RawFixtureRefusedError,
    load_raw_fixtures,
    synthetic_fixtures,
    synthetic_fixtures_for,
)
from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
    compute_usefulness,
    scan_text_for_forbidden,
)


def test_synthetic_fixtures_cover_five_families() -> None:
    fixtures = synthetic_fixtures()
    families = {f.task_family for f in fixtures}
    assert families == set(TASK_FAMILY_SCHEMAS)
    assert len(fixtures) == 5
    # Every synthetic fixture is redaction-clean by construction.
    for f in fixtures:
        assert scan_text_for_forbidden(f.synthetic_output) == [], f.fixture_id


def test_synthetic_fixtures_filter() -> None:
    only = synthetic_fixtures_for(["email_action_extraction_json"])
    assert [f.task_family for f in only] == ["email_action_extraction_json"]


def test_redaction_scanner_catches_forbidden_tokens() -> None:
    assert "url" in scan_text_for_forbidden("see http://example.com/x")
    assert "email" in scan_text_for_forbidden("ping bobby@example.com please")
    assert "join_link" in scan_text_for_forbidden("join at teams.microsoft.com/l/meetup")
    assert "bearer" in scan_text_for_forbidden("Authorization: Bearer abcdef1234567890")
    assert "access_token" in scan_text_for_forbidden('{"access_token": "x"}')
    assert "jwt_like" in scan_text_for_forbidden("eyJhbGciOi.eyJzdWIiOiJ")
    assert scan_text_for_forbidden("clean source-linked operator text id:cand:1") == []


def test_usefulness_rewards_source_links_and_penalizes_empty() -> None:
    good = {"executive_summary": ["clear point"], "items": [{"text": "do it", "source_id": "cand:1"}]}
    assert compute_usefulness(good, expected_sections=["executive_summary", "items"]) > 0.5
    assert compute_usefulness(None) == 0.0
    assert compute_usefulness({}) == 0.0


def test_synthetic_eval_is_decisive_and_clean() -> None:
    result = run_model_eval(suite="daily-brief", models=["auto"], mode="synthetic")
    assert result["ok"] is True
    assert result["applied"] is False
    assert result["dry_run"] is True
    assert result["redaction_passed"] is True
    assert result["blockers"] == []
    # Clean synthetic outputs validate.
    assert result["metrics"]["json_valid_rate"] == 1.0
    assert result["metrics"]["schema_valid_rate"] == 1.0
    # Decisive: every evaluated family gets a recommendation, none blocked.
    assert result["metrics"]["blocked_families"] == []
    assert result["use_next_run"]  # non-empty mapping
    assert "daily_brief_synthesis_quality" in result["use_next_run"]
    # selected_profile convenience field points at the synthesis recommendation.
    assert result["selected_profile"] == result["use_next_run"]["daily_brief_synthesis_quality"]


def test_eval_payload_has_no_raw_content() -> None:
    result = run_model_eval(suite="daily-brief", models=["auto"], mode="synthetic")
    blob = json.dumps(result)
    # A distinctive phrase from a synthetic model output must never appear in the returned payload.
    assert "Thread requests Bobby return" not in blob
    assert "shop-drawing transmittal" not in blob
    # Results carry hash-only provenance, never a validated/raw body.
    for row in result["results"]:
        assert "validated" not in row
        assert "raw" not in row
        assert set(row).issuperset({"output_hash", "schema_valid", "redaction_passed"})


def test_bad_json_output_is_fail_closed_structured_result() -> None:
    bad = [
        ModelEvalFixture(
            fixture_id="bad-001",
            task_family="email_action_extraction_json",
            input_redacted={"summary_redacted": "x"},
            synthetic_output="not json {",
        )
    ]
    result = run_model_eval(
        suite="extraction",
        task_families=["email_action_extraction_json"],
        models=["auto"],
        mode="synthetic",
        fixtures=bad,
    )
    rows = result["results"]
    assert rows, "expected at least one measurement"
    for row in rows:
        assert row["json_valid"] is False
        assert row["schema_valid"] is False
        assert row["status"] in {"schema_invalid", "failed", "unavailable"}
        assert row["redaction_passed"] is True
    # No reliable profile -> family is blocked (decisive, fail-closed).
    assert "email_action_extraction_json" in result["metrics"]["blocked_families"]


def test_live_mode_missing_client_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the live client resolver to fail-closed (no network).
    monkeypatch.setattr(
        model_eval,
        "resolve_local_model_client",
        lambda **_kw: (None, None, "live_model_client_missing"),
    )
    result = run_model_eval(
        suite="extraction",
        task_families=["email_action_extraction_json"],
        models=["auto"],
        mode="live",
    )
    rows = result["results"]
    assert rows
    for row in rows:
        assert row["status"] == "unavailable"
        assert row["error_code"] == "live_model_client_missing"
    assert "live_daemon_unreachable" in result["blockers"]


def test_raw_fixture_path_inside_repo_is_refused() -> None:
    # The tests/ directory is inside the repo and must be refused for raw fixtures.
    import pathlib

    repo_tests = pathlib.Path(__file__).resolve().parent
    with pytest.raises(RawFixtureRefusedError):
        load_raw_fixtures(repo_tests)
