"""Phase 10A batch extraction (extract-packets): dry-run/apply, capping, dedup, guardrails."""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import (
    UnsupportedBatchSourceError,
    run_batch_extraction,
)
from hb_assistant.construction.second_brain.local_ai.schema import PHASE_10_GUARD_COLUMNS
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()


def _seed_thread(store: ConstructionStore, *, thread_ref: str, body: str, n: int = 1) -> None:
    store.upsert_email_thread_raw_context(
        raw_thread_context_id=f"rtc-{thread_ref}", thread_ref=thread_ref, project_key="P",
        message_count=n, thread_subject=f"Subject {thread_ref}",
        messages_json=json.dumps([
            {"id": f"{thread_ref}-m{i}", "subject": f"Subject {thread_ref}", "body_text": body,
             "sent_at_utc": "2026-06-07T12:00:00+00:00"}
            for i in range(n)
        ]),
        source_refs_json="[]", model_ready=1,
    )


def _task(refs=("src_1",), *, assignee="user", waiting="waiting_on_me",
          title="Submit revised RFI 42 sketch by Friday", safety="normal", action="review") -> str:
    return json.dumps({"candidates": [{
        "candidate_type": "task", "title": title, "project_key": "P", "assignee": assignee,
        "due_at": None, "urgency": "normal", "waiting_state": waiting, "source_refs": list(refs),
        "confidence": 0.85, "reason": "Email asks to submit the revised RFI 42 sketch by Friday.",
        "safety_category": safety, "recommended_next_action": action, "review_status": "pending",
        "external_action_requires_approval": True,
    }]})


def _commitment(refs=("src_1",)) -> str:
    return json.dumps({"candidates": [{
        "candidate_type": "commitment", "title": "Andrew to deliver shop drawings Tuesday",
        "project_key": "P", "assignee": "other", "due_at": None, "urgency": "normal",
        "waiting_state": "waiting_on_others", "source_refs": list(refs), "confidence": 0.8,
        "reason": "Andrew states he will deliver the shop drawings Tuesday.",
        "safety_category": "normal", "recommended_next_action": "review", "review_status": "pending",
        "external_action_requires_approval": True,
    }]})


def _question(refs=("src_1",)) -> str:
    return json.dumps({"candidates": [{
        "candidate_type": "question", "title": "Where should we allocate the contingency",
        "project_key": "P", "assignee": "unknown", "due_at": None, "urgency": "normal",
        "waiting_state": "unknown", "source_refs": list(refs), "confidence": 0.7,
        "reason": "Open question about where to allocate the remaining contingency.",
        "safety_category": "normal", "recommended_next_action": "review", "review_status": "pending",
        "external_action_requires_approval": True,
    }]})


def _counts(store: ConstructionStore) -> dict:
    return {
        "task": len(store.list_task_candidates()),
        "commitment": len(store.list_commitment_candidates()),
        "refs": len(store.list_candidate_source_refs()),
    }


def test_dry_run_batch_processes_multiple_persists_zero_and_summarizes() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_thread(s, thread_ref="t1", body="Please submit the revised RFI 42 sketch by Friday.")
        _seed_thread(s, thread_ref="t2", body="Andrew will deliver the shop drawings Tuesday.")
        _seed_thread(s, thread_ref="t3", body="Where should we allocate the remaining contingency?")
        mocks = {"t1": _task(), "t2": _commitment(), "t3": _question()}
        payload = run_batch_extraction(
            source="email", store=s, limit=10, dry_run=True, mock_output_map=mocks,
            write_artifact=False,
        )
        assert payload["applied"] is False
        assert payload["processed_packets"] == 3
        sm = payload["summary"]
        assert sm["produced"] == 3 and sm["accepted"] == 3 and sm["persisted"] == 0
        # accepted (3) is separated from would_persist (task + commitment = 2); question is unsupported.
        assert sm["would_persist"] == 2
        assert sm["unsupported_candidate_type"] == 1
        assert payload["candidate_types"] == {
            "task": 1, "commitment": 1, "question": 1, "risk": 0, "other": 0
        }
        assert payload["safety_categories"].get("normal") == 3
        assert payload["recommended_actions"] == {"review": 3}
        assert _counts(s) == {"task": 0, "commitment": 0, "refs": 0}


