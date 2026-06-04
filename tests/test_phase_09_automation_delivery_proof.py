"""Phase 09 Prompt 08 — automation / delivery receipt proof tests.

Exercises the read-only automation-delivery proof over a controlled, NO-EXTERNAL receipt
population: the 08B delivery / notification (explicitly gated, fake notifier) / HTML / open /
health / launchd agents run against a temp DB with temp vault/HTML dirs and injected fake
callables (no real macOS notification, no real vault/HTML write, no launchctl), persisting
metadata-only receipts. Also covers the policy-off fail-closed path and stale-schema.
"""

from __future__ import annotations

import json
from pathlib import Path

from hb_assistant.construction.second_brain.automation_delivery_proof import (
    build_automation_delivery_proof,
)
from hb_assistant.construction.second_brain.daily_brief import run_daily_brief
from hb_assistant.construction.second_brain.daily_brief_delivery import (
    run_daily_brief_delivery_agent,
)
from hb_assistant.construction.second_brain.daily_brief_health import run_daily_brief_job_health
from hb_assistant.construction.second_brain.daily_brief_html import (
    run_daily_brief_html_render_agent,
)
from hb_assistant.construction.second_brain.daily_brief_notify import (
    run_daily_brief_notification_agent,
)
from hb_assistant.construction.second_brain.launchd_scheduler import run_launchd_schedule_agent
from hb_assistant.construction.second_brain.reasoning import MockClaudeAdapter
from hb_assistant.construction.store import ConstructionStore

_DATE = "2026-06-04"


def _seed_brief(db: str, vault_dir: str) -> None:
    store = ConstructionStore(db)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )
    run_daily_brief(
        brief_date=_DATE,
        project_key="P1",
        db_path=db,
        mode="apply",
        vault_brief_dir=vault_dir,
        emit_receipt=True,
        adapter=MockClaudeAdapter(),
    )


def test_controlled_population_is_guard_clean_and_no_external(tmp_path: Path) -> None:
    db = str(tmp_path / "proof.sqlite3")
    vault = str(tmp_path / "vault")
    html = str(tmp_path / "html")
    _seed_brief(db, vault)

    notifier_calls: list[bool] = []

    def fake_notifier(title: object, body: object) -> bool:
        notifier_calls.append(True)  # records emission; never a real osascript
        return True

    # Delivery (apply → temp vault), notification (explicitly gated, fake notifier),
    # HTML (apply → temp html), health, launchd — all emit metadata-only receipts.
    assert (
        run_daily_brief_delivery_agent(
            brief_date=_DATE, mode="apply", db_path=db, vault_brief_dir=vault, emit_receipt=True
        )[0].reason_code
        == "DELIVERY_COMPLETED"
    )
    assert (
        run_daily_brief_notification_agent(
            brief_date=_DATE,
            mode="apply",
            db_path=db,
            emit_receipt=True,
            policy_emit=True,
            notifier=fake_notifier,
        )[0].reason_code
        == "NOTIFY_EMITTED"
    )
    run_daily_brief_html_render_agent(
        brief_date=_DATE, mode="apply", db_path=db, html_dir=html, emit_receipt=True
    )
    run_daily_brief_job_health(db_path=db, emit_receipt=True)
    run_launchd_schedule_agent(db_path=db, emit_receipt=True)

    proof = build_automation_delivery_proof(db)
    assert proof["proof_passed"] is True
    assert proof["populated"] is True
    assert proof["delivery_receipt_count"] >= 1
    assert proof["agent_run_receipt_count"] >= 1
    assert proof["guard_violation"] is False
    assert proof["channel_or_mode_violation"] is False
    assert proof["external_writeback_total"] == 0
    assert proof["no_external_delivery"] is True
    # The notification was explicitly gated; the fake notifier ran (no real osascript).
    assert notifier_calls == [True]
    # Channels are pinned to local artifacts.
    assert proof["tables"]["daily_brief_delivery_receipts"]["channels"] == ["obsidian_vault"]
    assert proof["tables"]["daily_brief_notification_receipts"]["channels"] == ["local_macos"]


def test_notification_policy_off_is_fail_closed(tmp_path: Path) -> None:
    db = str(tmp_path / "proof2.sqlite3")
    vault = str(tmp_path / "vault")
    _seed_brief(db, vault)

    def must_not_call(title: object, body: object) -> bool:
        raise AssertionError("notifier must not be called when policy is off")

    status, _ = run_daily_brief_notification_agent(
        brief_date=_DATE,
        mode="apply",
        db_path=db,
        emit_receipt=True,
        policy_emit=False,
        notifier=must_not_call,
    )
    assert status.reason_code == "NOTIFY_DISABLED_BY_POLICY"  # fail-closed, no external emit


def test_empty_db_is_not_populated(tmp_path: Path) -> None:
    db = str(tmp_path / "empty.sqlite3")
    ConstructionStore(db)  # migrated, no receipts
    proof = build_automation_delivery_proof(db)
    assert proof["populated"] is False
    assert proof["proof_passed"] is False
    assert proof["total_receipts"] == 0
    assert proof["guard_violation"] is False  # vacuously clean


def test_stale_schema_is_handled_gracefully(tmp_path: Path) -> None:
    import sqlite3

    db = str(tmp_path / "stale.sqlite3")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_migrations (version INTEGER)")
    conn.execute("INSERT INTO schema_migrations (version) VALUES (5)")
    conn.commit()
    conn.close()

    proof = build_automation_delivery_proof(db)
    assert proof["schema_version"] == 5
    assert proof["proof_passed"] is False
    assert proof["populated"] is False
