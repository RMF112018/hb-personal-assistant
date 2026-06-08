"""Phase 10A — read-only candidate review CLI (second-brain review list/show/summary).

Exercises the Typer verbs end-to-end against a temp --db: filters, exit codes
(2 invalid status, 3 not-found), source refs in show, and a no-raw output guard.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

_FORBIDDEN_KEYS = {
    "body",
    "body_text",
    "raw_body",
    "prompt",
    "raw_prompt",
    "response",
    "raw_response",
    "signed_url",
    "download_url",
    "token",
    "secret",
}


def _seed(db: str) -> tuple[str, str]:
    s = ConstructionStore(db_path=db)
    pk = "PRJ-CLI"
    tid, cid = "cli-task-1", "cli-comm-1"
    s.upsert_task_candidate(
        candidate_id=tid,
        stable_key=f"{pk}:task:{tid}",
        title_redacted="Submit inspection report",
        project_key=pk,
        assignee_class="user",
        urgency="high",
        waiting_state="waiting_on_me",
        safety_category="normal",
        confidence=0.9,
        reason_redacted="Explicit ask.",
        recommended_next_action="review",
        review_status="pending",
    )
    s.upsert_candidate_source_ref(
        source_ref_id=f"sr-{tid}",
        candidate_type="task",
        candidate_id=tid,
        source_family="email_message_raw_content",
        source_ref_hash="hash-xyz",
        source_table="email_message_raw_content",
        source_primary_key_hash="hash-xyz",
        evidence_redacted="Submit inspection report",
    )
    s.upsert_commitment_candidate(
        candidate_id=cid,
        stable_key=f"{pk}:commitment:{cid}",
        title_redacted="Vendor delivers drawings",
        project_key=pk,
        commitment_actor_class="other",
        urgency="normal",
        waiting_state="waiting_on_others",
        safety_category="normal",
        confidence=0.8,
        reason_redacted="Promise.",
        recommended_next_action="review",
        review_status="accepted",
    )
    return tid, cid


def _assert_no_forbidden_keys(obj: object) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in _FORBIDDEN_KEYS, f"forbidden key {k!r} in output"
            _assert_no_forbidden_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_forbidden_keys(item)


def test_review_summary_cli(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    _seed(db)
    res = runner.invoke(app, ["review", "summary", "--db", db, "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["combined"]["total"] == 2
    assert payload["task"]["pending"] == 1
    assert payload["commitment"]["accepted"] == 1
    assert payload["guardrails"]["read_only"] is True


def test_review_list_cli_and_status_filter(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, cid = _seed(db)
    res = runner.invoke(app, ["review", "list", "--db", db, "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["count"] == 2
    assert {c["candidate_type"] for c in payload["candidates"]} == {"task", "commitment"}

    res2 = runner.invoke(app, ["review", "list", "--status", "accepted", "--db", db, "--json"])
    assert res2.exit_code == 0
    p2 = json.loads(res2.output)
    assert p2["count"] == 1 and p2["candidates"][0]["candidate_id"] == cid


def test_review_list_invalid_status_exit_2(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    _seed(db)
    res = runner.invoke(app, ["review", "list", "--status", "ignored", "--db", db, "--json"])
    assert res.exit_code == 2, res.output
    assert json.loads(res.output)["ok"] is False


def test_review_show_cli_found_and_not_found(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, _ = _seed(db)
    res = runner.invoke(app, ["review", "show", "--candidate-id", tid, "--db", db, "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True
    assert payload["candidate_type"] == "task"
    assert payload["candidate"]["candidate_id"] == tid
    assert len(payload["source_refs"]) == 1
    assert payload["source_refs"][0]["source_ref_hash"] == "hash-xyz"

    missing = runner.invoke(app, ["review", "show", "--candidate-id", "nope", "--db", db, "--json"])
    assert missing.exit_code == 3, missing.output
    assert json.loads(missing.output)["error"] == "candidate_not_found"


def test_review_cli_outputs_have_no_raw_keys(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, _ = _seed(db)
    for args in (
        ["review", "summary", "--db", db, "--json"],
        ["review", "list", "--db", db, "--json"],
        ["review", "show", "--candidate-id", tid, "--db", db, "--json"],
    ):
        res = runner.invoke(app, args)
        assert res.exit_code == 0, res.output
        _assert_no_forbidden_keys(json.loads(res.output))


# ---------------------------------------------------------------------------
# Mutation verbs (accept / ignore / reject)
# ---------------------------------------------------------------------------
def _audit_count(db: str, candidate_id: str) -> int:
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM candidate_review_events WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()[0]
    finally:
        conn.close()


def test_review_accept_cli_transitions_and_audits_and_preserves_refs(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, _ = _seed(db)
    s = ConstructionStore(db_path=db)
    refs_before = len(s.list_candidate_source_refs(candidate_id=tid))

    res = runner.invoke(app, ["review", "accept", "--candidate-id", tid, "--db", db, "--json"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["new_review_status"] == "accepted"
    assert payload["prior_review_status"] == "pending"
    assert payload["review_event_id"]
    assert payload["guardrails"]["no_external_writeback"] is True

    row = s.get_task_candidate(tid)
    assert row is not None and row["review_status"] == "accepted"
    assert _audit_count(db, tid) == 1
    # source refs untouched
    assert len(s.list_candidate_source_refs(candidate_id=tid)) == refs_before


def test_review_ignore_cli_normalizes_to_suppressed(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, _ = _seed(db)
    res = runner.invoke(
        app, ["review", "ignore", "--candidate-id", tid, "--reason", "not actionable", "--db", db, "--json"]
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["action"] == "ignore"
    assert payload["new_review_status"] == "suppressed"
    row = ConstructionStore(db_path=db).get_task_candidate(tid)
    assert row is not None and row["review_status"] == "suppressed"


def test_review_reject_cli_with_reason(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, _ = _seed(db)
    res = runner.invoke(
        app,
        ["review", "reject", "--candidate-id", tid, "--reason", "incorrect extraction", "--db", db, "--json"],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["new_review_status"] == "rejected"
    row = ConstructionStore(db_path=db).get_task_candidate(tid)
    assert row is not None
    assert row["review_status"] == "rejected"
    assert row["review_note_redacted"] == "incorrect extraction"


def test_review_action_not_found_exit_3(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    _seed(db)
    res = runner.invoke(app, ["review", "accept", "--candidate-id", "ghost", "--db", db, "--json"])
    assert res.exit_code == 3, res.output
    assert json.loads(res.output)["error"] == "candidate_not_found"


def test_review_action_outputs_have_no_raw_keys(tmp_path: Path) -> None:
    db = str(tmp_path / "db.sqlite")
    tid, cid = _seed(db)
    r1 = runner.invoke(app, ["review", "accept", "--candidate-id", tid, "--db", db, "--json"])
    r2 = runner.invoke(app, ["review", "reject", "--candidate-id", cid, "--reason", "x", "--db", db, "--json"])
    for res in (r1, r2):
        assert res.exit_code == 0, res.output
        _assert_no_forbidden_keys(json.loads(res.output))
