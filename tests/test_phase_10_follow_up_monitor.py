"""Phase 10 — deterministic Follow-up Watch Monitor (advisory, no writeback).

Covers the classifier (determinism / no clock read), the scan dry-run/apply posture,
the apply-requires-cap + max-persist enforcement, the source-ref gate, duplicate
skipping, status-change events, guard-column invariants, the no-raw output guard, the
empty-input clean path, the CLI wiring, and the oversized thread-context input guard.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import (
    classify_watch_status,
    run_follow_up_watch_scan,
)
from hb_assistant.construction.second_brain.local_ai import follow_up_watch as fuw
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

NOW = "2026-06-08T00:00:00+00:00"

_GUARD_COLUMNS = (
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "graph_writeback_performed",
    "procore_writeback_performed",
    "email_send_performed",
    "calendar_mutation_performed",
)

_FORBIDDEN_KEYS = {
    "body",
    "body_text",
    "raw_body",
    "prompt",
    "response",
    "signed_url",
    "download_url",
    "token",
    "secret",
    "messages_json",
}


def _seed_accepted_task(
    db: str,
    cid: str,
    *,
    waiting_state: str = "waiting_on_me",
    due_at_utc: str | None = None,
    accepted_utc: str = "2026-06-01T00:00:00+00:00",
    with_source_ref: bool = True,
) -> None:
    s = ConstructionStore(db_path=db)
    s.upsert_task_candidate(
        candidate_id=cid,
        stable_key=f"PRJ:task:{cid}",
        title_redacted=f"Task {cid}",
        project_key="PRJ",
        assignee_class="user",
        waiting_state=waiting_state,
        safety_category="normal",
        confidence=0.9,
        review_status="accepted",
    )
    if with_source_ref:
        s.upsert_candidate_source_ref(
            source_ref_id=f"sr-{cid}",
            candidate_type="task",
            candidate_id=cid,
            source_family="email_message_raw_content",
            source_ref_hash=f"hash-{cid}",
            source_table="email_message_raw_content",
            evidence_redacted=f"evidence {cid}",
        )
    s.insert_accepted_task(
        candidate_id=cid,
        title_redacted=f"Task {cid}",
        waiting_state=waiting_state,
        safety_category="normal",
        project_key="PRJ",
        due_at_utc=due_at_utc,
        accepted_utc=accepted_utc,
    )


# --- classifier ----------------------------------------------------------------


def test_classifier_is_deterministic() -> None:
    kw = {
        "waiting_state": "waiting_on_others",
        "status": "open",
        "due_at_utc": None,
        "accepted_utc": "2026-06-01T00:00:00+00:00",
        "now_utc": NOW,
    }
    assert classify_watch_status(**kw) == classify_watch_status(**kw)


def test_classifier_status_branches() -> None:
    assert (
        classify_watch_status(
            waiting_state="x", status="done", due_at_utc=None, accepted_utc=None, now_utc=NOW
        )["watch_status"]
        == "closed"
    )
    # overdue with no explicit external wait -> waiting_on_me
    assert (
        classify_watch_status(
            waiting_state="unknown",
            status="open",
            due_at_utc="2026-06-01T00:00:00+00:00",
            accepted_utc=None,
            now_utc=NOW,
        )["watch_status"]
        == "waiting_on_me"
    )
    assert (
        classify_watch_status(
            waiting_state="waiting_on_others",
            status="open",
            due_at_utc=None,
            accepted_utc=NOW,
            now_utc=NOW,
        )["watch_status"]
        == "waiting_on_others"
    )
    # aged, no due -> stale
    assert (
        classify_watch_status(
            waiting_state="unknown",
            status="open",
            due_at_utc=None,
            accepted_utc="2026-01-01T00:00:00+00:00",
            now_utc=NOW,
        )["watch_status"]
        == "stale"
    )
    # fresh active -> open
    assert (
        classify_watch_status(
            waiting_state="unknown", status="open", due_at_utc=None, accepted_utc=NOW, now_utc=NOW
        )["watch_status"]
        == "open"
    )


def test_module_has_no_clock_read() -> None:
    src = Path(fuw.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in src
    assert "time.time" not in src
    assert "utcnow" not in src


# --- scan posture --------------------------------------------------------------


def test_dry_run_writes_zero_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    out = run_follow_up_watch_scan(store=ConstructionStore(db_path=db), now_utc=NOW)
    assert out["applied"] is False
    assert out["summary"]["persisted"] == 0
    assert out["summary"]["would_persist"] == 1
    assert ConstructionStore(db_path=db).list_follow_up_watch_items() == []


def test_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    try:
        run_follow_up_watch_scan(store=ConstructionStore(db_path=db), now_utc=NOW, dry_run=False)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "max_persist" in str(e)


def test_max_persist_caps_writes(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    for i in range(3):
        _seed_accepted_task(db, f"t{i}")
    out = run_follow_up_watch_scan(
        store=ConstructionStore(db_path=db), now_utc=NOW, dry_run=False, max_persist=1
    )
    assert out["summary"]["persisted"] == 1
    assert out["summary"]["would_persist"] == 3
    assert len(ConstructionStore(db_path=db).list_follow_up_watch_items()) == 1


def test_missing_source_refs_block_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1", with_source_ref=False)
    out = run_follow_up_watch_scan(
        store=ConstructionStore(db_path=db), now_utc=NOW, dry_run=False, max_persist=5
    )
    assert out["summary"]["skipped_no_source_refs"] == 1
    assert out["summary"]["persisted"] == 0
    assert ConstructionStore(db_path=db).list_follow_up_watch_items() == []


def test_duplicate_unchanged_skipped(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    store = ConstructionStore(db_path=db)
    run_follow_up_watch_scan(store=store, now_utc=NOW, dry_run=False, max_persist=5)
    out2 = run_follow_up_watch_scan(store=store, now_utc=NOW, dry_run=False, max_persist=5)
    assert out2["summary"]["skipped_existing"] == 1
    assert out2["summary"]["persisted"] == 0
    assert len(store.list_follow_up_watch_items()) == 1


def test_status_change_emits_one_event(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    # First classifies 'open' (no due, recently accepted).
    _seed_accepted_task(db, "t1", waiting_state="unknown", accepted_utc=NOW)
    store = ConstructionStore(db_path=db)
    run_follow_up_watch_scan(store=store, now_utc=NOW, dry_run=False, max_persist=5)
    # Mutate the accepted row to be overdue -> reclassifies to waiting_on_me.
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE accepted_tasks SET due_at_utc=? WHERE candidate_id='t1'",
        ("2026-01-01T00:00:00+00:00",),
    )
    conn.commit()
    n_before = conn.execute("SELECT COUNT(*) FROM follow_up_status_events").fetchone()[0]
    conn.close()
    out = run_follow_up_watch_scan(store=store, now_utc=NOW, dry_run=False, max_persist=5)
    assert out["summary"]["persisted"] == 1
    conn = sqlite3.connect(db)
    n_after = conn.execute("SELECT COUNT(*) FROM follow_up_status_events").fetchone()[0]
    ev = conn.execute(
        "SELECT prior_status, new_status FROM follow_up_status_events ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert n_after - n_before == 1
    assert ev == ("open", "waiting_on_me")


def test_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    run_follow_up_watch_scan(
        store=ConstructionStore(db_path=db), now_utc=NOW, dry_run=False, max_persist=5
    )
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    for table in ("follow_up_watch_items", "follow_up_status_events"):
        for row in conn.execute(f"SELECT {cols} FROM {table}").fetchall():
            assert all(v == 0 for v in row), table
    conn.close()


def test_empty_accepted_is_clean(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    ConstructionStore(db_path=db)  # create schema, no rows
    out = run_follow_up_watch_scan(store=ConstructionStore(db_path=db), now_utc=NOW)
    assert out["ok"] is True
    assert out["note"] == "no_accepted_items"
    assert out["summary"]["scanned"] == 0


def test_no_raw_keys_in_output(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    out = run_follow_up_watch_scan(
        store=ConstructionStore(db_path=db), now_utc=NOW, dry_run=False, max_persist=5
    )
    blob = json.dumps(out)
    for k in _FORBIDDEN_KEYS:
        assert f'"{k}"' not in blob


# --- CLI -----------------------------------------------------------------------


def test_cli_dry_run_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    res = runner.invoke(app, ["follow-up-watch", "scan", "--db", db, "--as-of", NOW])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["applied"] is False
    assert payload["summary"]["persisted"] == 0


def test_cli_apply_requires_max_persist(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_accepted_task(db, "t1")
    res = runner.invoke(app, ["follow-up-watch", "scan", "--db", db, "--apply"])
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "apply_requires_max_persist"


def test_cli_apply_capped(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    for i in range(3):
        _seed_accepted_task(db, f"t{i}")
    res = runner.invoke(
        app,
        [
            "follow-up-watch",
            "scan",
            "--db",
            db,
            "--apply",
            "--max-persist",
            "2",
            "--as-of",
            NOW,
        ],
    )
    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["summary"]["persisted"] == 2


# --- oversized thread-context input guard --------------------------------------


def test_oversized_thread_skipped(tmp_path: Path) -> None:
    from hb_assistant.construction.second_brain.local_ai.batch_extraction import (
        _select_email_threads,
    )

    class _FakeStore:
        def list_email_thread_raw_context(self, *, limit: int):
            return [
                {"thread_ref": "small", "messages_json": '[{"x": 1}]'},
                {"thread_ref": "huge", "messages_json": "x" * 2_000_000},
            ]

    selected, skipped_unprocessed, skipped_oversized = _select_email_threads(
        store=_FakeStore(),
        limit=50,
        offset=0,
        thread_refs=None,
        only_unprocessed=False,
    )
    refs = {r["thread_ref"] for r in selected}
    assert refs == {"small"}
    assert skipped_oversized == 1