def test_apply_without_max_persist_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_thread(s, thread_ref="t1", body="Submit the sketch.")
        with pytest.raises(ValueError):
            run_batch_extraction(source="email", store=s, dry_run=False, max_persist=None,
                                 mock_output_map={"t1": _task()}, write_artifact=False)


def test_apply_max_persist_caps_actual_persisted_candidates() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        mocks = {}
        for i in range(1, 6):
            tr = f"t{i}"
            _seed_thread(s, thread_ref=tr, body=f"Submit the revised RFI {i} sketch by Friday.")
            mocks[tr] = _task()
        payload = run_batch_extraction(
            source="email", store=s, limit=10, dry_run=False, max_persist=2,
            mock_output_map=mocks, write_artifact=False,
        )
        assert payload["applied"] is True and payload["max_persist"] == 2
        assert payload["summary"]["persisted"] == 2
        # All 5 are persistence-eligible, but only 2 are actually written.
        assert payload["summary"]["would_persist"] == 5
        assert _counts(s)["task"] == 2
        # All persisted rows are review-gated with non-null traceability.
        for row in s.list_task_candidates():
            assert row["recommended_next_action"] == "review"
            assert row["model_profile_id"] == "default_extract"
            assert row["prompt_template_version"]


def test_apply_max_persist_one_persists_at_most_one() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        for i in range(1, 4):
            _seed_thread(s, thread_ref=f"t{i}", body=f"Submit sketch {i} by Friday please.")
        mocks = {f"t{i}": _task() for i in range(1, 4)}
        payload = run_batch_extraction(
            source="email", store=s, limit=10, dry_run=False, max_persist=1,
            mock_output_map=mocks, write_artifact=False,
        )
        assert payload["summary"]["persisted"] == 1
        assert _counts(s)["task"] == 1


def test_duplicate_stable_key_skipped_no_duplicate_rows() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_thread(s, thread_ref="t1", body="Submit the revised RFI 42 sketch by Friday.")
        first = run_batch_extraction(
            source="email", store=s, dry_run=False, max_persist=5,
            mock_output_map={"t1": _task()}, write_artifact=False,
        )
        assert first["summary"]["persisted"] == 1
        before = _counts(s)
        second = run_batch_extraction(
            source="email", store=s, dry_run=False, max_persist=5,
            mock_output_map={"t1": _task()}, write_artifact=False,
        )
        assert second["summary"]["persisted"] == 0
        assert second["summary"]["skipped_existing"] == 1
        assert _counts(s) == before  # no duplicate candidate/source-ref rows


def test_unsupported_question_accepted_but_not_persisted() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_thread(s, thread_ref="t1", body="Where should we allocate the remaining contingency?")
        payload = run_batch_extraction(
            source="email", store=s, dry_run=False, max_persist=5,
            mock_output_map={"t1": _question()}, write_artifact=False,
        )
        assert payload["summary"]["accepted"] == 1
        assert payload["summary"]["would_persist"] == 0
        assert payload["summary"]["persisted"] == 0
        assert payload["summary"]["unsupported_candidate_type"] == 1
        assert payload["candidate_types"]["question"] == 1
        # The accepted question is visible in the per-thread review output.
        res = payload["results"][0]
        assert res["accepted_candidates"][0]["candidate_type"] == "question"
        assert _counts(s)["task"] == 0


def test_source_alias_unresolved_reported_and_not_persisted() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_thread(s, thread_ref="t1", body="Submit the sketch.")
        _seed_thread(s, thread_ref="t2", body="Submit the other sketch.")
        # t1 cites an invalid alias; t2 is valid → batch continues past the failure.
        mocks = {"t1": _task(refs=("src_9",)), "t2": _task()}
        payload = run_batch_extraction(
            source="email", store=s, dry_run=True, mock_output_map=mocks, write_artifact=False,
        )
        assert payload["processed_packets"] == 2
        assert any(f["thread_ref"] == "t1" for f in payload["source_alias_failures"])
        assert any(r["reason"] == "source_alias_not_in_packet"
                   for r in payload["top_rejection_reasons"])
        # Apply: the unresolved-alias candidate is never persisted.
        run_batch_extraction(
            source="email", store=s, dry_run=False, max_persist=5, mock_output_map=mocks,
            write_artifact=False,
        )
        assert _counts(s)["task"] == 1  # only the valid t2 candidate persisted


