"""Phase 08B Prompt 12 — brief-open agent.

Covers success (opened), failure-to-open (never-generated), blocked, stale, not-available (artifact
not produced), dry-run preview (no opener call), the fail-closed disabled-by-policy apply path (no
`open` / no receipt), idempotent already-opened, the emit-gated V28 receipt, and no-raw-content. The
`open` runner is always an injected fake — the suite never launches an app.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from hb_assistant.construction.second_brain.daily_brief_open import (
    OPEN_ALREADY_OPENED,
    OPEN_BLOCKED,
    OPEN_COMPLETED,
    OPEN_DISABLED_BY_POLICY,
    OPEN_ELIGIBLE,
    OPEN_NEVER_GENERATED,
    OPEN_NOT_AVAILABLE,
    OPEN_STALE,
    evaluate_brief_open,
    run_brief_open_agent,
)
from hb_assistant.construction.store import ConstructionStore

_NOW = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)


def _seed_run(
    db: str, *, brief_run_id: str = "run-1", status: str = "synthesized", age_hours: int = 1
) -> None:
    generated = (_NOW - timedelta(hours=age_hours)).isoformat()
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
            "VALUES (?, '2026-06-02', 'dry_run', ?, ?)",
            (brief_run_id, status, generated),
        )
    conn.close()


def _seed_delivery(db: str, *, brief_run_id: str = "run-1") -> None:
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_delivery_receipts (delivery_receipt_id, brief_run_id, brief_date, "
            " delivery_channel, delivery_status, mode, output_path_redacted) "
            "VALUES (?, ?, '2026-06-02', 'obsidian_vault', 'delivered', 'apply', "
            " '12_Daily_Brief/2026-06-02_daily_brief.md')",
            (uuid.uuid4().hex, brief_run_id),
        )
    conn.close()


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, path: str) -> bool:
        self.calls.append(path)
        return True


def test_never_generated_on_empty_db(tmp_path) -> None:
    db = f"{tmp_path}/empty.sqlite3"
    ConstructionStore(db)
    assert evaluate_brief_open(db_path=db, now=_NOW).reason_code == OPEN_NEVER_GENERATED


def test_blocked_run_not_opened(tmp_path) -> None:
    db = f"{tmp_path}/blocked.sqlite3"
    ConstructionStore(db)
    _seed_run(db, status="blocked")
    _seed_delivery(db)
    assert evaluate_brief_open(db_path=db, now=_NOW).reason_code == OPEN_BLOCKED


def test_stale_run_not_opened(tmp_path) -> None:
    db = f"{tmp_path}/stale.sqlite3"
    ConstructionStore(db)
    _seed_run(db, age_hours=72)
    _seed_delivery(db)
    assert evaluate_brief_open(db_path=db, now=_NOW).reason_code == OPEN_STALE


def test_not_available_when_artifact_not_produced(tmp_path) -> None:
    db = f"{tmp_path}/na.sqlite3"
    ConstructionStore(db)
    _seed_run(db)  # delivered nothing
    assert evaluate_brief_open(db_path=db, now=_NOW).reason_code == OPEN_NOT_AVAILABLE


def test_eligible_dry_run_does_not_open(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    _seed_delivery(db)
    rec = _Recorder()
    status, agent_run_id = run_brief_open_agent(
        db_path=db, mode="dry_run", now=_NOW, opener=rec, policy_open=True
    )
    assert status.reason_code == OPEN_ELIGIBLE
    assert status.open_status == "preview"
    assert status.opened is False
    assert agent_run_id is None
    assert rec.calls == []
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_open_receipts").fetchone()[0] == 0


def test_apply_disabled_by_policy_is_fail_closed(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    _seed_delivery(db)
    rec = _Recorder()
    status, _ = run_brief_open_agent(
        db_path=db, mode="apply", now=_NOW, opener=rec, policy_open=False
    )
    assert status.reason_code == OPEN_DISABLED_BY_POLICY
    assert status.open_status == "disabled"
    assert status.opened is False
    assert rec.calls == []
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_open_receipts").fetchone()[0] == 0


def test_apply_opens_and_is_idempotent(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    _seed_delivery(db)
    rec = _Recorder()

    opened, _ = run_brief_open_agent(
        db_path=db, mode="apply", now=_NOW, opener=rec, policy_open=True
    )
    assert opened.reason_code == OPEN_COMPLETED
    assert opened.open_status == "opened"
    assert opened.opened is True
    assert opened.open_target == "vault"
    assert len(rec.calls) == 1

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT open_target, open_status, mode FROM daily_brief_open_receipts"
    ).fetchall()
    assert rows == [("vault", "opened", "apply")]

    idem, _ = run_brief_open_agent(db_path=db, mode="apply", now=_NOW, opener=rec, policy_open=True)
    assert idem.reason_code == OPEN_ALREADY_OPENED
    assert idem.open_status == "already_opened"
    assert len(rec.calls) == 1  # no second open
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_open_receipts").fetchone()[0] == 1


def test_html_target_requires_rendered_artifact(tmp_path) -> None:
    db = f"{tmp_path}/html.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    _seed_delivery(db)  # delivered (vault) but not rendered (html)
    assert (
        evaluate_brief_open(db_path=db, target="html", now=_NOW).reason_code == OPEN_NOT_AVAILABLE
    )
    # Add a rendered receipt -> html becomes eligible.
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_html_render_receipts (html_render_receipt_id, brief_run_id, "
            " brief_date, render_status, mode) VALUES (?, 'run-1','2026-06-02','rendered','apply')",
            (uuid.uuid4().hex,),
        )
    conn.close()
    assert evaluate_brief_open(db_path=db, target="html", now=_NOW).reason_code == OPEN_ELIGIBLE


def test_emit_receipt_persists_v28(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    _seed_delivery(db)
    status, agent_run_id = run_brief_open_agent(
        db_path=db, mode="apply", now=_NOW, opener=_Recorder(), policy_open=True, emit_receipt=True
    )
    assert status.reason_code == OPEN_COMPLETED
    assert agent_run_id is not None
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT run_kind, status, reason_code FROM second_brain_agent_run_receipts WHERE agent_run_id = ?",
        (agent_run_id,),
    ).fetchone()
    assert row == ("daily_brief_open", "ok", OPEN_COMPLETED)
