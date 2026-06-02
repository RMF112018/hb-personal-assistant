"""Phase 08B Prompt 10 — Local HTML Brief Renderer agent.

Covers success (completed), failure-to-render (never-generated), blocked, stale, dry-run preview
(writes nothing), idempotent already-rendered, the emit-gated V28 receipt, the required interactive
UI components, the fail-closed external-asset scan, and the no-raw-content guarantee. Determinism via
injected ``db_path`` / ``now`` / ``html_dir`` (a temp dir — never the real app-support html dir).
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hb_assistant.construction.second_brain.daily_brief_html import (
    HTML_RENDER_ALREADY_RENDERED,
    HTML_RENDER_BLOCKED,
    HTML_RENDER_COMPLETED,
    HTML_RENDER_ELIGIBLE,
    HTML_RENDER_NEVER_GENERATED,
    HTML_RENDER_STALE,
    _scan_html_for_external_assets,
    build_daily_brief_html_render_proof,
    evaluate_daily_brief_html_render,
    run_daily_brief_html_render_agent,
)
from hb_assistant.construction.store import ConstructionStore

_NOW = datetime(2026, 6, 2, 21, 0, tzinfo=timezone.utc)

_REQUIRED_UI = (
    'data-group="tier"',
    'data-group="project"',
    "sec-head",
    "evidence-drawer",
    "timeline",
    "review-panel",
    "@media print",
)


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
            "INSERT INTO daily_brief_runs (brief_run_id, brief_date, mode, status, generated_utc) "
            "VALUES (?, '2026-06-02', 'dry_run', ?, ?)",
            (brief_run_id, status, generated),
        )
        conn.execute(
            "INSERT INTO daily_brief_handoff_lines (line_id, brief_run_id, section, line_index, "
            " title_redacted, review_tier, source_refs_json, generated_utc) "
            "VALUES (?, ?, 'priority_actions', 0, 'Follow up on RFI 042', 2, ?, ?)",
            (
                uuid.uuid4().hex,
                brief_run_id,
                '[{"source_family": "procore", "source_ref": "rfi-042"}]',
                generated,
            ),
        )
    conn.close()


def test_never_generated_on_empty_db(tmp_path: Path) -> None:
    db = f"{tmp_path}/empty.sqlite3"
    ConstructionStore(db)
    status = evaluate_daily_brief_html_render(db_path=db, now=_NOW)
    assert status.reason_code == HTML_RENDER_NEVER_GENERATED
    assert status.overall_status == "attention"


def test_blocked_run_not_rendered(tmp_path: Path) -> None:
    db = f"{tmp_path}/blocked.sqlite3"
    ConstructionStore(db)
    _seed_run(db, status="blocked")
    assert evaluate_daily_brief_html_render(db_path=db, now=_NOW).reason_code == HTML_RENDER_BLOCKED


def test_stale_run_not_rendered(tmp_path: Path) -> None:
    db = f"{tmp_path}/stale.sqlite3"
    ConstructionStore(db)
    _seed_run(db, age_hours=72)
    assert evaluate_daily_brief_html_render(db_path=db, now=_NOW).reason_code == HTML_RENDER_STALE


def test_eligible_dry_run_writes_nothing(tmp_path: Path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    html_dir = f"{tmp_path}/html_out"
    ConstructionStore(db)
    _seed_run(db)
    status, agent_run_id = run_daily_brief_html_render_agent(
        db_path=db, html_dir=html_dir, mode="dry_run", now=_NOW
    )
    assert status.reason_code == HTML_RENDER_ELIGIBLE
    assert status.render_status == "preview"
    assert status.written is False
    assert agent_run_id is None
    assert not Path(html_dir).exists()
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_html_render_receipts").fetchone()[0] == 0


def test_apply_renders_self_contained_html_and_is_idempotent(tmp_path: Path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    html_dir = f"{tmp_path}/html_out"
    ConstructionStore(db)
    _seed_run(db)

    completed, _ = run_daily_brief_html_render_agent(
        db_path=db, html_dir=html_dir, mode="apply", now=_NOW
    )
    assert completed.reason_code == HTML_RENDER_COMPLETED
    assert completed.written is True
    assert completed.render_status == "rendered"
    assert completed.no_external_assets is True

    rendered = Path(html_dir) / "2026-06-02_daily_brief.html"
    assert rendered.exists()
    body = rendered.read_text(encoding="utf-8")
    assert body.startswith("<!DOCTYPE html>")
    for marker in _REQUIRED_UI:
        assert marker in body, f"missing UI component: {marker}"
    assert "Follow up on RFI 042" in body
    # Fully self-contained: no external assets / network calls.
    assert _scan_html_for_external_assets(body) == []

    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT render_status, mode, no_external_assets FROM daily_brief_html_render_receipts"
    ).fetchall()
    assert rows == [("rendered", "apply", 1)]

    idem, _ = run_daily_brief_html_render_agent(
        db_path=db, html_dir=html_dir, mode="apply", now=_NOW
    )
    assert idem.reason_code == HTML_RENDER_ALREADY_RENDERED
    assert idem.render_status == "already_rendered"
    assert conn.execute("SELECT COUNT(*) FROM daily_brief_html_render_receipts").fetchone()[0] == 1


def test_emit_receipt_persists_v28(tmp_path: Path) -> None:
    db = f"{tmp_path}/ok.sqlite3"
    html_dir = f"{tmp_path}/html_out"
    ConstructionStore(db)
    _seed_run(db)
    status, agent_run_id = run_daily_brief_html_render_agent(
        db_path=db, html_dir=html_dir, mode="apply", now=_NOW, emit_receipt=True
    )
    assert status.reason_code == HTML_RENDER_COMPLETED
    assert agent_run_id is not None
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT run_kind, status, reason_code FROM second_brain_agent_run_receipts WHERE agent_run_id = ?",
        (agent_run_id,),
    ).fetchone()
    assert row == ("daily_brief_html_render", "ok", HTML_RENDER_COMPLETED)


def test_apply_refuses_blocked(tmp_path: Path) -> None:
    db = f"{tmp_path}/blocked.sqlite3"
    html_dir = f"{tmp_path}/html_out"
    ConstructionStore(db)
    _seed_run(db, status="blocked")
    status, _ = run_daily_brief_html_render_agent(
        db_path=db, html_dir=html_dir, mode="apply", now=_NOW
    )
    assert status.reason_code == HTML_RENDER_BLOCKED
    assert status.render_status == "skipped"
    assert status.written is False
    assert not Path(html_dir).exists()


def test_external_asset_scanner_flags_network_refs() -> None:
    assert _scan_html_for_external_assets("<p>clean local content</p>") == []
    assert _scan_html_for_external_assets('<script src="https://cdn.example/x.js"></script>')
    assert _scan_html_for_external_assets("<style>@import url(//evil/x.css)</style>")
    assert _scan_html_for_external_assets("fetch('/data')")


def test_proof_passes() -> None:
    proof = build_daily_brief_html_render_proof()
    assert proof["proof_passed"] is True
    assert proof["ui_components_present"] is True
    assert proof["no_external_assets"] is True
    assert proof["dry_run_wrote_nothing"] is True
    assert proof["no_raw_content"] is True
