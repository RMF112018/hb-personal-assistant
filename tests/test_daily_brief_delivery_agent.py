"""Phase 08B Prompt 09 — Daily Brief Delivery Agent (local-only delivery).

Covers success (completed), failure-to-deliver (never-generated), blocked, stale, dry-run preview
(writes nothing), idempotent already-delivered, the emit-gated V28 receipt, and the no-raw-content
guarantee. Determinism via injected ``db_path`` / ``now`` / ``vault_brief_dir`` (a temp dir — never
the real vault).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hb_assistant.construction.second_brain.daily_brief_delivery import (
    DELIVERY_ALREADY_DELIVERED,
    DELIVERY_BLOCKED,
    DELIVERY_COMPLETED,
    DELIVERY_ELIGIBLE,
    DELIVERY_NEVER_GENERATED,
    DELIVERY_STALE,
    build_daily_brief_delivery_proof,
    evaluate_daily_brief_delivery,
    run_daily_brief_delivery_agent,
)
from hb_assistant.construction.store import ConstructionStore

_NOW = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)


def _seed_run(
    db: str,
    *,
    brief_run_id: str = "run-1",
    status: str = "synthesized",
    age_hours: int = 1,
    with_handoff: bool = True,
) -> None:
    generated = (_NOW - timedelta(hours=age_hours)).isoformat()
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
            "VALUES (?, '2026-06-02', 'dry_run', ?, ?)",
            (brief_run_id, status, generated),
        )
        if with_handoff:
            conn.execute(
                "INSERT INTO daily_brief_handoff_lines (line_id, brief_run_id, section, line_index, "
                " title_redacted, review_tier, source_refs_json, generated_utc) "
                "VALUES (?, ?, 'priority_actions', 0, 'Follow up on RFI', 2, '[]', ?)",
                (uuid.uuid4().hex, brief_run_id, generated),
            )
    conn.close()


def test_never_generated_on_empty_db(tmp_path: Path) -> None:
    db = f"{tmp_path}/empty.sqlite3"
    ConstructionStore(db)
    status = evaluate_daily_brief_delivery(db_path=db, now=_NOW)
    assert status.reason_code == DELIVERY_NEVER_GENERATED
    assert status.overall_status == "attention"
    assert status.eligible is False


def test_blocked_run_not_delivered(tmp_path: Path) -> None:
    db = f"{tmp_path}/blocked.sqlite3"
    ConstructionStore(db)
    _seed_run(db, status="blocked")
    status = evaluate_daily_brief_delivery(db_path=db, now=_NOW)
    assert status.reason_code == DELIVERY_BLOCKED
    assert status.overall_status == "attention"


def test_stale_run_not_delivered(tmp_path: Path) -> None:
    db = f"{tmp_path}/stale.sqlite3"
    ConstructionStore(db)
    _seed_run(db, age_hours=72)
    status = evaluate_daily_brief_delivery(db_path=db, now=_NOW)
    assert status.reason_code == DELIVERY_STALE


def test_eligible_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    vault = f"{tmp_path}/deliver_vault"
    ConstructionStore(db)
    _seed_run(db)
    status, agent_run_id = run_daily_brief_delivery_agent(
        db_path=db, vault_brief_dir=vault, mode="dry_run", now=_NOW
    )
    assert status.reason_code == DELIVERY_ELIGIBLE
    assert status.delivery_status == "preview"
    assert status.written is False
    assert agent_run_id is None
    assert not Path(vault).exists()  # dry-run never touches the vault
    # No V31 delivery receipt persisted on dry-run.
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_delivery_receipts").fetchone()[0] == 0


def test_apply_delivers_and_is_idempotent(tmp_path: Path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    vault = f"{tmp_path}/deliver_vault"
    ConstructionStore(db)
    _seed_run(db)

    completed, _ = run_daily_brief_delivery_agent(
        db_path=db, vault_brief_dir=vault, mode="apply", now=_NOW
    )
    assert completed.reason_code == DELIVERY_COMPLETED
    assert completed.written is True
    assert completed.delivery_status == "delivered"
    assert completed.delivery_channel == "obsidian_vault"
    delivered = Path(vault) / "2026-06-02_daily_brief.md"
    assert delivered.exists()
    body = delivered.read_text(encoding="utf-8")
    assert "HB-SECOND-BRAIN-DAILY-BRIEF:START" in body
    assert "Follow up on RFI" in body

    # Exactly one delivery receipt, channel-pinned.
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT delivery_channel, delivery_status, mode FROM daily_brief_delivery_receipts"
    ).fetchall()
    assert rows == [("obsidian_vault", "delivered", "apply")]

    # Re-applying is an idempotent no-op (no second receipt).
    idem, _ = run_daily_brief_delivery_agent(
        db_path=db, vault_brief_dir=vault, mode="apply", now=_NOW
    )
    assert idem.reason_code == DELIVERY_ALREADY_DELIVERED
    assert idem.delivery_status == "already_delivered"
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_delivery_receipts").fetchone()[0] == 1


def test_emit_receipt_persists_v28(tmp_path: Path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    vault = f"{tmp_path}/deliver_vault"
    ConstructionStore(db)
    _seed_run(db)
    status, agent_run_id = run_daily_brief_delivery_agent(
        db_path=db, vault_brief_dir=vault, mode="apply", now=_NOW, emit_receipt=True
    )
    assert status.reason_code == DELIVERY_COMPLETED
    assert agent_run_id is not None
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT run_kind, status, reason_code FROM second_brain_agent_run_receipts WHERE agent_run_id = ?",
        (agent_run_id,),
    ).fetchone()
    assert row == ("daily_brief_delivery", "ok", DELIVERY_COMPLETED)


def test_apply_refuses_blocked(tmp_path: Path) -> None:
    db = f"{tmp_path}/blocked.sqlite3"
    vault = f"{tmp_path}/deliver_vault"
    ConstructionStore(db)
    _seed_run(db, status="blocked")
    status, _ = run_daily_brief_delivery_agent(
        db_path=db, vault_brief_dir=vault, mode="apply", now=_NOW
    )
    assert status.reason_code == DELIVERY_BLOCKED
    assert status.delivery_status == "skipped"
    assert status.written is False
    assert not Path(vault).exists()


def test_proof_passes_and_has_no_raw_content() -> None:
    proof = build_daily_brief_delivery_proof()
    assert proof["proof_passed"] is True
    assert proof["no_raw_content"] is True
    assert proof["dry_run_wrote_nothing"] is True
    assert proof["delivery_channel"] == "obsidian_vault"
