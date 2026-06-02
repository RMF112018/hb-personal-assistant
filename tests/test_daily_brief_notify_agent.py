"""Phase 08B Prompt 11 — local macOS notification agent.

Covers success (emitted), failure-to-notify (never-generated), blocked, stale, dry-run preview (no
notifier call), the fail-closed disabled-by-policy apply path (no osascript / no receipt), idempotent
already-emitted, the emit-gated V28 receipt, and the no-raw-content guarantee. The osascript runner is
always an injected fake recorder — the suite never fires a real banner.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from hb_assistant.construction.second_brain.daily_brief_notify import (
    NOTIFY_ALREADY_EMITTED,
    NOTIFY_BLOCKED,
    NOTIFY_DISABLED_BY_POLICY,
    NOTIFY_ELIGIBLE,
    NOTIFY_EMITTED,
    NOTIFY_NEVER_GENERATED,
    NOTIFY_STALE,
    build_daily_brief_notification_proof,
    evaluate_daily_brief_notification,
    run_daily_brief_notification_agent,
)
from hb_assistant.construction.store import ConstructionStore

_NOW = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)


def _seed_run(
    db: str,
    *,
    brief_run_id: str = "run-1",
    status: str = "synthesized",
    age_hours: int = 1,
) -> None:
    generated = (_NOW - timedelta(hours=age_hours)).isoformat()
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, project_count, "
            " review_required_count, generated_utc) VALUES (?, '2026-06-02', 'dry_run', ?, 3, 1, ?)",
            (brief_run_id, status, generated),
        )
        conn.execute(
            "INSERT INTO daily_brief_handoff_lines (line_id, brief_run_id, section, line_index, "
            " title_redacted, review_tier, source_refs_json, generated_utc) "
            "VALUES (?, ?, 'priority_actions', 0, 'Follow up on RFI 042', 2, '[]', ?)",
            (uuid.uuid4().hex, brief_run_id, generated),
        )
    conn.close()


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, title: str, body: str) -> bool:
        self.calls.append((title, body))
        return True


def test_never_generated_on_empty_db(tmp_path) -> None:
    db = f"{tmp_path}/empty.sqlite3"
    ConstructionStore(db)
    status = evaluate_daily_brief_notification(db_path=db, now=_NOW)
    assert status.reason_code == NOTIFY_NEVER_GENERATED
    assert status.overall_status == "attention"


def test_blocked_run_not_notified(tmp_path) -> None:
    db = f"{tmp_path}/blocked.sqlite3"
    ConstructionStore(db)
    _seed_run(db, status="blocked")
    assert evaluate_daily_brief_notification(db_path=db, now=_NOW).reason_code == NOTIFY_BLOCKED


def test_stale_run_not_notified(tmp_path) -> None:
    db = f"{tmp_path}/stale.sqlite3"
    ConstructionStore(db)
    _seed_run(db, age_hours=72)
    assert evaluate_daily_brief_notification(db_path=db, now=_NOW).reason_code == NOTIFY_STALE


def test_eligible_dry_run_previews_without_calling_notifier(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    rec = _Recorder()
    status, agent_run_id = run_daily_brief_notification_agent(
        db_path=db, mode="dry_run", now=_NOW, notifier=rec, policy_emit=True
    )
    assert status.reason_code == NOTIFY_ELIGIBLE
    assert status.notify_status == "preview"
    assert status.emitted is False
    assert agent_run_id is None
    assert rec.calls == []  # dry-run never emits
    # Preview carries the redacted banner (counts only).
    assert status.body_preview is not None and "review" in status.body_preview
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_notification_receipts").fetchone()[0] == 0


def test_apply_disabled_by_policy_is_fail_closed(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    rec = _Recorder()
    status, _ = run_daily_brief_notification_agent(
        db_path=db, mode="apply", now=_NOW, notifier=rec, policy_emit=False
    )
    assert status.reason_code == NOTIFY_DISABLED_BY_POLICY
    assert status.notify_status == "disabled"
    assert status.emitted is False
    assert rec.calls == []  # no osascript / notifier call while emission is disabled
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_notification_receipts").fetchone()[0] == 0


def test_apply_emits_and_is_idempotent(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    rec = _Recorder()

    emitted, _ = run_daily_brief_notification_agent(
        db_path=db, mode="apply", now=_NOW, notifier=rec, policy_emit=True
    )
    assert emitted.reason_code == NOTIFY_EMITTED
    assert emitted.notify_status == "emitted"
    assert emitted.emitted is True
    assert emitted.channel == "local_macos"
    assert len(rec.calls) == 1

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT channel, notify_status, mode, project_count FROM daily_brief_notification_receipts"
    ).fetchall()
    assert rows == [("local_macos", "emitted", "apply", 3)]

    idem, _ = run_daily_brief_notification_agent(
        db_path=db, mode="apply", now=_NOW, notifier=rec, policy_emit=True
    )
    assert idem.reason_code == NOTIFY_ALREADY_EMITTED
    assert idem.notify_status == "already_emitted"
    assert len(rec.calls) == 1  # no second emission
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_notification_receipts").fetchone()[0] == 1


def test_emit_receipt_persists_v28(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    status, agent_run_id = run_daily_brief_notification_agent(
        db_path=db,
        mode="apply",
        now=_NOW,
        notifier=_Recorder(),
        policy_emit=True,
        emit_receipt=True,
    )
    assert status.reason_code == NOTIFY_EMITTED
    assert agent_run_id is not None
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT run_kind, status, reason_code FROM second_brain_agent_run_receipts WHERE agent_run_id = ?",
        (agent_run_id,),
    ).fetchone()
    assert row == ("daily_brief_notification", "ok", NOTIFY_EMITTED)


def test_proof_passes() -> None:
    proof = build_daily_brief_notification_proof()
    assert proof["proof_passed"] is True
    assert proof["disabled_invoked_no_notifier"] is True
    assert proof["disabled_wrote_no_receipt"] is True
    assert proof["no_raw_content"] is True
    assert proof["channel"] == "local_macos"
