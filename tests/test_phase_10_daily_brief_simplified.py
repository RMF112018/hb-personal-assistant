"""Phase 10 (253) — daily brief simplification around New Today.

*New Today is the daily brief; everything else is diagnostics.* These tests lock the simplified
contract:

* the user-facing product status lives in an additive ``daily_brief`` block (``primary_surface =
  new_today``); the legacy top-level ``status`` is preserved for backward compatibility;
* ``daily_brief.status`` is derived from New Today + its substrate ONLY — legacy LLM-synthesis
  degradation / MEI-withheld / optional-Ollama-unavailability never flip it to degraded and never
  surface an above-the-fold warning when deterministic New Today is useful (the crux);
* product-relevant degradation (email substrate present + 0 actionable; projection failed/coverage-
  degraded; raw-safety dropped every built event) sets ``degraded`` + a visible warning;
* a genuinely empty refresh window stays ``success``;
* the two enrichment status fields never collide (``new_today.model_enrichment_status`` vs
  legacy ``diagnostics.model_enriched_intelligence_status``);
* Markdown ↔ browser HTML render the same New Today items and both are raw-safe, with the legacy
  status banner / date-policy internals confined to the collapsed diagnostics block;
* the full scheduled run emits the ``daily_brief`` block (status JSON + return payload) and keeps the
  guard columns zero.
"""

from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

from hb_assistant.construction.second_brain.local_ai import run_daily_local_agent
from hb_assistant.construction.second_brain.local_ai.daily_run_html import (
    render_daily_run_html,
    scan_daily_run_html,
)
from hb_assistant.construction.second_brain.local_ai.model_eval_metrics import (
    scan_text_for_forbidden,
)
from hb_assistant.construction.second_brain.local_ai.new_today_digest import build_new_today_digest
from hb_assistant.construction.second_brain.local_ai.new_today_presentation import (
    build_render_model,
    render_markdown,
)
from hb_assistant.construction.second_brain.local_ai.new_today_usefulness import (
    evaluate_new_today_status,
)
from hb_assistant.construction.store import ConstructionStore
from tests._phase_10_new_today_seed import BRIEF_DATE, seed_new_today_fixture

NOW_UTC = f"{BRIEF_DATE}T05:00:00-04:00"  # Friday 2026-06-12, a weekday

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


class _Store:
    """Minimal store shim — the New Today digest reads only ``_db_path``."""

    def __init__(self, db: str) -> None:
        self._db_path = db


def _seed(tmp_path: Path, *, detail_gaps: bool = True) -> str:
    db = str(tmp_path / "simplified.db")
    seed_new_today_fixture(db, include_detail_gaps=detail_gaps)
    return db


# --- Part A: pure usefulness/status gate (the crux semantics, no store) ------------------------


def _digest_stub(*, email_degraded: bool = False, total_events: int = 0) -> dict:
    return {"gates": {"email_degraded": email_degraded, "total_events": total_events}}


def test_clean_empty_refresh_window_is_success() -> None:
    """Nothing changed overnight + clean substrate → success, operator-usable, no warning."""
    out = evaluate_new_today_status(
        digest=_digest_stub(total_events=0),
        rendered_total_items=0,
        projection_receipt={"status": "ok"},
    )
    assert out["status"] == "success"
    assert out["operator_usable"] is True
    assert out["degraded_reasons"] == []
    assert out["visible_warning"] is False


def test_email_substrate_with_no_actionable_is_product_degraded() -> None:
    out = evaluate_new_today_status(
        digest=_digest_stub(email_degraded=True, total_events=2),
        rendered_total_items=2,
        projection_receipt={"status": "ok"},
    )
    assert out["status"] == "degraded"
    assert "email_followup_degraded" in out["degraded_reasons"]
    assert out["visible_warning"] is True


def test_projection_failure_is_degraded() -> None:
    out = evaluate_new_today_status(
        digest=_digest_stub(total_events=1),
        rendered_total_items=1,
        projection_receipt={"status": "failed"},
    )
    assert out["status"] == "degraded"
    assert "projection_degraded" in out["degraded_reasons"]


