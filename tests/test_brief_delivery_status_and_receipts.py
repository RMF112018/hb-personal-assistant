"""Phase 08B Prompt 12 — consolidated brief delivery-status + receipts list."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from hb_assistant.construction.second_brain.daily_brief_open import (
    STATUS_COMPLETE,
    STATUS_DELIVERED,
    STATUS_NEVER_GENERATED,
    STATUS_NOT_DELIVERED,
    STATUS_PARTIAL,
    build_brief_open_proof,
    evaluate_brief_delivery_status,
    list_brief_receipts,
)
from hb_assistant.construction.store import ConstructionStore

_NOW = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)
_RUN = "run-1"


def _seed_run(db: str) -> None:
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
            "VALUES (?, '2026-06-02', 'dry_run', 'synthesized', ?)",
            (_RUN, _NOW.isoformat()),
        )
    conn.close()


def _add(db: str, sql: str) -> None:
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(sql)
    conn.close()


def _deliver(db: str) -> None:
    _add(
        db,
        "INSERT INTO daily_brief_delivery_receipts (delivery_receipt_id, brief_run_id, brief_date, "
        f" delivery_channel, delivery_status, mode, output_path_redacted) VALUES ('{uuid.uuid4().hex}', "
        "'run-1','2026-06-02','obsidian_vault','delivered','apply','12_Daily_Brief/x.md')",
    )


def _render(db: str) -> None:
    _add(
        db,
        "INSERT INTO daily_brief_html_render_receipts (html_render_receipt_id, brief_run_id, brief_date, "
        f" render_status, mode) VALUES ('{uuid.uuid4().hex}', 'run-1','2026-06-02','rendered','apply')",
    )


def _notify(db: str) -> None:
    _add(
        db,
        "INSERT INTO daily_brief_notification_receipts (notification_receipt_id, brief_run_id, brief_date, "
        f" channel, notify_status, mode) VALUES ('{uuid.uuid4().hex}', 'run-1','2026-06-02','local_macos','emitted','apply')",
    )


def _open(db: str) -> None:
    _add(
        db,
        "INSERT INTO daily_brief_open_receipts (open_receipt_id, brief_run_id, brief_date, open_target, "
        f" open_status, mode) VALUES ('{uuid.uuid4().hex}', 'run-1','2026-06-02','vault','opened','apply')",
    )


def test_status_never_generated(tmp_path) -> None:
    db = f"{tmp_path}/empty.sqlite3"
    ConstructionStore(db)
    assert (
        evaluate_brief_delivery_status(db_path=db, now=_NOW).reason_code == STATUS_NEVER_GENERATED
    )


def test_status_transitions(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    s = evaluate_brief_delivery_status(db_path=db, now=_NOW)
    assert s.reason_code == STATUS_NOT_DELIVERED and s.delivered is False

    _deliver(db)
    s = evaluate_brief_delivery_status(db_path=db, now=_NOW)
    assert s.reason_code == STATUS_DELIVERED and s.delivered is True

    _render(db)
    s = evaluate_brief_delivery_status(db_path=db, now=_NOW)
    assert s.reason_code == STATUS_PARTIAL and s.rendered is True and s.opened is False

    _notify(db)
    _open(db)
    s = evaluate_brief_delivery_status(db_path=db, now=_NOW)
    assert s.reason_code == STATUS_COMPLETE
    assert (s.delivered, s.rendered, s.notified, s.opened) == (True, True, True, True)


def test_receipts_list_metadata_only(tmp_path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    ConstructionStore(db)
    _seed_run(db)
    _deliver(db)
    _render(db)
    _notify(db)
    _open(db)
    receipts = list_brief_receipts(db_path=db)
    surfaces = {r["surface"] for r in receipts}
    assert surfaces == {"delivery", "html_render", "notification", "open"}
    # Metadata-only: each row exposes status/reason/path/created, never raw content.
    for r in receipts:
        assert set(r.keys()) >= {"surface", "brief_date", "status", "created_utc"}
    blob = " ".join(str(v) for r in receipts for v in r.values())
    for forbidden in ("raw_prompt", "raw_response", "signed_url", "download_url", "secret"):
        assert forbidden not in blob


def test_open_proof_passes() -> None:
    proof = build_brief_open_proof()
    assert proof["proof_passed"] is True
    assert proof["disabled_invoked_no_opener"] is True
    assert proof["no_raw_content"] is True
    assert proof["status_codes"][-1] == STATUS_COMPLETE
