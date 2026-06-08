"""Phase 10 Prompt 07 — Email Task Candidate Extraction tests.

Covers the six required scenarios (success, blocked/bounded-content-gated, unavailable dependency,
invalid schema, stale schema, no-raw/no-writeback), deterministic-signal unit behavior, contract↔
module parity, persistence linkage, and the glob-safety regression keeping the new summary fixtures
out of the ``ai_jobs`` fixture glob. Fully offline — no Ollama, no network.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace

from hb_assistant.construction.second_brain.local_ai import (
    extract_email_task_candidates,
    score_email_task_signals,
)
from hb_assistant.construction.second_brain.local_ai.contracts import load_phase_10_contract
from hb_assistant.construction.second_brain.local_ai.email_task_extraction import (
    CANDIDATE_TYPES,
    MODES,
    REASON_CODES,
    SIGNAL_CATEGORIES,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.second_brain.local_ai.structured_output import StaticOutputClient
from hb_assistant.construction.store import ConstructionStore

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SUMMARIES_DIR = _REPO_ROOT / "tests" / "fixtures" / "local_ai" / "email_summaries"
_LOCAL_AI_DIR = _REPO_ROOT / "tests" / "fixtures" / "local_ai"

_TASK_SUMMARY = {
    "source_ref": "email_thread_summary:test:001",
    "project_key": "P1",
    "input_redacted": {
        "thread_subject_redacted": "Hilltop RFI follow-up",
        "summary_redacted": "Please confirm whether the revised sketch will be issued by Friday.",
    },
}


def _candidate(**overrides) -> str:
    base = {
        "candidate_type": "task",
        "title": "Confirm revised sketch issuance",
        "project_key": "P1",
        "assignee": "user",
        "due_at": None,
        "urgency": "normal",
        "waiting_state": "waiting_on_me",
        "source_refs": ["email_thread_summary:test:001"],
        "confidence": 0.8,
        "reason": "Sender asks Bobby to confirm whether the sketch will be issued.",
        "review_status": "pending",
        "safety_category": "normal",
        "recommended_next_action": "review",
        "external_action_requires_approval": True,
    }
    base.update(overrides)
    return json.dumps(base)


def _guard_sum(db: str, table: str) -> int:
    conn = sqlite3.connect(db)
    expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
    val = conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]
    conn.close()
    return int(val or 0)


# --------------------------------------------------------------------------------------------------
# Deterministic signals.
# --------------------------------------------------------------------------------------------------
def test_signals_fire_on_fixtures() -> None:
    for path in sorted(_SUMMARIES_DIR.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        sig = score_email_task_signals(fixture)
        assert set(sig["reason_codes"]) == set(fixture["signals_expected"]), fixture["scenario"]


def test_signals_low_signal_when_nothing_fires() -> None:
    sig = score_email_task_signals(
        {"source_ref": "x", "input_redacted": {"summary_redacted": "Monthly newsletter."}}
    )
    assert sig["reason_codes"] == ["low_signal"]


def test_sent_by_user_reads_as_commitment_waiting_on_others() -> None:
    sig = score_email_task_signals(
        {"source_ref": "x", "input_redacted": {"sent_by_user": True, "summary_redacted": "I will send it by Friday."}}
    )
    assert sig["candidate_type_hint"] == "commitment"
    assert sig["waiting_state_hint"] == "waiting_on_others"


# --------------------------------------------------------------------------------------------------
# Six-scenario matrix.
# --------------------------------------------------------------------------------------------------
def test_success_metadata_safe() -> None:
    rep = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY], backend=StaticOutputClient(_candidate()), dry_run=True
    )
    assert rep["mode"] == "metadata_safe"
    assert rep["produced"] == 1 and rep["accepted"] == 1 and rep["rejected"] == 0
    assert rep["candidates"][0]["candidate_type"] == "task"


def test_bounded_content_blocked_falls_back() -> None:
    # A policy that disallows bounded content → downgrade to metadata_safe with a recorded blocker.
    policy = SimpleNamespace(
        raw_content=SimpleNamespace(
            enabled=False,
            model_context=SimpleNamespace(include_raw_content=False),
            starting_sources=SimpleNamespace(email=False),
        )
    )
    rep = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(_candidate()),
        mode="bounded_content",
        policy=policy,
        dry_run=True,
    )
    assert rep["requested_mode"] == "bounded_content"
    assert rep["mode"] == "metadata_safe"
    assert "bounded_content_not_eligible_fell_back_to_metadata_safe" in rep["blockers"]


def test_unavailable_dependency() -> None:
    rep = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY], backend=StaticOutputClient(raise_unavailable=True), dry_run=True
    )
    assert rep["backend_unavailable"] is True
    assert rep["accepted"] == 0 and rep["error_redacted"]


def test_invalid_schema_rejected() -> None:
    # Missing required fields → client reports schema_invalid → rejected, not crash.
    rep = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(json.dumps({"candidate_type": "task"})),
        dry_run=True,
    )
    assert rep["produced"] == 1 and rep["accepted"] == 0 and rep["rejected"] == 1


def test_stale_forbidden_field_rejected() -> None:
    rep = extract_email_task_candidates(
        summaries=[_TASK_SUMMARY],
        backend=StaticOutputClient(_candidate(raw_email_body="LEAK")),
        dry_run=True,
    )
    assert rep["accepted"] == 0 and rep["rejected"] == 1


def test_no_writeback_dry_run_then_apply_clean_guards() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p07.db")
        store = ConstructionStore(db_path=db)
        # Dry-run: zero writes.
        extract_email_task_candidates(
            summaries=[_TASK_SUMMARY], store=store, backend=StaticOutputClient(_candidate()),
            dry_run=True,
        )
        assert store.list_task_candidates() == []
        # Apply: persists exactly one task + linked source ref; guards clean; raw absent.
        rep = extract_email_task_candidates(
            summaries=[_TASK_SUMMARY], store=store, project_key="P1",
            backend=StaticOutputClient(_candidate()), dry_run=False,
        )
        assert rep["persisted"] == 1
        tasks = store.list_task_candidates()
        refs = store.list_candidate_source_refs(candidate_type="task")
        assert len(tasks) == 1 and len(refs) == 1
        assert refs[0]["candidate_id"] == tasks[0]["candidate_id"]
        assert refs[0]["source_family"] == "email_thread_summary"
        for table in ("task_candidates", "candidate_source_refs", "local_model_run_receipts"):
            assert _guard_sum(db, table) == 0
        assert "LEAK" not in json.dumps(refs) and "LEAK" not in json.dumps(tasks)


def test_commitment_persists_to_commitment_table() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "p07c.db")
        store = ConstructionStore(db_path=db)
        cand = _candidate(candidate_type="commitment", waiting_state="waiting_on_others")
        rep = extract_email_task_candidates(
            summaries=[_TASK_SUMMARY], store=store, backend=StaticOutputClient(cand), dry_run=False
        )
        assert rep["persisted"] == 1
        assert len(store.list_commitment_candidates()) == 1
        assert store.list_task_candidates() == []


# --------------------------------------------------------------------------------------------------
# Contract parity + glob safety.
# --------------------------------------------------------------------------------------------------
def test_contract_module_parity() -> None:
    contract = load_phase_10_contract("email_task_signal_contract")
    assert set(contract["signal_categories"]) == set(SIGNAL_CATEGORIES)
    assert set(contract["reason_codes"]) == set(REASON_CODES)
    assert set(contract["modes"]) == set(MODES)
    assert set(contract["candidate_types"]) == set(CANDIDATE_TYPES)
    assert len(contract["guard_columns"]) == len(PHASE_10_GUARD_COLUMNS)


def test_summary_fixtures_excluded_from_ai_jobs_glob() -> None:
    from hb_assistant.construction.second_brain.local_ai import ai_jobs

    loaded = ai_jobs._load_fixtures(str(_LOCAL_AI_DIR), 1000)
    ids = {f.get("fixture_id") for f in loaded}
    assert len(loaded) == 4  # the original four flat fixtures only
    assert not any(str(i).startswith("email_summary_") for i in ids)