def test_projection_coverage_degraded_is_degraded() -> None:
    out = evaluate_new_today_status(
        digest=_digest_stub(total_events=1),
        rendered_total_items=1,
        projection_receipt={"status": "ok", "projection_coverage_status": "degraded"},
    )
    assert out["status"] == "degraded"
    assert "projection_coverage_degraded" in out["degraded_reasons"]


def test_all_events_dropped_by_raw_safety_is_degraded() -> None:
    out = evaluate_new_today_status(
        digest=_digest_stub(total_events=3),
        rendered_total_items=0,
        projection_receipt={"status": "ok"},
    )
    assert out["status"] == "degraded"
    assert "all_events_dropped_raw_safety" in out["degraded_reasons"]


def test_model_unavailable_is_not_product_degraded() -> None:
    """Optional Ollama overlay unavailability is diagnostics, never product degradation."""
    out = evaluate_new_today_status(
        digest=_digest_stub(total_events=2),
        rendered_total_items=2,
        projection_receipt={"status": "ok"},
        model_enrichment_status="unavailable",
    )
    assert out["status"] == "success"
    assert out["degraded_reasons"] == []
    assert out["visible_warning"] is False
    assert out["deterministic_fallback_used"] is True
    assert out["model_enrichment_status"] == "unavailable"


def test_gate_cannot_see_legacy_synthesis_state() -> None:
    """Structural lock: synthesis/MEI are NOT inputs, so they can never flip the product status."""
    params = set(inspect.signature(evaluate_new_today_status).parameters)
    assert "synthesis" not in params
    assert not any("synthesis" in p or "mei" in p for p in params)


# --- Part B: shared render model drives both surfaces; warning is New-Today-driven --------------


def test_success_status_renders_no_visible_warning(tmp_path: Path) -> None:
    """Useful New Today (status=success) → no degraded warning above the fold; legacy status banner
    confined to the collapsed diagnostics block."""
    digest = build_new_today_digest(store=_Store(_seed(tmp_path)), brief_date=BRIEF_DATE)
    model = build_render_model(digest, status="success")
    assert model["degraded_warning"] is None

    html = render_daily_run_html(
        brief_date=BRIEF_DATE,
        status="success",
        sections=[],
        summary={"rendered": 0},
        warnings=[],
        generated_label="2026-06-12T05:00",
        new_today=model,
    )
    diag_at = html.index("Run details / diagnostics")
    assert html.index("New Today") < diag_at
    # No product warning above the New Today section.
    assert "Some sources were degraded" not in html[:diag_at]
    # The legacy status banner lives INSIDE the collapsed diagnostics block, never above New Today.
    assert "Success — fresh local-model brief" not in html[:diag_at]


def test_degraded_status_renders_visible_warning(tmp_path: Path) -> None:
    digest = build_new_today_digest(store=_Store(_seed(tmp_path)), brief_date=BRIEF_DATE)
    model = build_render_model(digest, status="degraded")
    assert model["degraded_warning"]
    html = render_daily_run_html(
        brief_date=BRIEF_DATE,
        status="success",  # legacy status irrelevant; the New Today model drives the warning
        sections=[],
        summary={"rendered": 0},
        warnings=[],
        generated_label="2026-06-12T05:00",
        new_today=model,
    )
    assert "Some sources were degraded" in html[: html.index("Run details / diagnostics")]


