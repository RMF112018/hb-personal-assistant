"""Phase 10 Prompt 04 — Local Model Structured Output Client tests.

Covers the schema-enforced client (success, blocked heavy profile, unavailable backend + fallback,
invalid schema, stale/unknown schema, retry-repair), the hash-only run-receipt write contract
(dry-run writes nothing; --apply writes exactly one row whose 13 guard columns sum to 0 and which
carries only hashes), the ai-jobs status read surface, and the four CLI surfaces via CliRunner.
Fully offline — no Ollama, no network.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai.contracts import load_local_model_profiles
from hb_assistant.construction.second_brain.local_ai.models import ActionCandidate
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.second_brain.local_ai.structured_output import (
    StaticOutputClient,
    StructuredOutputClient,
    action_candidate_dict_from_fixture,
)
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_FIXTURES = Path(__file__).parent / "fixtures" / "local_ai"
_VALID_CANDIDATE = {
    "candidate_type": "task",
    "title": "Confirm revised RFI sketch issuance today",
    "assignee": "user",
    "waiting_state": "waiting_on_me",
    "source_refs": ["email:001"],
    "confidence": 0.8,
    "reason": "Sender asks Bobby to confirm.",
    "safety_category": "normal",
    "recommended_next_action": "review",
    "external_action_requires_approval": True,
}


def _profiles():
    return load_local_model_profiles()


def _profile(profile_id: str):
    return next(p for p in _profiles().profiles if p.profile_id == profile_id)


def _temp_store(td: str) -> tuple[ConstructionStore, str]:
    db = str(Path(td) / "p10p04.db")
    return ConstructionStore(db_path=db), db


# ---------------------------------------------------------------------------
# Client behaviour
# ---------------------------------------------------------------------------
def test_success_validates_and_previews_receipt() -> None:
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("default_extract"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="extract_email_tasks",
        backend=StaticOutputClient(json.dumps(_VALID_CANDIDATE)),
        dry_run=True,
    )
    assert res.status == "ok"
    assert res.schema_valid is True
    assert res.fallback_used is False
    assert res.validated and res.validated["candidate_type"] == "task"
    # dry-run: no receipt id, would-write fields surfaced (hash-only)
    assert res.receipt_id is None
    assert res.would_write_receipt is not None
    assert res.input_context_hash and res.output_hash
    assert len(res.input_context_hash) == 12


def test_blocked_heavy_profile_without_enable() -> None:
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("heavy_context"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(json.dumps(_VALID_CANDIDATE)),
        dry_run=True,
    )
    assert res.status == "blocked"
    assert res.error_redacted == "heavy_profile_requires_explicit_enable"
    assert res.schema_valid is False


def test_heavy_profile_runs_when_explicitly_enabled() -> None:
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("heavy_context"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(json.dumps(_VALID_CANDIDATE)),
        dry_run=True,
        heavy_enabled=True,
    )
    assert res.status == "ok"
    assert res.schema_valid is True


def test_unavailable_backend_attempts_fallback() -> None:
    # quality_reasoning -> default_extract per the seed fallbacks; same injected backend keeps failing.
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("quality_reasoning"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(raise_unavailable=True),
        dry_run=True,
    )
    assert res.status in {"unavailable", "timeout"}
    assert res.fallback_used is True
    assert res.error_redacted  # redacted category code, never raw text
    assert "http" not in (res.error_redacted or "")


def test_invalid_schema_is_captured_not_raised() -> None:
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("default_extract"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient('{"candidate_type": "task"}'),  # missing required fields
        dry_run=True,
    )
    assert res.status == "schema_invalid"
    assert res.schema_valid is False
    assert res.attempts == 3  # bounded retry/repair before giving up


def test_unknown_field_rejected_as_schema_invalid() -> None:
    # extra="forbid" + a forbidden raw field => stale/unknown schema shape rejected.
    bad = dict(_VALID_CANDIDATE)
    bad["raw_email_body"] = "secret body"
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("default_extract"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(json.dumps(bad)),
        dry_run=True,
    )
    assert res.status == "schema_invalid"
    assert res.validated is None


def test_retry_repair_recovers_after_bad_json() -> None:
    res = StructuredOutputClient().run(
        schema=ActionCandidate,
        profile=_profile("default_extract"),
        profiles=_profiles(),
        system="s",
        prompt="p",
        input_context="ctx",
        task_type="x",
        backend=StaticOutputClient(outputs=["not json", json.dumps(_VALID_CANDIDATE)]),
        dry_run=True,
    )
    assert res.status == "ok"
    assert res.attempts == 2


# ---------------------------------------------------------------------------
# Receipt write contract (hash-only, no-writeback)
# ---------------------------------------------------------------------------
def test_dry_run_writes_zero_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _temp_store(td)
        StructuredOutputClient().run(
            schema=ActionCandidate,
            profile=_profile("default_extract"),
            profiles=_profiles(),
            system="s",
            prompt="p",
            input_context="ctx",
            task_type="x",
            backend=StaticOutputClient(json.dumps(_VALID_CANDIDATE)),
            store=store,
            dry_run=True,
        )
        assert store.list_local_model_run_receipts() == []


def test_apply_writes_one_hash_only_receipt_with_clean_guards() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, db = _temp_store(td)
        res = StructuredOutputClient().run(
            schema=ActionCandidate,
            profile=_profile("default_extract"),
            profiles=_profiles(),
            system="s",
            prompt="p",
            input_context="ctx",
            task_type="extract_email_tasks",
            backend=StaticOutputClient(json.dumps(_VALID_CANDIDATE)),
            store=store,
            dry_run=False,
        )
        rows = store.list_local_model_run_receipts()
        assert len(rows) == 1
        assert res.receipt_id is not None
        row = rows[0]
        # Only hashes + metadata — assert no raw text leaked into hash columns.
        assert row["input_context_hash"] == res.input_context_hash
        assert row["output_hash"] == res.output_hash
        assert row["schema_name"] == "ActionCandidate"
        assert row["schema_valid"] is True
        assert "ctx" not in json.dumps(row)  # raw input context never persisted

        # 13 guard columns must sum to 0 (no raw persisted, no writeback).
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        guard_sum = conn.execute(f"SELECT {expr} FROM local_model_run_receipts").fetchone()[0]
        conn.close()
        assert guard_sum == 0


def test_ai_job_status_summary_empty_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, _ = _temp_store(td)
        summary = store.ai_job_status_summary(environment="dev")
        assert summary["queue_total"] == 0
        assert summary["runs"]["run_count"] == 0


# ---------------------------------------------------------------------------
# Fixture helper
# ---------------------------------------------------------------------------
def test_fixture_helper_builds_valid_candidate() -> None:
    fixture = json.loads((_FIXTURES / "email_task_candidate_001.json").read_text())
    cand = ActionCandidate.model_validate(action_candidate_dict_from_fixture(fixture))
    assert cand.candidate_type == "task"
    assert cand.assignee == "user"
    assert cand.review_status == "pending"
    assert len(cand.source_refs) >= 1


# ---------------------------------------------------------------------------
# CLI surfaces
# ---------------------------------------------------------------------------
def test_cli_local_model_status_mock() -> None:
    result = runner.invoke(app, ["local-model", "status", "--mock", "--json"])
    payload = json.loads(result.output)
    assert payload["command"] == "second-brain local-model status"
    assert payload["provider"] == "mock"
    # mock with no present models => not ready => exit 3
    assert result.exit_code == 3


def test_cli_ai_jobs_status_isolated_db() -> None:
    with tempfile.TemporaryDirectory() as td:
        _, db = _temp_store(td)
        result = runner.invoke(app, ["ai-jobs", "status", "--db", db, "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["queue_total"] == 0


def test_cli_ai_jobs_run_dry_run() -> None:
    # Prompt 05 made `ai-jobs run` queue-driven; an empty ambient queue is a clean no-op.
    with tempfile.TemporaryDirectory() as td:
        _, db = _temp_store(td)
        result = runner.invoke(
            app, ["ai-jobs", "run", "--dry-run", "--max-items", "10", "--db", db, "--json"]
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["ok"] is True
        assert payload["dry_run"] is True
        assert payload["status"] == "ok"
        assert payload["claimed"] == 0


def test_cli_extract_fixture_advisory_no_write() -> None:
    fixture = str(_FIXTURES / "email_task_candidate_001.json")
    result = runner.invoke(app, ["action-intel", "extract-fixture", "--fixture", fixture, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_valid"] is True
    assert payload["applied"] is False
    assert payload["receipt_id"] is None
    assert payload["candidate"]["review_status"] == "pending"
    assert len(payload["candidate"]["source_refs"]) >= 1


def test_cli_extract_fixture_apply_writes_receipt() -> None:
    with tempfile.TemporaryDirectory() as td:
        store, db = _temp_store(td)
        fixture = str(_FIXTURES / "email_task_candidate_001.json")
        result = runner.invoke(
            app,
            ["action-intel", "extract-fixture", "--fixture", fixture, "--apply", "--db", db, "--json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["applied"] is True
        assert payload["receipt_id"] is not None
        assert len(store.list_local_model_run_receipts()) == 1
