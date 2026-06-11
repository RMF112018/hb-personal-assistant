"""Phase 10 V50 — `second-brain candidates` CLI tests.

Asserts read/mutate commands operate only on the passed --db, emit raw-safe JSON, return the
documented exit codes (3 not-found, 2 blocked/invalid, 0 ok), and that --include-hidden surfaces
hidden rows. Also verifies the existing `second-brain review` verbs are unchanged (still present).
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()
_FORBIDDEN = ("raw_body", "body_html", "signed_url", "download_url", "join_url", "bearer",
              "secret", "http://", "https://", "@example")


def _db(tmp_path: Path) -> str:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    s.upsert_task_candidate(candidate_id="t1", stable_key="PRJ:task:t1", title_redacted="Submit RFI",
                            project_key="PRJ", assignee_class="user", waiting_state="waiting_on_me",
                            safety_category="normal", confidence=0.9, review_status="pending")
    s.upsert_candidate_source_ref(source_ref_id="sr1", candidate_type="task", candidate_id="t1",
                                  source_family="email", source_ref_hash="h1", source_table="email")
    return db


def test_review_reads_only_passed_db(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = runner.invoke(app, ["candidates", "review", "--db", db, "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.stdout)
    assert payload["ok"] is True
    assert payload["visible_count"] == 1
    assert payload["guardrails"]["operates_only_on_passed_db"] is True


def test_accept_then_promote_exit_codes(tmp_path: Path) -> None:
    db = _db(tmp_path)
    acc = runner.invoke(app, ["candidates", "accept", "t1", "--subject-type", "task_candidate",
                              "--db", db, "--json"])
    assert acc.exit_code == 0
    assert json.loads(acc.stdout)["status"] == "accepted"
    promo = runner.invoke(app, ["candidates", "promote", "t1", "--subject-type", "task_candidate",
                                "--db", db, "--json"])
    assert promo.exit_code == 0
    assert json.loads(promo.stdout)["promotion_status"] == "promoted"


def test_not_found_exit_code_3(tmp_path: Path) -> None:
    db = _db(tmp_path)
    res = runner.invoke(app, ["candidates", "accept", "nope", "--subject-type", "task_candidate",
                              "--db", db, "--json"])
    assert res.exit_code == 3
    assert json.loads(res.stdout)["status"] == "not_found"


def test_source_missing_blocked_exit_code_2(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = ConstructionStore(db_path=db)
    s.upsert_task_candidate(candidate_id="m1", stable_key="PRJ:task:m1", title_redacted="x",
                            project_key="PRJ", assignee_class="user", waiting_state="waiting_on_me",
                            safety_category="normal", confidence=0.9, review_status="pending")
    res = runner.invoke(app, ["candidates", "accept", "m1", "--subject-type", "task_candidate",
                              "--db", db, "--json"])
    assert res.exit_code == 2
    assert json.loads(res.stdout)["status"] == "accept_blocked_source_missing"


def test_reject_hidden_then_include_hidden(tmp_path: Path) -> None:
    db = _db(tmp_path)
    runner.invoke(app, ["candidates", "reject", "t1", "--subject-type", "task_candidate",
                        "--reason", "not_actionable", "--db", db, "--json"])
    default = json.loads(runner.invoke(app, ["candidates", "review", "--db", db, "--json"]).stdout)
    assert all(r["subject_id"] != "t1" for r in default["rows"])
    hidden = json.loads(runner.invoke(
        app, ["candidates", "review", "--include-hidden", "--db", db, "--json"]).stdout)
    assert any(r["subject_id"] == "t1" for r in hidden["rows"])


def test_cli_json_raw_free(tmp_path: Path) -> None:
    db = _db(tmp_path)
    out = runner.invoke(app, ["candidates", "review", "--include-hidden", "--db", db, "--json"]).stdout
    low = out.lower()
    for f in _FORBIDDEN:
        assert f not in low, f


def test_existing_review_group_unchanged(tmp_path: Path) -> None:
    # The additive candidates group must not have removed the existing `review` verbs.
    res = runner.invoke(app, ["review", "--help"])
    assert res.exit_code == 0
    for verb in ("accept", "reject", "snooze"):
        assert verb in res.stdout
