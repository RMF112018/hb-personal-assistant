"""Phase 10 — local-agent pipeline orchestration (one repeatable daily run).

Covers the dry-run-default full run, per-stage + global persist caps, apply fail-closed, idempotency,
guard-column invariants, fail-loud stage isolation (a failed stage → ok=false/partial + nonzero CLI
exit unless --allow-partial), brief_freshness (partial / preexisting) + banner, --stage subset, --raw
local-consumption surfacing, and CLI wiring. Registry stays at 13 agents (no new agent).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hb_assistant.cli.second_brain import app
from hb_assistant.construction.second_brain.local_ai import pipeline as pipeline_mod
from hb_assistant.construction.second_brain.local_ai import run_local_agent_pipeline
from hb_assistant.construction.store import ConstructionStore

runner = CliRunner()

NOW = "2026-06-09T00:00:00+00:00"
DATE = "2026-06-09"

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


def _seed_calendar(db: str, n: int = 5) -> ConstructionStore:
    """Seed N upcoming, non-cancelled calendar index events so calendar_prep has work to persist."""
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    for i in range(n):
        conn.execute(
            """
            INSERT INTO calendar_event_index
                (event_index_id, source_id, graph_event_id_hash, start_datetime_utc,
                 end_datetime_utc, subject_redacted, organizer_domain, is_online_meeting,
                 is_cancelled, is_private, project_key)
            VALUES (?, 'src1', ?, ?, ?, ?, 'hbcompany.com', 0, 0, 0, ?)
            """,
            (
                f"ev{i}",
                f"gh-ev{i}",
                f"2026-06-1{i % 5}T15:00:00.0000000",
                f"2026-06-1{i % 5}T16:00:00.0000000",
                f"[redacted-{i}]",
                f"PROJ-{i % 2}",
            ),
        )
    conn.commit()
    conn.close()
    return s


def _candidate_count(db: str) -> int:
    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM daily_brief_action_candidates").fetchone()[0]
    conn.close()
    return n


# --- dry-run / shape -----------------------------------------------------------


def test_dry_run_runs_all_stages_writes_nothing(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    before = _candidate_count(db)
    out = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db)
    assert out["ok"] is True
    assert out["dry_run"] is True and out["applied"] is False
    assert [r["stage"] for r in out["stages"]] == pipeline_mod.STAGE_ORDER
    assert all(r["status"] == "ok" for r in out["stages"])
    assert out["summary"]["total_persisted"] == 0
    assert out["summary"]["total_would_persist"] >= 5  # calendar stage would persist 5
    assert _candidate_count(db) == before == 0
    # dry-run → brief reflects pre-existing candidates, clearly marked
    assert out["brief_freshness"] == "preexisting"
    assert out["warnings"]


def test_guardrails_block(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    g = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db)["guardrails"]
    assert g["no_vault_write"] is True
    assert g["read_only_render"] is True
    assert g["raw_local_consumption_only"] is False


def test_deterministic(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    a = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db)
    b = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db)
    assert a["summary"] == b["summary"]
    assert [r["would_persist"] for r in a["stages"]] == [r["would_persist"] for r in b["stages"]]


# --- apply / caps / idempotency ------------------------------------------------


def test_apply_requires_per_stage_cap(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    try:
        run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db, dry_run=False)
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "max_persist_per_stage" in str(e)


def test_per_stage_cap_bounds_writes(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db, n=5)
    out = run_local_agent_pipeline(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist_per_stage=2
    )
    cal = next(r for r in out["stages"] if r["stage"] == "calendar_prep")
    assert cal["persisted"] == 2  # capped per stage
    assert out["applied"] is True
    assert out["brief_freshness"] == "fresh"  # applied + all generation ok


def test_global_cap_halts_persistence(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db, n=5)
    # global ceiling 1: the first write stage that has work consumes it; later stages run dry-run.
    out = run_local_agent_pipeline(
        store=s,
        now_utc=NOW,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=5,
        max_total_persist=1,
    )
    assert out["summary"]["total_persisted"] <= 1
    assert out["summary"]["total_persist_capped"] is True


def test_apply_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db, n=5)
    run_local_agent_pipeline(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist_per_stage=10
    )
    out2 = run_local_agent_pipeline(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist_per_stage=10
    )
    assert out2["summary"]["total_persisted"] == 0  # nothing new on re-run


def test_guard_columns_zero_after_apply(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db, n=5)
    run_local_agent_pipeline(
        store=s, now_utc=NOW, db_path=db, dry_run=False, max_persist_per_stage=10
    )
    conn = sqlite3.connect(db)
    cols = ", ".join(_GUARD_COLUMNS)
    rows = conn.execute(f"SELECT {cols} FROM daily_brief_action_candidates").fetchall()
    assert rows
    for row in rows:
        assert all(v == 0 for v in row)
    conn.close()


# --- fail-loud stage isolation -------------------------------------------------


def test_stage_failure_is_loud(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)

    def _boom(**_kwargs: object) -> dict:
        raise RuntimeError("forced stage failure")

    monkeypatch.setattr(pipeline_mod, "run_follow_up_watch_scan", _boom)
    out = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db)
    fu = next(r for r in out["stages"] if r["stage"] == "follow_up_watch")
    assert fu["status"] == "failed"
    assert fu["reason_code"].startswith("stage_error:")
    assert out["ok"] is False
    assert out["partial"] is True
    # pipeline still completed: render ran, brief marked partial with a banner
    assert any(r["stage"] == "daily_brief_render" and r["status"] == "ok" for r in out["stages"])
    assert out["brief_freshness"] == "partial"
    assert "Partial brief" in out["brief"]["markdown"]


def test_cli_stage_failure_exit_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_calendar(db)
    monkeypatch.setattr(
        pipeline_mod,
        "build_calendar_prep_candidates",
        lambda **_k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    res = runner.invoke(app, ["pipeline", "run", "--db", db, "--as-of", NOW])
    assert res.exit_code == 1  # fail-loud: nonzero on stage failure
    assert json.loads(res.output)["ok"] is False
    res2 = runner.invoke(app, ["pipeline", "run", "--db", db, "--as-of", NOW, "--allow-partial"])
    assert res2.exit_code == 0  # explicit opt-in → exit 0
    assert json.loads(res2.output)["ok"] is False  # payload still reports the failure


# --- freshness / subset / raw --------------------------------------------------


def test_render_only_subset_is_preexisting(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    out = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db, stages=["daily_brief_render"])
    assert [r["stage"] for r in out["stages"]] == ["daily_brief_render"]
    assert out["brief_freshness"] == "preexisting"
    assert out["ok"] is True


def test_raw_surfaces_local_consumption_flag(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    s = _seed_calendar(db)
    out = run_local_agent_pipeline(store=s, now_utc=NOW, db_path=db, include_raw=True)
    assert out["guardrails"]["raw_local_consumption_only"] is True


# --- CLI -----------------------------------------------------------------------


def test_cli_dry_run_default(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_calendar(db)
    res = runner.invoke(app, ["pipeline", "run", "--db", db, "--as-of", NOW, "--summary"])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    assert payload["ok"] is True and payload["dry_run"] is True
    assert payload["summary"]["total_persisted"] == 0


def test_cli_apply_requires_cap(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_calendar(db)
    res = runner.invoke(app, ["pipeline", "run", "--db", db, "--apply"])
    assert res.exit_code == 2
    assert json.loads(res.output)["error"] == "apply_requires_per_stage_cap"


def test_cli_apply_capped(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    _seed_calendar(db, n=5)
    res = runner.invoke(
        app,
        [
            "pipeline",
            "run",
            "--db",
            db,
            "--as-of",
            NOW,
            "--apply",
            "--max-persist-per-stage",
            "2",
            "--summary",
        ],
    )
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output)
    cal = next(r for r in payload["stages"] if r["stage"] == "calendar_prep")
    assert cal["persisted"] == 2