def test_markdown_html_parity_and_raw_safe(tmp_path: Path) -> None:
    digest = build_new_today_digest(store=_Store(_seed(tmp_path)), brief_date=BRIEF_DATE)
    model = build_render_model(digest, status="success")
    md = render_markdown(model)
    html = render_daily_run_html(
        brief_date=BRIEF_DATE,
        status="success",
        sections=[],
        summary={"rendered": 0},
        warnings=[],
        generated_label="2026-06-12T05:00",
        new_today=model,
    )
    for anchor in ("Invoice #1842", "RFI #025"):
        assert anchor in md and anchor in html
    # Required header/subhead/section contract on the user-facing Markdown.
    assert md.startswith("# Today's Daily Brief")
    assert "Summary of the top items for 2026-06-12 and prep through" in md
    assert "## New Today" in md
    # Forbidden internal artifacts never render on either surface.
    for token in (
        "friday_next_week",
        "dbac-",
        "rel-",
        "daily_brief_action_candidates",
        "project_key",
        "None.",
    ):
        assert token not in md
        assert token not in html
    assert scan_text_for_forbidden(md) == []
    assert scan_daily_run_html(html) == []


# --- Part C: full scheduled run emits the daily_brief block (hermetic; synthesis/MEI off) -------


def _run(tmp_path: Path) -> dict:
    db = _seed(tmp_path)
    store = ConstructionStore(db_path=db)
    out = run_daily_local_agent(
        store=store,
        now_utc=NOW_UTC,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=200,
        max_total_persist=500,
        browser_output_dir=str(tmp_path / "html"),
        status_dir=str(tmp_path / "status"),
        vault_brief_dir=str(tmp_path / "vault"),
    )
    return out


def test_daily_run_emits_daily_brief_block_with_new_today_primary(tmp_path: Path) -> None:
    out = _run(tmp_path)
    db = out  # noqa: F841 - keep symmetry; not used
    daily_brief = out["daily_brief"]
    assert daily_brief["primary_surface"] == "new_today"
    assert daily_brief["status"] in ("success", "degraded")
    # Legacy synthesis/MEI demoted to diagnostics — never the product status.
    assert daily_brief["diagnostics"]["model_enriched_intelligence_status"] == "diagnostic_only"
    # The two enrichment fields are distinct and never collide.
    assert daily_brief["new_today"]["model_enrichment_status"] == "not_requested"
    # Backward compatibility: the legacy top-level status field is preserved.
    assert "status" in out and out["status"]
    assert daily_brief["diagnostics"]["legacy_status"] == out["status"]


def test_daily_run_status_json_carries_daily_brief_block(tmp_path: Path) -> None:
    _run(tmp_path)
    latest = json.loads((tmp_path / "status" / "latest-status.json").read_text())
    assert latest["daily_brief"]["primary_surface"] == "new_today"
    # The legacy top-level status remains for scheduler/status-reader backward compatibility.
    assert latest["status"]


def test_daily_run_browser_html_leads_with_new_today(tmp_path: Path) -> None:
    _run(tmp_path)
    html = (tmp_path / "html" / f"daily-brief-{BRIEF_DATE}.html").read_text()
    assert "<h1>Today's Daily Brief</h1>" in html
    # Use structural markers — the degraded warning copy itself mentions "Run details / diagnostics",
    # so match the actual section/details tags, not the prose.
    assert html.index("<section class='new-today'>") < html.index("<details class='diag'>")
    # The legacy run/status banner is confined to the collapsed diagnostics block.
    assert html.index("Local-agent family") > html.index("<details class='diag'>")
    assert scan_daily_run_html(html) == []


def test_daily_run_guard_columns_stay_zero(tmp_path: Path) -> None:
    db = _seed(tmp_path)
    store = ConstructionStore(db_path=db)
    run_daily_local_agent(
        store=store,
        now_utc=NOW_UTC,
        db_path=db,
        dry_run=False,
        max_persist_per_stage=200,
        max_total_persist=500,
        browser_output_dir=str(tmp_path / "html"),
        status_dir=str(tmp_path / "status"),
        vault_brief_dir=str(tmp_path / "vault"),
    )
    conn = sqlite3.connect(db)
    cols = ",".join(f"COALESCE(SUM({c}),0)" for c in _GUARD_COLUMNS)
    row = conn.execute(f"SELECT {cols} FROM daily_brief_change_events").fetchone()
    assert all(v == 0 for v in row), f"guard columns nonzero: {row}"