def test_guardrail_columns_remain_zero_after_apply() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s, thread_ref="t1", body="Submit the revised RFI 42 sketch by Friday.")
        run_batch_extraction(
            source="email", store=s, dry_run=False, max_persist=5,
            mock_output_map={"t1": _task()}, write_artifact=False,
        )
        conn = sqlite3.connect(db)
        expr = " + ".join(f"COALESCE(SUM({g}),0)" for g in PHASE_10_GUARD_COLUMNS)
        for table in ("task_candidates", "candidate_source_refs"):
            assert int(conn.execute(f"SELECT {expr} FROM {table}").fetchone()[0]) == 0
        conn.close()


def test_unsupported_source_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        for src in ("calendar", "related"):
            with pytest.raises(UnsupportedBatchSourceError):
                run_batch_extraction(source=src, store=s, dry_run=True, write_artifact=False)


def test_artifact_written_with_safe_content() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        _seed_thread(s, thread_ref="t1", body="SENSITIVE RAW BODY: submit the sketch by Friday.")
        payload = run_batch_extraction(
            source="email", store=s, dry_run=True, mock_output_map={"t1": _task()},
            write_artifact=True, artifact_dir=td, timestamp="20260608T000000Z",
        )
        path = payload["artifact_path"]
        assert path and Path(path).exists()
        assert path == str(Path(td) / "phase10a_extract_packets_20260608T000000Z.json")
        text = Path(path).read_text(encoding="utf-8")
        doc = json.loads(text)
        assert "summary" in doc and "results" in doc
        # The raw email body must not appear in the review artifact.
        assert "SENSITIVE RAW BODY" not in text


def test_offset_selection() -> None:
    with tempfile.TemporaryDirectory() as td:
        s = ConstructionStore(db_path=str(Path(td) / "b.db"))
        # Distinct body lengths → deterministic length(messages_json) DESC ordering.
        _seed_thread(s, thread_ref="t1", body="x" * 300)
        _seed_thread(s, thread_ref="t2", body="x" * 200)
        _seed_thread(s, thread_ref="t3", body="x" * 100)
        payload = run_batch_extraction(
            source="email", store=s, limit=1, offset=1, dry_run=True,
            mock_output_map={"t1": _task(), "t2": _task(), "t3": _task()}, write_artifact=False,
        )
        # Longest-first ordering = t1, t2, t3; offset 1 limit 1 → t2.
        assert payload["processed_packets"] == 1
        assert payload["results"][0]["thread_ref"] == "t2"


# --- CLI wiring -------------------------------------------------------------------------------


def test_cli_apply_without_max_persist_exits_2() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        ConstructionStore(db_path=db)
        res = runner.invoke(
            app, ["extract-packets", "--source", "email", "--apply", "--db", db, "--json"]
        )
        assert res.exit_code == 2, res.output
        assert json.loads(res.output)["error"] == "apply_requires_max_persist"


def test_cli_unsupported_source_exits_2() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        ConstructionStore(db_path=db)
        res = runner.invoke(
            app,
            ["extract-packets", "--source", "calendar", "--db", db, "--no-client", "--json"],
        )
        assert res.exit_code == 2, res.output
        assert "unsupported_source" in json.loads(res.output)["error"]


def test_cli_dry_run_default_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        db = str(Path(td) / "b.db")
        s = ConstructionStore(db_path=db)
        _seed_thread(s, thread_ref="t1", body="Submit the sketch by Friday.")
        # --no-client (test mode) + default dry-run: structural wiring, zero writes.
        res = runner.invoke(
            app,
            ["extract-packets", "--source", "email", "--limit", "5", "--summary",
             "--no-artifact", "--db", db, "--no-client", "--json"],
        )
        assert res.exit_code == 0, res.output
        body = json.loads(res.output)
        assert body["ok"] is True and body["applied"] is False
        assert body["guardrails"]["dry_run_default"] is True
        assert "summary" in body and "candidate_types" in body
        assert s.list_task_candidates() == []
