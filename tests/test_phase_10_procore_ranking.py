"""Phase 10 — Procore signal ranking + aggregate suppression (daily-brief usefulness repair).

Covers promotion of due-soon / recent / high-critical / owner-linked / source-change-linked /
financially-material signals, suppression of stale high-count aggregate backlog and semantically
closed signals (observation_closed never surfaces as an open action), the why_today requirement,
and the digest's executive-vs-suppressed split + cap enforcement.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import build_procore_action_digest
from hb_assistant.construction.second_brain.local_ai.procore_ranking import rank_procore_signals
from hb_assistant.construction.store import ConstructionStore

NOW = "2026-06-08T00:00:00+00:00"

_COLS = (
    "action_signal_id, project_key, record_key, endpoint_id, signal_type, signal_status, "
    "importance, due_at_utc, owner_entity_key, title_redacted, summary_redacted, "
    "reason_codes_json, first_detected_at_utc, last_seen_at_utc, resolved_at_utc, "
    "source_change_event_id, metadata_json"
)


def _row(
    sid: str,
    project: str,
    signal_type: str,
    *,
    importance: str = "medium",
    due: str | None = None,
    owner: str | None = None,
    first_seen: str = "2026-05-01T00:00:00+00:00",
    source_change: str | None = None,
) -> tuple:
    return (
        sid, project, f"{project}|ep||{sid}", "ep", signal_type, "open", importance, due,
        owner, "t", "sm", "[]", first_seen, "2026-06-01T00:00:00+00:00", None, source_change, "{}",
    )


def _signal_dict(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "action_signal_id": "x", "project_key": "alpha", "signal_type": "inspection_item_unanswered",
        "importance": "medium", "due_at_utc": None, "owner_entity_key": None,
        "source_change_event_id": None, "first_detected_at_utc": "2026-05-01T00:00:00+00:00",
    }
    base.update(over)
    return base


# --- unit: rank_procore_signals ------------------------------------------------


def test_overdue_is_promoted_with_why_today() -> None:
    r = rank_procore_signals(
        [_signal_dict(due_at_utc="2026-06-01T00:00:00+00:00")], now_utc=NOW
    )[0]
    assert r.promoted is True
    assert r.overdue is True
    assert r.suppression_reason is None
    assert r.why_today  # non-empty


def test_due_soon_is_promoted() -> None:
    r = rank_procore_signals(
        [_signal_dict(due_at_utc="2026-06-10T00:00:00+00:00")], now_utc=NOW
    )[0]
    assert r.due_soon is True
    assert r.promoted is True


def test_recent_since_last_success_is_promoted() -> None:
    r = rank_procore_signals(
        [_signal_dict(first_detected_at_utc="2026-06-07T00:00:00+00:00")],
        now_utc=NOW,
        last_success_utc="2026-06-06T00:00:00+00:00",
    )[0]
    assert r.recent is True
    assert r.promoted is True


def test_high_importance_is_promoted() -> None:
    r = rank_procore_signals([_signal_dict(importance="high")], now_utc=NOW)[0]
    assert r.promoted is True
    assert "high" in r.rank_reasons


def test_source_change_linked_is_promoted() -> None:
    r = rank_procore_signals([_signal_dict(source_change_event_id="chg-1")], now_utc=NOW)[0]
    assert r.source_change_linked is True
    assert r.promoted is True


def test_financial_materiality_is_promoted() -> None:
    r = rank_procore_signals([_signal_dict(signal_type="invoice_payment_due")], now_utc=NOW)[0]
    assert r.financial_materiality is True
    assert r.promoted is True


def test_stale_medium_backlog_is_suppressed_as_sludge() -> None:
    # medium, no due, not recent, no owner, no change → pure aggregate backlog.
    r = rank_procore_signals([_signal_dict(importance="medium")], now_utc=NOW)[0]
    assert r.promoted is False
    assert r.is_aggregate_sludge is True
    assert r.suppression_reason == "no_why_today_stale_backlog"
    assert r.why_today == ""


def test_observation_closed_never_surfaces() -> None:
    # Even high importance: a semantically-closed signal is suppressed, not an open action.
    r = rank_procore_signals(
        [_signal_dict(signal_type="observation_closed", importance="high")], now_utc=NOW
    )[0]
    assert r.promoted is False
    assert r.is_semantically_actionable is False
    assert r.suppression_reason == "semantically_closed"


def test_ranked_order_is_deterministic_score_desc() -> None:
    rows = [
        _signal_dict(action_signal_id="a", importance="medium"),
        _signal_dict(action_signal_id="b", due_at_utc="2026-06-01T00:00:00+00:00"),  # overdue
        _signal_dict(action_signal_id="c", importance="high"),
    ]
    ranked = rank_procore_signals(rows, now_utc=NOW)
    assert [r.action_signal_id for r in ranked][0] == "b"  # overdue scores highest
    assert ranked == rank_procore_signals(rows, now_utc=NOW)


# --- integration: digest executive vs suppressed -------------------------------


def _seed(db: str, rows: list[tuple]) -> ConstructionStore:
    s = ConstructionStore(db_path=db)
    conn = sqlite3.connect(db)
    conn.executemany(
        f"INSERT INTO procore_action_signals ({_COLS}) VALUES ({', '.join(['?'] * 17)})", rows
    )
    conn.commit()
    conn.close()
    return s


def test_digest_demotes_aggregate_sludge_from_executive(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    # 1 overdue (promoted) + 50 stale medium backlog (suppressed) + 1 observation_closed (suppressed).
    rows = [_row("due", "alpha", "inspection_overdue", importance="high", due="2026-06-01T00:00:00+00:00")]
    rows += [_row(f"b{i}", "alpha", "inspection_item_unanswered", importance="medium") for i in range(50)]
    rows.append(_row("closed", "alpha", "observation_closed", importance="high"))
    s = _seed(db, rows)
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert out["summary"]["promoted_count"] == 1
    assert out["summary"]["suppressed_count"] == 51
    assert out["summary"]["aggregate_sludge_count"] == 50
    assert out["summary"]["semantically_closed_count"] == 1
    # executive rows are only the promoted, source-linked signal
    assert len(out["executive_rows"]) == 1
    assert out["executive_rows"][0]["action_signal_id"] == "due"
    assert out["executive_rows"][0]["why_today"]
    # the aggregate backlog lives in diagnostics, labeled by suppression reason
    backlog = {b["signal_type"]: b for b in out["suppressed_backlog"]}
    assert backlog["inspection_item_unanswered"]["count"] == 50
    assert backlog["observation_closed"]["suppression_reason"] == "semantically_closed"


def test_executive_cap_enforced(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    rows = [
        _row(f"h{i}", "alpha", "inspection_overdue", importance="high", due="2026-06-01T00:00:00+00:00")
        for i in range(10)
    ]
    s = _seed(db, rows)
    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db, limit=3)
    assert out["summary"]["promoted_count"] == 10
    assert out["summary"]["executive_considered"] == 3
    assert out["summary"]["would_persist"] == 3


def test_no_owner_key_leaks_into_output(tmp_path: Path) -> None:
    db = str(tmp_path / "t.sqlite")
    rows = [_row("o", "alpha", "inspection_overdue", importance="high", owner="secret-owner-hash",
                 due="2026-06-01T00:00:00+00:00")]
    s = _seed(db, rows)
    import json

    out = build_procore_action_digest(store=s, now_utc=NOW, db_path=db)
    assert "secret-owner-hash" not in json.dumps(out)
    assert '"owner_entity_key"' not in json.dumps(out)
